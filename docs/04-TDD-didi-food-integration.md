# TDD: Hub de Integraciones y Conector DiDi Food Marketplace

## TDD-TS-104 Suite de Integración DiDi Food y Hub de Canales

### TDD-TC-226 Validación de firma y autenticación de webhooks DiDi Food

- Archivo: `apps/api/tests/test_didi_food_integration.py::test_didi_signature_validation`
- Propósito: Verificar que peticiones con firma HMAC válida se acepten con 200 OK y peticiones con firma alterada o ausente se rechacen con 401 Unauthorized.

### TDD-TC-227 Enrutamiento de Shop ID y creación de pedido DiDi Food

- Archivo: `apps/api/tests/test_didi_food_integration.py::test_didi_store_routing_and_order_creation`
- Propósito: Verificar que la notificación de orden entrante se asocie a la sucursal Kiwi correcta mediante el Shop ID y genere una orden con canal `DIDI_FOOD`.

### TDD-TC-228 Idempotencia de notificaciones duplicadas de DiDi Food

- Archivo: `apps/api/tests/test_didi_food_integration.py::test_didi_webhook_idempotency`
- Propósito: Demostrar que reintentos de webhooks de DiDi Food con el mismo payload no duplican órdenes ni movimientos de inventario.

### TDD-TC-229 Configuración de credenciales y mapeo en API Admin DiDi Food

- Archivo: `apps/api/tests/test_didi_food_integration.py::test_didi_admin_configuration_api`
- Propósito: Validar que el panel de administración pueda consultar, actualizar credenciales seguras de DiDi Food y mapear sucursales.

### TDD-TC-230 Consulta y transición de estados de pedidos DiDi Food en POS

- Archivo: `apps/api/tests/test_didi_food_integration.py::test_didi_pos_orders_lifecycle`
- Propósito: Verificar que la terminal POS pueda listar pedidos de DiDi Food filtrados por sucursal y cambiar estados operativos.
