# Contracts

Contratos compartidos versionados.

Los schemas base viven en `schemas/` y gobiernan la comunicacion entre API central, gateway, frontends y workers.

`schemas/purchase-command.schema.json` define comandos offline idempotentes para crear, confirmar y cancelar compras directas.

`schemas/purchase-create-http-v1.schema.json` y `purchase-workspace-v1.ts` describen la captura
online de `POST /api/v1/purchases` y su preview. La creación online nueva envía `Idempotency-Key`
(8..180 caracteres) fuera del cuerpo. El documento admite día `YYYY-MM-DD` o timestamp ISO,
notas/evidencia y 1..200 partidas con precio explícito. Los decimales de preview y creación con
clave se devuelven como cadenas exactas. Clientes antiguos sin clave conservan temporalmente su
respuesta numérica y fallback de precio; no tienen garantía de recuperación durable. El envelope
offline y su compatibilidad gateway permanecen bajo su contrato separado.

`schemas/pos-catalog-projection-v1.schema.json` versiona la proyección de lectura del catálogo POS;
`selection` es nullable para mantener la compatibilidad de categorías sin selector previo.

PCO-004 agrega contratos estrictos (`additionalProperties: false`) para apertura, consulta, listado,
detalle y cierre operativo de turnos, además del monitor de ventas, su drill-down y los errores de
negocio. Los indicadores financieros del monitor siempre separan `known_cents` de
`unknown_operation_count`; un dato histórico ausente no se convierte en cero.
