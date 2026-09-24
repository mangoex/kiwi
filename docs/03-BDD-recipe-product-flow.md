# BDD - Continuidad de Producto a Receta

## BDD-FEAT-115 RECIPES-UX-001 configuración contextual

```gherkin
@PRD-FR-248 @recipes @admin @r3
Feature: Configurar la receta sin perder el producto seleccionado

  @BDD-SC-538
  Scenario: Abrir la receta del producto seleccionado en el mismo contexto
    Given un usuario con `recipes.manage`, sucursal autorizada y un producto persistido seleccionado
    When abre la pestaña Receta y solicita configurar su composición
    Then Productos monta el editor canónico para ese producto y esa sucursal
    And carga únicamente los insumos autorizados del workspace
    And no navega a una lista donde deba buscar otra vez el producto

  @BDD-SC-539
  Scenario: Guardar un producto nuevo y continuar con su receta
    Given un producto nuevo válido todavía no persistido
    When el usuario elige Guardar y configurar receta
    Then primero confirma el comando idempotente del producto
    And abre Receta sólo con el ID persistido devuelto por el backend
    But si el guardado falla conserva el borrador y no abre el editor

  @BDD-SC-540
  Scenario: Capturar una receta con lenguaje operativo
    Given el editor recibió unidades e insumos canónicos del workspace
    When el usuario filtra un insumo, captura neto, merma porcentual y rendimiento con unidad
    Then puede revisar bruto y costo como estimaciones no autoritativas
    And el PUT envía la merma fraccional exacta, la versión esperada y la misma clave al reintentar
    And Python vuelve a validar y calcular antes de crear una versión

  @BDD-SC-541
  Scenario: Conservar la captura hasta una salida explícita
    Given una receta capturada en el editor contextual
    When el backend confirma el guardado
    Then el editor permanece abierto, muestra éxito persistido y ofrece volver al producto
    When ocurre validación, red, idempotencia o conflicto de versión
    Then conserva rendimiento, unidad e ingredientes sin anunciar éxito ni sobrescribir el baseline
```
