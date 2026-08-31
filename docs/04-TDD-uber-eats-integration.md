# TDD: Hub de Integraciones y Conector Uber Eats Marketplace

## TDD-TS-103 Suite de Integración Uber Eats y Hub de Canales

### TDD-TC-221 Validación de firma X-Uber-Signature y autenticación

- Archivo: `apps/api/tests/test_uber_eats_integration.py::test_uber_signature_validation`
- Propósito: Verificar que peticiones con firma HMAC válida se acepten con 200 OK y peticiones con firma alterada o ausente se rechacen con 401 Unauthorized.

### TDD-TC-222 Enrutamiento de Store UUID y creación de pedido

- Archivo: `apps/api/tests/test_uber_eats_integration.py::test_uber_store_routing_and_order_creation`
- Propósito: Verificar que la notificación de orden entrante se asocie a la sucursal Kiwi correcta mediante el Store UUID y genere una orden con canal `UBER_EATS`.

### TDD-TC-223 Idempotencia de notificaciones duplicadas de Uber Eats

- Archivo: `apps/api/tests/test_uber_eats_integration.py::test_uber_webhook_idempotency`
- Propósito: Demostrar que reintentos de webhooks de Uber con el mismo payload no duplican órdenes ni movimientos de inventario.

### TDD-TC-224 Configuración de credenciales y mapeo en API Admin

- Archivo: `apps/api/tests/test_uber_eats_integration.py::test_uber_admin_configuration_api`
- Propósito: Validar que el panel de administración pueda consultar, actualizar credenciales seguras y mapear sucursales.

### TDD-TC-225 Consulta y transición de estados de pedidos Uber Eats en POS

- Archivo: `apps/api/tests/test_uber_eats_integration.py::test_uber_pos_orders_lifecycle`
- Propósito: Verificar que la terminal POS pueda listar pedidos filtrados por sucursal y cambiar estados operativos (marcar listo para entrega con notificación a API externa).
