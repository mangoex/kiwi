# BDD - Compras directas, caja y costo promedio

## BDD-FEAT-038 Recepción directa conciliada

```gherkin
@PRD-FR-052 @PRD-FR-100 @PRD-FR-108 @PRD-FR-110 @purchases @cash
Feature: Confirmar compra directa desde sucursal

  @BDD-SC-079
  Scenario: Compra pagada desde caja
    Given un supervisor tiene turno de caja abierto
    And captura una compra directa con comprobante y presentaciones
    When confirma la compra como pagada desde caja indicando la caja configurada
    Then se crea un retiro con motivo Compra de insumos
    And se generan entradas de inventario
    And compra y retiro quedan vinculados sin duplicar el egreso
    But sin una caja validada para su sucursal la UI no envía la confirmación y conserva el borrador

  @BDD-SC-080
  Scenario: Reintento idempotente de confirmación
    Given una compra ya fue confirmada con una clave de idempotencia
    When la sucursal reintenta la misma confirmación
    Then obtiene el mismo resultado
    And no duplica retiro, recepción ni costo

  @BDD-SC-081
  Scenario: Cancelar compra confirmada
    Given una compra confirmada generó inventario y retiro
    When un supervisor autorizado la cancela con motivo
    Then conserva los movimientos originales
    And crea contramovimientos de inventario y caja referenciados
```

## BDD-FEAT-128 Efectivo y contexto de caja verificables

Diseño PUR-CASH-001; escenarios nuevos pendientes de implementación y ejecución.

```gherkin
@PRD-FR-207 @PRD-FR-108 @PRD-FR-110 @cash @purchases
Feature: Comprar con efectivo de la sucursal activa

  @BDD-SC-592
  Scenario: Efectivo visible y predeterminado sin efectos del borrador
    Given una cuenta tiene purchases.manage en la sucursal activa
    When abre una nota nueva desde Administración o el acceso administrativo del POS
    Then el selector muestra Efectivo seleccionado y permite Transferencia, Tarjeta y Otro
    And no existe una casilla independiente que contradiga el método
    And guardar o previsualizar no crea retiro ni recepción
    And los métodos no efectivos no se rotulan como crédito

  @BDD-SC-593
  Scenario: Resolver la caja dentro del alcance autorizado
    Given la cuenta tiene permiso de compra y retiro en la sucursal activa
    When revisa una compra en efectivo
    Then una caja del POS sólo se propone si está abierta y validada en esa sucursal
    And sin preferencia válida se propone la única caja abierta o se exige elegir entre varias
    And sin caja abierta se puede guardar el borrador pero no confirmar
    And la revisión muestra sucursal, caja, turno y total antes del retiro

  @BDD-SC-594
  Scenario: Rechazar alcance manipulado y contexto anterior
    Given una compra pertenece a la sucursal A
    When cambia cuenta o sucursal o altera la sucursal y caja en la petición
    Then la UI invalida selección y respuestas tardías del contexto anterior
    And la API exige alcance y permisos vigentes y coincidencia con la sucursal documental
    And un usuario sin permiso de retiro puede guardar pero no confirmar efectivo
    And ninguna sucursal ajena recibe efectos ni se exponen sus cajas o saldos

  @BDD-SC-595
  Scenario: Confirmación atómica y turno revisado
    Given el efectivo esperado es 2000 pesos y la compra totaliza 300 pesos
    When confirma con el turno revisado todavía abierto
    Then queda un retiro de 300 pesos enlazado a la compra y el esperado es 1700 pesos
    And se reciben las partidas y actualiza el costo una sola vez
    But si cierra el turno o abre otro antes de confirmar se rechaza sin efectos parciales
    And la revisión permanece abierta para resolver el rechazo

  @BDD-SC-596
  Scenario: Respuesta perdida y confirmaciones concurrentes
    Given una confirmación puede haber terminado aunque su respuesta no llegó
    When se recupera o reintenta con la misma identidad de actor, compra, sucursal, caja y turno
    Then se obtiene el documento vigente sin repetir retiro, recepción o costo
    And la UI mantiene clave y body durante la incertidumbre
    And un cambio de identidad con la misma clave se rechaza
    And dos claves simultáneas para la misma compra producen como máximo una confirmación
    And un replay válido después del cierre o compensación no crea efectos nuevos

  @BDD-SC-597
  Scenario: Coherencia de método y ausencia de retiro para otros medios
    Given una compra usa Transferencia, Tarjeta u Otro
    When se confirma con los permisos de compra correspondientes
    Then no requiere caja ni genera retiro y no declara una cuenta por pagar
    And la API rechaza cash con paid_from_cash false y no cash con paid_from_cash true
    And preview, creación y confirmación rechazan credit y cualquier método desconocido
    And un borrador histórico incoherente no se confirma ni se corrige silenciosamente

  @BDD-SC-598
  Scenario: Compensar conservando el movimiento original
    Given una compra en efectivo confirmada conserva su turno original abierto
    When un actor autorizado la cancela con motivo
    Then se conservan retiro y recepción originales con sus contramovimientos vinculados
    And el efectivo esperado se recupera por la compensación una sola vez
    But con el turno original cerrado se conserva el rechazo vigente sin escribir parcialmente
```

## BDD-FEAT-039 Costo promedio por recepción

```gherkin
@PRD-FR-089 @PRD-FR-109 @PRD-FR-111 @costing
Feature: Actualizar costo al recibir, no al cotizar

  @BDD-SC-082
  Scenario: Promedio ponderado con existencia positiva
    Given existen 10 kg a costo promedio de 20 pesos
    When se reciben 10 kg a costo de 30 pesos
    Then la existencia queda en 20 kg
    And el costo promedio queda en 25 pesos
    And la UI identifica el precio capturado como precio de la presentación antes de descuento
    And explica que impuesto no integra el costo de inventario
    And muestra el promedio en el alcance de la sucursal y su almacén seleccionados

  @BDD-SC-083
  Scenario: Rechazar política no definida para existencia negativa
    Given la existencia física calculada es negativa
    When se intenta confirmar una compra
    Then la compra permanece en borrador
    And no crea retiro ni movimientos parciales
    And responde que falta política para costo con inventario negativo
```
