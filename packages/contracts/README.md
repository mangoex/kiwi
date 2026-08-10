# Contracts

Contratos compartidos versionados.

Los schemas base viven en `schemas/` y gobiernan la comunicacion entre API central, gateway, frontends y workers.

`schemas/purchase-command.schema.json` define comandos offline idempotentes para crear, confirmar y cancelar compras directas.

`schemas/pos-catalog-projection-v1.schema.json` versiona la proyección de lectura del catálogo POS;
`selection` es nullable para mantener la compatibilidad de categorías sin selector previo.
