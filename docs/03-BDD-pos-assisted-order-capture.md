# BDD - Captura asistida de pedidos en POS

## BDD-FEAT-093 Convertir lenguaje natural en un borrador revisable

```gherkin
@PRD-FR-228 @PRD-NFR-029 @pos @orders @privacy
Feature: El cajero prepara un pedido mediante texto o dictado sin delegar la confirmación

  @BDD-SC-406
  Scenario: Una solicitud inequívoca llena el carrito como borrador
    Given un Cajero con orders.create y la sucursal canónica activa
    And Baguette BBQ está disponible con el comentario Sin cebolla configurado
    When interpreta "Pedido para Miguel Ángel González con teléfono 6672013019, un baguette de BBQ sin cebolla para recoger"
    Then propone Miguel Ángel González, el teléfono normalizado y tipo takeout
    And muestra una línea de Baguette BBQ con Sin cebolla antes de aplicarla
    And aplicar llena el carrito sin crear, cobrar, aceptar ni reservar el pedido

  @BDD-SC-407
  Scenario: Un teléfono con coincidencia única selecciona al cliente
    Given el borrador contiene un teléfono mexicano válido
    When la búsqueda exacta de la sucursal devuelve un solo cliente
    Then el POS lo selecciona y conserva nombre, carrito y tipo de servicio editables

  @BDD-SC-408
  Scenario: Cero o múltiples clientes requieren decisión humana
    Given el borrador contiene un teléfono mexicano válido
    When la búsqueda devuelve cero o más de una coincidencia
    Then el POS no elige una identidad arbitraria
    And permite registrar o seleccionar al cliente mediante el flujo vigente

  @BDD-SC-409
  Scenario: Productos e instrucciones ambiguos fallan cerrados
    Given la frase nombra un producto ambiguo, no disponible o una instrucción no configurada
    When el intérprete resuelve el borrador contra el catálogo efectivo
    Then marca cada elemento no resuelto con explicación en español
    And no inventa product_id, option_id, precio ni sustitución
    And no permite aplicar una línea incompleta silenciosamente

  @BDD-SC-410
  Scenario: Descartar no modifica la venta
    Given un carrito, cliente y tipo de servicio existentes
    When el Cajero abre Captura asistida, escribe una frase y cancela
    Then conserva exactamente el carrito, cliente, modalidad y checkout anteriores

  @BDD-SC-411
  Scenario: El dictado es una mejora progresiva
    Given un navegador con reconocimiento de voz disponible
    When el Cajero inicia y termina el dictado
    Then la transcripción queda visible y editable antes de interpretar
    But si la capacidad no está disponible el POS ofrece captura escrita sin bloquear la venta

  @BDD-SC-412
  Scenario: La primera versión no revela PII a terceros
    Given una frase con nombre y teléfono
    When el POS interpreta y aplica el borrador
    Then el procesamiento ocurre localmente sin proveedor externo
    And el texto, audio y teléfono no se escriben en logs, métricas ni almacenamiento persistente
    And el pedido final sólo se crea por el checkout canónico autorizado e idempotente
```
