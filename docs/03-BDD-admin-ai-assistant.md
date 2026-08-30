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
