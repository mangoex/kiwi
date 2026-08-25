# TDD - Gateway local y outbox SQLite

## TDD-TS-024 Gateway Local Outbox

Casos:

- inicializar SQLite en modo WAL,
- crear tablas locales de outbox,
- registrar sólo `cash.movement.create.v1` válido como `PENDING_SYNC`,
- retornar el mismo comando ante la misma `idempotency_key`,
- listar solo comandos pendientes,
- marcar comando como `CONFIRMED` con checkpoint,
- conservar ultimo checkpoint local,
- rechazar comandos sin campos obligatorios,
- validar forma, UUID y fecha contra el contrato versionado,
- derivar actor y alcance de un grant Ed25519 ligado al gateway,
- rechazar correlación, causación, campos adicionales y payload vacío,
- detectar conflicto ante cualquier diferencia de intención o alcance.

## TDD-TC-017 Outbox local idempotente

Given el gateway recibe un comando con `idempotency_key`
When el mismo comando se registra dos veces
Then existe una sola fila local
And el comando queda PENDING_SYNC una sola vez.

## TDD-TC-018 Confirmacion local de checkpoint

Given existe un comando pendiente en SQLite
When la API central confirma checkpoint 7
Then el gateway guarda ese checkpoint
And el comando deja de aparecer en pendientes.

## TDD-TC-179 Replay estricto y sobre versionado

Given una fila local creada desde un `command-envelope.v1` válido
When se reintenta con la misma clave y la intención completa idéntica
Then se devuelve la fila existente.

When cambia cada campo inmutable de forma parametrizada
Then se devuelve `idempotency_conflict` y no se inserta ni retorna una fila de otro alcance.

La suite valida además UUID, `date-time`, grant/actor, campos adicionales y payload vacío como
rechazos cerrados. Ocho replays idénticos concurrentes deben obtener el mismo identificador de fila
y dejar una sola fila `PENDING_SYNC`, sin propagar `IntegrityError`.
