# BDD — alcance de comentarios por producto

## BDD-FEAT-127 Productos visibles y editables por comentario

```gherkin
@PRD-FR-261 @comments @catalog @admin @r2
Feature: Revisar y ajustar los productos que reciben cada comentario

  @BDD-SC-586
  Scenario: Seleccionar productos individuales dentro de una subcategoría
    Given un Administrador con catalog.manage y una subcategoría con productos activos
    When despliega la subcategoría en el alta masiva de comentarios
    Then ve el nombre y SKU de cada producto activo
    And la subcategoría comunica estado vacío, parcial o completo según sus productos seleccionados
    When desmarca uno o más productos y solicita la vista previa
    Then el resumen y el preview usan exactamente los product_ids todavía seleccionados
    And cualquier cambio posterior de subcategoría o producto invalida ese preview

  @BDD-SC-587
  Scenario: Inspeccionar y reemplazar el alcance de un comentario vigente
    Given un comentario activo relacionado con productos de una o más subcategorías
    When el Administrador despliega su tarjeta en el catálogo vigente
    Then ve los productos relacionados con nombre y SKU agrupados por subcategoría
    When agrega y retira productos y confirma el impacto mostrado
    Then el sistema reemplaza el conjunto completo por los productos activos confirmados
    And devuelve el alcance persistido y registra order_comment.products_replaced
    And pedidos y snapshots históricos permanecen sin cambios

  @BDD-SC-588
  Scenario: El alta masiva no desvincula relaciones existentes
    Given un comentario existente relacionado previamente con dos productos
    When el Administrador lo incluye en un alta masiva dirigida sólo a uno de ellos
    Then el sistema crea o reactiva las relaciones incluidas sin retirar la relación anterior
    And la interfaz explica que las desvinculaciones se realizan en el editor individual

  @BDD-SC-589
  Scenario: Rechazar un alcance vacío o inválido sin perder la edición
    Given el Administrador abrió el editor de productos de un comentario
    When intenta guardar sin productos o con un producto inactivo, inexistente o de otra organización
    Then el backend rechaza el comando sin mutación parcial
    And la interfaz conserva la selección y muestra un error accionable
    And un error al recargar comentarios no convierte el catálogo de productos en un estado vacío

  @BDD-SC-590
  Scenario: Retirar rápidamente un producto desde el comentario desplegado
    Given un comentario relacionado con más de un producto activo
    When el Administrador pasa el cursor, enfoca o toca la X de uno de sus chips de producto
    Then el sistema reemplaza el alcance con todos los product_ids vigentes excepto el elegido
    And el chip desaparece únicamente después de confirmar la persistencia
    And la tarjeta anuncia el producto retirado o conserva el chip y muestra el error
    And la X del último producto permanece visible pero deshabilitada
```
