# BDD — POS de Cajero

## BDD-FEAT-121 Operación de recoger y domicilio

@PRD-FR-253 @PRD-FR-254 @pos
Feature: Captura clara conservando contratos
  @BDD-SC-566
  Scenario: Recoger distingue cobro inmediato y al entregar
    Given un Cajero inicia un pedido nuevo
    Then ve Recoger en caja con Cobrar al entregar y Domicilio, sin mesas
    When elige Cobrar ahora para recoger
    Then se conserva el contrato dine-in de cobro inmediato
    And Cobrar al entregar conserva takeout sin pago confirmado
  @BDD-SC-567
  Scenario: Buscar y personalizar desde inicio
    Given el menú tiene productos con opciones y grupos obligatorios
    When busca un producto desde el inicio del catálogo
    Then puede seleccionarlo sin recorrer categorías
    And debe completar las opciones obligatorias
    And puede capturar cantidad y nota por línea sin perder extras ni instrucciones

## BDD-FEAT-122 Espera sin efectos operativos

@PRD-FR-255 @pos @recovery
Feature: Borradores distintos de órdenes aceptadas
  @BDD-SC-568
  Scenario: Navegar y recuperar captura
    Given un carrito con cantidades, notas, complementos y domicilio seleccionado
    When navega a Pedidos y vuelve o recarga el POS
    Then recupera la captura activa en el mismo usuario, sucursal, caja y transporte
    And vuelve a cotizar con Python antes de confirmar
  @BDD-SC-569
  Scenario: Dejar en espera sin enviar
    Given una captura que todavía no se confirmó
    When la deja en espera y empieza otra
    Then recupera el borrador sin crear órdenes, reservas, pagos, tareas ni impresión
    And un contexto distinto no puede recuperarlo
    And cerrar sesión elimina los borradores locales
  @BDD-SC-570
  Scenario: Fallo de almacenamiento o confirmación incierta
    Given el navegador rechaza almacenamiento o hay un checkout sin respuesta definitiva
    When intenta guardar o recuperar como otra venta
    Then se informa el fallo sin afirmar éxito
    And el intento incierto se recupera antes de permitir duplicar la captura

## BDD-FEAT-123 Seguimiento y pago preciso

@PRD-FR-256 @PRD-FR-257 @PRD-FR-258 @payments @security
Feature: Estados independientes y cobro autorizado
  @BDD-SC-571
  Scenario: Datos históricos canónicos de domicilio y personalización
    Given una orden con teléfonos estructurados, domicilio y notas en su snapshot
    When abre su detalle
    Then ve teléfono, dirección, referencias, instrucciones y notas de sus líneas
    And editar el catálogo del cliente no altera esa presentación histórica
    And ACCEPTED con tareas pendientes muestra Cocina pendiente y Pago pendiente separadamente
  @BDD-SC-572
  Scenario: Efectivo recibido suficiente con cálculo Python
    Given un pedido por 19000 centavos
    When captura 200.00 como efectivo recibido
    Then Python devuelve recibido 20000 y cambio 1000
    And un recibido menor, booleano, float, negativo o fracción inválida bloquea confirmar
    And el pago se mantiene por 19000 y reintentar conserva la misma identidad
  @BDD-SC-573
  Scenario: Entrega y cancelación dependen de autoridad y estado
    Given un Cajero sin orders.fulfill ni orders.cancel
    When abre una orden pagada o pendiente
    Then pagar no la marca entregada y no se ofrecen acciones no autorizadas
    And un actor con orders.fulfill sólo ve transiciones vigentes con confirmación física
    And no se añade cancelación hasta verificar concurrencia con pago y cocina
    And recuperar no duplica envío a cocina ni confunde impresión en cola con impresa
    And tareas CANCELLED históricas no bloquean READY cuando todas las activas completan tras enmendar
    And ninguna tarea activa pendiente puede omitirse para habilitar entrega
