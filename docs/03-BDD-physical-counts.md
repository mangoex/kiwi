# BDD - Conteo físico y conciliación

## BDD-FEAT-045 Fotografía y captura ciega

```gherkin
@PRD-FR-068 @inventory @counts
Feature: Capturar inventario físico

  @BDD-SC-105
  Scenario: Abrir una fotografía sin mover inventario
    Given una sucursal tiene artículos inventariables activos
    When el supervisor abre una sesión de conteo
    Then congela cantidad teórica, costo y valor por artículo
    And queda en estado counting
    And no genera movimientos

  @BDD-SC-106
  Scenario: Captura ciega
    Given una sesión está en counting
    When el supervisor consulta y captura cantidades físicas
    Then la interfaz no muestra existencia teórica ni diferencia
    And cada captura conserva usuario y fecha

  @BDD-SC-107
  Scenario: Enviar conteo incompleto
    Given falta capturar al menos una línea
    When se intenta enviar a revisión
    Then el sistema lo rechaza sin calcular ajustes

@PRD-FR-068 @inventory @reconciliation
Feature: Revisar y autorizar diferencias

  @BDD-SC-108
  Scenario: Ajustar contra ledger vigente
    Given la fotografía registró 10 unidades teóricas
    And se contaron 8 unidades físicas
    And después de abrir ocurrió una salida legítima de 1 unidad
    When se aprueba el conteo
    Then el reporte conserva diferencia de fotografía igual a -2
    And genera COUNT_ADJUSTMENT por -1 contra la existencia vigente
    And no sobrescribe la salida intermedia

  @BDD-SC-109
  Scenario: Aprobar y cerrar idempotentemente
    Given un conteo enviado contiene diferencias positivas y negativas
    When el supervisor lo aprueba con idempotency key
    Then crea un movimiento por cada ajuste no cero una sola vez
    And conserva costo, actor y documento de origen
    When cierra la sesión
    Then el reporte queda inmutable y separado de mermas

  @BDD-SC-580
  Scenario: Abrir por grupos congela el alcance
    Given existen artículos activos en distintos grupos
    When un usuario con inventory.count.capture abre un conteo seleccionando dos grupos
    Then la sesión contiene solamente los artículos activos de esos grupos
    And conserva los grupos y artículos resueltos aunque el catálogo cambie después

  @BDD-SC-581
  Scenario: Cajero captura sin conocer la conciliación
    Given un Cajero tiene inventory.count.capture pero no inventory.count.review
    And existe una sesión en counting para su sucursal
    When consulta, captura y envía el conteo
    Then puede ver productos, unidades, presentaciones y avance
    And nunca recibe fotografía teórica, costos, valores ni diferencias
    And no puede aprobar, cerrar ni cancelar administrativamente

  @BDD-SC-582
  Scenario: Capturar por presentaciones conserva el origen del total
    Given una presentación Frasco rinde 450 gramos
    When el capturista registra 2 frascos y 125 gramos en la misma línea
    Then el backend conserva ambas entradas y sus rendimientos congelados
    And calcula una cantidad física autoritativa de 1025 gramos con Decimal
    And cambiar posteriormente la presentación no altera el conteo

  @BDD-SC-583
  Scenario: Administrador revisa y aprueba el conteo enviado
    Given un Cajero envió un conteo completo
    When un Administrador con inventory.count.review consulta la sesión
    Then ve fotografía, físico, diferencia, costo unitario y diferencia valorizada
    When lo aprueba con inventory.count.approve e idempotency key
    Then los ajustes se calculan contra el ledger vigente una sola vez

  @BDD-SC-584
  Scenario: Guardar un lote de captura es atómico
    Given una sesión contiene varias líneas pendientes
    When una entrada del lote es inválida o pertenece a otra sesión
    Then no se guarda ninguna línea del lote
    And el usuario puede corregirlo sin reconstruir las capturas válidas en su cliente

  @BDD-SC-585
  Scenario: POS sin conexión no simula un conteo confirmado
    Given la caja pierde conectividad antes de abrir o guardar el conteo
    When el Cajero intenta continuar
    Then la interfaz conserva su borrador local de captura cuando sea seguro
    And informa que requiere reconexión para confirmar el guardado o envío
    And no muestra éxito ni altera inventario sin confirmación del servidor
```
