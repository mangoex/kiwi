# BDD-FEAT-134 Integración gobernada de GrokBot con agentes Kiwi

Feature: Conectar un orquestador con cuatro identidades técnicas sin entregar autoridad directa sobre Kiwi

  @BDD-SC-663
  Scenario: El scaffold permanece inaccesible mientras el feature flag global está apagado
    Given los flags GrokBot de API y Admin conservan su valor default false
    When un usuario abre Integraciones o un cliente intenta invocar Agent Tools
    Then el Admin no ofrece la tarjeta GrokBot
    And la API no registra las rutas externas
    And ninguna configuración persistida puede activar el scaffold por sí sola

  @BDD-SC-662
  Scenario: Un solo Administrador Kiwi coordina especialistas sin credencial maestra
    Given el usuario conversa únicamente con el bot Administrador Kiwi
    When solicita una tarea de catálogo, cocina, inventarios o compras
    Then GrokBot delega la herramienta al especialista privado correspondiente
    And Kiwi autentica y audita la llamada con la identidad técnica de ese especialista
    And el orquestador no puede afirmar otro perfil ni ampliar capacidades o sucursales en el cuerpo

  @BDD-SC-647
  Scenario: Configurar el conector no habilita identidades automáticamente
    Given GrokBot está deshabilitado y no existen identidades activas
    When un Administrador corporativo guarda URL, callback y referencias de secreto válidas
    Then el Hub conserva la configuración y permite probar conectividad
    And cada identidad permanece deshabilitada hasta una activación explícita
    And ningún secreto persistido vuelve a mostrarse

  @BDD-SC-648
  Scenario: Cada bot recibe una identidad y capacidades independientes
    Given existen los perfiles Administrador, Cocinero, Inventarios y Compras
    When se activa cada identidad con sucursales y capacidades permitidas
    Then Kiwi emite credenciales diferentes y rotatorias para cada una
    And una identidad no puede usar capacidades ni sucursales de otra
    And una edición basada en una authorization_version obsoleta falla sin revertir cambios recientes

  @BDD-SC-649
  Scenario: La autenticación de servicio falla cerrada
    Given una llamada usa token vencido, integración pausada o credencial de dispositivo o usuario
    When intenta acceder a Agent Tools
    Then Kiwi responde con un error estable sin consultar datos de dominio
    And no acepta X-Actor-User-Id como autenticación

  @BDD-SC-650
  Scenario: Las lecturas respetan capacidad y sucursal
    Given el bot de Inventarios sólo está autorizado para la sucursal Centro
    When consulta insumos y existencia resumida de Centro
    Then obtiene una proyección paginada y minimizada de Centro
    And cada existencia incluye min_quantity y max_quantity exactos del almacén de Centro
    And unit_id es la unidad base compartida por existencia y umbrales
    And un umbral configurado en cero se distingue de null cuando no existe configuración
    And los insumos sin stock o sin umbral permanecen en el listado sin duplicados entre páginas
    And la consulta no modifica configuración, existencias, costos ni movimientos
    But una consulta a otra sucursal o a pagos, caja, clientes o personal falla cerrada

  @BDD-SC-666
  Scenario: Inventarios consulta movimientos sin recibir autoridad de ajuste
    Given el bot de Inventarios sólo está autorizado para la sucursal Centro
    And existen movimientos de Centro y de otra sucursal dentro del periodo solicitado
    When consulta los movimientos de Centro para un periodo UTC de hasta treinta y un días
    Then recibe una página ordenada del movimiento más reciente al más antiguo
    And cada fila contiene sólo IDs operativos, tipo, cantidad, unidad, fecha efectiva y estado
    And no recibe costos, referencias, motivos, notas, actores, secretos ni movimientos de otra sucursal
    But un periodo inválido, un cursor alterado, otra sucursal o una identidad distinta de Inventarios falla cerrado
    And Agent Tools no ofrece comandos para crear, ajustar, revertir o confirmar movimientos

  @BDD-SC-651
  Scenario: El bot Cocinero propone una versión de receta sin activarla
    Given el bot Cocinero puede leer recetas y proponer en Centro
    When envía componentes, unidades, rendimiento y versión esperada válidos
    Then Kiwi crea una propuesta READY_FOR_REVIEW con origen GROKBOT
    And la receta activa y el inventario permanecen intactos
    And sólo un humano con permiso canónico puede revisarla y aplicarla

  @BDD-SC-652
  Scenario: El bot de Inventarios propone un insumo sin crear movimientos
    Given el bot de Inventarios tiene capacidad corporativa explícita para proponer insumos
    When propone un insumo con SKU, unidad y datos allowlist válidos
    Then Kiwi crea una propuesta revisable de alta de insumo
    And no crea existencia, saldo inicial, ajuste, conteo ni movimiento

  @BDD-SC-661
  Scenario: Un bot limitado a sucursal no crea catálogos corporativos
    Given el bot Administrador o de Inventarios sólo está autorizado para Centro
    When intenta proponer un producto o insumo con alcance corporativo o de sucursal
    Then Kiwi responde agent_capability_denied
    And no usa una sucursal fija por omisión ni crea disponibilidad parcial

  @BDD-SC-653
  Scenario: El bot de Compras crea un borrador que un humano debe confirmar
    Given el bot de Compras puede leer proveedores y necesidades de Centro
    When envía una compra con proveedor, presentación, cantidad y costo válidos
    Then Kiwi crea una compra DRAFT mediante el servicio canónico
    And no cambia existencias, costo promedio, cuenta por pagar ni caja
    And Agent Tools no ofrece comandos para confirmar, recibir, pagar o cancelar la compra

  @BDD-SC-667
  Scenario: Compras consulta precios vigentes e historial confirmado sin autoridad financiera
    Given una persona habilitó agent.purchases.read para Compras y sólo autorizó Centro
    And existen presentaciones vigentes y compras confirmadas de Centro y de otra sucursal
    When consulta presentaciones de Centro y un periodo UTC de hasta treinta y un días
    Then recibe precios, costos y líneas económicas como decimales exactos sólo de Centro
    And la moneda del historial se identifica como configuración vigente del proveedor y no snapshot histórico
    And cada nombre indica si procede del snapshot de compra o del catálogo vigente
    And no recibe folio, método de pago, caja, evidencia, notas, actores, idempotencia ni datos de otra sucursal
    But otra identidad, una branch no autorizada, un periodo inválido o un cursor alterado falla cerrado
    And las consultas no modifican compras, costos, existencias, movimientos ni caja

  @BDD-SC-668
  Scenario: Administrador consulta cortes finalizados con permiso financiero explícito
    Given una persona habilitó agent.cash_cuts.read para Administrador y sólo autorizó Centro
    And existen cortes finalizados de Centro y de otra sucursal dentro del periodo solicitado
    When consulta los cortes de Centro para un periodo UTC de hasta treinta y un días
    Then recibe importes en centavos y la compensación más reciente como valor efectivo
    And cada fila identifica si fue compensada sin reescribir el corte original
    And no recibe cajero, creadores, autorizadores, operaciones, motivos, evidencia ni texto libre
    But otra identidad, la capacidad deshabilitada, otra sucursal, periodo inválido o cursor alterado falla cerrado
    And habilitar o retirar el permiso conserva el actor y el delta de capacidades en auditoría
    And Agent Tools no ofrece comandos para abrir, contar, finalizar, reabrir, compensar o mover caja

  @BDD-SC-808
  Scenario: Administrador consulta gastos operativos por concepto con permiso explícito
    Given una persona habilitó agent.operating_expenses.read para Administrador y sólo autorizó Centro
    And el catálogo de gastos no clasifica fijo ni variable
    And existen gastos confirmados de Centro dentro y fuera del día local America/Mazatlan
    When consulta el día local convertido a un periodo UTC de hasta treinta y un días
    Then recibe cada concepto del snapshot con importes enteros en centavos y el neto de confirmaciones y cancelaciones
    And no recibe folio, notas, evidencia, actores ni gastos de otra sucursal
    But la capacidad apagada, otra identidad, otra sucursal o un periodo inválido falla cerrado
    And la consulta no modifica documentos de gasto

  @BDD-SC-809
  Scenario: Administrador consulta ventas por método sin alterar el neto de ventas
    Given una persona habilitó agent.payment_methods.read y agent.sales.read sólo para Administrador
    And hay ventas confirmadas en efectivo, tarjeta, transferencia y un pedido externo dentro del día local
    And una entrega incluye el envío en el neto y una corrección posterior no reescribe el snapshot
    When consulta el mismo periodo UTC en ventas y en métodos de pago
    Then el neto por moneda coincide, incluye IVA y envío, y el pedido externo cuenta como venta
    And la corrección queda separada y no se resta del neto por método
    But agent.sales.read por sí solo, otra sucursal o un periodo mayor a treinta y un días falla cerrado
    And la consulta no modifica pagos ni snapshots

  @BDD-SC-810
  Scenario: Administrador consulta la conciliación diaria sin datos personales salvo permiso aparte
    Given una persona habilitó agent.cash_reconciliation.read para Administrador y la zona de Centro es America/Mazatlan
    And la conciliación v2 tiene tarjeta, transferencia, depósito, proveedor, gasto fijo, retiro, crédito, reembolso y cancelación
    And no existe un ledger distinto de producción o panadería
    When consulta el día local del turno y el día local siguiente
    Then el saldo del turno abierto y la actividad del día civil se devuelven en centavos, con la diferencia sólo si el arqueo está contado
    And sin agent.cash_personal_data.read no recibe nombres, teléfonos ni quién recibió el retiro
    And con esa segunda capacidad, apagada por defecto, recibe ticket, nombre, teléfono y receptor
    And la producción o panadería se informa como no registrada
    But un periodo de más de treinta y un días, otra sucursal o la capacidad apagada falla cerrado
    And Agent Tools no ofrece comandos para abrir, contar, compensar o mover caja

  @BDD-SC-654
  Scenario: Un comando repetido es idempotente y un conflicto no escribe
    Given una propuesta fue aceptada con una Idempotency-Key y un cuerpo canónico
    When la identidad autorizada repite exactamente el comando
    Then recibe el mismo operation_id y referencia canónica
    But si reutiliza la clave con otro cuerpo recibe idempotency_conflict
    And no se crea una segunda propuesta o compra

  @BDD-SC-655
  Scenario: Revocar autoridad también protege la recuperación idempotente
    Given un comando se persistió y después se revocó la identidad o su sucursal
    When intenta consultar o repetir el comando con la misma clave
    Then Kiwi revalida la autoridad y responde agent_disabled o agent_branch_denied
    And no revela el resultado persistido ni reactiva la operación

  @BDD-SC-656
  Scenario: Los callbacks notifican estado sin ejecutar dominio ni filtrar datos
    Given una propuesta cambia de estado por revisión humana y existe un callback HTTPS permitido
    When Kiwi envía el callback a GrokBot
    Then firma key ID, timestamp, event ID y cuerpo canónico con el secreto de callback
    And revalida que DNS resuelva al mismo destino público permitido sin seguir redirects
    And el cuerpo sólo contiene estado, tipo, operation_id opaco y código estable
    And un reintento conserva el event ID y no vuelve a aplicar la acción
    And logs y callback excluyen secretos, tokens, PII, texto libre y payload completo

  @BDD-SC-657
  Scenario: Un fallo incierto se recupera por estado y no por éxito simulado
    Given el cliente pierde la respuesta después de enviar una propuesta o borrador
    When consulta operation_id o repite exactamente con la misma Idempotency-Key
    Then Kiwi devuelve el estado autoritativo persistido
    And si la dependencia está indisponible conserva un estado no terminal consultable
    And GrokBot nunca presenta la operación como aplicada sin confirmación canónica

  @BDD-SC-659
  Scenario: El rollback drena operaciones sin reabrir autoridad
    Given existen operaciones aceptadas y se inicia el rollback del conector
    When la integración entra en Drenando
    Then rechaza tokens y comandos nuevos
    And sólo permite a tokens vigentes consultar sus operaciones preexistentes
    And el worker puede entregar callbacks pendientes sin aplicar dominio
    But al terminar el drenado pasa a Pausado y toda consulta externa falla cerrada

  @BDD-SC-660
  Scenario: Un callback con destino inseguro falla antes de abrir conexión
    Given la URL o su resolución DNS apunta a loopback, red privada, link-local, metadata
    And el destino es un host interno o el propio servicio
    When se configura o intenta entregar el callback
    Then Kiwi rechaza el destino con un código estable
    And no sigue redirects ni abre una conexión al destino prohibido

  @BDD-SC-658
  Scenario: El conector conserva evidencia externa con acceso restringido
    Given la política de auditoría exige conservar un payload de herramienta externo
    When Kiwi registra la solicitud
    Then almacena el original cifrado con retención y acceso restringido
    And publica sólo un resumen operativo redactado
    And no conserva transcript de WhatsApp ni texto libre en logs o métricas

  @BDD-SC-664
  Scenario: El Administrador consulta ventas confirmadas sin acceder a caja ni clientes
    Given la identidad Administrador está autorizada únicamente para Centro
    And existen snapshots inmutables de ventas confirmadas y correcciones posteriores
    When consulta un periodo UTC válido de hasta treinta y un días
    Then Kiwi devuelve conteos, importes por moneda, servicios y productos agregados de Centro
    And limita productos por moneda, consolida renombres por product_id y agrega en SQL sin cargar el periodo completo
    And presenta las correcciones como un agregado separado del snapshot original
    But no devuelve folio, pedido, pago, caja, cliente, personal ni datos de otra sucursal
    And Cocinero, Inventarios y Compras reciben agent_capability_denied para la misma consulta

  @BDD-SC-665
  Scenario: La frontera externa limita abuso sin registrar credenciales
    Given Agent Tools está habilitado con Redis y un secreto HMAC dedicado
    When una identidad rebasa el límite configurado
    Then Kiwi responde rate_limited y Retry-After sin consultar dominio
    And sus rechazos posteriores no consumen el límite global compartido
    But si Redis está indisponible responde dependency_unavailable y falla cerrado
    And ninguna clave, log o métrica conserva el token o client secret original
    And autenticación inválida se limita por señal de red separada sin consumir el bucket de la identidad
    And cada solicitud aceptada o denegada deja una señal redactada con operación y sucursal válida
