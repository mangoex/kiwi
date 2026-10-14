# BDD de políticas de abastecimiento y valuación

```gherkin
Feature: Políticas versionadas con cálculo explicable y datos completos
  @PRD-FR-275
  @BDD-SC-685
  Scenario: Demanda completa distingue cero observado de información ausente
    Given consumo confirmado por fecha local con calendario y revisiones coherentes
    When calcula D05_v1 para plazo del proveedor y siete días de revisión
    Then usa historial de 28 días completos y observaciones del día de semana
    And cero observado puede producir necesidad cero sin MOQ ficticio
    But día abierto desconocido o censurado exige revisión sin demanda inventada

  @PRD-FR-275
  @BDD-SC-686
  Scenario: Pendientes y empaques no ocultan un déficit temporal
    Given stock utilizable reservas y recepciones pendientes con ETA y cantidad residual
    When simula demanda por fecha y convierte a presentación vigente
    Then una recepción tardía no oculta desabasto anterior
    And reservas o recepciones confirmadas no se cuentan dos veces
    And consumo desde apertura reduce demanda restante del día al mismo corte de stock
    And una ETA intradía se cuenta desde el siguiente día en la simulación conservadora
    And mínimo es piso del objetivo y máximo se verifica contra stock proyectado a ETA
    And múltiplo MOQ y excedente se muestran para revisión humana
    And máximo o caducidad incompatibles no generan una compra automática

  @PRD-FR-111
  @BDD-SC-687
  Scenario: Valuación separa costo impuesto recuperable y deuda
    Given precio neto 100 impuesto 16 y flete atribuible 10 con perfil fiscal explícito
    When calcula D06_v1 con fracción recuperable uno cero o medio
    Then costo es 110 126 o 118 respectivamente sin alterar obligación documental
    But fracción desconocida o fuera del dominio exige revisión
    And repartir un centavo entre tres líneas conserva exactamente un centavo

  @PRD-FR-111
  @BDD-SC-688
  Scenario: Corregir después de consumo conserva historia y delta
    Given recibo de diez unidades con tres remanentes siete consumidas y delta de valor 10
    When construye un plan autorizado de compensación D03 y D06
    Then propone 3 a inventario y 7 a variación de consumo
    And un delta negativo conserva el signo y suma exacta
    But atribución desconocida o incongruente exige revisión
    And el plan no modifica recibo ledger caja ni pagos originales
```
