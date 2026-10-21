# TDD — DELIVERY-FEE-001 Tarifas y cargo de entrega

Estado: núcleo online automatizado y verificado localmente; ver evidencia exacta, límites y
pendientes en el plan DELIVERY-FEE-001 §7. PRD-FR-283..288 y SDD §70. La enumeración completa
sigue siendo contrato objetivo: no acredita canales/offline, emisión CFDI ni CI aún no ejecutados.

## TDD-TS-154 Catálogo, política y autorización de tarifas

Destinos nuevos: `apps/api/tests/test_delivery_fee_catalog.py`,
`test_delivery_fee_postgres.py` (incluye migración real, reversión vacía y bloqueo con historia).
Suite nueva de UI administrativa dentro de los destinos de TS-156.

### TDD-TC-438 Identidad, versiones y precisión de catálogo

BDD-SC-745/746; crear, consultar, publicar y archivar sin producto/receta/estación. Precio $28.00
capturado como 2800 centavos, tarifa sintética posterior de 3000; aceptar 28/28.0/28.00 y rechazar
28.001, negativos, moneda ajena y tipos boolean/string indebidos del DTO de centavos. Guardar sin
cambios no crea una revisión artificial. Defaults/umbral y captura son atómicos e idempotentes;
umbral desactivado NULL frente a 50000 habilitado, cero/negativo no equivalen a desactivado.
Archivar no borra historia ni reprecifica pedidos. Fixture explícito de dos sucursales y otra org.

### TDD-TC-439 Autoridad, destino y publicación concurrente

BDD-SC-747/751/766; `catalog.manage` corporativo, opciones locales scoped, rechazo de manipulación
de org/branch/tariff y de rol sin capacidad. Sin cambios de workspace, caja ni carrito. Herencia y
override de §58, default único dentro de lista activa; intento de inactivar default sin reemplazo.
PostgreSQL con dos conexiones/barrera real: dos publicaciones con misma versión, sólo un ganador;
rollback sin escritura parcial y errores seguros. No sustituir esa carrera con SQLite o mocks.

## TDD-TS-155 Cotización, selección y comando monetario

Destinos nuevos: `apps/api/tests/test_delivery_fee_pricing.py`, `test_delivery_fee_commands.py`
y carreras incluidas en `test_delivery_fee_postgres.py`; regresiones de creación, enmienda y pago
existentes se seleccionan por funciones `quote_local_order`, `create_local_order`, `amend_order`
y `pay_order`, sin ejecutar una suite completa local sólo por comodidad.

### TDD-TC-440 Sugerencia, sustitución y retiro persistente

BDD-SC-748/749/750; predeterminada 2800 y tarifa alternativa sintética 4200: elegir la segunda
produce 4200, nunca 7000. Rechazar lista/cantidad/duplicados y precio enviado como autoridad.
AUTO, SELECTED y REMOVED sobreviven recotización, restauración de borrador y cambios de tipo;
recoger cobra cero y regresar a delivery conserva preferencia. Restaurar y nuevo pedido funcionan
de forma distinta: nuevo usa AUTO/config actual. Retiro registra actor/motivo sin elevar permiso.
Verificar estado UI y respuesta real del servicio, no sólo presencia de strings en el componente.

### TDD-TC-441 Enmienda y fronteras de autorización

BDD-SC-749/751/756; borrador con orders.create, pedido persistido con orders.amend, misma branch y
versión; rechazo de pagado/no editable o producción iniciada según FR-217, aunque sólo cambie fee.
En una edición permitida fee-only no modifica líneas, reservas ni tareas; no amplía los estados
editables del pedido. Tarifa archivada conserva snapshot sin permitir nueva selección; sustitución explícita
elige precio actual y conserva política congelada. Toda escritura/auditoría/outbox se confirma o
revierte íntegra ante fallo inyectado. Enmienda con líneas y cargo comparte transacción/versión.

### TDD-TC-442 Tabla de verdad del umbral

BDD-SC-752/753/754; con umbral 50000 probar base 49999/50000/50001, envío 2800/0/0; desactivado
no exenta. Productos y modificadores 52000 menos descuento válido 3000 => base 49000, envío 2800;
propina 2000 no completa el umbral ni se suma al envío. Combo se cuenta una vez. Cruzar umbral
en ambos sentidos, cambiar tarifa estando gratis, retirar antes/durante/después y restaurar:
REMOVED prevalece; restaurar con base suficiente produce WAIVED_THRESHOLD. Cambiar configuración
no altera política de pedido confirmado ni repricing de historia pagada.

### TDD-TC-443 Aritmética y ausencia de efectos productivos

BDD-SC-755/756; Decimal: bruto 28, base 28/1.16, IVA diferencia; visual 24.14/3.86 y total +28.
Pruebas de propiedades de suma/conservación sobre centavos y varios pedidos; nada de float ni
recalcular desde 24.14. Datos de alimentos con impuesto NULL conservan desconocido; cero de fee
nuevo exento es conocido, legacy no capturado no lo es. Snapshot fiscal preciso y redondeo por
documento concilian sin doble IVA. Comparar ledger/consumos/tareas antes y después de añadir,
quitar y reemplazar fee; cambios fee-only producen delta productivo cero.

### TDD-TC-444 Replay, cotización obsoleta y carrera con pago

BDD-SC-757/758/766; hash incluye selección, retiro, carrito, ajuste, contexto y revisiones. Replay
idéntico tras cambio/desactivación recupera respuesta original; otro body misma key rechaza.
Publicar precio entre quote y create obliga recotizar; en pedido histórico sin cambio de selección
no provoca repricing. Dos transacciones PostgreSQL con barrera: pago frente a quitar/cambiar envío,
incluida liquidación agrupada de repartidor, sin payment/total/version discrepantes. Probar fallo
entre snapshot, order total, evento y commit. Quote no hace DML productivo; invalidación/alcance
de referencia y respuestas fuera de orden se prueban con el mecanismo fijado en D02.

## TDD-TS-156 Proyecciones, experiencia y compatibilidad de canales

Destinos nuevos: `tests/frontend/test_delivery_fee.mjs`, `tests/browser/test_delivery_fee.mjs`,
`apps/api/tests/test_delivery_fee_projections.py`, `test_delivery_fee_channels.py` y
`test_delivery_fee_offline.py`; PostgreSQL/migración comparten destinos TS-154.

### TDD-TC-445 Catálogo y comanda en navegador real

BDD-SC-745/748/749/750/759/766; UI Admin lista/alta/publicación, default, umbral y conflictos;
POS selección única, Quitar/Restaurar, gratis por monto frente a retirado, recuperación y readonly
tras pago. Rutas reales con fixture aislado, sin publicar datos productivos. Probar keyboard/foco
y 390/1024/1440 px sólo en estados afectados: loading, sin configuración, error, tarifa normal,
gratis, retirado y conflicto. Respuesta tardía no cambia selección; error conserva carrito y bloquea
confirmación desconocida. Test semántico de estado/comandos además de typecheck y QA visual.

### TDD-TC-446 Ticket, ventas, corte y recaudación

BDD-SC-759/760/761; fixture con cobrado/exento/retirado/compensado/legacy; sumas producto + fee =
total cobrado, sin sumar ajustes dos veces, y base + IVA conocido concilia. Ranking/unidades/food
cost excluyen fee. Impresión y reimpresión después de cambiar catálogo mantienen snapshots;
KDS no crea línea productiva. Actualización de tarifa/retirada posterior a asignación conserva
historia y enlaza revisión, pero deuda impaga usa total actual. Recepción cash atómica e idempotente;
tarjeta/prepagado no genera deuda ficticia ni remuneración automática. Reportes por alcance/período.

### TDD-TC-447 Concepto fiscal y recibo sin duplicación

BDD-SC-762; usar adaptador aislado y respuestas simuladas deterministas, no PAC productivo. Snapshot
contiene servicio con clave/unidad del emisor validadas y tasa aprobada; alimentos excluyen cargo;
rechazar mapeo ausente/tasa inconsistente, pagos parciales, actor ajeno y pedidos cancelados.
No fabricar impuestos de alimentos desconocidos. Exento/retirado no emite monto gravado inexistente.
Probar precisión del serializador y totales de varios pedidos, replay/incertidumbre, rectificación
compensatoria autorizada y no duplicación entre recibo y factura. Corregir sólo alimentos conserva
el fee histórico o reevalúa el umbral con su política congelada, sin perderlo/duplicarlo; antes y
después del cargo integran la imagen y el delta, sin alterar originales. Cubrir ruta legacy que hoy agrupa
todo en Consumo: un test debe fallar por su falta de desglose antes de cambiarla. Sandbox externo,
si se necesita, requiere autorización distinta y evidencia separada.

Oráculos numéricos de corrección autorizada con umbral histórico 50000 y tarifa 2800, después
de descuentos, sin modificar los registros originales:

| Imagen original pagada | Imagen corregida | Delta financiero | Delta bruto / IVA conocido del envío |
| --- | --- | --- | --- |
| Productos 49999 + envío 2800 = 52799 | Productos 50000 + envío 0 = 50000 | REFUND 2799 | -2800 / -386 centavos presentados |
| Productos 50000 + envío 0 = 50000 | Productos 49999 + envío 2800 = 52799 | CHARGE 2799 | +2800 / +386 centavos presentados |
| Productos 49999, envío REMOVED = 49999 | Productos 50000, envío REMOVED = 50000 | CHARGE 1 | 0 / 0 |

La base/IVA exactos del cargo y su compensación conservan Decimal; 386 es presentación del IVA
conocido del envío, no impuesto supuesto de alimentos ni base para recalcular. Validar el total
original inmutable, el snapshot corregido, el periodo actual del ajuste y el adaptador fiscal.

### TDD-TC-448 Contratos de canales y sincronización

BDD-SC-763/764/766; contratos para intenciones/aceptación, Asistto y adaptadores activos según su
escritor real. Propiedad del envío explícita, marketplace original no duplica fee local; modalidad
ambigua falla/revisa antes de cobrar. Payloads original y IDs trazables; importes maliciosos, retiro
externo sin capacidad y canal incompatible no evaden reglas. Offline requiere SQLite y PostgreSQL
reales, grant autorizado, política/versiones firmadas, outbox e inbox idempotentes, pérdida de red,
reinicio de gateway y central con precio distinto. Mantener snapshot de origen, rechazar manipulado,
ausente/expirado o contrato antiguo; comprobar también evento y total, no sólo respuesta HTTP.

### TDD-TC-449 Migración, rollout y rollback con historia

BDD-SC-765/766; upgrade desde head descubierto con datos legacy, sin reinterpretar productos
eliminados ni backfill de dinero. Downgrade vacío reversible y downgrade con revisiones, cargos,
documentos o outbox bloqueado sin pérdida. Rollback funcional y drenado en entorno aislado;
cliente POS/gateway viejo no escribe entrega nueva en branch/canal activados. No habilitar otros
canales mediante flag global. Contrato de error seguro y sin datos sensibles; gate CI no puede
aceptar suite PostgreSQL skippeada ni falta de URL de pruebas obligatoria.

## Gates y evidencia de implementación

- Integridad documental: `python -m pytest tests/architecture/test_traceability.py -q`,
  integridad de enlaces/IDs y `git diff --check`; no califica runtime como probado.
- Por incremento: RED causal de la prueba del TC correspondiente, GREEN, regresión focal y revisión
  de frontera `entrada -> autoridad -> total -> pago/snapshot -> proyección`.
- Backend: pytest de destinos afectados, Ruff y mypy. PostgreSQL es obligatorio para publicación,
  idempotencia monetaria, pago/enmienda y migración. SQLite/gateway sólo al implementar incremento
  offline, con ambos dialectos, nunca como sustituto de concurrencia PostgreSQL.
- Frontend: `pnpm typecheck`, pruebas semánticas focales y navegador real; build antes de release.
- CI actual ejecuta pytest global, mypy/Ruff, test:frontend-semantic y browser enumerados. Los
  destinos nuevos deben registrarse en esos gates y en `scripts/verify_postgres_evidence.py` cuando
  corresponda; ampliar `tests/architecture/test_ci_gates.py` para exigir su ejecución. No asumir que
  descubrimiento pytest registra por sí solo las pruebas browser o evidencia PostgreSQL obligatoria.
- Una auditoría R3 independiente del diff runtime con contexto fresco; matriz de afirmaciones y
  refutación en el plan. La suite completa aplicable corre una vez en CI según GOV-TEST-001.
- Activación/canary acotado sólo tras CI y autorización productiva; migración/configuración/datos y
  emisión externa no quedan autorizados por este diseño. Sin gates reales no marcar Implementado.


Destinos ejecutables actuales: `apps/api/tests/test_delivery_fee_{pricing,catalog,commands,
corrections,fiscal,postgres}.py`, `tests/frontend/test_delivery_fee.mjs`,
`tests/browser/test_delivery_fee.mjs` y gate de `tests/architecture/test_ci_gates.py`.
TC448 conserva sólo guardas de incompatibilidad en este incremento; su soporte funcional por
canal/gateway no está implementado. TC447 cubre concepto exacto aislado, bloqueo de agregado y
corrección sin descuentos; emisión real y correcciones descontadas conservan las dependencias de §70.7.


Límite de compensaciones encadenadas del incremento online: una segunda corrección pagada de un
pedido con cargo de domicilio se rechaza con `delivery_correction_chain_pending`, conservando
la primera corrección y permitiendo replay de su mismo comando. Requiere contrato de saldo
compensado acumulado antes de habilitar otra corrección, no recalcular contra el pago original.
Regresión persistida: original3300/productos500/envío2800, retiro autorizado devuelve2800;
una nueva solicitud no puede devolver otros2800. RED causal: segunda corrección se aplicaba;
GREEN: una sola corrección. Es guarda técnica de compatibilidad, sin ampliar edición impaga.


TC449: test_delivery_fee_schema_compatibility.py agrega siete casos de lecturas históricas,
esquema actual/desconocido sin tablas y esquema parcial; el error original UndefinedTable fue
RED causal. El gate PostgreSQL incluye delivery_fee tanto en su colección obligatoria como en
el fixture positivo del verificador. Los destinos históricos de downgrade permanecen intactos.
