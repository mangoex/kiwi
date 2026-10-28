# TDD - Compras directas, caja y costo promedio

## TDD-TS-041 Compra, recepción, caja y costeo

Casos:

- crear compra en borrador con documento y renglones convertidos;
- recalcular subtotal, descuento, impuestos y total en backend;
- impedir flete u otros gastos mientras no exista política aprobada;
- confirmar con `purchases.manage`, turno abierto y `cash.movement.withdraw` cuando usa caja;
- crear un solo retiro vinculado y una entrada por renglón;
- calcular costo promedio ponderado con existencias positiva y cero;
- mostrar el precio de presentación antes de descuento sin llamarlo precio neto;
- aclarar que el costo de inventario excluye impuesto y se presenta por sucursal/almacén;
- excluir reservas de venta del saldo físico usado para costeo;
- rechazar existencia negativa sin producir efectos parciales;
- devolver el mismo resultado ante reintento con idempotency key;
- cancelar con contramovimientos, sin editar ni eliminar originales;
- auditar actor, sucursal, documento, motivo y referencias;
- aplicar y revertir migración conservando movimientos anteriores;
- probar precisión Decimal y ausencia de `float` en dominio.

## TDD-TC-034 Compra desde caja y promedio

Given existen 10 kg de azúcar a 20 pesos por kg
And existe un turno de caja abierto
When el supervisor confirma 10 kg a 30 pesos por kg pagados desde caja
Then crea un retiro por el total una sola vez
And crea una recepción por 10 kg
And el costo promedio queda en 25 pesos por kg.

## TDD-TC-212 Payload de confirmación distingue efectivo y otros métodos

- Archivo: `tests/frontend/test_pos_purchases_and_reprint.mjs`
- Backend: `apps/api/tests/test_branch_purchases_and_courtesies.py`

Given borradores equivalentes en Administración corporativa y Administración de sucursal
When se confirma una compra `paid_from_cash=true`
Then ambas UI exigen una caja validada por servidor para la sucursal activa y envían `register_id`
y el turno revisado junto con una clave y body estables hasta resolver el resultado. La cobertura
actual de `pos_register_id` sólo acredita el baseline; PUR-CASH-001 debe sustituir la aserción de
implementación por la conducta de alcance autorizada. Para `paid_from_cash=false` envían un body
sin campos de caja; el backend confirma
la recepción sin crear retiro. La prueba API conserva el caso negativo de efectivo sin caja/turno y
la atomicidad de inventario, costo y ledger.

## TDD-TS-135 Efectivo visible, alcance y confirmación única

PUR-CASH-001, R3. Casos 324..330 diseñados; no acreditados por las pruebas anteriores.
Fixtures: dos sucursales y almacenes, cuenta restringida y corporativa con sucursal activa,
usuario con sólo compras, usuario con compra+retiro sin cash.shift.read, cero/una/dos cajas OPEN,
turno cerrado y nuevo turno del mismo código. Sin red externa ni datos productivos.

## TDD-TC-324 Selector compartido y captura coherente

BDD-SC-607/612. Prueba de reducer/editor en `tests/frontend/test_purchase_workspace.mjs` y
validación API en `apps/api/tests/test_purchase_workspace.py`: default cash, cada método deriva
booleano correcto, guardar/preview sin movimientos, métodos explícitos incoherentes rechazados
en ambas direcciones, credit y métodos desconocidos rechazados en preview/creación/confirmación.
Preview y creación con clave siguen exigiendo ambos campos explícitos; probar por separado los
defaults existentes de creación legacy sin clave, sin extenderlos al contrato estricto. Mantener
históricos sin reescritura; confirmar un borrador incoherente o con método no admitido falla sin
efectos. Etiquetas no efectivo no implican crédito.
RED esperado: initialPurchaseDraft comienza hoy en other y el backend acepta cash/false.

## TDD-TC-325 Contexto mínimo de caja y autorización

BDD-SC-608/609. API: cero/una/varias cajas, código repetido entre sucursales, duplicidad OPEN
ambigua, actor/organización ajenos y permiso revocado. Sólo compras+retiro obtiene metadatos
mínimos de su sucursal, incluso sin cash.shift.read; no filtrar saldos por error o listado.
UI: preferencia global obsoleta no prevalece; elección explícita entre varias, borrador permitido
sin turno o retiro. Cambios de actor/sucursal invalidan selección y respuesta tardía.
RED esperado: no existe cash-context y hoy la UI confía en un código global de localStorage.

## TDD-TC-326 Contratos y revisión del turno

BDD-SC-609/610/612. Actualizar DTO y esquemas online de contexto/confirmación y las pruebas
`tests/contract/test_purchase_workspace_contract.py`; no modificar contrato offline.
Tipos inválidos, branch distinto al documento, turno de otra caja y campos de caja en no efectivo
se rechazan; clientes antiguos explícitos mantienen guarda OPEN. UI conserva modal ante 403/409,
muestra método/branch/caja/turno/importe y sólo refresca consultas autorizadas tras éxito.
RED esperado: la revisión no muestra contexto de caja y hoy se cierra aunque falle confirmación.

## TDD-TC-327 Atomicidad, conciliación y carreras

BDD-SC-610/611. Extender `test_cash_ledger.py` y `test_cash_ledger_postgres.py` en bases aisladas:
cierre contra compra, cierre+reapertura del mismo código contra turno revisado, doble confirmación
con misma y distinta clave, y confirmación contra cancelación. Usar barreras deterministas,
sin sleeps como prueba de orden. Contar compras/recepciones/retiros/costo/auditoría; comprobar
esperado 200000 - 30000 = 170000 centavos y ausencia de doble resta. Inyectar fallo tras retiro,
recepción, actualización de costo y auditoría: rollback completo. Revisar orden de locks/deadlock.
El test actual compra/cierre no acredita doble confirmación de la misma compra en PostgreSQL.

## TDD-TC-328 Recuperación e identidad idempotente

BDD-SC-611. Backend: misma clave/identidad devuelve documento y vínculos aun tras cierre/cancelación;
cambiar actor autorizado, branch, caja, turno o documento con esa clave produce conflicto, no efecto.
Revocar permiso impide replay no autorizado. Frontend: doble clic, timeout antes/después de commit,
recarga y fallo al refrescar conservan el resultado sin generar intención nueva automáticamente.
Probar recuperación desde campos existentes también para documentos legados; si la evidencia
persistida no basta, detener esa implementación y revisar el diseño, sin inferir éxito ni migrar datos.

## TDD-TC-329 Cancelación y otros métodos sin regresión

BDD-SC-612/613. Reutilizar pruebas cash/compensación de `test_branch_purchases_and_courtesies.py`
y `test_purchase_workspace.py`: efectivo resta total inclusive impuesto informativo; costo excluye
impuesto; tarjeta/transferencia/otro no mueven caja; cancelación con turno original OPEN compensa
y con cerrado rechaza sin parcialidad. Sin cambios a existencias históricas ni fórmulas Decimal.

## TDD-TC-330 Recorrido compartido y QA visual

BDD-SC-607..613. Extender `tests/browser/test_purchase_workspace_e2e.mjs` con API/BD aisladas:
cuenta autorizada abre desde Admin y acceso POS el mismo editor, crea nota, revisa caja, confirma
y verifica retiro único/esperado; repetir otro medio y cambio de sucursal. QA desktop y ancho reducido:
selector, contexto, errores en español, teclado/foco y nombres sin recorte. No usar producción.
Gate: typecheck/build de frontends afectados, lint/mypy focal backend, contratos, E2E,
PostgreSQL/SQLite focales, CI aplicable y auditoría Sol independiente. Canary productivo R3 queda
pendiente de autorización separada y no se acredita con pruebas locales.

## TDD-TC-407 Fecha local, entrega y controles compactos

BDD-SC-705. Extender `tests/frontend/test_purchase_workspace.mjs` para probar el día de sucursal
en ambos lados de medianoche UTC, default sin marcar captura como editada, conservación de snapshot,
`delivered_by_name`, inserción inmediatamente después, límite/remoción y contratos accesibles de
`+`/papelera. Verificar por semántica CSS que el cuerpo puede encogerse y desplazarse.

Extender `tests/contract/test_purchase_workspace_contract.py` y
`apps/api/tests/test_purchase_workspace.py` con campo opcional acotado a 160, recorte canónico,
rechazo de tipo/longitud sin efectos, persistencia, lectura y replay idempotente. La migración
SQLite sube desde 0093, conserva documentos antiguos con `NULL`, permite downgrade sin datos y lo
bloquea cuando eliminaría un nombre; PostgreSQL focal confirma el mismo DDL/roundtrip cuando exista
la base aislada. QA visual: 1440x900, 1024x768 y ancho reducido, con teclado, foco, iconos, scroll y
acciones finales visibles. Gates: prueba semántica, contrato, pytest/ruff focal, typecheck, migración,
`git diff --check`, CI aplicable y auditoría independiente R3; despliegue y migración productiva
conservan autorización separada. La cobertura de autocompletado documental y multimodal del borrador
de compra (`PUR-AI-CAPTURE-001`, `BDD-SC-804`) se registra en `TDD-TC-474` (`docs/04-TDD-procurement-assistance.md`).

## TDD-TS-162 Borradores de compra inspeccionables y editables

PUR-DRAFT-001, R3. Base aislada con dos sucursales, cuentas read/manage, borrador de varias partidas,
documento confirmado y cancelado, versiones concurrentes y fallos inyectados. No usa producción.

## TDD-TC-475 Detalle y autoridad de UI

BDD-SC-805. La prueba semántica y el recorrido browser comprueban **Ver** para lectura, detalle de
todas las partidas y ausencia de Editar/Eliminar sin `purchases.manage`. Para un manager comprueban
Ver, Editar, Confirmar y Eliminar borrador, hidratación exacta del editor y que una fila cancelada en
draft deja de ser pendiente sin ocultar cancelaciones de compras antes confirmadas.

## TDD-TC-476 Edición idempotente, versionada y atómica

BDD-SC-806. Contrato y API prueban payload explícito, rama inmutable, autorización, versión vigente,
replay de la misma key/hash/actor/documento, conflicto de key o versión y rechazo de estados no draft.
Inyectar fallo después de reemplazar líneas, auditoría y recibo; documento, partidas, versión y efectos
deben quedar intactos. Contar cero movimientos/caja/costo antes y después. PostgreSQL usa barreras para
editar contra confirmar/cancelar; SQLite focal verifica la misma transición serial.

## TDD-TC-477 Descarte controlado y revisión exacta

BDD-SC-807. Descartar draft mediante el comando exclusivo `discard`, con estado y versión vigentes,
conserva filas y auditoría, no genera evento financiero
ni reversa y no borra físicamente. Versión obsoleta y ausencia de versión tras una edición fallan sin
mutación. Confirmación UI envía `expected_version`; una confirmación obsoleta no recibe las partidas
editadas sin nueva revisión. Migración sube documentos existentes a versión 1, persiste recibos y
bloquea downgrade con ediciones. Gates: pytest/ruff/mypy focales, contrato, prueba frontend, typecheck,
migración SQLite/PostgreSQL focal, `git diff --check`, QA visual de tabla/modal y auditoría Sol fresca.
