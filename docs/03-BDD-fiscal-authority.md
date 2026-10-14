# BDD - Facturación directa gobernada

## BDD-FEAT-142 FISCAL-001

```gherkin
@PRD-FR-276 @fiscal
Feature: Emitir y recuperar documentos con autorización y evidencia final

  @BDD-SC-679
  Scenario: El permiso fiscal se verifica sobre el recurso
    Given un lector fiscal de A sin permiso de emisión y una factura en B
    When consulta o intenta emitir cancelar o crear recibo fuera de su alcance
    Then recibe una denegación estable antes del proveedor y no obtiene datos sensibles
    And un usuario inactivo o con sólo orders.read tampoco obtiene autoridad fiscal
    And una lista sin branch sólo incluye sucursales autorizadas
    Given un lector con alcance fiscal corporativo
    When consulta detalle o descarga documentos de otra sucursal de su organización
    Then su permiso actual sobre el recurso autoriza lectura sin contexto operativo
    Given una sucursal desactivada con facturas históricas
    When un lector autorizado consulta lista detalle o PDF XML
    Then conserva esa historia sin reactivar sucursal ni adquirir permiso de emisión o recibo
    But actor inactivo permiso retirado recurso ajeno o alcance insuficiente no obtienen historia
    And la portabilidad móvil sobre ramas activas no concede historia de ramas cerradas no asignadas

  @BDD-SC-680
  Scenario: El conjunto completo cumple elegibilidad y configuración
    Given pedidos con pago completo no cancelados del mismo emisor sucursal y moneda
    And configuración habilitada y explícita de ese emisor
    When un actor autorizado solicita emisión con una intención válida
    Then se conservan todos los pedidos y sus importes exactos en el snapshot fiscal
    But un pedido desconocido repetido parcial cancelado ajeno o de otro emisor rechaza todo
    And pagos y compensaciones confirmados concilian exactamente con el total vigente
    But un neto mayor al total requiere revisión antes de emisión recibo o preparación durable
    And el rechazo no altera pedidos pagos correcciones ni genera una intención fiscal
    And configuración ausente apagada o fiscalmente insuficiente no llama al proveedor
    And una configuración antigua sin razón social vinculada no habilita un emisor nuevo
    And cambiar el ambiente exige credencial explícita sin copiar la clave de otro emisor

  @BDD-SC-681
  Scenario: La pérdida de respuesta recupera una intención y documento únicos
    Given el proveedor creó el documento y la respuesta o confirmación local se perdió
    When se recupera la misma intención y clave bajo permisos actuales
    Then se reconcilia el mismo documento externo sin nueva emisión
    And cambiar recursos o payload bajo la misma clave produce conflicto
    And un replay con autoridad revocada no entrega datos ni revive el efecto

  @BDD-SC-682
  Scenario: UUID y estados finales requieren evidencia final
    Given el proveedor responde pending o verifying sin UUID
    When se proyecta el resultado
    Then el documento continúa pendiente y uuid_sat es null
    And un identificador local no se presenta como UUID SAT
    When se solicita cancelar una factura emitida y el proveedor responde pendiente
    Then conserva UUID y documento con cancellation_pending hasta confirmación final
    And un rechazo conserva la emisión y un evento tardío no retrocede un estado final

  @BDD-SC-683
  Scenario: Credenciales y documentos protegidos no se exponen por proyecciones
    Given una configuración con credencial y una respuesta fiscal original protegida
    When se consultan configuración lista detalle errores o auditoría
    Then no incluyen api_key ni payloads crudos ni credenciales en URLs
    And descargar PDF o XML exige autorización actual sobre el documento
    And recibir cabeceras o cuerpo lentamente no renueva el plazo total del proveedor
    And agotar el plazo devuelve un fallo saneado sin reintentar una emisión
    And una respuesta truncada respecto de Content-Length no se devuelve como documento válido
    Given un lector fiscal de sucursal sin permiso de operación POS
    When recupera su contexto con su capacidad fiscal y consulta sus documentos
    Then puede leerlos sin adquirir autoridad de venta caja selección ni operación offline
    Given un configurador fiscal corporativo y dos razones sociales activas
    When guarda una revisión con razón social y versión esperada explícitas
    Then la configuración afecta sólo ese emisor y conserva cifradas las revisiones anteriores
    But una versión obsoleta o identidad fiscal discordante rechaza sin escritura ni proveedor
    And una revisión externa no adopta silenciosamente el borrador ni su clave pendiente
    And recargar la revisión explícitamente descarta la clave pendiente antes de habilitar guardar

  @BDD-SC-684
  Scenario: Workers y rollback preservan intención e historia
    Given dos workers compiten por una intención pendiente con lease de ejecución
    When uno reclama y el otro recupera tras incertidumbre o vencimiento
    Then sólo se confirma evidencia de la misma intención externa
    And no se mantiene un lock de base durante la llamada de red
    When se revierte la aplicación con documentos y comandos registrados
    Then permanecen consulta y recuperación autorizadas y el downgrade destructivo se bloquea
    And la migración no corrige automáticamente estados o UUID históricos
```
