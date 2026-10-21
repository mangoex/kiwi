# BDD — DELIVERY-FEE-001 Catálogo y cargo de entrega

Estado: núcleo POS online con evidencia local; fiscal/canales/offline parciales y CI pendiente. Autoridad: PRD-FR-283..288 y SDD §70.
Importes distintos de $28 y el umbral $500 son fixtures sintéticos, no configuración productiva.

## BDD-FEAT-154 Elegir una tarifa de domicilio sin convertirla en alimento

```gherkin
@PRD-FR-283 @PRD-FR-284 @PRD-FR-285 @PRD-FR-286 @PRD-FR-287 @PRD-FR-288 @delivery @critical
Feature: Tarifas de envío versionadas y un único cargo por pedido

  Background:
    Given la sucursal de prueba tiene política de envío habilitada
    And tiene tarifa predeterminada Estándar de 28.00 MXN con IVA 16% incluido
    And el umbral de envío gratis está desactivado

  @BDD-SC-745
  Scenario: Administrar tarifas sin receta y sin cambiar contexto POS
    Given un administrador con autoridad corporativa de catálogo
    When crea una tarifa y publica una política para una sucursal autorizada
    Then guarda identidad y versión de precio sin producto, receta ni estación
    And el POS, turno y borrador del administrador conservan su contexto

  @BDD-SC-746
  Scenario: Publicar un nuevo precio conserva el pedido anterior
    Given un pedido confirmado con tarifa Estándar de 28.00
    When se publica otra versión sintética de 30.00
    Then un pedido nuevo obtiene 30.00
    And el detalle, cobro y reimpresión del pedido anterior conservan 28.00

  @BDD-SC-747
  Scenario: Rechazar configuración inválida y publicaciones concurrentes
    Given dos administradores parten de la misma versión de política
    When intentan publicar cambios incompatibles en paralelo
    Then sólo una publicación válida se confirma y la otra ve conflicto
    And no se permite default inactivo, de otra organización o fuera de las tarifas elegibles
    And rechazar una publicación no deja cambios parciales

  @BDD-SC-748
  Scenario: Sugerir y sustituir una única tarifa
    Given una segunda tarifa sintética Zona amplia de 42.00 disponible en la sucursal
    When el cajero elige A domicilio y después selecciona Zona amplia
    Then inicialmente ve Estándar de 28.00 y finalmente sólo Zona amplia de 42.00
    And el total no incluye ambas tarifas ni cantidades del servicio

  @BDD-SC-749
  Scenario: Quitar desde comanda conserva la decisión explícita
    Given un cajero autorizado para el borrador o para enmendar ese pedido impago editable
    When quita el envío, cambia productos, recarga y recupera la comanda
    Then el envío continúa retirado y no se restaura por recotizar
    And el pedido confirmado conserva actor, motivo operativo e importes del retiro
    And puede restaurar explícitamente el envío sin aprobación administrativa adicional

  @BDD-SC-750
  Scenario: Tipo de servicio y nuevo pedido no heredan cargos indebidos
    Given un borrador delivery con selección manual o retiro explícito
    When pasa a recoger y después vuelve a domicilio
    Then recoger no cobra envío y domicilio conserva la preferencia del borrador
    And repetir el pedido como uno nuevo usa AUTO y configuración vigente
    And el servidor rechaza una tarifa explícita enviada para otro tipo de servicio

  @BDD-SC-751
  Scenario: Permisos y pago impiden modificaciones indebidas
    Given un actor sin autoridad sobre el pedido o un pedido pagado o con producción iniciada
    When intenta quitar o cambiar la tarifa mediante edición ordinaria
    Then la solicitud se rechaza sin cambiar pago, total ni auditoría histórica
    And producción iniciada exige el proceso de reapertura autorizado aun para cambiar sólo envío
    And un retiro autorizado impago no concede editar precios ni política de catálogo

  @BDD-SC-752
  Scenario Outline: Comparar el umbral de forma inclusiva
    Given un umbral sintético habilitado de 500.00
    When el subtotal de productos tras descuentos es <subtotal>
    Then el envío cobrado es <envio> y su estado es <estado>
    And la tarifa Estándar continúa identificada
    And cuando es gratis la comanda muestra "Envío gratis por monto mínimo" y el resumen "Gratis"
    And no presenta el precio de lista ni el desglose de base e IVA como importes del envío exento

    Examples:
      | subtotal | envio | estado           |
      | 499.99   | 28.00 | CHARGED          |
      | 500.00   | 0.00  | WAIVED_THRESHOLD |
      | 500.01   | 0.00  | WAIVED_THRESHOLD |

  @BDD-SC-753
  Scenario: Descuentos, modificadores y propinas no falsean el mínimo
    Given un umbral sintético de 500.00 y productos con modificadores cobrables por 520.00
    And un descuento de productos autorizado de 30.00 y propina de 20.00
    When el servidor cotiza
    Then compara 490.00 contra el umbral y cobra envío de 28.00
    And ni envío ni propina completan el umbral
    And un combo no suma nuevamente los precios de sus componentes

  @BDD-SC-754
  Scenario: Cambiar el subtotal reevalúa gratuidad sin deshacer un retiro
    Given un pedido impago editable con tarifa seleccionada y política congelada de 500.00
    When el subtotal sube a 500.00 y después baja a 499.99
    Then el envío pasa de gratis a cobrado según la política del pedido
    And si el cajero lo retiró manualmente permanece retirado en ambos subtotales
    And desactivar o cambiar el umbral global no modifica esa política histórica

  @BDD-SC-755
  Scenario: Calcular IVA incluido sin fabricar impuestos de alimentos
    Given productos con impuesto no determinado y tarifa de envío de 28.00
    When el servidor calcula el pedido
    Then el envío muestra base 24.14 e IVA incluido 3.86 con precisión interna conservada
    And el total aumenta 28.00 y no 32.48
    And el impuesto total desconocido de alimentos no se convierte en cero ni se infiere
    And una entrada manual de precio con tres decimales se rechaza sin redondear

  @BDD-SC-756
  Scenario: Cargo monetario no provoca consumo ni producción
    Given una comanda con alimentos y tarifa seleccionada
    When se confirma o se modifica únicamente la selección del envío
    Then no se exige receta al servicio ni se crean reservas, consumos o tareas por él
    And los movimientos y tareas de alimentos conservan sus invariantes

  @BDD-SC-757
  Scenario: Reintentos conservan intención y snapshot
    Given una creación o enmienda ya confirmada con una clave idempotente
    When se reintenta después de cambiar o archivar la tarifa de catálogo
    Then recupera el resultado de la misma intención sin duplicar cargo ni auditoría efectiva
    And reutilizar esa clave con otra selección o retiro produce conflicto sin escritura

  @BDD-SC-758
  Scenario: Conflicto de cotización y carrera con el pago
    Given un precio publicado después de cotizar un pedido nuevo
    When se intenta confirmar con la cotización obsoleta
    Then se rechaza y se pide recotizar antes de aceptar otro importe
    And ante una carrera de pago y retiro sólo se confirma una revisión monetaria consistente
    And la cotización no genera reservas ni venta

  @BDD-SC-759
  Scenario: Ticket y reimpresión separan envío de cocina
    Given un pedido con envío cobrado, exento o retirado
    When se imprime el ticket o su copia histórica
    Then muestra servicio, tarifa, importe o causa correspondiente y total canónico
    And cocina no ve un platillo ni una tarea de envío
    And un cambio posterior del catálogo no altera esa impresión

  @BDD-SC-760
  Scenario: Reportes concilian sin contaminar alimentos o historia incompleta
    Given pedidos nuevos cobrados, exentos, retirados y compensados y pedidos legacy sin snapshot
    When se consultan ventas, cierre y reporte de envíos
    Then separa productos, envío, impuestos conocidos y compensaciones sin doble conteo
    And no agrega envíos a unidades, ranking de platillos ni food cost
    And conserva desconocido el dato legacy no capturado sin inferirlo por nombre de producto

  @BDD-SC-761
  Scenario: Recaudación del repartidor es distinta de su remuneración
    Given un pedido de alimentos por 200.00 con envío de 28.00 y pago en efectivo pendiente
    When se asigna un repartidor y después se cambia la tarifa o se retira con autorización
    Then la deuda pendiente concuerda con el total impago vigente
    And la asignación histórica conserva el importe que tenía y enlaza el cambio posterior
    And recibir efectivo confirma el cobro una sola vez sin liquidar un sueldo supuesto de 28.00

  @BDD-SC-762
  Scenario: Concepto fiscal no duplica envío ni inventa claves
    Given un pedido pagado con cargo y mapeo fiscal aprobado por emisor
    When se prepara factura o recibo facturable mediante el adaptador
    Then el envío cobrado aparece una sola vez como servicio separado del consumo de alimentos
    And base, IVA y total provienen de snapshots y concilian con el pago
    And sin mapeo fiscal suficiente no se emite ni se declara éxito
    And envío retirado o exento no genera un importe gravado inexistente

  @BDD-SC-763
  Scenario: Contratos de canales evitan cobro doble o evasión
    Given pedidos de canal propio y de marketplace con responsable de envío identificado
    When el adaptador conserva la tarifa externa y aplica la política correspondiente
    Then no añade envío local a un servicio cobrado por tercero sin regla explícita
    And un origen ambiguo o escritor incompatible no confirma por omisión un envío gratuito
    And los payloads originales y referencias se conservan sin exponer datos sensibles

  @BDD-SC-764
  Scenario: Offline conserva tarifa, retiro y precio confirmado
    Given un gateway compatible con política y autorización local vigentes
    When confirma delivery offline y sincroniza después de un cambio de precio central
    Then mantiene selección, exención o retiro y el importe autorizado de origen
    And un reintento no duplica pedido, cargo, pago ni outbox efectivo
    And rechaza importes manipulados o política no autorizada sin repricing silencioso

  @BDD-SC-765
  Scenario: Activación y migración preservan historia y clientes incompatibles
    Given un entorno aislado con pedidos históricos y cliente POS o gateway antiguo
    When se migra y habilita la política para un canal piloto
    Then los pedidos históricos no reciben nuevos cargos ni valores fiscales inventados
    And el escritor incompatible no puede confirmar nuevas entregas en ese alcance
    And la reversión conserva lectura, conciliación y recuperación de cargos confirmados
    And un downgrade destructivo con historia o pendientes se bloquea

  @BDD-SC-766
  Scenario: Fallos y aislamiento no se convierten en gratuidad
    Given política ausente, almacenamiento fallido o selección ajena a la sucursal u organización
    When se intenta cotizar o confirmar delivery habilitado
    Then el servidor devuelve un error explícito sin escritura parcial ni cargo cero simulado
    And la UI conserva carrito y selección sin habilitar confirmar un total desconocido
    And una respuesta tardía no reemplaza la cotización actual ni revela catálogo ajeno
```
