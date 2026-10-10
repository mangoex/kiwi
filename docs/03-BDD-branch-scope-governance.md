# BDD - Alcance corporativo y contexto seguro de sucursal

## BDD-FEAT-133 Configuración heredable y movilidad POS gobernada

```gherkin
@PRD-NFR-031 @admin @pos @branch-scope
Feature: La configuración parte de todas las sucursales y la operación cambia de contexto sin mezclar datos

  @PRD-FR-266
  @BDD-SC-630
  Scenario: Admin abre configuración en Todas las sucursales
    Given un actor con permiso corporativo para configurar el módulo solicitado
    When abre Insumos, Proveedores, Presentaciones, Recetas, Productos o Precios
    Then configuration_scope es organization con branch_id nulo
    And el selector muestra Todas las sucursales
    And active_branch, la primera sucursal y localStorage no sustituyen ese alcance

  @PRD-FR-266
  @BDD-SC-631
  Scenario: Seleccionar una sucursal exige confirmación y conserva una señal persistente
    Given Admin está en alcance Todas las sucursales
    When selecciona la sucursal Centro
    Then un diálogo informa que los cambios serán sólo para Centro
    And Cancelar mantiene alcance organization
    When confirma Continuar
    Then la pantalla muestra Sólo Centro durante toda la edición
    And cada escritura envía kind branch y el branch_id confirmado

  @PRD-FR-266
  @BDD-SC-632
  Scenario: Un módulo sin excepción local falla cerrado
    Given el usuario confirmó alcance de una sucursal
    And el módulo todavía no tiene contrato de excepción local
    When intenta guardar un valor heredado como si fuera local
    Then la acción queda deshabilitada o la API responde configuration_scope_unsupported
    And no se clona ni modifica la definición corporativa

  @PRD-FR-266
  @BDD-SC-633
  Scenario: Una sucursal nueva hereda la configuración corporativa
    Given existe configuración corporativa vigente sin excepción local
    When se crea una nueva sucursal activa
    Then sus valores efectivos provienen de la configuración corporativa
    And no se crean copias de productos, insumos, proveedores o presentaciones

  @PRD-FR-267
  @BDD-SC-634
  Scenario: Cajero Cajero jefe y Líder permanecen en una sola sucursal
    Given un Cajero Cajero jefe o Líder con pos.operate y sin pos.branch.select
    When inicia sesión con una única asignación válida
    Then active_branch es su sucursal asignada
    And no ve un selector de sucursal
    When manipula URL o almacenamiento local para solicitar otra sucursal
    Then el servidor rechaza la solicitud y conserva la sucursal canónica
    And GET /auth/session con branch_id no cambia el contexto

  @PRD-FR-267
  @BDD-SC-635
  Scenario: Supervisor Administrador y Dueño seleccionan una sucursal autorizada
    Given un actor con pos.branch.select y acceso persistido a dos sucursales activas
    When selecciona la segunda sucursal y no tiene bloqueadores operativos
    Then el servidor confirma el mismo target como active_branch
    And entrega un workspace context opaco ligado al actor sucursal y versión
    And recalcula capacidades para esa sucursal
    And la selección temporal no cambia user_roles ni su sucursal base

  @PRD-FR-267
  @BDD-SC-636
  Scenario: Destino no autorizado o respuesta obsoleta no cambia el contexto
    Given el actor trabaja en la sucursal A
    When solicita una sucursal B no autorizada o llega tarde una respuesta de un intento anterior
    Then la selección se rechaza con código estable
    And active_branch continúa siendo A
    And ningún módulo ejecuta comandos con B ni restaura un contexto obsoleto
    When otra pestaña intenta operar con el workspace context supersedido de A
    Then el backend rechaza la operación aunque el payload declare una sucursal autorizada
    When la selección A hacia B sí confirmó pero su respuesta se perdió
    Then un replay autenticado con la misma clave recupera B y rota un secreto nuevo si B sigue vigente
    And una recarga puede reemitir el contexto vigente sin persistir ni revelar el secreto anterior
    And si cambió versión permiso o contexto el replay no revive B
    When dos reemisiones responden fuera de orden
    Then el cliente conserva sólo el secreto con secret_version mayor y descarta la respuesta tardía

  @PRD-FR-267
  @BDD-SC-637
  Scenario: Estado operativo crítico bloquea el cambio de sucursal
    Given un actor con turno OPEN o CLOSING, comando incierto, grant offline o reconciliación pendiente
    When solicita cambiar de sucursal
    Then recibe 409 con la razón estable correspondiente
    And no se confirma ni publica la nueva sucursal
    And la operación pendiente permanece recuperable en la sucursal original

  @PRD-FR-267
  @BDD-SC-638
  Scenario: El cambio confirmado no mezcla captura ni dispositivo
    Given un actor sin bloqueadores tiene un borrador aislado en la sucursal A
    When confirma cambiar a la sucursal B
    Then consultas y formularios de A se cancelan o desmontan
    And caja, gateway, grant, carrito y borrador de A no aparecen en B
    And al volver a A el borrador sólo se recupera con el mismo usuario sucursal y caja

  @PRD-FR-267
  @BDD-SC-639
  Scenario: Offline permanece fijado al bundle firmado
    Given el POS opera sin conexión mediante un bundle firmado para la sucursal A
    When un actor intenta seleccionar la sucursal B
    Then el selector no está disponible y active_branch permanece A
    And ningún comando local se acepta con branch_id B
    And emitir una concesión y seleccionar sucursal no pueden confirmar concurrentemente

  @PRD-FR-268
  @BDD-SC-640
  Scenario: Supervisor reasigna un Cajero sin actividad pendiente
    Given un Supervisor con staff.branch.reassign autorizado en origen y destino
    And un Cajero activo en la sucursal A sin turno ni grant vigente
    When envía una reasignación idempotente hacia la sucursal B con versión y motivo válidos
    Then todas las asignaciones operativas branch-scoped del Cajero cambian atómicamente a B
    And aumenta authorization_version
    And la auditoría registra actor objetivo origen destino versiones y resultado

  @PRD-FR-268
  @BDD-SC-641
  Scenario: Reasignación con estado crítico falla sin escritura parcial
    Given un Cajero o Cajero jefe tiene turno abierto, comando incierto o concesión offline vigente
    When Supervisor Administrador o Dueño intenta reasignarlo
    Then la API rechaza con un código estable
    And ninguna asignación ni authorization_version cambia
    And la denegación queda auditada sin credenciales ni razón libre
    And un grant legacy no registrado mantiene la función deshabilitada hasta expirar o invalidarse

  @PRD-FR-268
  @BDD-SC-642
  Scenario: Reasignación concurrente e idempotencia conservan un único resultado
    Given dos solicitudes observan la misma versión del usuario
    When compiten por reasignarlo a destinos distintos
    Then sólo una confirma bajo lock y la otra recibe version_conflict
    And repetir la clave ganadora con el mismo payload devuelve el mismo resultado
    And reutilizarla con otro payload devuelve idempotency_conflict

  @PRD-FR-268
  @BDD-SC-643
  Scenario: Reasignar no reescribe historia
    Given el Cajero tiene pedidos pagos movimientos cortes inventario y snapshots en la sucursal A
    When se confirma su reasignación a B
    Then cada registro histórico conserva branch_id A y sus vínculos originales
    And sólo las operaciones nuevas autorizadas se crean en B

  @PRD-FR-266
  @BDD-SC-644
  Scenario: El selector mantiene separación y accesibilidad
    Given Admin se muestra a 1440x900 o 1024x768
    When el usuario navega por teclado al selector de alcance
    Then existe separación visible respecto del borde superior y del contenido
    And foco etiqueta estado y diálogo son perceptibles sin solapamiento
    And Escape o Cancelar cierran la confirmación sin cambiar el alcance

  @PRD-FR-267
  @BDD-SC-645
  Scenario: Desactivar movilidad drena estados antes de volver al contexto base
    Given un actor trabaja fuera de su sucursal base con turno abierto o comando incierto
    When operaciones inicia el rollback de BRANCH_SCOPE_V2
    Then nuevas selecciones y reasignaciones quedan deshabilitadas
    And el contexto cambia a recovery_only y sólo conserva autoridad para recuperar y cerrar su estado pendiente
    And rechaza iniciar ventas pedidos pagos compras recepciones movimientos o turnos nuevos
    And el sistema no vuelve al contexto fijo hasta que contextos turnos comandos leases y reconciliaciones lleguen a cero
    And si el drenado no concluye se aplica corrección hacia adelante sin borrar historia
```
