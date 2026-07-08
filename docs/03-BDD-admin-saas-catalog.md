# BDD - Admin SaaS y catalogos operativos

## BDD-FEAT-030 Consola Admin SaaS

```gherkin
@PRD-FR-001 @PRD-FR-002 @PRD-FR-003 @PRD-FR-005 @admin @phase1
Feature: Consola administrativa SaaS

  @BDD-SC-046
  Scenario: Navegar modulos operativos desde Admin
    Given existe la organizacion Kiwi Restaurante
    When el administrador abre Admin
    Then ve una navegacion por modulos de operacion, catalogos, inventario, configuracion y sistema
    And ve indicadores de sucursales, productos, usuarios, roles y sincronizacion
    And puede abrir el modulo Catalogos sin salir de Admin

  @BDD-SC-056
  Scenario: Operar catalogos e inventario desde un workbench visual
    Given existen sucursales, productos, insumos, recetas y movimientos de inventario
    When el administrador abre Admin
    Then ve accesos destacados a POS, KDS, Catalogos, Inventario y Usuarios
    And Catalogos separa sucursales y productos con acciones primarias visibles
    And Inventario muestra existencia teorica, recetas vigentes y kardex en una sola vista
    And los estados criticos se distinguen con texto y color, no solo con color
    And las tablas conservan encabezados, labels visibles y mensajes de carga
```

## BDD-FEAT-031 Catalogos administrables

```gherkin
@PRD-FR-002 @PRD-FR-003 @PRD-FR-010 @PRD-FR-011 @PRD-FR-012 @PRD-FR-014 @PRD-FR-015 @catalog @phase1
Feature: Catalogos de sucursales y productos

  @BDD-SC-047
  Scenario: Crear sucursal con almacen
    Given existe una razon social de Kiwi Restaurante
    When el administrador crea una sucursal con nombre y codigo
    Then el sistema conserva la sucursal
    And crea su almacen formal
    And evita duplicar el codigo dentro de la organizacion
    And registra auditoria del alta

  @BDD-SC-048
  Scenario: Crear producto vendible
    Given existe la Sucursal Piloto
    When el administrador crea un producto con categoria, SKU, estacion y precio
    Then el sistema conserva el producto activo
    And crea precio vigente en centavos
    And marca disponibilidad para la Sucursal Piloto
    And registra auditoria del alta
```
