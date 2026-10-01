# BDD — SR-WORKSPACE-001

Estado: criterios implementados con evidencia local en TDD y cierre del plan. CI y producción
permanecen pendientes. La compatibilidad legacy se especifica separadamente en SDD §51.2.

## BDD-FEAT-116 Capturar una nota completa

```gherkin
@PRD-FR-249
Feature: Captura documental compartida

  @BDD-SC-542
  Scenario: Guardar tres partidas en Admin y sucursal
    Given una sucursal, proveedor y presentaciones autorizados
    When la persona captura cabecera y tres partidas en cualquiera de las dos interfaces
    Then ve el documento completo y los totales Python
    And guarda un único borrador con las tres partidas
    And confirmar produce sus recepciones y un solo retiro si procede

  @BDD-SC-543
  Scenario: Rechazar la última partida sin efectos parciales
    Given dos partidas válidas y una tercera con presentación inválida
    When se guarda el documento
    Then se rechaza con error de negocio y referencia de partida
    And no quedan documento, líneas, movimientos, costo o retiro parciales
    And se conserva la captura para corregirla

  @BDD-SC-544
  Scenario: Revisar filas al cambiar proveedor
    Given una nota sin guardar con partidas del proveedor anterior
    When se elige otro proveedor
    Then las filas incompatibles quedan pendientes de revisión sin perder captura
    And guardar permanece bloqueado hasta reemplazarlas o retirarlas explícitamente
    And cambiar presentación no arrastra su precio anterior sin revisión

  @BDD-SC-545
  Scenario: Aislar sucursales, cache y respuestas tardías
    Given una captura y consultas de la sucursal A
    When la persona cambia a la sucursal B
    Then se avisa antes de abandonar captura
    And B no recibe borrador ni datos de A
    And una respuesta tardía de A se descarta
    And un comando con sucursal o datos ajenos se rechaza en servidor

  @BDD-SC-558
  Scenario: Recuperar una creación cuya respuesta se perdió
    Given una creación fue confirmada y su respuesta no llegó al navegador
    When se reenvía la misma clave, actor, alcance y carga todavía autorizados
    Then devuelve el documento original sin duplicados
    And otra carga con esa clave produce conflicto
    And la confirmación usa su propia clave y no se dispara por recuperar la creación

  @BDD-SC-559
  Scenario: Recibir el mismo insumo en varias presentaciones
    Given tres partidas del mismo insumo con dos presentaciones y precios distintos
    When se confirma la nota
    Then cada partida conserva su snapshot y recepción
    And el saldo y costo acumulados incluyen las tres partidas
    And un replay no repite efectos
    And cancelar preserva originales y registra sus compensaciones
```

## BDD-FEAT-117 Vistas previas calculadas por Python

```gherkin
@PRD-FR-250
Feature: Autoridad única de cálculos

  @BDD-SC-546
  Scenario: Conservar precisión de partidas y convertir sólo el retiro a centavos
    Given partidas con cantidad por precio de 500.00, 19.99 y 0.145
    And descuentos monetarios de 1.00, 0.29 y 0.00
    And impuestos monetarios de 40.00, 3.15 y 0.02
    When Python calcula la nota con Decimal y ROUND_HALF_UP
    Then los subtotales son 500.000000, 19.990000 y 0.145000
    And subtotal es 520.135000, descuento 1.290000, impuesto 43.170000 y total 562.015000
    And el costo recibido excluye impuesto y suma 518.845000
    And si usa caja el retiro es 56202 centavos calculados por Python

  @BDD-SC-547
  Scenario: Previsualizar sin persistencia
    Given captura válida de compra, presentación, insumo o receta
    When solicita un preview autorizado
    Then recibe resultados y fuentes sin crear documento, versión o movimiento
    And el costo contable y la caja permanecen iguales
    And entradas no finitas, ajenas o no persistibles se rechazan sin efectos

  @BDD-SC-548
  Scenario: Descartar un cálculo obsoleto
    Given un preview para una captura y contexto anteriores
    When cambia una entrada, sucursal o relación antes de recibirlo
    Then no se muestra como resultado vigente
    And guardar y confirmar revalidan las relaciones y recalculan
    And un fallo o desconexión conserva captura sin fabricar cifras

  @BDD-SC-549
  Scenario: Mostrar costos y merma sin fórmulas del navegador
    Given una presentación, insumo o receta con entradas explícitas
    When se muestra su costo, equivalencia o cantidad bruta
    Then se usa la función canónica Python con Decimal
    And la UI únicamente captura y presenta cadenas/resultados
    And un costo informativo no se anuncia como promedio contable
```

## BDD-FEAT-118 Presentaciones y alta contextual seguras

```gherkin
@PRD-FR-251
Feature: Configurar catálogo desde una compra sin recibir inventario

  @BDD-SC-550
  Scenario: Rechazar proveedor inexistente sin sustitución
    Given proveedor ausente, inactivo, inexistente o de otra organización
    When se intenta registrar una presentación
    Then devuelve un error de negocio
    And no elige otro proveedor aunque existan varios
    And no persiste una presentación ni historial parcial

  @BDD-SC-551
  Scenario: Exigir equivalencias explícitas y conservar ceros válidos
    Given un insumo y su unidad base
    When la captura nueva previsualiza un empaque con unidad o rendimiento incompatible o faltante
    Then se exige corregir la equivalencia autorizada
    And no se deduce conversión del nombre ni rendimiento uno por omisión
    When se envía cero explícito en un precio o impuesto que admite cero
    Then se conserva sin sustituirlo por una tasa o importe predeterminado

  @BDD-SC-552
  Scenario: Volver de un alta contextual a la misma nota
    Given una nota sin guardar y una persona con permiso de alta de catálogo
    When confirma una nueva presentación
    Then se relee su pertenencia al proveedor y alcance de la nota
    And puede incorporarla sin perder las otras filas
    And no se crea recepción ni retiro
    When cancela el alta
    Then la captura de compra permanece intacta

  @BDD-SC-553
  Scenario: Separar precio informativo de costo contable
    Given una presentación y existencias del almacén
    When cambia el precio permitido de catálogo
    Then se distingue precio comercial, costo informativo por base y promedio contable
    And el promedio no cambia hasta una recepción canónica
    And un usuario sin permiso no puede escribir mediante el alta contextual
```

## BDD-FEAT-119 Compuestos, precio y copia completos

```gherkin
@PRD-FR-252
Feature: Configuración seleccionable versionada

  @BDD-SC-554
  Scenario: Respetar incluidos y preservar pedidos
    Given grupos con cardinalidades, incluidos y componentes válidos
    When se previsualiza y acepta una selección válida
    Then Python calcula precio adicional y consumo según orden de selección
    And el pedido conserva receta y precios congelados
    And editar catálogo después no modifica ese snapshot

  @BDD-SC-555
  Scenario: Copiar con revisión del destino
    Given configuraciones y versiones leídas de origen y destino autorizados
    When confirma reemplazar la configuración seleccionable del destino
    Then el comando valida todos los componentes y copia grupos con IDs propios
    And no copia precio base, receta, combo fijo ni disponibilidad
    And una relación prohibida rechaza toda la copia

  @BDD-SC-556
  Scenario: Resolver copia concurrente e idempotencia sin mezcla
    Given una copia con versiones y clave de comando
    When otro escritor cambia origen o destino antes de aplicarla
    Then la copia falla por conflicto sin grupos parciales
    And se conserva captura para revisar versiones
    When se repite una copia aplicada con misma clave y carga autorizadas
    Then devuelve el resultado original sin otra versión

  @BDD-SC-557
  Scenario: Distinguir comentario, componente y combo fijo
    Given el editor de un producto
    When se configura un comentario de preparación
    Then no produce inventario ni se convierte en componente
    And componentes consumibles exigen producto y receta efectivos
    And combo fijo conserva su escritor separado
    And no se adopta máximo cero como infinito ni anidamiento del tutorial
```
