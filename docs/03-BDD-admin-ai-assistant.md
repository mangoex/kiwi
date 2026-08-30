# AIA-001 — comportamiento del asistente administrativo

Feature: Asistente de conocimiento y configuración exclusivo del backoffice

  @BDD-SC-431
  Scenario: El icono de persona abre el asistente sin sustituir el perfil
    Given un Administrador autenticado en Admin
    When activa el icono de persona del encabezado
    Then abre el diálogo del asistente de configuración
    And el avatar conserva la edición de perfil

  @BDD-SC-432
  Scenario: Una consulta cita reglas canónicas sin escribir configuración
    Given una consulta sobre flujo u operación
    When el asistente responde
    Then devuelve respuesta y fuentes allowlist
    And no crea ni aplica una acción de dominio

  @BDD-SC-433
  Scenario: El proveedor apagado falla cerrado para propuestas
    Given que el flag Admin o la clave del proveedor están ausentes
    When el usuario solicita configurar
    Then recibe orientación local con warning explícito
    And la respuesta queda DRAFT sin change set aplicable

  @BDD-SC-434
  Scenario: Una salida válida crea una propuesta revisable de una acción
    Given un proveedor habilitado que devuelve JSON estricto
    And todos los valores materiales tienen evidencia en la solicitud
    And los IDs y fuentes pertenecen al contexto autorizado
    When Python valida la salida
    Then persiste READY_FOR_REVIEW con actual, propuesto, ruta, fingerprint y expiración
    And todavía no cambia producto, insumo, modificador o receta

  @BDD-SC-435
  Scenario: No se aceptan invenciones ni referencias ajenas
    Given una salida con precio, cantidad o SKU sin evidencia, una fuente desconocida o un ID ajeno
    When Python la valida
    Then rechaza la salida con error explícito
    And no persiste una propuesta aplicable ni configuración

  @BDD-SC-436
  Scenario: La revisión ocurre sobre la configuración correspondiente
    Given una propuesta READY_FOR_REVIEW
    When el usuario elige Revisar configuración
    Then navega al módulo de producto, insumo, modificador o receta
    And muestra actual vs propuesto, fuentes, faltantes y advertencias

  @BDD-SC-437
  Scenario: Aceptar aplica una sola acción mediante autoridad canónica
    Given una propuesta vigente y sin cambios de contexto
    And un revisor con el permiso de dominio requerido
    When acepta con una clave idempotente
    Then el backend llama el servicio canónico de la acción
    And persiste APPLIED, resultado y auditoría sin prompt
    And un replay idéntico devuelve el mismo resultado

  @BDD-SC-438
  Scenario: Rechazar o expirar conserva configuración intacta
    Given una propuesta pendiente
    When el revisor la rechaza o vence su TTL
    Then queda REJECTED o EXPIRED
    And ninguna configuración cambia

  @BDD-SC-439
  Scenario: Permiso ausente o catálogo obsoleto bloquean la aceptación
    Given una propuesta READY_FOR_REVIEW
    When el revisor carece del permiso requerido o el fingerprint ya cambió
    Then la aceptación falla cerrada
    And no aplica la acción de dominio

  @BDD-SC-440
  Scenario: El contexto externo excluye superficies operativas y personales
    Given una solicitud al proveedor
    When se construye su contexto
    Then incluye sólo reglas y catálogo allowlist mínimo
    And excluye clientes, personal, pedidos, pagos, caja, compras, producción, existencias y auditoría

  @BDD-SC-446
  Scenario: Una consulta ambigua de precio no mezcla productos, compras y costo promedio
    Given un Administrador pregunta “¿Qué insumos no tienen precio?”
    When el asistente clasifica la intención antes de consultar al proveedor
    Then pide elegir entre precio de venta, precio de compra y costo promedio por sucursal
    And la respuesta queda DRAFT sin invocar al proveedor ni crear una propuesta aplicable
    And no presenta productos como insumos ni un identificador interno como nombre

  @BDD-SC-447
  Scenario: Un diagnóstico explícito falla cerrado sin su proyección canónica
    Given un Administrador pide insumos sin precio de compra o sin costo promedio
    And la proyección canónica correspondiente todavía no está habilitada para el asistente
    When el backend clasifica la consulta
    Then explica qué fuente de datos falta y conserva la respuesta DRAFT
    And no invoca al proveedor ni presenta resultados de otra autoridad como equivalentes

  @BDD-SC-448
  Scenario: Diagnosticar insumos sin precio de compra usa el catálogo de compras canónico
    Given una sucursal seleccionada con insumos corporativos y locales dentro de su alcance
    And existen insumos con y sin presentación activa de proveedor habilitado y precio positivo
    When el Administrador pregunta por insumos sin precio de compra
    Then Python devuelve sólo los insumos faltantes con nombre, SKU y unidad
    And respeta proveedor, presentación y habilitación de sucursal sin enviar datos al proveedor de IA
    And revalida purchases.read con la compatibilidad canónica de catalog.manage
    And la respuesta queda DRAFT sin change set
    But sin sucursal pide seleccionarla y nunca agrega insumos exclusivos de otra sucursal

  @BDD-SC-449
  Scenario: Diagnosticar costo promedio exige alcance y permiso de inventario
    Given una sucursal con almacén e insumos con y sin costo confirmado
    When un actor con inventory.read consulta los insumos sin costo promedio
    Then Python devuelve sólo los faltantes para esa sucursal y almacén
    And no expone existencias, importes, proveedor ni movimientos
    But sin sucursal pide seleccionarla y sin inventory.read falla cerrado
    And recuperar o rechazar la respuesta vuelve a exigir inventory.read vigente

  @BDD-SC-450
  Scenario: Revisar un diagnóstico desde una interfaz guiada sin atribuirle autoridad
    Given una respuesta diagnóstica DRAFT con insumos estructurados y acotados
    When el Administrador busca, filtra y selecciona resultados en el asistente
    Then la interfaz muestra consulta completada, revisión en progreso y validación pendiente
    And distingue que no se realizó ningún cambio y conserva visibles las reglas utilizadas
    And permite abrir la configuración canónica para los insumos seleccionados mediante estado efímero
    But no presenta aceptar ni aplicar para un diagnóstico sin change set
    And precio de compra navega a presentaciones mientras costo promedio navega a insumos
