# BDD - Sincronizacion minima nube-gateway

## BDD-FEAT-027 Confirmacion idempotente de comando local

```gherkin
@PRD-FR-180 @PRD-FR-184 @PRD-FR-185 @PRD-FR-187 @sync @phase1
Feature: Sincronizar comando local con nube

  @BDD-SC-037
  Scenario: Confirmar comando local pendiente una sola vez
    Given existe un comando local pendiente de sincronizacion
    When el gateway envia el comando a la API central
    Then la nube registra el comando recibido
    And asigna un checkpoint de sucursal
    And devuelve un evento de confirmacion
    And conserva auditoria de la sincronizacion

  @BDD-SC-038
  Scenario: Reintentar comando ya confirmado
    Given la nube ya confirmo un comando con la misma clave idempotente
    When el gateway reintenta el envio del mismo comando
    Then la nube devuelve la confirmacion original
    And no crea un segundo checkpoint
    And no duplica el evento confirmado
```
