# BDD - Bootstrap de datos base

## BDD-FEAT-018 Datos operativos iniciales

```gherkin
@PRD-FR-001 @PRD-FR-002 @PRD-FR-003 @PRD-FR-005 @PRD-FR-007 @platform @phase0
Feature: Bootstrap de organizacion y sucursal

  @BDD-SC-025
  Scenario: Consultar datos base despues de migrar
    Given las migraciones de Postgres fueron ejecutadas
    When el usuario abre Admin
    Then el sistema muestra la organizacion Kiwi Restaurante
    And muestra la Sucursal Piloto
    And muestra el almacen formal de la sucursal
    And conserva un evento de auditoria del bootstrap
```

