# BDD — INV-VIEW-001

Estado: implementación y evidencia local en plan INV-VIEW-2026-10-19; sin acreditar CI o release.
Diseño en SDD §68.

## BDD-FEAT-151 Existencias administrativas con alcance independiente

```gherkin
@PRD-FR-279
Feature: Consultar existencias sin trasladar la operación del POS

  @BDD-SC-723
  Scenario: Administrador corporativo abre todas las sucursales autorizadas
    Given el actor tiene autoridad organizacional y permiso organizacional inventory.read
    And existen Centro y Norte activas con almacenes canónicos
    When abre Existencias
    Then ve Todas las sucursales con filas identificadas por sucursal almacén insumo y unidad
    And el mismo insumo sin movimientos en Norte aparece con cero
    And no ve artículos locales de Centro como aplicables a Norte

  @BDD-SC-724
  Scenario: Filtrar Norte conserva la operación en Centro
    Given el POS tiene sucursal Centro y un borrador recuperable
    When el administrador consulta Norte y vuelve a Todas las sucursales
    Then active_branch workspace caja turno carrito y borrador conservan sus valores
    And no se envía un comando de selección o reemisión POS por cambiar el filtro
    And el filtro funciona con ambos flags de movilidad apagados

  @BDD-SC-725
  Scenario: La lectura local no se convierte en acceso corporativo
    Given un actor tiene inventory.read únicamente en Centro
    When solicita organization u otra sucursal manipulando URL o almacenamiento
    Then el servidor rechaza el alcance sin entregar filas ni conteos ajenos
    And una lectura legítima de Centro sigue disponible

  @BDD-SC-726
  Scenario: Separar existencia y reservas sin cambiar el ledger
    Given un insumo tiene saldo inicial de 10.000000 kilos en Centro
    And tiene una reserva pendiente de 3.000000 kilos
    When se consulta Existencias
    Then muestra existencia teórica 10.00 reserva pendiente 3.00 y disponible 7.00
    When producción libera esa reserva y consume 3.000000 kilos
    Then muestra existencia teórica 7.00 reserva pendiente 0.00 y disponible 7.00
    And la lectura no escribe movimientos ni adquiere locks operativos de inventario

  @BDD-SC-727
  Scenario: Filtrar y paginar sin sumar unidades distintas
    Given hay insumos en kilos litros y piezas con disponible positivo cero y negativo
    When busca por nombre o SKU y filtra unidad y disponibilidad
    Then recibe filas y conteos del conjunto filtrado completo con orden estable
    And distingue conteo de filas de número de insumos distintos
    And no ve una suma de cantidades ni valoración monetaria
    And una cantidad negativa conserva su signo

  @BDD-SC-728
  Scenario: Una respuesta tardía no mezcla sucursales ni identidades
    Given una consulta de Centro tarda mientras el usuario solicita Norte
    When responde primero Norte y luego Centro
    Then permanece Norte con su fecha de consulta
    When cambia la identidad o pierde la autoridad
    Then se ocultan los datos anteriores y se revalida el alcance

  @BDD-SC-729
  Scenario: Fallo e inconsistencia no se presentan como inventario vacío
    Given existe una sucursal activa sin almacén canónico válido o falla la base
    When se consulta Todas las sucursales
    Then se informa el fallo sin presentar ceros ni un total parcial como completo
    And una respuesta correcta sin coincidencias muestra un vacío distinto del error
    And desconexión o sesión vencida no muestran datos como actuales
```

## BDD-FEAT-152 Umbrales con destino explícito y presentación legible

```gherkin
@PRD-FR-280
Feature: Consultar y editar umbrales sin cambiar la sucursal del POS

  @BDD-SC-730
  Scenario: Abrir umbrales del destino de una fila
    Given el administrador consulta el insumo Aceituna en Norte
    When abre Umbrales con permiso vigente
    Then el modal identifica Norte su almacén y su unidad base
    And compara mínimos y máximos contra existencia teórica antes de reservas
    And Todas las sucursales no permite guardar una edición masiva

  @BDD-SC-731
  Scenario: Conflicto o cambio de filtro no redirige una edición
    Given está abierto un modal de Norte con versión esperada
    When cambia el filtro o otro actor modifica el umbral
    Then el destino del modal no cambia a otra sucursal
    And el conflicto exige refrescar y revisar sin sobrescribir automáticamente
    And la API rechaza un destino sin permiso aunque el navegador muestre la acción

  @BDD-SC-732
  Scenario: Mostrar y capturar cantidades preservando precisión
    Given hay un umbral legacy de 12.345678
    When se abre y guarda sin cambiar ese campo
    Then la presentación usa 12.35 y el valor original sigue siendo 12.345678
    When se captura explícitamente 12.345 como valor nuevo
    Then aparece error de máximo dos decimales y no se envía la escritura
    And una captura válida mantiene mínimo no negativo y máximo mayor o igual al mínimo

  @BDD-SC-733
  Scenario: Fechas cantidades y estados se entienden en pantalla estrecha
    Given se consulta inventario a 390 1024 o 1440 píxeles
    When se recorre tabla filtros y modal con teclado
    Then los campos tienen etiquetas foco visible y mensajes asociados
    And las cantidades tienen dos decimales sin recalcular con el valor mostrado
    And las fechas son legibles con su zona y no un timestamp ISO partido
    And Sin umbrales se distingue de disponible cero y del error de consulta

  @BDD-SC-734
  Scenario: Guardar y retirar configuración preserva inventario e historial
    Given existe un umbral y movimientos históricos en Norte
    When un actor autorizado guarda o retira su configuración con versión vigente
    Then cambia sólo el umbral de Norte y conserva la auditoría vigente
    And movimientos existencias reservas costos y el umbral de Centro permanecen intactos
```
