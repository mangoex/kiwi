# TDD - Gateway local y outbox SQLite

## TDD-TS-024 Gateway Local Outbox

Casos:

- inicializar SQLite en modo WAL,
- crear tablas locales de outbox,
- registrar comando valido como `PENDING`,
- retornar el mismo comando ante la misma `idempotency_key`,
- listar solo comandos pendientes,
- marcar comando como `CONFIRMED` con checkpoint,
- conservar ultimo checkpoint local,
- rechazar comandos sin campos obligatorios.

## TDD-TC-017 Outbox local idempotente

Given el gateway recibe un comando con `idempotency_key`
When el mismo comando se registra dos veces
Then existe una sola fila local
And el comando queda pendiente una sola vez.

## TDD-TC-018 Confirmacion local de checkpoint

Given existe un comando pendiente en SQLite
When la API central confirma checkpoint 7
Then el gateway guarda ese checkpoint
And el comando deja de aparecer en pendientes.
