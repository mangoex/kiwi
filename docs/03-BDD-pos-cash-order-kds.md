# BDD - POS, caja y KDS inicial

## BDD-FEAT-021 Caja minima

```gherkin
@PRD-FR-050 @PRD-FR-051 @PRD-FR-057 @cash @phase1
Feature: Turno de caja minimo

  @BDD-SC-028
  Scenario: Abrir y consultar turno de caja
    Given existe la Sucursal Piloto
    When el cajero abre caja con fondo inicial
    Then el sistema crea un turno abierto
    And conserva fecha UTC de apertura
    And evita abrir otro turno simultaneo para la misma caja

  @BDD-SC-029
  Scenario: Cerrar turno sin ventas complejas
    Given existe un turno abierto
    When el cajero cierra el turno
    Then el sistema marca el turno como cerrado
    And conserva fecha UTC de cierre
```

## BDD-FEAT-022 Pedido local minimo

```gherkin
@PRD-FR-020 @PRD-FR-025 @PRD-FR-027 @PRD-FR-030 @orders @phase1
Feature: Pedido local desde POS

  @BDD-SC-030
  Scenario: Crear pedido local con producto del catalogo
    Given existe un turno de caja abierto
    And existe un producto disponible con precio vigente
    When el cajero crea un pedido con ese producto
    Then el sistema crea un pedido aceptado
    And calcula total en centavos
    And asigna folio local
    And registra evento de pedido
```

## BDD-FEAT-023 KDS inicial

```gherkin
@PRD-FR-040 @PRD-FR-041 @PRD-FR-043 @production @phase1
Feature: Tareas KDS desde pedido local

  @BDD-SC-031
  Scenario: Pedido aceptado genera tarea de produccion
    Given existe un pedido aceptado
    When el producto tiene estacion asignada
    Then el sistema crea una tarea KDS pendiente para esa estacion
    And la tarea puede avanzar a en proceso
    And la tarea puede completarse
```

