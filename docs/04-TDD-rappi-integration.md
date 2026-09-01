# TDD: Hub de Integraciones y Conector Rappi Restaurante

## TDD-TS-105 Suite de Integración Rappi Restaurante y Hub de Canales

### TDD-TC-231 Validación de firma y autenticación de webhooks Rappi

- Archivo: `apps/api/tests/test_rappi_integration.py::test_rappi_signature_validation`
- Propósito: Verificar que peticiones con firma HMAC-SHA256 válida en header `Rappi-Signature` o `X-Rappi-Signature` se acepten con 200 OK y peticiones con firma alterada o ausente se rechacen con 401 Unauthorized.

### TDD-TC-232 Enrutamiento de Store ID y creación de pedido Rappi

- Archivo: `apps/api/tests/test_rappi_integration.py::test_rappi_store_routing_and_order_creation`
- Propósito: Verificar que la notificación de orden entrante (`NEW_ORDER`) se asocie a la sucursal Kiwi correcta mediante el `Store ID` y genere una orden con canal `RAPPI` y folio `#R...`.

### TDD-TC-233 Idempotencia de notificaciones duplicadas de Rappi

- Archivo: `apps/api/tests/test_rappi_integration.py::test_rappi_webhook_idempotency`
- Propósito: Demostrar que reintentos de webhooks de Rappi con el mismo payload no duplican órdenes, comandas ni consumos de inventario.

### TDD-TC-234 Configuración de credenciales y mapeo en API Admin Rappi

- Archivo: `apps/api/tests/test_rappi_integration.py::test_rappi_admin_configuration_api`
- Propósito: Validar que el panel de administración pueda consultar, actualizar credenciales seguras de Rappi y mapear sucursales.

### TDD-TC-235 Simulación de pedidos Rappi para pruebas Sandbox

- Archivo: `apps/api/tests/test_rappi_integration.py::test_rappi_simulate_order_sandbox`
- Propósito: Verificar que el endpoint de simulación genere un pedido de prueba estructurado como Rappi que ingrese exitosamente al flujo operativo.
