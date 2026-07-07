# BDD - POS solo lectura

## BDD-FEAT-020 POS minimo de catalogo

```gherkin
@PRD-FR-010 @PRD-FR-012 @PRD-FR-014 @PRD-FR-015 @pos @phase0
Feature: POS con catalogo de solo lectura

  @BDD-SC-027
  Scenario: Ver productos disponibles en POS
    Given el catalogo minimo fue migrado
    When el usuario abre `/pos`
    Then ve productos activos del catalogo
    And cada producto muestra precio vigente
    And cada producto muestra disponibilidad de sucursal
    And la vista no permite crear pedidos todavia
```

