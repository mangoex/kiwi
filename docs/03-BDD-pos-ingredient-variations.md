# BDD - Variaciones de insumos relacionadas con productos

## BDD-FEAT-058 Catálogo reusable de cambios de insumos

```gherkin
@PRD-FR-200 @pos @modifiers @inventory @catalog
Feature: Variaciones de insumos relacionadas con productos

  @BDD-SC-175
  Scenario: Admin crea Aguacate con Con y Sin normalizados
    Given un administrador corporativo con catalog.manage y el insumo Aguacate
    When crea el cambio permitiendo Con y Sin
    Then las etiquetas quedan normalizadas como Con aguacate y Sin aguacate
    And la unidad base del insumo queda visible sin crear una segunda definición canónica

  @BDD-SC-176
  Scenario: Preview expande productos y categorías actuales sin duplicarlos
    Given una selección de dos productos y una categoría con productos activos actuales
    When el administrador solicita preview de Con aguacate
    Then el preview colapsa duplicados e identifica producto, SKU, categoría y compatibilidad
    When confirma sólo los compatibles
    Then persiste exclusivamente los productos activos existentes en ese momento

  @BDD-SC-177
  Scenario: Sin rechaza recetas que no contienen el insumo
    Given una selección que incluye un producto cuya receta efectiva no contiene cebolla
    When el administrador intenta aplicar Sin cebolla
    Then recibe variation_assignment_incompatible con el motivo por producto
    And ninguna asignación ni opción se crea parcialmente

  @BDD-SC-178
  Scenario: Con agrega Decimal y costo promedio al snapshot
    Given una sucursal con costo promedio vigente de aguacate
    When el cajero selecciona Con aguacate con cantidad Decimal configurada
    Then el snapshot, reserva y consumo incluyen esa cantidad exacta
    And el costo teórico usa el costo promedio vigente de la sucursal

  @BDD-SC-179
  Scenario: Con azúcar sin cargo conserva venta y aumenta consumo interno
    Given Con azúcar configurado sin cargo
    When se vende un café con esa acción
    Then el total de venta no cambia
    And consumo y costo teórico incluyen la azúcar configurada

  @BDD-SC-180
  Scenario: Cargo explícito no usa costo promedio como precio
    Given Con aguacate tiene un price_delta_cents explícito
    When se vende una línea con cantidad dos
    Then el backend suma ese cargo por cantidad de línea
    And no deriva el precio del costo promedio contable

  @BDD-SC-181
  Scenario: Con y Sin de una misma variación son exclusivos
    Given el POS muestra Con aguacate y Sin aguacate para un producto
    When el cajero selecciona una acción y después la opuesta
    Then el POS conserva sólo una acción seleccionada
    When un cliente envía ambas opciones manipulando el payload
    Then el backend responde variation_actions_conflict

  @BDD-SC-182
  Scenario: Supervisor modifica disponibilidad por acción y sucursal
    Given dos sucursales con Con y Sin aguacate heredados
    When el Supervisor de una sucursal marca Con como No disponible
    Then Sin permanece disponible en esa sucursal
    And la otra sucursal conserva ambas acciones heredadas

  @BDD-SC-183
  Scenario: Archivar o desvincular conserva pedidos históricos
    Given un pedido previo con cambio de insumo, snapshot, costo y kitchen_text
    When el administrador archiva o desvincula la relación
    Then las ventas nuevas no reciben la opción
    And el pedido previo conserva su snapshot, costo, texto KDS e impresión

  @BDD-SC-184
  Scenario: Catálogo muestra y gestiona relaciones según permiso
    Given un administrador, un Supervisor y un Cajero autenticados
    When el administrador abre un cambio de insumo
    Then ve productos relacionados y puede agregar, editar o desvincular relaciones
    And el Supervisor sólo gestiona disponibilidad por acción en su sucursal
    And el Cajero no puede abrir ninguna ruta administrativa
```
