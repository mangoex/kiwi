# TDD - Integración conversacional WhatsApp Asistto

### TDD-TS-145 Suite de integración conversacional WhatsApp Asistto

Verificación dirigida del adaptador de WhatsApp (Asistto Tech Provider), el agente conversacional,
el reconocimiento de clientes, el registro de pedidos desacoplado de turnos de caja y la configuración
en el panel de administración.

### TDD-TC-398 Verificación de autenticación y payload del webhook Asistto
- Archivo: `apps/api/tests/test_whatsapp_integration.py::test_tc398_whatsapp_webhook_authentication_and_idempotency`
- Propósito: Verificar que `POST /api/v1/integrations/whatsapp/webhook` rechace solicitudes sin token o con token inválido con 401, acepte payloads válidos de Asistto con Bearer token configurado y maneje la idempotencia mediante `message_id`.

### TDD-TC-399 Resolución de cliente, direcciones y favoritos por teléfono normalizado
- Archivo: `apps/api/tests/test_whatsapp_integration.py::test_tc399_customer_identification_and_address_lookup`
- Propósito: Verificar que al recibir un número telefónico en el webhook, el adaptador normalice el número a 10 dígitos, identifique el registro en `customer_phones`, recupere el nombre del cliente en `customers`, sus direcciones en `customer_addresses` y sus platillos frecuentes en `order_lines`.

### TDD-TC-400 Persistencia de orden en POS con canal WHATSAPP y cash_shift_id nulo
- Archivo: `apps/api/tests/test_whatsapp_integration.py::test_tc400_whatsapp_order_persistence_with_closed_shift`
- Propósito: Verificar que la confirmación de un pedido por WhatsApp persista la orden en `models.orders` con `channel="WHATSAPP"`, `status="PENDING"`, folio oficial de la sucursal `#KIWI-XXXX`, total en centavos exacto y `cash_shift_id=None`, y que `/orders/pending-count` lo contabilice inmediatamente.

### TDD-TC-401 Configuración en Admin con Master Prompt y despacho de respuesta a Asistto
- Archivo: `apps/api/tests/test_whatsapp_integration.py::test_tc401_whatsapp_admin_config_and_outbound_dispatch`
- Propósito: Verificar que un usuario con `admin.manage` pueda guardar y recuperar la configuración de WhatsApp en `IntegrationsService` (incluyendo `master_prompt`, `webhook_secret`, `return_url`, `auth_token`, `coexistence_enabled`), protegiendo secretos y enviando respuestas formateadas a la URL de retorno de Asistto.
