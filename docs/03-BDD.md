# BDD — Behavior-Driven Development

## Convenciones

- Lenguaje Gherkin.
- Cada escenario debe incluir identificador.
- Etiquetas obligatorias: requisito, módulo, prioridad y tipo.
- Los escenarios críticos deben automatizarse.
- No describir implementación interna en BDD.

## BDD-FEAT-001 Operación offline de pedidos

```gherkin
@PRD-FR-180 @PRD-FR-182 @critical @offline
Feature: Operación de pedidos sin internet

  Background:
    Given la sucursal tiene un gateway local activo
    And el catálogo vigente está sincronizado
    And la caja tiene un turno abierto

  @BDD-SC-001
  Scenario: Crear un pedido mientras la sucursal no tiene internet
    Given la conexión con la nube está interrumpida
    When el cajero crea y acepta un pedido para recoger
    Then el gateway asigna un identificador único
    And el pedido aparece en el KDS local
    And el comando queda pendiente de sincronización
    And el usuario ve que el pedido está operando en modo offline

  @BDD-SC-002
  Scenario: Sincronizar un pedido creado offline
    Given existe un pedido local pendiente de sincronización
    When la conexión con la nube se recupera
    Then el gateway envía el comando una sola vez de forma efectiva
    And la nube registra el pedido
    And el gateway recibe confirmación
    And el pedido conserva su identidad y folio
```

## BDD-FEAT-002 Idempotencia

```gherkin
@PRD-FR-022 @PRD-FR-187 @critical
Feature: Evitar pedidos duplicados

  @BDD-SC-003
  Scenario: Reintento del mismo webhook externo
    Given la plataforma externa envió un pedido con identificador externo X
    And el pedido X ya fue aceptado
    When el mismo webhook se recibe nuevamente
    Then el sistema responde de forma idempotente
    And no crea un segundo pedido
    And registra el reintento
```

## BDD-FEAT-003 Producción por estaciones

```gherkin
@PRD-FR-011 @PRD-FR-040 @PRD-FR-043 @production
Feature: Separación de componentes por estación

  @BDD-SC-004
  Scenario: Un combo genera tareas en cocina y bebidas
    Given un combo contiene una hamburguesa asignada a cocina
    And contiene una bebida asignada a bebidas
    When el pedido se envía a producción
    Then cocina recibe la tarea de hamburguesa
    And bebidas recibe la tarea de bebida
    And empaque no puede liberar el pedido hasta que ambas tareas terminen
```

## BDD-FEAT-004 Inventario reservado y consumido

```gherkin
@PRD-FR-063 @PRD-FR-064 @inventory @critical
Feature: Reserva y consumo de inventario

  @BDD-SC-005
  Scenario: Reservar al aceptar y consumir al producir
    Given existe inventario disponible para una receta
    When el pedido es aceptado
    Then el sistema crea reservas por los componentes requeridos
    And la existencia física no disminuye todavía
    When la producción es confirmada
    Then las reservas se convierten en movimientos de consumo
    And la existencia disminuye
```

## BDD-FEAT-005 Cancelación

```gherkin
@PRD-FR-028 @PRD-FR-065 @PRD-FR-066 @critical
Feature: Cancelación de pedido

  @BDD-SC-006
  Scenario: Cancelar antes de producir
    Given un pedido aceptado tiene inventario reservado
    And ningún componente ha sido producido
    When un usuario autorizado cancela el pedido
    Then las reservas se liberan
    And no se genera merma

  @BDD-SC-007
  Scenario: Cancelar después de producir
    Given un pedido tiene componentes confirmados como producidos
    When un usuario autorizado cancela el pedido
    Then el sistema solicita clasificar recuperación o merma
    And genera movimientos compensatorios
    And conserva auditoría
```

## BDD-FEAT-006 Recetas multinivel

```gherkin
@PRD-FR-080 @PRD-FR-081 @costing
Feature: Recetas y subrecetas

  @BDD-SC-008
  Scenario: Calcular costo de producto con aderezo por lote
    Given una ensalada utiliza una porción de aderezo
    And el aderezo tiene una receta vigente
    When se calcula el costo estándar de la ensalada
    Then el costo del aderezo se obtiene recursivamente
    And se suma al resto de componentes

  @BDD-SC-009
  Scenario: Rechazar ciclo de recetas
    Given la receta A contiene la receta B
    When se intenta agregar A como componente de B
    Then el sistema rechaza el cambio
    And explica que se generaría un ciclo
```

## BDD-FEAT-007 Producción por lote

```gherkin
@PRD-FR-083 @PRD-FR-085 @PRD-FR-087
Feature: Producción de aderezos por lote

  @BDD-SC-010
  Scenario: Registrar rendimiento real menor al esperado
    Given una orden planea producir 10 litros de aderezo
    When el operador registra 9.4 litros reales
    Then el sistema calcula la diferencia de rendimiento
    And registra la merma real
    And calcula el costo real por litro
    And crea un lote con caducidad
```

## BDD-FEAT-008 Caja

```gherkin
@PRD-FR-050 @PRD-FR-056 @PRD-FR-057 @cash @critical
Feature: Turno y corte de caja

  @BDD-SC-011
  Scenario: Cerrar turno con diferencia
    Given una caja tiene ventas y movimientos registrados
    When el cajero captura el efectivo contado
    Then el sistema calcula el efectivo esperado
    And muestra la diferencia
    And requiere autorización si supera el límite
    And al cerrar genera un corte inmutable
```

## BDD-FEAT-009 Pagos inmutables

```gherkin
@PRD-FR-054 @cash
Feature: Corrección de pagos

  @BDD-SC-012
  Scenario: Corregir una forma de pago confirmada
    Given un pago fue confirmado como tarjeta
    When un usuario autorizado detecta que debía ser efectivo
    Then el sistema no edita el pago original
    And crea movimientos compensatorios
    And registra motivo y autorización
```

## BDD-FEAT-010 Compras XML

```gherkin
@PRD-FR-102 @PRD-FR-103 @purchasing
Feature: Importación de XML de proveedor

  @BDD-SC-013
  Scenario: Importar CFDI nuevo
    Given un XML válido corresponde a la razón social de la sucursal
    When el usuario lo importa
    Then el sistema extrae proveedor, conceptos e impuestos
    And propone equivalencias
    And permite crear recepción y cuenta por pagar

  @BDD-SC-014
  Scenario: Rechazar XML duplicado
    Given el UUID fiscal ya fue importado
    When el usuario intenta importar el mismo XML
    Then el sistema lo rechaza
    And muestra la importación original
```

## BDD-FEAT-011 Traspasos

```gherkin
@PRD-FR-069 @inventory
Feature: Traspaso entre sucursales

  @BDD-SC-015
  Scenario: Confirmar recepción parcial
    Given una sucursal origen envió 20 unidades
    When la sucursal destino recibe 19
    Then el sistema registra salida de 20 en origen
    And entrada de 19 en destino
    And mantiene una diferencia pendiente de conciliación
```

## BDD-FEAT-012 Optimización de reparto

```gherkin
@PRD-FR-123 @PRD-FR-124 @delivery
Feature: Optimización simultánea

  @BDD-SC-016
  Scenario: Agrupar pedidos compatibles
    Given existen tres pedidos próximos en ubicación
    And dos estarán listos dentro de la misma ventana
    And hay un repartidor con capacidad suficiente
    When el despachador solicita optimización
    Then el sistema propone una ruta con los pedidos compatibles
    And muestra secuencia y ETA
    And deja visible cualquier pedido no asignado

  @BDD-SC-017
  Scenario: Operar manualmente sin proveedor de rutas
    Given el proveedor de optimización no responde
    When el despachador abre el tablero
    Then puede asignar pedidos manualmente
    And el sistema registra que la asignación fue manual
```

## BDD-FEAT-013 Impresión

```gherkin
@PRD-FR-046 @PRD-FR-048 @printing
Feature: Impresión automática

  @BDD-SC-018
  Scenario: Reintentar una impresión fallida
    Given una comanda fue enviada a una impresora sin papel
    When el agente detecta el error
    Then el trabajo queda en estado fallido o reintentable
    And no se duplica silenciosamente
    When la impresora vuelve a estar disponible
    Then un usuario puede reintentar
    And el sistema conserva el historial
```

## BDD-FEAT-014 Facturación y exportación

```gherkin
@PRD-FR-160 @PRD-FR-164 @exports
Feature: Exportación de tickets

  @BDD-SC-019
  Scenario: Crear lote de exportación individual
    Given existen tickets elegibles de una razón social
    When el usuario crea un lote
    Then el sistema genera documentos, conceptos, clientes y pagos
    And marca los tickets como incluidos
    And evita incluirlos en otro lote activo

  @BDD-SC-020
  Scenario: Reexportar con autorización
    Given un lote fue rechazado por el sistema contable
    When un usuario autorizado corrige el layout
    Then el sistema crea una nueva versión de exportación
    And conserva el archivo anterior
    And registra motivo y usuario
```

## BDD-FEAT-015 Permisos

```gherkin
@PRD-FR-005 @security
Feature: Permisos por sucursal

  @BDD-SC-021
  Scenario: Impedir ajuste de inventario a cajero
    Given un usuario tiene rol de cajero
    When intenta crear un ajuste de inventario
    Then el sistema rechaza la operación
    And registra el intento
```

## BDD-FEAT-016 Conectividad externa

```gherkin
@PRD-FR-189 @offline
Feature: Continuidad de canales externos

  @BDD-SC-022
  Scenario: Continuar con enlace de respaldo
    Given la conexión principal falla
    And el enlace 4G está disponible
    When llega un pedido externo
    Then el pedido se entrega a la sucursal
    And el sistema informa que opera con respaldo

  @BDD-SC-023
  Scenario: Pérdida total de conectividad
    Given fallan la conexión principal y el respaldo
    When la nube detecta que la sucursal no confirma recepción
    Then intenta pausar la sucursal en canales compatibles
    And alerta a operación corporativa
    And la sucursal continúa con pedidos locales
```

## Regla de expansión

Cada historia nueva deberá incluir:

- escenario feliz,
- validaciones,
- permisos,
- fallo de proveedor,
- reintento,
- offline cuando aplique,
- auditoría,
- reversión o compensación,
- concurrencia cuando aplique.
