# Contracts

Contratos compartidos versionados.

Los schemas base viven en `schemas/` y gobiernan la comunicacion entre API central, gateway, frontends y workers.

`schemas/purchase-command.schema.json` define comandos offline idempotentes para crear, confirmar y cancelar compras directas.
