# BDD - Compras directas, caja y costo promedio

## BDD-FEAT-038 Recepción directa conciliada

```gherkin
@PRD-FR-052 @PRD-FR-100 @PRD-FR-108 @PRD-FR-110 @purchases @cash
Feature: Confirmar compra directa desde sucursal

  @BDD-SC-079
  Scenario: Compra pagada desde caja
    Given un supervisor tiene turno de caja abierto
    And captura una compra directa con comprobante y presentaciones
    When confirma la compra como pagada desde caja
    Then se crea un retiro con motivo Compra de insumos
    And se generan entradas de inventario
    And compra y retiro quedan vinculados sin duplicar el egreso

  @BDD-SC-080
  Scenario: Reintento idempotente de confirmación
    Given una compra ya fue confirmada con una clave de idempotencia
    When la sucursal reintenta la misma confirmación
    Then obtiene el mismo resultado
    And no duplica retiro, recepción ni costo

  @BDD-SC-081
  Scenario: Cancelar compra confirmada
    Given una compra confirmada generó inventario y retiro
    When un supervisor autorizado la cancela con motivo
    Then conserva los movimientos originales
    And crea contramovimientos de inventario y caja referenciados
```

## BDD-FEAT-039 Costo promedio por recepción

```gherkin
@PRD-FR-089 @PRD-FR-109 @PRD-FR-111 @costing
Feature: Actualizar costo al recibir, no al cotizar

  @BDD-SC-082
  Scenario: Promedio ponderado con existencia positiva
    Given existen 10 kg a costo promedio de 20 pesos
    When se reciben 10 kg a costo de 30 pesos
    Then la existencia queda en 20 kg
    And el costo promedio queda en 25 pesos

  @BDD-SC-083
  Scenario: Rechazar política no definida para existencia negativa
    Given la existencia física calculada es negativa
    When se intenta confirmar una compra
    Then la compra permanece en borrador
    And no crea retiro ni movimientos parciales
    And responde que falta política para costo con inventario negativo
```
