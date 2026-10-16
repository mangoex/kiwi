# BDD — Historias del piloto POS/Admin

```gherkin
@PRD-FR-267 @pos @critical
Feature: Entender y conservar la autoridad de sucursal
  @BDD-SC-700
  Scenario: Selector autorizado visible con bloqueo explicado
    Given una sesión corporativa con varias sucursales autorizadas
    When el rollout está apagado o el POS opera por gateway local
    Then ve las sucursales y el motivo por el que no puede cambiar
    And el selector está deshabilitado y no emite cambios
    When servidor y operación permiten seleccionar
    Then el cambio utiliza el comando canónico y conserva sus bloqueadores

@PRD-FR-266 @admin
Feature: Distinguir catálogo corporativo e inventario operativo
  @BDD-SC-701
  Scenario: Hub de inventario e insumos sin sucursal operativa engañosa
    Given un usuario autorizado en Administración
    When abre el hub Inventario o el catálogo de Insumos
    Then el topbar no muestra la sucursal del POS como alcance de ese catálogo
    And las pantallas de existencias conservan su contexto de almacén

@PRD-FR-020 @pos @critical
Feature: Encontrar pedidos de caja y web en su sucursal
  @BDD-SC-702
  Scenario: Lista conjunta paginada y acceso al pedido confirmado
    Given pedidos operativos y solicitudes web pendientes de la misma sucursal
    When consulta Pedidos con límite y filtros
    Then ambos orígenes respetan fecha, servicio y búsqueda y se ordenan juntos
    And las páginas no repiten filas ni exceden el límite
    When pulsa Ver pedidos tras confirmar una venta
    Then abre ese pedido con la misma autoridad local o central
    And no consulta otra sucursal ni cae silenciosamente a otra autoridad

@PRD-FR-010 @PRD-FR-243 @admin
Feature: Configurar un producto utilizando el espacio disponible
  @BDD-SC-703
  Scenario: Selector superior y protección del borrador
    Given el catálogo de Productos con un producto seleccionado
    When selecciona otro producto en el desplegable superior
    Then su detalle ocupa el ancho disponible bajo el selector
    And conserva búsqueda, grupo, acciones y seis pestañas
    When hay una edición o alta sin guardar y cancela el descarte
    Then conserva el producto seleccionado y sus datos sin enviar escrituras
```
