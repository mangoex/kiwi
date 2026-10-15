# BDD-FEAT-143 Integración conversacional de WhatsApp vía Asistto Tech Provider

Feature: Integración omnicanal con Asistto para atención de clientes y pedidos WhatsApp en Kiwi

  @BDD-SC-695
  Scenario: Autenticación simétrica e idempotencia del webhook Asistto
    Given la integración de WhatsApp está habilitada con un secreto de webhook configurado
    When Asistto envía un mensaje con encabezado Authorization Bearer válido y message_id único
    Then Kiwi valida la credencial y procesa la solicitud
    And una repetición idéntica con el mismo message_id devuelve la respuesta previa sin duplicar turnos ni comandas
    But una solicitud con token inválido o ausente es rechazada con código 401 sin consultar el dominio

  @BDD-SC-696
  Scenario: Reconocimiento de cliente existente, historial y validación de domicilio
    Given un cliente con teléfono registrado en customer_phones y domicilio habitual en customer_addresses
    When el cliente envía un mensaje desde su WhatsApp
    Then el agente lo saluda por su nombre registrado
    And si solicita servicio a domicilio el agente le ofrece validar su dirección habitual
    And si solicita sugerencias el agente consulta sus favoritos en el historial de order_lines

  @BDD-SC-697
  Scenario: Generación de comanda conversacional con catálogo vigente sin alucinación de precios
    Given una sucursal activa con catálogo de productos y precios oficiales en centavos
    When el cliente pide platillos en lenguaje natural a través de WhatsApp
    Then el agente resuelve exclusivamente productos y modificadores disponibles en esa sucursal
    And si el platillo exige modificadores obligatorios formula una pregunta de clarificación
    And cotiza el total exacto usando los precios de la base de datos sin inventar importes

  @BDD-SC-698
  Scenario: Registro directo de orden en POS con caja cerrada sin exigir cash_shift_id
    Given la sucursal mapeada tiene la caja cerrada y no existe turno de caja activo
    When el cliente confirma su orden a través de WhatsApp
    Then Kiwi persiste el pedido en models.orders con channel WHATSAPP, status PENDING y cash_shift_id nulo
    And asigna un folio correlativo oficial de la sucursal
    And al iniciar el cajero su turno en el POS la orden aparece inmediatamente en el conteo de pedidos pendientes

  @BDD-SC-699
  Scenario: Coexistencia con WhatsApp Business móvil y pausa ante intervención humana
    Given un chat activo atendido por el bot de Kiwi en modo coexistencia
    When el cliente solicita hablar con un humano o el personal responde desde la app móvil de WhatsApp Business
    Then Kiwi transiciona el estado de la conversación a PAUSED durante la ventana de tiempo configurada
    And el bot no interfiere con la conversación humana mientras el estado permanezca pausado
