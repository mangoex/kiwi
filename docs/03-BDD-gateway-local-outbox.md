# BDD - Gateway local y outbox SQLite

## BDD-FEAT-028 Outbox local del gateway

```gherkin
@PRD-FR-180 @PRD-FR-182 @PRD-FR-184 @PRD-FR-187 @offline @phase1
Feature: Persistencia local de comandos offline

  @BDD-SC-041
  Scenario: Guardar comando local antes de sincronizar
    Given la sucursal opera mediante gateway local
    And la conexion con la nube puede estar interrumpida
    When el POS envia un comando al gateway
    Then el gateway valida el sobre de comando
    And persiste el comando en SQLite
    And lo deja pendiente en outbox
    And usa la clave idempotente para evitar duplicados locales

  @BDD-SC-042
  Scenario: Marcar comando local como confirmado
    Given existe un comando pendiente en outbox
    When la nube confirma el comando con checkpoint
    Then el gateway marca el comando como confirmado
    And conserva el checkpoint confirmado
    And ya no lo lista como pendiente
```
