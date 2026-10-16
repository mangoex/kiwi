# TDD-TS-149 Seguimiento público móvil

## TDD-TC-416 Proyección pública y ciclo operativo

`apps/api/tests/test_public_order_tracking.py`: prueba la consulta HTTP desde PENDING_REVIEW,
aceptación y estados operativos, modalidades y CLOSED con evidencia de entrega/devolución.
Compara efectos antes/después para demostrar ausencia de escrituras. El contrato JSON se valida
contra `packages/contracts/schemas/public-order-tracking-v1.schema.json`.

## TDD-TC-417 Privacidad, alcance y disponibilidad

La misma suite rechaza folios y referencias malformadas, corta vínculos de otra organización o
sucursal, verifica DTO mínimo, headers de privacidad y 429/503 ante límite/fallo del limiter.
La lectura original sin `tracking=true` conserva su contrato anterior.
`test_public_tracking_index_postgres.py` verifica la migración0097 y su reversión sin pérdida de
filas en PostgreSQL aislado y SQLite; CI exige que ambos casos se ejecuten sin omisiones.

## TDD-TC-418 Persistencia y sincronización móvil

`tests/frontend/test_public_order_tracking.mjs`: ejecuta almacenamiento validado, mapeo de etapas
y consultas con respuestas diferidas, cancelación y temporizadores deterministas. Cubre varios
pedidos, cambio de sucursal, terminales, storage bloqueado/corrupto y fallos HTTP. No usa red real.

## TDD-TC-419 Recorrido completo y presentación

`tests/browser/test_public_order_tracking.mjs`: navegador contra API SQLite efímera; crea solicitud,
consulta, acepta y avanza con comandos reales, recarga y valida aislamiento entre sucursales.
QA visual en 390 y 1280 píxeles, teclado, contraste y progreso accesible. Typecheck/build móvil,
Ruff/mypy dirigidos, trazabilidad y auditoría R3 independiente antes del cierre. CI completa y
despliegue/canary mantienen evidencia y autorización separadas.
