# Contracts

Contratos compartidos versionados.

Los schemas base viven en `schemas/` y gobiernan la comunicacion entre API central, gateway, frontends y workers.

`schemas/purchase-command.schema.json` define comandos offline idempotentes para crear, confirmar y cancelar compras directas.

`schemas/pos-catalog-projection-v1.schema.json` versiona la proyección de lectura del catálogo POS;
`selection` es nullable para mantener la compatibilidad de categorías sin selector previo.

PCO-004 agrega contratos estrictos (`additionalProperties: false`) para apertura, consulta, listado,
detalle y cierre operativo de turnos, además del monitor de ventas, su drill-down y los errores de
negocio. Los indicadores financieros del monitor siempre separan `known_cents` de
`unknown_operation_count`; un dato histórico ausente no se convierte en cero.
