# BDD - Platform Shell

## BDD-FEAT-017 Consola inicial de plataforma

```gherkin
@PRD-NFR-009 @PRD-NFR-010 @PRD-NFR-011 @platform @phase0
Feature: Shell operativo inicial

  @BDD-SC-024
  Scenario: Ver la consola inicial desplegada
    Given la API esta desplegada en Easypanel
    And PostgreSQL y Redis estan configurados
    When el usuario abre la raiz publica del servicio
    Then ve la consola inicial de RestaurantOS
    And la consola muestra el estado de Postgres y Redis
    And ofrece accesos a Admin, POS, KDS y documentacion API
```

