# BDD - Inventario SaaS inicial

## BDD-FEAT-032 Inventario por movimientos

```gherkin
@PRD-FR-060 @PRD-FR-061 @PRD-FR-062 @PRD-FR-070 @inventory @phase2
Feature: Inventario inicial administrable

  @BDD-SC-049
  Scenario: Registrar saldo inicial de insumo
    Given existe la Sucursal Piloto con almacen formal
    And existe un insumo inventariable con unidad base
    When el encargado registra un saldo inicial con cantidad positiva
    Then el sistema conserva un movimiento OPENING_BALANCE inmutable
    And la existencia teorica se calcula sumando movimientos del almacen
    And el kardex muestra el movimiento con fecha, tipo y cantidad
    And registra auditoria del alta de movimiento

  @BDD-SC-050
  Scenario: Consultar inventario desde Admin
    Given existen movimientos de inventario
    When el administrador abre el modulo Inventario
    Then ve insumos, unidad base, almacen, existencia teorica y ultimo movimiento
    And puede registrar un saldo inicial sin editar saldos directamente
```

## BDD-FEAT-033 Receta simple para producto vendible

```gherkin
@PRD-FR-080 @PRD-FR-082 @PRD-FR-088 @inventory @phase2
Feature: Recetas simples versionadas

  @BDD-SC-051
  Scenario: Asociar componentes base a un producto
    Given existe un producto vendible
    And existen insumos inventariables
    When se consulta la receta vigente
    Then el sistema muestra la version de receta
    And muestra los componentes con cantidades exactas
    And no calcula consumo destructivo en esta etapa

  @BDD-SC-052
  Scenario: Reservar inventario al aceptar pedido
    Given existe un producto vendible con receta vigente
    And existe inventario disponible para sus componentes
    When el cajero crea un pedido con ese producto
    Then el sistema registra movimientos SALE_RESERVATION por componente
    And la existencia teorica disponible disminuye desde el ledger
    And los movimientos quedan vinculados al pedido

  @BDD-SC-053
  Scenario: Convertir reserva en consumo al completar produccion
    Given un pedido aceptado tiene inventario reservado
    When cocina completa la tarea de produccion
    Then el sistema registra RESERVATION_RELEASE por componente
    And registra SALE_CONSUMPTION por componente
    And la existencia teorica no se descuenta dos veces
    And los movimientos quedan vinculados a la tarea de produccion
```
