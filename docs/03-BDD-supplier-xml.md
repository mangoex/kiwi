# BDD de la frontera XML de proveedor

```gherkin
@PRD-FR-102 @PRD-FR-107
Feature: Extracción XML acotada antes de validación fiscal
  @BDD-SC-689
  Scenario: Un XML no confiable no activa entidades ni devuelve resultados parciales
    Given bytes XML originales de proveedor sin autorización de efectos contables
    When la frontera sintáctica recibe DTD entidades PI compresión o estructura excesiva
    Then rechaza con un código estable sin payload ni acceso a red o archivos
    And motor incompatible exige revisión sin fallback
    But XML benigno dentro de límites produce un árbol para validación posterior
    And el resultado no acredita validez fiscal ni recibe stock ni genera deuda

  @BDD-SC-690
  Scenario: Captura identidad declarada sin atribuir validación fiscal
    Given CFDI 4.0 con Timbre 1.1 y receptor explícito de un consumidor autorizado
    When captura identidad declarada y hash de bytes originales
    Then entrega DTO congelado y fiscal_validation unverified
    And UUID equivalente se normaliza sin alterar el hash original
    But receptor ajeno versión incompatible o identidad ambigua rechaza sin exponer RFC
```
