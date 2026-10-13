# TDD - Compras corporativas distribuidas

## TDD-TS-140 CORP-PUR-001

R3. Primero pruebas focales SQLite de dominio/API y frontend; PostgreSQL aislado acredita locks y
sobrerrecepción concurrente. La fixture focal implementada usa una razón social, dos sucursales con
almacenes, proveedor, presentaciones, Dueño organizacional, actor organizacional de sólo lectura y
comprador limitado a sucursal. Casos multi-organización, sucursal inactiva y costo con existencia
positiva quedan como ampliación explícita y no se presentan como evidencia ejecutada de este paquete.

La limpieza del esquema sintético PostgreSQL usa `SET LOCAL statement_timeout=60000` exclusivamente
en su transacción de TRUNCATE; fuera de ella los comandos conservan 15 s y lock timeout de 10 s.

## TDD-TC-374 Creación, asignación y aprobación puras

Prueba create/replay/conflict, suma exacta de asignaciones, snapshots Decimal, una razón social,
destinos activos y almacén canónico. Crear/aprobar no cambia inventario, costo, precio ni caja.
AUD-2026-10-13 agrega regresiones de catálogo local/insumo inactivo y límites agregados Numeric(18,6).
La frontera acepta únicamente campos de su comando y una versión entera no booleana.

## TDD-TC-375 Recepción parcial y completa por destino

Prueba cantidades comerciales/base, movimiento inmutable, costo promedio con existencia cero,
historial con lineage de sucursal/almacén/orden/recepción y estados
`APPROVED → PARTIALLY_RECEIVED → RECEIVED`. Divide un costo no finito en varias recepciones y exige
que el último tramo absorba el remanente y la suma de movimientos coincida exactamente con la línea.
Repite el caso con conversión base fraccionaria y exige que inventario y asignación terminen en la
cantidad base congelada, sin acumular redondeo por recepción.
Con conversión base mínima, intenta una parcial cuyo remanente cuantiza a cero: exige rechazo estable,
rollback total y que una recepción completa posterior sí termine la orden.
Reparto entre destinos: base 0.333333 en dos mitades conserva 0.333333; costo 0.000002 entre
cuatro destinos no produce remanente negativo. Se congela secuencia/target/policy 2; una orden
legacy inválida se bloquea sin reescribir snapshots. Costeo con stock previo positivo se verifica
separadamente del promedio derivado redondeado.

## TDD-TC-376 Idempotencia, autorización y aislamiento

Prueba mismo key/body, key/body distinto, rol branch y warehouse que no corresponde. Todos los
rechazos comparan efectos antes y después y verifican respuestas sin SQL ni payload sensible. Un rol organizacional de sólo lectura
obtiene las referencias corporativas sin `purchases.read`, pero no muta ni recibe.
Después de recibir en B, un actor con `purchases.read` limitado a A sólo obtiene historial legacy
global y de A; el actor organizacional sí puede consultar el lineage de B.
Reutilizar clave con URL de otra orden falla; body.order_id inesperado se rechaza en approve/cancel.
La suite `test_corporate_purchase_remediation.py` convierte los repros H09-H13 en aceptación.
U01/U02 verifican journal previo al POST, exactitud key/body tras respuesta perdida y reload,
rechazo de storage corrupto/ajeno, ausencia de nueva intención mientras existe incertidumbre,
cantidad vacía/cero/excesiva, SKU/unidades visibles y confirmación explícita del destino. El refresh
fallido después de un POST confirmado no habilita un segundo efecto.
Una credencial B instalada antes del clic en una vista aún validada como A no crea journal ni POST.
Replay v3 con detalle ya v4 consulta el GET actual y muestra v4, sin reutilizar pendientes antiguos.

## TDD-TC-377 Concurrencia y rollback R3

PostgreSQL con barreras deterministas prueba dos recepciones que exceden saldo, orden de locks y
fallos inyectados después de movimiento/costo/historial/auditoría. Como máximo una confirma y todo
fallo revierte completo. SQLite sólo cubre invariantes e idempotencia.

## TDD-TC-378 Cancelación e historia

Cancelar DRAFT exige motivo y conserva filas/auditoría; APPROVED, PARTIALLY_RECEIVED y RECEIVED no se
eliminan ni revierten implícitamente. La futura compensación deberá referenciar originales y tendrá
su propio RED antes de exponerse.
Migración de targets hace upgrade/downgrade vacío y mantiene policy legacy sin cambios; downgrade
con órdenes policy 2 se bloquea. No recalcula efectos históricos ni aplica migración productiva.

## TDD-TC-379 Dos recorridos y QA visual

Prueba semántica y navegador verifican las acciones Compra corporativa/Compra de sucursal, ausencia
de selector/etiqueta redundante en corporativa, selección explícita de destinos, progreso y errores;
la compra local conserva sucursal/caja. Typecheck, build Admin si cambia empaquetado, migración
upgrade/downgrade vacío, Ruff, mypy focal, `git diff --check`, CI aplicable y auditoría Sol fresca.
La prueba frontend semántica y el recorrido manual conservan evidencia separada. U01/U02 agregan
`test_corporate_purchase_remediation.mjs`: navegador automatizado con servidor simulado para
respuesta perdida, recuperación e identidad; no certifica E2E contra backend real ni producción.
