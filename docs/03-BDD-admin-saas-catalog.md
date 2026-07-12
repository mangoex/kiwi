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

  @BDD-SC-058
  Scenario: Revisar centro de mando visual SaaS
    Given existen datos base de organizacion, sucursal, catalogo, inventario y usuarios
    When el administrador abre Admin
    Then ve un centro de mando con pasos de preparacion operativa
    And cada paso muestra estado textual, avance y modulo relacionado
    And puede saltar desde el centro de mando a Catalogos, Inventario, Usuarios o Sistema
    And ve una lectura rapida de salud operativa sin depender solo de color
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

## BDD-FEAT-047 Catálogos consistentes y administración desde POS

```gherkin
@PRD-FR-017 @PRD-FR-019 @catalog @branches
Feature: Compartir catálogos y contexto de sucursal

  @BDD-SC-110
  Scenario: Heredar un producto central sin excepción de sucursal
    Given existe un producto activo con precio vigente en el catálogo central
    And no existe una excepción de disponibilidad para Sucursal Norte
    When POS consulta el menú de Sucursal Norte
    Then el producto aparece como vendible
    When la sucursal registra explícitamente que el producto no está disponible
    Then el producto deja de aparecer sólo en esa sucursal

  @BDD-SC-111
  Scenario: Conservar productos incompletos en administración
    Given existe un producto central sin precio vigente
    When el administrador consulta Productos
    Then el producto aparece marcado como sin precio y no vendible
    And POS no lo ofrece para cobrar

  @BDD-SC-114
  Scenario: Mostrar todos los insumos con existencia real en POS
    Given existen insumos centrales con y sin movimientos en Sucursal Norte
    When el usuario autorizado abre Inventario en POS
    Then aparecen todos los insumos activos del catálogo central
    And la existencia se obtiene del libro de movimientos de Sucursal Norte
    And un insumo sin movimientos aparece con existencia cero

  @BDD-SC-112
  Scenario: Usar la misma sucursal en los módulos administrativos
    Given un administrador selecciona Sucursal Norte
    When abre Compras, Proveedores, Producción, Mermas, Traspasos, Conteos o Modificadores
    Then todos los módulos consultan Sucursal Norte
    And el selector conserva la misma sucursal al volver al POS

  @BDD-SC-113
  Scenario: Abrir administración desde POS sólo con permiso
    Given una cuenta con permiso `admin.manage` opera POS
    Then ve un centro administrativo con accesos a catálogos y operación
    And puede abrir los módulos existentes de Admin
    Given una cuenta Cajero sin `admin.manage`
    Then no ve el centro administrativo
    And la ruta administrativa del POS rechaza el acceso directo
```
