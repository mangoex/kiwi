# BDD — AUD-CORE-001: integridad de compras, gastos, caja y alcance

Estado: especificado; implementación y verificación en curso. Evidencia y gates pendientes en
AUD-CORE-001 §11; no acredita cierre. Autoridad técnica: SDD §57.
PUR-CASH-001 conserva SC-607..613; no duplicar esos escenarios ni declarar verde por baseline.

## BDD-FEAT-131 Correcciones financieras y de alcance

```gherkin
@audit-core @PRD-FR-108 @PRD-FR-220 @PRD-FR-225 @PRD-FR-226
Feature: Conservar efectos únicos, historia y autoridad en la operación

  @BDD-SC-615
  Scenario: Una compra en efectivo se descuenta una sola vez
    Given una sucursal autorizada con turno abierto y 200000 centavos iniciales
    And una compra confirmada de 30000 centavos con retiro PURCHASE vinculado
    When consulta ledger, conciliación, consolidado y Excel para el mismo alcance
    Then el esperado es 170000 centavos
    And la compra se desglosa una vez por proveedor
    And su retiro no se suma también como gasto fijo o retiro manual
    And una compensación manual autorizada enlaza la categoría al proveedor sin depósito genérico

  @BDD-SC-616
  Scenario: Los pagos confirmados conservan su método y estado canónicos
    Given pagos CONFIRMED de 10000 cash, 20000 card y 30000 transfer
    And un pago no confirmado que no debe participar
    When consulta conciliación y sus consumidores
    Then registra ventas por 60000 centavos y sólo 10000 incrementan el efectivo
    And ningún método desconocido se reclasifica automáticamente como cash
    And conserva la política de crédito ya aprobada sin usarla para compras directas

  @BDD-SC-617
  Scenario: Confirmación y devolución se atribuyen a sus propios días
    Given un borrador creado el día D y confirmado en D más uno
    And la compra se anula en D más dos con compensaciones autorizadas
    When consulta cada periodo local, su consolidado y exportación
    Then la actividad calendario de D no contiene egreso por el borrador
    And la actividad de D más uno conserva el positivo después de la anulación
    And la actividad de D más dos registra sólo la reversa correspondiente
    And los límites locales convertidos a UTC no solapan eventos
    And los snapshots de cierre y revisiones anteriores permanecen idénticos
    And el saldo agrupa turnos abiertos ese día y todo su ledger, congelado al cierre
    And consolidado y Excel suman las dos poblaciones por separado sin duplicar turnos
    And un turno sin conteo físico equivalente muestra Pendiente de arqueo con contado y diferencia nulos
    And ni cierre operativo ni corte parcial por usuario inventan un conteo
    And un conteo real de cero conserva cero y una caja pendiente impide certificar el total
    And un consolidado sin sucursales conserva estado EMPTY, contado/diferencia nulos y nueve totales de actividad cero
    And el botón de revisión refleja audit.read, branch.admin.access o admin.manage en el alcance activo
    And cash.shift.close por sí solo no habilita una revisión gerencial

  @BDD-SC-618
  Scenario: Descartar una compra en borrador no crea gasto negativo
    Given una compra de 30000 centavos nunca confirmada
    When el actor autorizado cancela su borrador
    Then queda anulada con auditoría documental
    And no existe evento positivo ni reversa financiera en el reporte general
    And no cambia inventario, costo ni caja

  @BDD-SC-619
  Scenario: Cancelación suma todas las partidas del mismo insumo
    Given una compra con dos recepciones de 5 unidades del mismo insumo
    And el costo de ambas partidas es cero y sólo quedan 5 unidades físicas
    When el actor autorizado intenta anular la compra confirmada
    Then recibe purchase_reversal_insufficient_stock sin efectos parciales
    And la existencia sigue en 5 y no se compensa caja
    But con 10 unidades suficientes crea dos reversas referenciadas y deja existencia cero
    And el resultado no depende de que se utilicen presentaciones distintas del mismo insumo

  @BDD-SC-620
  Scenario: Transiciones concurrentes y fallos no dejan efectos parciales
    Given una compra autorizada en borrador o confirmada
    When compiten confirmación, cancelación o cierre con barreras deterministas
    Then cada resultado corresponde a una transición serial válida
    And no se duplica retiro, recepción, compensación ni auditoría de transición
    And un fallo tras una escritura revierte todos los efectos del comando
    And replay o cancelación de originales inconsistentes rechaza sin modificar caja o almacenes
    And un replay reautorizado conserva identidad y no requiere un nuevo turno abierto

  @BDD-SC-621
  Scenario: Desactivar la sucursal bloquea nuevas transiciones de compra
    Given una compra creada en una sucursal activa autorizada
    And posteriormente se desactiva la sucursal o se revoca el permiso del actor
    When solicita confirmar, cancelar o recuperar una intención
    Then se aplica el alcance y permiso vigente conforme al contrato de la ruta
    And ninguna nueva recepción o compensación se produce en la sucursal inactiva
    And los documentos y movimientos históricos no se eliminan ni reasignan

  @BDD-SC-622
  Scenario: Las condiciones no enlazan proveedores de otra organización
    Given un administrador de la organización A y su sucursal A
    And existe un proveedor de la organización B
    When intenta guardar condiciones de ese proveedor para la sucursal A
    Then el servicio rechaza sin persistir asociación ni auditoría de éxito
    And las condiciones válidas de proveedores de A permanecen intactas

  @BDD-SC-623
  Scenario: Consultas corporativas y restringidas conservan su alcance
    Given compras en dos sucursales de A y una sucursal de B
    When una cuenta corporativa autorizada de A consulta compras sin branch_id
    Then obtiene las compras de sus sucursales autorizadas de A
    And nunca una lista vacía causada por branch_id IS NULL ni documentos de B
    But una cuenta restringida sin branch_id conserva su sucursal resuelta
    And solicitar otra sucursal no amplía su permiso
    And diario, consolidado y Excel rechazan efectos cuyo turno padre tenga otro alcance o fecha posterior al cierre
    And un concepto o versión de otra organización no revela su nombre en ningún desglose
    And un pago con pedido padre ajeno falla sin datos del cliente ajeno

  @BDD-SC-624
  Scenario: Rechazos de consultas usan errores explícitos y redactados
    Given solicitudes sin sesión, fuera de alcance o con almacenamiento indisponible
    When consulta compras o proveedores
    Then falta de sesión responde 401 y falta de alcance responde 403
    And la indisponibilidad responde 503 con detalle constante
    And un conflicto de negocio conserva su código y respuesta canónicos
    And nunca convierte esos rechazos en 500 ni expone SQL, parámetros o datos ajenos

  @BDD-SC-625
  Scenario: Correcciones no amplían los permisos de roles y cuentas
    Given cuentas canónicas y personalizadas con permisos persistidos por sucursal
    When registran compras, gastos, conceptos, anulaciones y reportes
    Then sólo permisos y alcance explícitos autorizan cada acción
    And purchases.manage no concede expenses.manage
    And cash.movement.withdraw no concede captura de compras o gastos
    And Supervisor y Administrador no administran conceptos ni anulan gastos confirmados sin los grants correspondientes
    And compensar internamente una compra conserva su contrato distinto de la compensación manual

  @BDD-SC-626
  Scenario: Compras y gastos se integran sin cruzar sus dependencias
    Given un turno con 200000 centavos y una compra cash de 30000
    And un gasto cash de 30000 y un gasto transfer de 100000
    When confirma documentos y consulta las proyecciones autorizadas
    Then el esperado de caja es 140000 centavos
    And el neto de Gastos es 130000 y excluye la compra
    And sólo la compra produce recepción y costo de inventario
    And los comandos de Gastos conservan idénticos inventario, costos y proveedores
    And las compensaciones autorizadas conservan originales y referencias
```

## BDD-FEAT-132 Entorno reproducible y evidencia efectiva

```gherkin
@audit-core @PRD-NFR-006
Feature: Preparar diagnóstico histórico sin modificar operaciones

  @BDD-SC-629
  Scenario: Diagnóstico acotado y de sólo lectura conserva el historial
    Given una base aislada con compras válidas y discrepancias históricas conocidas
    When diagnostica una organización explícita usando una conexión de sólo lectura
    Then identifica efectos incoherentes, huérfanos y relaciones entre organizaciones
    And conserva idénticas todas las tablas y no expone datos sensibles ni IDs ajenos
    And informa cobertura parcial al limitar documentos o evidencias
    And distingue candidatos a investigación de defectos causales confirmados
    And no ejecuta reparación ni autoriza una consulta productiva
```

```gherkin
@audit-core @PRD-NFR-016
Feature: Verificar el paquete real sin depender del equipo del desarrollador

  @BDD-SC-627
  Scenario: Instalación limpia carga la API y las rutas multipart
    Given un entorno aislado del runtime objetivo sin paquetes globales
    When instala dependencias verificadas desde locks y paquetes propios sin reresolver
    Then pip check valida el proyecto instalado y create_app construye sus rutas
    And las rutas multipart y health funcionan en configuración test
    And dos instalaciones del mismo objetivo reproducen las versiones resueltas
    And Docker y CI no actualizan silenciosamente las resoluciones

  @BDD-SC-628
  Scenario: CI no acepta pruebas PostgreSQL obligatorias omitidas
    Given la corrección activa concurrencia, persistencia y dialecto PostgreSQL
    When CI ejecuta el gate con una URL ausente o un servicio no disponible
    Then el gate falla y no acredita esas pruebas como superadas
    But con bases aisladas provisionadas ejecuta todos los casos obligatorios
    And su evidencia identifica commit, runtime, lock y cantidad de pruebas sin skips ocultos
```
