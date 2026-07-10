# BDD - POS, caja y KDS inicial

## BDD-FEAT-021 Caja minima

```gherkin
@PRD-FR-050 @PRD-FR-051 @PRD-FR-057 @cash @phase1
Feature: Turno de caja minimo

  @BDD-SC-028
  Scenario: Abrir y consultar turno de caja
    Given existe un usuario Cajero autenticado y asignado a Sucursal Piloto
    And tiene permiso de abrir caja
    When el cajero selecciona la sucursal asignada y abre caja con fondo inicial
    Then el sistema crea un turno abierto
    And asocia el turno a la sucursal, caja registradora y cajero
    And conserva fecha UTC de apertura
    And evita abrir otro turno simultaneo para la misma caja
    And registra auditoria con el cajero como actor

  @BDD-SC-066
  Scenario: Configurar POS por cuenta y sucursal
    Given un administrador crea una cuenta POS con rol Cajero
    And asigna esa cuenta a una sucursal operativa
    When el usuario POS inicia sesion
    Then el POS preselecciona la sucursal asignada
    And no permite abrir caja en una sucursal fuera de su alcance
    When el cajero abre o cierra caja
    Then el panel Admin muestra la notificacion con cajero, sucursal, caja y hora
    And las ventas, inventario y movimientos quedan asociados a esa sucursal

  @BDD-SC-061
  Scenario: Bloquear apertura de caja sin permiso o fuera de sucursal
    Given existe un usuario Cajero autenticado en Sucursal Piloto
    When intenta abrir caja en otra sucursal
    Then el sistema rechaza la operacion por alcance de sucursal
    And registra auditoria del intento denegado
    When un usuario sin permiso intenta abrir caja
    Then el sistema rechaza la operacion por falta de permiso

  @BDD-SC-029
  Scenario: Cerrar turno sin ventas complejas
    Given existe un turno abierto
    When el cajero cierra el turno
    Then el sistema marca el turno como cerrado
    And conserva fecha UTC de cierre
    And registra auditoria con el cajero como actor
```

## BDD-FEAT-022 Pedido local minimo

```gherkin
@PRD-FR-020 @PRD-FR-025 @PRD-FR-027 @PRD-FR-030 @orders @phase1
Feature: Pedido local desde POS

  @BDD-SC-030
  Scenario: Crear pedido local con producto del catalogo
    Given existe un Cajero autenticado con permiso de operar POS
    And existe un turno de caja abierto para su sucursal y caja
    And existe un producto disponible con precio vigente
    When el cajero crea un pedido con ese producto desde el POS
    Then el sistema crea un pedido aceptado
    And asocia el pedido a la sucursal, caja y turno abierto enviados por el POS
    And calcula total en centavos
    And asigna folio local
    And registra evento de pedido

  @BDD-SC-062
  Scenario: Cobrar pedido local con total del backend
    Given existe un pedido aceptado creado desde POS
    And el backend devolvio el total del pedido
    When el cajero confirma el pago por el total devuelto
    Then el sistema registra el pago confirmado
    And cierra el pedido
    And el panel Admin refleja la venta y el pago

  @BDD-SC-063
  Scenario: Bloquear pedido y pago sin permiso
    Given existe un usuario autenticado sin permisos POS
    When intenta crear un pedido desde POS
    Then el sistema rechaza la operacion por falta de permiso
    When intenta confirmar un pago
    Then el sistema rechaza la operacion por falta de permiso
```

## BDD-FEAT-023 KDS inicial

```gherkin
@PRD-FR-040 @PRD-FR-041 @PRD-FR-043 @production @phase1
Feature: Tareas KDS desde pedido local

  @BDD-SC-031
  Scenario: Pedido aceptado genera tarea de produccion
    Given existe un pedido aceptado
    When el producto tiene estacion asignada
    Then el sistema crea una tarea KDS pendiente para esa estacion
    And la tarea puede avanzar a en proceso
    And la tarea puede completarse
```
