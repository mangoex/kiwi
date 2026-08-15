# PCO-005B — paquete de decisión para aplicación compensatoria

**Estado:** aprobado por el Dueño de producto el 2026-08-14; listo para propagación y handoff Terra.<br>
**Riesgo:** R3 — pago, efectivo, inventario, producción, permisos, migración y concurrencia.<br>
**Base:** PCO-005A cerrado en producción; `/apply` continúa fail-closed.

## 1. Resultado que debe producir PCO-005B

Un Dueño revisa una solicitud `APPROVED`, la imagen exacta de corrección y sus compensaciones; al
aplicarla, el sistema conserva intacta la operación histórica original y registra una corrección
enlazada, idempotente y auditable. El usuario ve la cuenta corregida y el vínculo con la cuenta
original, pero reportes, turnos y cortes históricos siguen explicando exactamente lo ocurrido.

PCO-005B no es una edición libre de historia. Tampoco incluye reapertura de corte por usuario
(PCO-006), sincronización offline (PCO-008), integración con adquirentes, devolución fiscal,
impresión o exportación.

## 2. Decisión solicitada

Se recomienda aprobar en un solo paquete estas reglas:

1. **Identidad:** la cuenta original permanece cerrada; la corrección es un artefacto enlazado con
   snapshot anterior/posterior y folio de corrección visible.
2. **Autoridad:** Cajero jefe o superior solicita; Dueño aprueba y aplica el plan exacto. Nadie puede
   cambiar líneas, método, clasificación o importe después de la aprobación que se ejecuta.
3. **Dinero:** el pago original no cambia. Delta positivo crea cargo adicional; delta negativo crea
   reembolso. Efectivo afecta sólo el turno abierto actual mediante ledger append-only. Tarjeta y
   transferencia requieren confirmación manual y evidencia hasta que exista adaptador.
4. **Producción:** `PENDING` permite liberar/reemplazar; `IN_PROGRESS` bloquea; `COMPLETED` exige
   `waste|recovery` por cantidad reducida. Adiciones generan reserva y tarea nuevas.
5. **Historia:** snapshots, movimientos, pagos, cierres y asociaciones a cortes originales nunca se
   actualizan, eliminan ni reasignan.
6. **Atomicidad:** o se escriben corrección, compensaciones, evento, auditoría y estado `APPLIED`, o
   no se escribe nada.

El Dueño de producto autorizó las seis reglas mediante la frase exacta **“Apruebo SDD-ADR-027 y el
paquete PCO-005B”**. No se registraron excepciones.

## 3. Requisitos propuestos

La aprobación se propaga a los documentos canónicos mediante estas reglas:

- `PRD-FR-217A`: aplicar una reapertura aprobada crea una corrección enlazada sin mutar la cuenta
  histórica original.
- `PRD-FR-217B`: toda diferencia financiera se registra como cargo o reembolso append-only,
  conciliable con pago original, turno actual y corte histórico.
- `PRD-FR-217C`: toda diferencia de inventario/producción se deriva de snapshots; producción en
  curso falla cerrada y producción terminada exige merma o recuperación explícita.
- `PRD-NFR-025`: aplicación atómica, idempotente, concurrente, auditable y sin PII/evidencia libre en
  logs o respuestas no autorizadas.

## 4. Diseño técnico propuesto

### 4.1 Datos aditivos

- `order_corrections`: organización, sucursal, pedido original, solicitud, versión capturada,
  before/after, delta en centavos, moneda, estado `APPLIED`, actor, UTC e idempotency key.
- `order_correction_lines`: imagen deseada y enlace opcional a línea original; nunca sobreescribe
  `order_lines` ni snapshots de venta.
- `order_payment_adjustments`: `CHARGE|REFUND`, importe positivo, método, pago original, turno actual
  nullable para métodos no cash, estado confirmado, evidencia opaca y correlación.
- `order_production_adjustments`: línea original, tarea, cantidad exacta y
  `RELEASE|WASTE|RECOVERY|ADDITION`, con movimiento/tarea resultante.
- `order_reopen_commands` amplía el hash de `apply` al plan completo y conserva respuesta estable.

La migración siguiente a `0039` debe ser aditiva, con claves foráneas, checks, índices de consulta y
unicidad de una corrección por solicitud. El downgrade se bloquea si existe una corrección o ajuste;
no intenta borrar historia R3.

### 4.2 Contrato de aplicación

`POST /api/v1/orders/reopen-requests/{request_id}/apply`

- autoridad: sesión real + `orders.reopen.authorize`; sólo Dueño;
- headers: `Idempotency-Key` obligatorio;
- body estricto: `expected_order_version`, `lines[]`, `production_dispositions[]`, `register_id`
  nullable, `settlement_method`, `settlement_evidence_refs[]`;
- `register_id` es obligatorio sólo para un delta cash; el backend deriva organización, sucursal,
  moneda, importe original, snapshots, delta, turno y cantidades. El cliente no afirma totales,
  actor, estado, `cash_shift_id` ni IDs de movimientos;
- respuesta: solicitud `APPLIED`, corrección, delta, ajuste financiero, ajustes productivos e IDs de
  correlación; excluye evidencia y motivos libres;
- errores estables: `order_reopen_transition_invalid`, `order_version_conflict`,
  `order_reopen_plan_invalid`, `production_in_progress`,
  `production_disposition_required`, `cash_shift_not_open`, `payment_adjustment_invalid`,
  `historical_snapshot_missing`, `idempotency_conflict` y `actor_not_authorized`.

### 4.3 Cálculo determinista

Python es autoridad única:

```text
original_paid_cents = suma de pagos CONFIRMED capturados en el snapshot aprobado
corrected_total_cents = suma exacta de las líneas deseadas validadas
settlement_delta_cents = corrected_total_cents - original_paid_cents
```

- delta `> 0`: `CHARGE` por el delta;
- delta `< 0`: `REFUND` por `abs(delta)`;
- delta `= 0`: no crea ajuste financiero y registra reconciliación cero en la corrección;
- dinero permanece entero; cantidades/conversiones usan `Decimal`; React no recalcula ni decide.

### 4.4 Transacción y concurrencia

El servicio bloquea solicitud, pedido y turno efectivo aplicable; revalida estado `APPROVED`, versión,
snapshot, moneda, producción, alcance y plan. Inserta artefactos aditivos, movimientos/tareas/eventos,
auditoría y por último cambia la solicitud a `APPLIED`, todo en una transacción. Dos aplicaciones
con claves distintas dejan una sola corrección; replay idéntico devuelve la misma respuesta.

### 4.5 UI mínima

La cola de Dueño abre el editor POS existente en modo corrección para construir la imagen corregida, seleccionar
merma/recuperación sólo donde backend lo exige, ver el plan calculado por servidor y confirmar una
vez. Estados: carga, validación, cálculo, confirmación, enviando, aplicado, conflicto y error. Un
perfil sin permiso no ve la acción y la API lo rechaza. La UI muestra folio original, folio de
corrección, delta, método y vínculos; nunca presenta una mutación del pago original.

## 5. BDD propuesto

- `BDD-SC-317`: Dueño aplica delta cero y la cuenta original conserva su huella.
- `BDD-SC-318`: delta positivo crea un único cargo actual sin mover el pago/corte original.
- `BDD-SC-319`: delta negativo crea un único reembolso; cash exige turno abierto y no cash evidencia.
- `BDD-SC-320`: reducción `PENDING` libera reserva y adición crea nueva reserva/tarea.
- `BDD-SC-321`: `IN_PROGRESS` bloquea sin escritura; `COMPLETED` exige `waste|recovery` y crea el
  movimiento correcto.
- `BDD-SC-322`: plan, versión o idempotency key conflictivos fallan sin escritura parcial.
- `BDD-SC-323`: actor no Dueño, otra organización o sucursal fuera de alcance no aplica.
- `BDD-SC-324`: dos aplicaciones concurrentes producen una corrección y respuesta estable.
- `BDD-SC-325`: reportes/cortes históricos permanecen iguales y la corrección aparece separada.
- `BDD-SC-326`: fallo inyectado entre ajustes revierte todo, incluida la transición `APPLIED`.

## 6. TDD propuesto

- `TDD-TC-101`: contratos JSON estrictos, errores y redacción.
- `TDD-TC-102`: cálculo Python de delta para positivo, negativo y cero; límites y moneda.
- `TDD-TC-103`: pago original/snapshot/corte inmutables y ajuste financiero enlazado.
- `TDD-TC-104`: matriz de tareas `PENDING|IN_PROGRESS|COMPLETED` y disposiciones.
- `TDD-TC-105`: movimientos de inventario por snapshot con `Decimal`, sin receta vigente histórica.
- `TDD-TC-106`: RBAC Dueño, alcance organizacional y negativos de cinco perfiles.
- `TDD-TC-107`: idempotencia, payload-hash, versión y carrera en SQLite.
- `TDD-TC-108`: misma carrera/locks/índices en PostgreSQL aislado con URL explícita PCO-005B.
- `TDD-TC-109`: rollback transaccional con fallo después de cada escritura sensible.
- `TDD-TC-110`: migración `0039 -> siguiente -> 0039 -> siguiente` vacía y downgrade bloqueado con
  historia.
- `TDD-TC-111`: UI semántica, TypeScript, build y estados visuales desktop/reducido.
- `TDD-TC-112`: reconciliación de reportes, efectivo esperado, cierre y corte antes/después.

## 7. Plan de implementación para Terra

1. Crear RED focal de TC-101/102/106/107 sobre el gate actual.
2. Agregar migración y modelos aditivos; validar upgrade/downgrade vacío antes de lógica.
3. Implementar servicio Python cohesivo de plan/aplicación; controladores sólo validan frontera.
4. Implementar delta financiero y ledger cash mediante adaptadores/servicios existentes, sin SQL
   duplicado ni lógica React.
5. Implementar compensaciones productivas/inventario desde snapshots.
6. Cerrar atomicidad, idempotencia y concurrencia SQLite/PostgreSQL.
7. Agregar contratos versionados y endpoint.
8. Implementar UI Dueño mínima y negativos de permiso.
9. Ejecutar suite focal R3 una vez: TC-101..112, tests afectados de PCO-003/004/005A, migración
   SQLite/PostgreSQL, typecheck/build y QA visual.
10. Entregar commit aislado sin producción. Sol audita trazabilidad, diff, invariantes y evidencia;
    Terra corrige sólo hallazgos reales hasta aceptación.

## 8. Gates proporcionales

- **Gate de decisión:** aprobación explícita de ADR-027 y paquete; único gate previo a RED.
- **Gate RED:** pruebas focales fallan por ausencia del comportamiento, no por fixture roto.
- **Gate GREEN:** suite focal R3 y CI verdes; PostgreSQL no puede sustituirse por SQLite.
- **Gate de auditoría:** Sol verifica código y evidencia una vez; reabre sólo hallazgos materiales.
- **Gate de publicación:** commit/PR/merge/push pueden aprobarse como paquete.
- **Gate de producción:** redeploy, migración y canary son autorización separada.

## 9. Riesgos residuales visibles

- Un reembolso no cash sigue siendo confirmación manual hasta integrar un proveedor; el sistema
  registra evidencia pero no puede probar liquidación bancaria.
- `IN_PROGRESS` queda deliberadamente bloqueado; resolver producción parcialmente elaborada exige
  una política operativa adicional, no una inferencia técnica.
- Factura/CFDI y devolución fiscal no forman parte de PCO-005B.
- La corrección no libera operaciones de cortes finalizados; la diferencia pertenece al turno/corte
  en que realmente se ejecuta.
