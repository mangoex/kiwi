# BDD - Administración única desde POS

## BDD-FEAT-052 Administración autorizada con pantallas canónicas

```gherkin
@PRD-FR-005 @PRD-FR-018 @PRD-FR-019 @pos @branch @frontend
Feature: Administración del POS utiliza las funciones existentes del administrador

  @BDD-SC-136
  Scenario: El menú muestra sólo funciones consultables
    Given una sesión canónica con una capacidad administrativa consultable
    When abre Administración en el POS
    Then ve sólo las tarjetas permitidas por la política compartida

  @BDD-SC-137
  Scenario: Cajero sin capacidades administrativas
    Given una sesión con sólo pos.operate
    Then no ve Administración
    And el acceso directo no monta páginas administrativas ni consulta sus datos

  @BDD-SC-138
  Scenario: Paridad con la entrada directa del administrador
    Given una cuenta autorizada y una sucursal validada
    When abre una tarjeta administrativa del POS
    Then abre la misma página, editor y comandos de Admin
    And las rutas locales antiguas redirigen al mismo destino autorizado

  @BDD-SC-139
  Scenario: Regreso a caja
    Given una captura persistida en la caja seleccionada
    When entra a Admin y usa Volver a caja
    Then revalida la misma sucursal y recupera la captura
    And respeta las guardas de operaciones pendientes

  @BDD-SC-140
  Scenario: Sucursal confirmada sin fallback
    Given un administrador ha seleccionado la sucursal B
    When consulta o modifica disponibilidad local desde Admin
    Then cada petición contiene branch_id B
    And la sucursal A permanece sin cambios
    And una sucursal no autorizada se rechaza antes de montar el módulo

  @BDD-SC-141
  Scenario: Consulta separada de escritura
    Given una cuenta con purchases.read y sin purchases.manage
    Then puede consultar Compras sin crear, confirmar ni cancelar
    And la API rechaza esos comandos con 403
    And Mermas y Traspasos sin inventory.read devuelven 403 sin exponer datos

  @BDD-SC-142
  Scenario: Catálogo central y disponibilidad local
    Given una cuenta con permisos de sucursal sin catalog.manage
    Then usa las secciones locales de las páginas canónicas
    And no puede editar proveedores ni catálogo central
    And un permiso de envío no habilita recepción de traspasos

  @BDD-SC-143
  Scenario: La sesión del servidor es autoridad
    Given permisos falsificados en localStorage o nombres de roles corporativos
    When Admin revalida la sesión o la cuenta pierde permisos
    Then menús, rutas y comandos respetan las capacidades del servidor
    And un error de sesión o conexión bloquea los módulos hasta revalidar
```
