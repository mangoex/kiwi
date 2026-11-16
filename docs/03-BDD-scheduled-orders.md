# BDD - Pedidos programados en Caja

## BDD-FEAT-110 Programación de pedidos en Caja con validación de horario y alarma

```gherkin
@PRD-FR-001 @PRD-FR-002 @pos @orders @scheduled
Feature: Programar pedidos en Caja sin enviarlos a cocina ni cobrarlos por adelantado

  @BDD-SC-709
  Scenario: Programar un pedido en caja dentro del horario de la sucursal
    Given que el cajero está en Venta Rápida de una sucursal activa
    And la sucursal está abierta el día y hora seleccionados según branch_operating_hours
    And el pedido cuenta con teléfono de contacto del cliente
    When el cajero selecciona "Programar", captura día y hora y guarda el pedido
    Then el pedido se persiste con estado "SCHEDULED" y cash_shift_id nulo
    And no se crean tareas de producción en KDS
    And no se reservan ni descuentan insumos del inventario
    And no se dispara impresión térmica ni cobro en caja

  @BDD-SC-710
  Scenario: Rechazar pedido programado sin teléfono o fuera de horario de sucursal
    Given que el cajero intenta programar un pedido en caja
    When no proporciona teléfono de contacto
    Then recibe error "scheduled_order_phone_required"
    When proporciona teléfono pero elige una hora en día cerrado o fuera del horario de la sucursal
    Then recibe error "branch_closed_at_scheduled_time"

  @BDD-SC-711
  Scenario: Alarma de 30 minutos y liberación a cocina de pedido programado
    Given que existe un pedido en estado "SCHEDULED" cuya hora programada está dentro de los próximos 30 minutos
    When el cajero consulta el conteo de pendientes o la pestaña "Programados" en Pedidos
    Then scheduled_due_count refleja el pedido en ventana de alarma
    When el cajero presiona "Mandar a cocina ahora" con un turno de caja abierto
    Then el pedido transiciona a "ACCEPTED" y se asocia al cash_shift_id vigente
    And se crean las tareas de producción en KDS y la reserva de inventario

  @BDD-SC-712
  Scenario: Reprogramar o cancelar un pedido programado sin merma
    Given que existe un pedido en estado "SCHEDULED"
    When el cajero lo reprograma a otro horario abierto de la sucursal
    Then scheduled_for se actualiza y queda auditado
    When el cajero cancela el pedido programado
    Then transiciona a "CANCELLED" sin generar merma ni movimientos de inventario
```
