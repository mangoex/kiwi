# BDD — POS-CASH-OPS-001 caja, cuentas, corte y perfiles

**Estado:** decisiones `OPEN-011..017` resueltas el 2026-08-10 y conservadas como trazabilidad.
PCO-001 ejecuta la semilla/proyección de permisos de `BDD-SC-270`, la asignación y denegación de
alcance de `BDD-SC-271`, la autoridad persistida/cross-org de `BDD-SC-277`, y la migración SQLite de
`BDD-SC-290`. En `BDD-SC-272..276`, `291` y `293` sólo ejecuta las denegaciones o permisos base que
ya tienen ruta; los flujos de movimientos, corte, conceptos, receta, reportes y reapertura permanecen
definidos/proyectados para sus PCO posteriores. PCO-002 ejecuta `BDD-SC-296`, `BDD-SC-301` y la
precondición de catálogo de `BDD-SC-278`. PCO-003 fue autorizado para completar `BDD-SC-278..280`,
`BDD-SC-294` y los escenarios específicos `BDD-SC-302..305`; no ejecuta offline ni PCO-004+.

## BDD-FEAT-076 Perfiles acumulativos y alcance

```gherkin
@rbac
Feature: Autorizar capacidades acumulativas por permisos persistidos

  @PRD-FR-215
  @BDD-SC-270
  Scenario: La jerarquía concede sólo las capacidades acumuladas
    Given usuarios Cajero, Cajero jefe, Líder, Supervisor, Administrador y Dueño con permisos semilla
    When cada usuario consulta su proyección de capacidades para su sucursal canónica
    Then cada nivel conserva las capacidades de los niveles inferiores
    And ningún nivel inferior recibe una capacidad del nivel superior
    And la respuesta no depende del texto visible del rol

  @PRD-FR-215 @PRD-NFR-020
  @BDD-SC-271
  Scenario: Una sucursal no asignada se deniega por defecto
    Given un Supervisor con asignación branch-scoped `NULL` legacy o asignado únicamente a Sucursal Centro
    When solicita inventario, caja o reporte de Sucursal Norte
    Then el backend responde branch_scope_denied o permission_denied sin datos ni mutación
    And registra authorization.denied con actor, recurso y correlation id
    When un administrador intenta crear una asignación branch-scoped sin sucursal
    Then el backend responde branch_assignment_required sin escritura

  @PRD-FR-215
  @BDD-SC-272
  Scenario: Cajero vende y registra retiro sin manejar caja
    Given un Cajero con turno abierto en su sucursal asignada
    When crea y cobra un pedido y registra un retiro manual válido
    Then las operaciones quedan auditadas y el retiro se incorpora una vez al efectivo esperado
    When intenta abrir/cerrar turno, depositar, comprar, registrar merma o crear corte por usuario
    Then cada comando se rechaza por permiso sin escritura parcial

  @PRD-FR-215
  @BDD-SC-273
  Scenario: Cajero jefe maneja caja y operación pero no acciones de Líder
    Given un Cajero jefe con sucursal y turno autorizados
    When abre o cierra operativamente turno, deposita, enmienda pedido elegible, compra y registra merma
    Then cada acción usa permisos granulares y auditoría append-only
    When intenta cancelar pedido o crear corte por usuario
    Then el backend responde permission_denied

  @PRD-FR-215
  @BDD-SC-274
  Scenario: Líder cancela y corta por usuario sin modificar recetas
    Given un Líder autorizado y un corte con alcance válido
    When cancela un pedido elegible y solicita el corte por usuario
    Then ambas acciones guardan actor, alcance e idempotency key
    When intenta editar una receta
    Then el backend lo deniega

  @PRD-FR-215 @PRD-FR-220
  @BDD-SC-275
  Scenario: Supervisor consulta insumos e inventario y administra receta dentro de alcance
    Given un Supervisor asignado a una sucursal
    When consulta venta por insumos, inventario y reporte de merma y modifica una receta autorizada
    Then sólo recibe datos y efectos de su alcance y cada acción sensible se audita
    And la venta por insumos usa snapshots históricos de receta

  @PRD-FR-215 @PRD-FR-220
  @BDD-SC-276
  Scenario: Administrador consulta reportes de ventas y gastos sólo dentro de alcance asignado
    Given un Administrador con sucursales asignadas
    When consulta reportes de ventas y gastos
    Then el backend agrega únicamente las sucursales autorizadas
    And no concede acceso organizacional total por el nombre Administrador

  @PRD-FR-215
  @BDD-SC-277
  Scenario: Dueño opera consolidado de todas las sucursales
    Given un Dueño con todos los permisos persistidos vigentes de su organización y access.organization.all_branches
    When consulta un reporte consolidado, administra un catálogo corporativo y ejecuta una capacidad especializada autorizada
    Then recibe únicamente datos de la organización y puede consultar todas sus sucursales
    And cada autorización se resuelve en backend sin wildcard enviado por cliente
    When intenta consultar o mutar una segunda organización
    Then recibe branch_scope_denied o permission_denied sin escritura parcial
```

## BDD-FEAT-077 Movimientos y consulta de cuentas

```gherkin
@cash
Feature: Registrar efectivo y revisar cuentas históricas

  @PRD-FR-216
  @BDD-SC-278
  Scenario: Concepto versionado gobierna depósito o retiro
    Given un concepto activo compatible con retiro que requiere referencia
    When un actor autorizado registra un retiro con importe positivo, referencia e idempotency key
    Then se congela el snapshot del concepto y se crea un movimiento append-only
    And un concepto inactivo, tipo incompatible o referencia omitida se rechaza

  @PRD-FR-216 @PRD-NFR-021
  @BDD-SC-279
  Scenario: Efectivo esperado usa pagos y movimientos exactamente una vez
    Given un turno con fondo de 10000, pago cash de 5000, depósito de 1000, retiro manual de 2000 y compra cash de 3000
    When el backend calcula efectivo esperado
    Then devuelve 11000 centavos usando cada cash_movement una sola vez
    And la compra es un WITHDRAWAL source_type PURCHASE y no se resta en otro término
    And un reintento con la misma clave no agrega un segundo movimiento

  @PRD-FR-216 @PRD-NFR-021
  @BDD-SC-280
  Scenario: Corregir un movimiento crea compensación y no borra historia
    Given un retiro confirmado con error de concepto o importe
    When un actor autorizado registra su compensación referenciada
    Then permanecen visibles original, compensación, actores y motivo
    And no se puede editar ni eliminar el retiro original

  @PRD-FR-217
  @BDD-SC-281
  Scenario: Consultar cuentas por filtros y abrir detalle snapshot
    Given cuentas de venta directa y domicilio en varias cajas, turnos y fechas
    When un actor autorizado filtra por turno, día, caja, sucursal y servicio o busca folio/cliente
    Then sólo recibe el conjunto dentro de alcance
    And el detalle muestra líneas, cantidades, productos, pago y snapshots históricos

  @PRD-FR-217
  @BDD-SC-282
  Scenario: Pedido pagado o con producción iniciada no se reabre
    Given un pedido pagado, cerrado o con tarea fuera de PENDING
    When cualquier perfil solicita editarlo o aplicarle reapertura directa
    Then el backend devuelve order_reopen_not_eligible o order_reopen_policy_pending
    And no toca pago, reservas, consumo, corte ni eventos existentes

  @PRD-FR-217
  @BDD-SC-283
  Scenario: Reapertura es sólo una solicitud hasta decisión de Dueño
    Given la política aprobada asigna orders.reopen.request a Cajero jefe o superior
    And existe un pedido consultable y motivo/evidencia válidos
    When el actor crea la solicitud auditada
    Then se crea una solicitud auditable sin cambiar el pedido
    And sólo Dueño puede autorizar/aplicar cuando PCO-005 implemente esas rutas
```

## BDD-FEAT-078 Turnos, monitor y corte por usuario

```gherkin
@cash @reports
Feature: Separar cierre operativo de corte final y monitorear ventas

  @PRD-FR-218
  @BDD-SC-284
  Scenario: Cierre operativo no fabrica un corte final
    Given un turno abierto con operaciones confirmadas
    When un Cajero jefe autorizado lo cierra operativamente
    Then se congela el resumen y actor del cierre
    And no se envía counted_cash_cents=0 ni se crea UserCashCut

  @PRD-FR-218
  @BDD-SC-285
  Scenario: Monitor de ventas filtra y baja a operaciones trazables
    Given ventas con familias, servicios, impuestos y cortesías en distintos turnos
    When un actor autorizado filtra fecha, turno, familia y tipo de servicio
    Then ve importes, conteos, impuestos, descuentos y cortesías calculados por backend
    And cada indicador permite drill-down a operaciones dentro de su alcance

  @PRD-FR-219 @PRD-NFR-021
  @BDD-SC-286
  Scenario: Corte por usuario calcula contado, esperado y diferencia
    Given un Líder con alcance explícito de cajero, caja, turno y periodo aprobado
    When captura efectivo contado y confirma el corte con idempotency key
    Then el backend calcula esperado, diferencia y tolerancia en centavos
    And crea reporte inmutable con actor, autorizador y operaciones incluidas

  @PRD-FR-219 @PRD-NFR-021
  @BDD-SC-287
  Scenario: Corte duplicado o concurrente no doble contabiliza
    Given dos solicitudes simultáneas para la misma tupla de corte
    When ambas intentan finalizar
    Then sólo una adquiere el lock y finaliza
    And la otra recibe cash_cut_in_progress o cash_cut_already_finalized sin duplicar operaciones

  @PRD-FR-218
  @BDD-SC-292
  Scenario: Candidatos visuales del video no se convierten en requisitos silenciosos
    Given la pantalla de monitor propuesta
    When no existe decisión para estación, impresora, Excel o nota de consumo
    Then no se publica un contrato ni permiso para esos controles
    And el plan los conserva como pendientes de producto
```

## BDD-FEAT-079 Reportes históricos, offline y transición

```gherkin
@offline
Feature: Derivar reportes y sincronizar sin reemplazar autoridad central

  @PRD-FR-220 @PRD-NFR-021
  @BDD-SC-288
  Scenario: Venta por insumos conserva receta aplicada históricamente
    Given dos pedidos equivalentes aceptados con versiones distintas de receta
    When un Supervisor consulta venta por insumo de ambos periodos
    Then Python agrega Decimal desde los snapshots aplicados
    And editar la receta actual no cambia ningún resultado histórico

  @PRD-FR-216 @PRD-NFR-022
  @BDD-SC-289
  Scenario: Movimiento offline se revalida y no declara éxito final antes de nube
    Given un gateway SQLite sin conexión y un comando de caja con actor e idempotency key
    When lo persiste en outbox y después recupera conectividad
    Then PostgreSQL revalida actor, permiso, alcance, turno e idempotencia en inbox
    And una denegación se muestra como conflicto pendiente sin crear compensación automática

  @PRD-FR-215 @PRD-NFR-024
  @BDD-SC-290
  Scenario: Migración de roles semilla es reversible y conserva especialidades
    Given Administrador corporativo, un perfil Cajero legacy y roles especializados existentes
    When se ejecuta el upgrade propuesto y luego downgrade en bases PostgreSQL y SQLite
    Then bloquea downgrade si existen asignaciones, mappings o grants externos no revertidos
    And sólo tras revertirlas controladamente baja sin borrar datos confirmados
    And conserva asignaciones, permisos efectivos, auditoría y roles especializados
    And no convierte Administrador corporativo en Dueño sin mapeo individual aprobado

  @PRD-FR-215 @PRD-NFR-020 @PRD-NFR-023
  @BDD-SC-291
  Scenario: Acciones R3 y denegaciones son auditables y observables
    Given una acción de efectivo, cancelación, reapertura, merma, receta o corte
    When se autoriza o se deniega
    Then registra actor, alcance, resultado, UTC y correlation id sin secretos
    And emite métrica estructurada del resultado
```

## BDD-FEAT-080 Invariantes de auditoría iteración 2

```gherkin
@cash @security @reports
Feature: Cerrar ambigüedades contables y de autorización

  @PRD-FR-215 @PRD-NFR-020
  @BDD-SC-293
  Scenario: Dueño ejerce permisos corporativos persistidos y no cruza organización
    Given un Dueño de Organización A con admin.manage, catalog.manage y un permiso especializado persistidos
    When administra catálogo corporativo y consulta una capacidad especializada de Organización A
    Then ambas acciones son autorizadas por permisos almacenados en backend
    When reutiliza su token o payload contra Organización B
    Then es rechazado sin que access.organization.all_branches conceda cruce organizacional
    And un Administrador corporativo sin esa concesión no puede asignarse ni asignar Dueño

  @PRD-FR-215 @PRD-NFR-020
  @BDD-SC-298
  Scenario: La concesión de autoridad de organización conserva su invariante
    Given un rol con organization_all_permissions y un Administrador corporativo legacy
    When el Administrador intenta cambiar su scope, borrarlo o reemplazar sus permisos
    Then recibe un error estable auditado y el grant conserva scope organization y autoridad dinámica
    When un actor con la misma autoridad renombra el rol
    Then el nombre cambia sin alterar la autorización persistida
    And un rol organizacional con access.organization.all_branches ordinario no obtiene permisos futuros

  @PRD-FR-215 @PRD-NFR-020 @PRD-NFR-024
  @BDD-SC-299
  Scenario: Bootstrap explícito asigna sólo los dos Dueños iniciales configurados
    Given usuarios preexistentes y activos aniacuestas@gmail.com y mangoex@gmail.com de una organización explícita
    And ambos conservan Administrador corporativo legacy antes y después del bootstrap
    And un actor operacional de esa organización y una procedencia de mantenimiento válida
    When ejecuta bootstrap_initial_owners con exactamente esos dos correos
    Then asigna atómicamente el único rol con organization_all_permissions y audita actor/procedencia
    And no crea cuenta, contraseña, rol, organización ni asignación para un correo diferente
    When se repite el mismo comando
    Then devuelve already_bootstrapped sin agregar asignaciones
    When falta un usuario, hay parcialidad, otra organización o un Dueño externo
    Then falla cerrado sin asignación parcial
    And revierte una escritura ajena pendiente antes de persistir sólo la auditoría de denegación

  @PRD-FR-215 @PRD-NFR-020 @PRD-NFR-024
  @BDD-SC-300
  Scenario: Mapeo explícito preserva especialidades y permite reversión auditable
    Given un Dueño solicita dry-run sin PII para un usuario legacy y un perfil destino válido
    When crea PENDING con snapshot, scope, procedencia e idempotency key y después lo aplica
    Then MAPPED agrega sólo el perfil destino y conserva roles especializados
    When reintenta cada etapa con la misma key
    Then recibe el resultado estable sin otra mutación
    And un replay que llega tras colisión de inserción compara roles, sucursal y procedencia antes de responder
    And si el rol legacy desaparece o cambia de sucursal antes de aplicar, falla auditado sin asignar destino
    When revierte el mapping
    Then restaura el snapshot, marca REVERSED y conserva toda la historia/auditoría
    And si el destino fue retirado y reasignado en otra sucursal, falla auditado sin borrarlo ni marcar REVERSED
    And un actor existente de otra organización es denegado, revierte escritura ajena pendiente y deja authorization.denied en la organización objetivo
    And una organización inexistente o inactiva falla con profile_transition_organization_invalid sin mapping ni auditoría
    And un nuevo ciclo sólo puede crear otro PENDING después de REVERSED, sin borrar el ciclo previo
    And dos mappings pending o mapped para la misma pareja se rechazan

  @PRD-FR-216 @PRD-NFR-021
  @BDD-SC-294
  Scenario: Compensación de compra cash conserva signo e importe una sola vez
    Given una compra cash confirmada crea WITHDRAWAL de 3000 con source_type PURCHASE
    When Dueño compensa ese movimiento con motivo válido
    Then crea DEPOSIT de 3000 con compensates_movement_id y amount positivo
    And el esperado cambia de 11000 a 14000 sin contar la compra o compensación dos veces

  @PRD-FR-216 @PRD-NFR-020
  @BDD-SC-302
  Scenario: Permiso, turno y evidencia gobiernan cada movimiento manual
    Given un Cajero y un Cajero jefe con sucursal canónica y caja configurada
    When Cajero registra un retiro durante turno OPEN con concepto efectivo, centavos positivos, referencia y evidencia
    Then se crea un único withdrawal auditado y recibe el efectivo esperado calculado por Python
    When Cajero intenta depositar o cualquiera intenta operar sin turno OPEN, referencia, evidencia o concepto compatible
    Then falla permission_denied, cash_shift_not_open, cash_reference_required, cash_evidence_required o cash_concept_invalid sin movimiento ni comando completado
    When Cajero jefe registra un depósito válido
    Then se crea un único deposit dentro de su sucursal autorizada

  @PRD-FR-216 @PRD-NFR-021
  @BDD-SC-303
  Scenario: Idempotencia de movimiento compara actor y payload completo
    Given un comando manual confirmado con Idempotency-Key
    When el mismo actor repite sucursal, caja, tipo, concepto, centavos, referencia y evidencias
    Then recibe el resultado persistido sin recalcularlo ni insertar otra fila
    When cambia actor, campo, orden canónico de evidencia u objetivo usando la misma clave
    Then falla idempotency_conflict sin escritura parcial

  @PRD-FR-216 @PRD-NFR-020
  @BDD-SC-304
  Scenario: Consulta de ledger respeta alcance y conserva snapshots
    Given movimientos manuales, compras legacy y compensaciones en dos sucursales
    When un actor con cash.movement.read filtra por sucursal, caja, turno, fecha y tipo
    Then recibe sólo filas autorizadas en orden estable con cursor y snapshot histórico disponible
    And no recibe command hash, Idempotency-Key ni evidencias de otra organización

  @PRD-FR-216 @PRD-NFR-021
  @BDD-SC-305
  Scenario: Compra cash y cancelación usan el mismo ledger compatible
    Given una compra cash confirmada durante turno OPEN
    When se confirma y luego se cancela con inventario reversible y el turno todavía OPEN
    Then existe un withdrawal PURCHASE y un deposit compensatorio exacto enlazado
    And ambos participan una vez en el efectivo esperado sin término adicional de compra
    When se reintenta confirmación o cancelación
    Then no aparece otro movimiento
    And las filas legacy withdrawal y cash_reversal conservan su proyección histórica

  @PRD-FR-219 @PRD-NFR-021
  @BDD-SC-295
  Scenario: Cortes parcialmente solapados y dos turnos no comparten operaciones
    Given un cajero con dos turnos y operaciones distintas en cada uno
    And un corte FINALIZED ya incluye una operación del primer turno
    When se intenta finalizar un segundo corte con periodo parcialmente solapado que la incluye
    Then falla cash_cut_already_finalized aunque su period_start y period_end sean distintos
    And un corte del segundo turno sólo puede incluir operaciones de ese turno
    When el primer corte se reabre y se compensa bajo una política futura aprobada
    Then la operación original conserva su asociación histórica y no puede entrar al segundo corte

  @PRD-FR-216
  @BDD-SC-296
  Scenario: Operador sólo puede seleccionar conceptos efectivos publicados
    Given un Cajero abre depósito o retiro con turno autorizado
    When consulta conceptos efectivos para tipo y fecha
    Then sólo recibe conceptos vigentes compatibles desde backend
    When envía texto libre, código inventado o concepto archivado
    Then el comando falla cash_concept_invalid sin crear movimiento

  @PRD-FR-216
  @BDD-SC-301
  Scenario: Dueño versiona y archiva conceptos sin borrar historia
    Given un Dueño con cash.concept.manage y un concepto retiro publicado en versión uno
    When publica una versión dos con vigencia futura usando Idempotency-Key
    Then la fecha anterior sigue resolviendo versión uno y la fecha vigente resuelve versión dos
    And el replay idéntico devuelve el mismo resultado sin agregar otra versión
    When reutiliza la clave con payload diferente o intenta cambiar el código
    Then falla idempotency_conflict o cash_concept_code_immutable sin escritura parcial
    When archiva el concepto
    Then desaparece de la lectura efectiva pero identidad y ambas versiones siguen en historia

  @PRD-FR-220 @PRD-NFR-021
  @BDD-SC-297
  Scenario: Reportes no mezclan unidades ni doble cuentan gasto enlazado
    Given una venta con snapshots convertibles y otra sin conversión histórica válida
    And una compra con retiro cash enlazado por source_id
    When se consulta venta por insumo y gastos
    Then agrega sólo cantidades de unidad base compatibles y marca o rechaza la línea incompleta
    And presenta una sola fila de gasto para compra y retiro enlazados
```
