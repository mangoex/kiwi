# PUR-CASH-001 — Compras en efectivo vinculadas a la caja de la sucursal

Fecha: 2026-10-08. Estado: especificaciones y plan; implementación pendiente.
Riesgo funcional R3: caja, inventario, permisos, concurrencia e idempotencia.
Esta entrega modifica documentación; no modifica runtime, dependencias, datos ni despliegue.

## Historia y resultado

Como usuario autorizado para compras de mi sucursal, quiero registrar una nota con **Efectivo**
predeterminado y ver la caja y el turno que la pagarán, para que al confirmar se reciba la mercancía
y se descuente el total una sola vez del efectivo de esa sucursal, con trazabilidad del documento.

La cuenta identifica actor y alcance; la sucursal activa autorizada identifica la operación.
Una compra en efectivo usa dinero de la caja seleccionada de esa sucursal. No equivale a una
compra con dinero personal ni crea una caja asociada directamente a cada usuario.

## Auditoría del estado actual

| Evidencia del repositorio | Hallazgo e implicación |
| --- | --- |
| PRD-FR-207; SDD §34.7 | Efectivo ya es el default especificado y confirma retiro vinculado con turno abierto. |
| `packages/ui/src/components/purchaseDraft.ts` y `PurchaseDocumentEditor.tsx` | El editor inicia en Otro; efectivo se representa por una casilla separada y no aparece en el selector. Divergencia de UI respecto del PRD. |
| `apps/admin-web/src/features/purchasing/PurchasesList.tsx` | La confirmación toma un código de `localStorage.pos_register_id` global y editable libremente. Falta selección validada por sucursal/turno. No prueba por sí solo una fuga backend. |
| `packages/ui/src/components/PurchaseDocumentReview.tsx` y su caller | Falta contexto de pago/caja en revisión; el caller puede cerrar la revisión después de capturar un error. Etiqueta no efectivo implica crédito indebidamente. |
| `apps/api/restaurant_os/purchase_workspace.py` | Rechaza paid_from_cash true con método distinto de cash, pero no la combinación inversa explícita. Admite texto arbitrario de método, por lo que falta rechazar credit/desconocidos en frontera conforme §34.7. |
| `apps/api/restaurant_os/operations.py`, `confirm_purchase_document` | Ya crea retiro SUPPLY_PURCHASE, recepción, costo, vínculo y auditoría. Ya exige purchases.manage, cash.movement.withdraw, caja y turno OPEN en sucursal documental. |
| Mismo comando y `models.purchase_documents` | Replay usa clave persistida; falta comprobar intención completa y serialización por documento. El riesgo de doble confirmación con claves distintas requiere prueba PostgreSQL antes de afirmarlo como fallo reproducido. |
| `calculate_expected_cash` y cancelación de compras | El ledger ya resta ese retiro. Cancelación compensa sin borrar y exige turno original abierto. No añadir una segunda resta ni otra política de cancelación. |
| `/cash/shifts` frente a `/cash-shifts/current` | Listado histórico exige cash.shift.read; búsqueda de turno por código admite retiro. Contexto nuevo expone sólo metadatos mínimos con compras+retiro, sin ampliar acceso a saldos. |

## Contrato y dependencias

Autoridades: [PRD-FR-207](../01-PRD.md), [SDD §51.8](../02-SDD.md),
[BDD-SC-607..613](../03-BDD-direct-purchases-costing.md),
[TDD-TS-135 / TC-324..330](../04-TDD-direct-purchases-costing.md) y
[matriz FR-207](../05-matriz-trazabilidad.md). Se amplía TC-212; no se crea otro flujo de compras.

Secuencia: sesión autenticada → sucursal activa autorizada → proveedor/presentaciones existentes →
nota en borrador → contexto de caja autorizado → revisión → confirmación transaccional →
recepción/costo/retiro/auditoría → refresco de vistas. El almacén se deriva de la sucursal.

Dependencias de código: editor compartido `packages/ui`, DTO/esquemas online `packages/contracts`,
sesión/consultas `admin-web`, API y dominio Python. La entrada desde POS reutiliza Administración.
Sin nuevos paquetes ni proveedores externos. Sin migración prevista: identidad de confirmación
se reconstruye de campos y vínculos existentes; su suficiencia es un gate explícito de TC-328.

Decisiones de diseño para implementar:

- Selector único: Efectivo por defecto, Transferencia, Tarjeta, Otro. Booleano cash derivado y
  validado en ambas direcciones. API aplica lista cerrada de esos cuatro métodos, incluyendo
  confirmación de borradores; no habilita credit por petición directa. La lectura histórica no
  reescribe documentos.
- Contexto de caja mínimo autorizado por servidor; preferencia POS validada, única caja abierta
  propuesta, varias requieren elección, ninguna permite guardar pero bloquea confirmar efectivo.
- Revisión visible de sucursal, método, caja, turno y total; la nueva confirmación incluye el turno
  revisado para impedir sustitución silenciosa después de cierre/reapertura.
- Congelar clave y body durante incertidumbre, reautorizar replay y serializar por documento;
  conservar transacción existente y una sola contabilización en efectivo esperado.
- Sin nuevas reglas de fondos insuficientes, crédito, cuentas por pagar, pagos mixtos, caja personal,
  apertura automática, compras offline o compensación postcierre. No cambiar fórmulas de costos.

## Criterios de aceptación

| ID | Criterio observable | Pruebas diseñadas |
| --- | --- | --- |
| AC-1 | Nota nueva muestra Efectivo seleccionado; guardar/preview no mueve caja ni inventario. | SC-607; TC-324 |
| AC-2 | Caja propuesta pertenece a sucursal activa autorizada y tiene turno OPEN; varias se eligen, cero bloquea sólo confirmación cash. | SC-608; TC-325 |
| AC-3 | La UI invalida contexto al cambiar cuenta/sucursal; la API coteja documento/body/alcance y rechaza permisos revocados o IDs ajenos. Un comando ya enviado conserva su contexto original. | SC-609; TC-325/326 |
| AC-4 | Confirmar $300 con esperado previo $2,000 deja $1,700, un retiro vinculado y recepción/costo correctos; fallo revierte todo. | SC-610; TC-327 |
| AC-5 | Cierre/reapertura obliga a revisar nuevamente; error conserva la revisión y la nota. | SC-610; TC-326/327 |
| AC-6 | Doble clic, respuesta perdida y dos confirmaciones concurrentes no duplican efectos; misma clave con intención distinta falla. | SC-611; TC-327/328 |
| AC-7 | Tarjeta, Transferencia y Otro no usan caja ni se presentan como crédito; cash/booleano contradictorios se rechazan. | SC-612; TC-324/329 |
| AC-8 | Cancelación autorizada conserva originales y compensa una vez bajo la regla vigente del turno original. | SC-613; TC-329 |
| AC-9 | Administración y acceso POS usan el mismo recorrido, legible con teclado y ancho reducido; vistas de caja se actualizan tras éxito. | SC-607..613; TC-330 |

## Plan de implementación y tareas

Las tareas se ejecutan en orden; D3 puede prepararse tras definir D1, pero no se publica por separado
del contrato backend. Cada corrección obtiene primero su prueba RED dirigida.

| Tarea | Cambio y entrega | Dependencia / salida |
| --- | --- | --- |
| D1 | Pruebas RED del default, contradicción cash/false, contexto y rechazo de intención incompatible. Definir DTO/esquemas de contexto/confirmación y compatibilidad legacy. | TC-324..328; contratos sin cambios offline |
| D2 | Resolver cajas OPEN por alcance con respuesta mínima; validar método/coherencia en preview, creación y confirmación; revalidar permisos y turno revisado. | D1; pruebas frontera/permisos verdes |
| D3 | Selector compartido, contexto de sucursal/caja/turno, elección múltiple, revisión persistente ante error y preferencias por contexto; eliminar etiqueta crédito. | D1/D2; TC-324..326 verdes |
| D4 | Serialización por documento, identidad persistida de replay y congelación de intento; cerrar carreras con cierre/cancelación y atomicidad ante fallos. | D2; TC-327/328 verdes en SQLite/PostgreSQL |
| D5 | Refresco de compras/inventario/caja, compensación/no efectivo y recuperación UI; recorrido Admin/POS y QA visual focal. | D3/D4; TC-329/330 verdes |
| D6 | Lint/mypy focal, typecheck/build, contratos, trazabilidad, CI aplicable y auditoría Sol independiente R3. Registrar evidencia y límites reales. | D1..D5; sin hallazgos bloqueantes |
| D7 | Commit/merge/push dentro de autorización aplicable; despliegue y canary R3 sólo con autorización productiva separada. | D6; registrar Git y producción por separado |

Checklist de ejecución:

- [x] Contrastar historia con PRD/SDD y dependencias reales.
- [x] Especificar función, API/guardas, BDD, TDD y matriz sin acreditar implementación futura.
- [x] Ejecutar baseline focal del motor existente.
- [ ] Implementar D1..D5 y obtener sus pruebas RED/GREEN.
- [ ] Completar D6 y evidencias de runtime/CI.
- [ ] Publicación y verificación productiva según D7.

## Evidencia y riesgos de esta entrega

Baseline local ejecutado el 2026-10-08: **3 passed**, 24.46 s:

```text
python -m pytest apps/api/tests/test_branch_purchases_and_courtesies.py::test_purchase_paid_from_cash_shift_and_cancellation_compensation apps/api/tests/test_purchase_workspace.py::test_three_line_cash_receipt_has_exact_prior_weighted_cost_and_compensation apps/api/tests/test_cash_ledger.py::test_sqlite_close_and_cash_purchase_race_share_the_open_shift_guard -q
```

Una advertencia de deprecación Starlette/httpx; no se modifica dependencia por este paquete.
Estas pruebas acreditan baseline de retiro/compensación/recepción/costo y carrera SQLite con cierre;
no acreditan selector nuevo, contexto nuevo ni doble confirmación PostgreSQL.

Integridad documental: `python -m pytest tests/architecture/test_traceability.py -q`: **9 passed**,
0.50 s en la ejecución final. `git diff --check`: limpio.
Revisión Sol independiente R3 del diseño (`audit_purchase_cash_spec`): cerrada sin hallazgos
bloqueantes después de corregir, dentro del mismo ciclo, tres observaciones: delimitar defaults
legacy frente a captura explícita, exigir allowlist API y distinguir autoridad de contexto UI/API.
El veredicto sólo acredita integridad del diseño, no runtime ni cumplimiento de los casos nuevos.
Typecheck/build, nuevos contratos, E2E/QA, PostgreSQL, CI y canary del incremento no ejecutados:
runtime aún no implementado. No hay despliegue, migración ni operación en caja productiva.

| Afirmación R3 | Evidencia / intento de refutación | Resultado y riesgo residual |
| --- | --- | --- |
| Reutilizar motor conserva retiro único y compensación en casos actuales | Tres pruebas baseline, incluido replay en compra de tres líneas y compra/cierre SQLite | Verde local; no prueba carreras nuevas PG. |
| El diseño impide afectar otra sucursal o turno | Validación servidor y expected_cash_shift_id definidos; negativos TC-325/326 | Diseñado; pendiente implementar y atacar IDs/contexto/permisos en pruebas. |
| La confirmación permanece única ante dos claves o respuesta perdida | Serialización e identidad persistida descritas; TC-327/328 con barreras/fallos | No verificado en runtime; bloqueo de liberación hasta verde. |
| No se altera historia ni duplica resta de compras | Ledger/cancelación existentes inspeccionados; TC-329 de conciliación | Baseline parcial; comprobar saldo/cierre y cancelación postcierre en incremento. |

Preguntas operativas y señales quedan en SDD §51.8; este plan no crea una instrumentación paralela.
Canary propuesto para autorización posterior: nota real autorizada de importe controlado en sucursal
y caja explícitas, revisar vínculo/esperado y replay sin duplicación; compensar sólo si corresponde
a la operación real y con turno abierto, dejando historia. Nunca usar ventas o compras ficticias
en producción ni considerar push como evidencia de despliegue.
