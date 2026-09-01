# BDD - Hub de Integraciones y Conector Rappi Restaurante

## BDD-FEAT-103 Hub de Integraciones y Configuración de Rappi en Backoffice

```gherkin
@PRD-FR-140 @PRD-FR-232 @integrations @admin @rappi
Feature: Administración centralizada de credenciales y mapeo de Rappi Restaurante

  @BDD-SC-476
  Scenario: Guardar configuración de Rappi y generar URL de Webhook
    Given el administrador corporativo accede al Hub de Integraciones
    When ingresa Client ID "rappi_client_123", Client Secret "rappi_sec_456", Webhook Secret "rappi_whsec_789" y entorno "sandbox"
    Then el sistema almacena la configuración de forma persistente y segura
    And expone la URL oficial de webhook para registro en Rappi Partners Developer Portal
    And permite activar o pausar el conector globalmente

  @BDD-SC-477
  Scenario: Asociar Store ID de Rappi a sucursal Kiwi
    Given existe la sucursal Kiwi "Sucursal Principal"
    And existe una configuración activa de Rappi
    When el administrador asocia el Store ID "rappi_store_guadalajara_01" a "Sucursal Principal"
    Then los webhooks y órdenes asociadas a ese Store ID se enrutan exclusivamente a "Sucursal Principal"

  @BDD-SC-478
  Scenario: Consulta de bitácora y monitor de webhooks Rappi
    Given se han recibido eventos de webhook de Rappi
    When el administrador consulta el monitor de integraciones para Rappi
    Then visualiza la lista cronológica con timestamp, tipo de evento, estado de procesamiento y respuesta
```

## BDD-FEAT-104 Ingestión Segura e Idempotente de Órdenes Rappi

```gherkin
@PRD-FR-141 @PRD-FR-147 @PRD-FR-232 @webhooks @security @rappi
Feature: Recepción y normalización de pedidos de Rappi Restaurante

  @BDD-SC-479
  Scenario: Validar firma criptográfica HMAC-SHA256 en webhooks de Rappi
    Given un webhook entrante en "/v1/integrations/rappi/webhook"
    When el encabezado de firma "Rappi-Signature" o "X-Rappi-Signature" contiene un HMAC válido calculado con el Webhook Secret
    Then el servidor acepta la solicitud y responde con HTTP 200 OK
    And registra el evento en "integration_webhook_logs"

  @BDD-SC-480
  Scenario: Rechazar webhook de Rappi sin firma o con firma manipulada
    Given un webhook entrante a Rappi con firma incorrecta o ausente
    When el validador de seguridad procesa la firma
    Then rechaza la llamada con HTTP 401 Unauthorized
    And no crea órdenes ni despacha eventos operativos

  @BDD-SC-481
  Scenario: Idempotencia en reintentos de webhooks de Rappi
    Given una notificación de orden de Rappi con ID "rappi_ord_999" ya fue procesada
    When Rappi reintenta la misma notificación con el mismo payload
    Then el sistema responde HTTP 200 OK con estado already_processed
    And no duplica el pedido, ni las comandas ni los consumos de inventario
```

## BDD-FEAT-105 Gestión Operativa y Simulación de Pedidos Rappi

```gherkin
@PRD-FR-233 @pos @orders @rappi
Feature: Visualización, control y simulación de pedidos Rappi en Punto de Venta y Backoffice

  @BDD-SC-482
  Scenario: Visualizar pedidos de Rappi en la terminal POS y monitores
    Given un cajero está en el POS de "Sucursal Principal"
    And existen pedidos activos de Rappi
    When el cajero consulta los pedidos de canales externos
    Then visualiza las tarjetas de los pedidos con su folio Rappi (ej. #R101), comensal y artículos
    And puede cambiar el estado operativo notificando la actualización

  @BDD-SC-483
  Scenario: Simular pedido de Rappi desde el panel de administración
    Given el administrador está en la pestaña de Rappi en el Hub de Integraciones
    When hace clic en "Simular Pedido de Prueba (Sandbox)" con una sucursal vinculada
    Then el sistema genera un webhook sintético válido de Rappi
    And procesa la orden exitosamente devolviendo el ID de orden interna y folio generado
```
