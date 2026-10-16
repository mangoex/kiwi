# BDD - Liquidación de efectivo por repartidor

## BDD-FEAT-148 Recepción agrupada de cobros a domicilio

```gherkin
@PRD-FR-059 @PRD-FR-129 @cash @delivery @R3
Feature: Cajero recibe el efectivo cobrado por un repartidor

  @BDD-SC-708
  Scenario: El filtro de repartidor depende del servicio a domicilio
    Given el Cajero consulta Pedidos de su sucursal
    When selecciona el servicio A domicilio
    Then aparece el selector de Repartidor
    And al elegir uno se muestran sus pedidos asignados
    And otro servicio limpia y oculta el filtro y la selección agrupada

  @BDD-SC-709
  Scenario: Sólo se seleccionan cobros en efectivo pendientes
    Given el repartidor tiene pedidos cash pendientes, pagados, cancelados y no cash
    When el Cajero consulta sus pedidos
    Then sólo los cash pendientes no cancelados ni cerrados son seleccionables
    And puede seleccionar uno, varios o todos los elegibles visibles
    And la interfaz suma cantidad e importe en centavos sin redondeo del navegador

  @BDD-SC-710
  Scenario: Liquidación exacta confirma varios pagos atómicamente
    Given un turno OPEN en la caja seleccionada
    And dos pedidos elegibles del mismo repartidor y sucursal
    When el Cajero confirma la recepción del total exacto con una clave idempotente
    Then se crea una liquidación inmutable enlazada a dos pagos cash confirmados
    And los pedidos aparecen pagados sin cambiar su estado de cocina o entrega
    And el efectivo esperado del turno aumenta exactamente por el total liquidado

  @BDD-SC-711
  Scenario: Un pedido inválido revierte el lote completo
    Given dos pedidos seleccionados y uno ya fue pagado o dejó de ser elegible
    When el Cajero intenta liquidar el lote
    Then la operación falla con conflicto estable
    And no crea liquidación, pagos, snapshots, eventos ni auditoría parcial

  @BDD-SC-712
  Scenario: Reintentar la misma liquidación no duplica efectivo
    Given una liquidación confirmada cuya respuesta no llegó al navegador
    When el Cajero reintenta la misma intención con la misma clave y cuerpo
    Then obtiene la respuesta persistida
    And no se crean pagos ni liquidaciones adicionales
    But reutilizar la clave con otro repartidor, caja o conjunto de pedidos falla

  @BDD-SC-713
  Scenario: Alcance, caja y pertenencia fallan cerrado
    Given pedidos de otra sucursal, otro repartidor, sin asignación o sin turno OPEN
    When se intenta incluirlos en una liquidación
    Then el sistema rechaza todo el lote
    And no revela ni modifica pedidos fuera del alcance autorizado

  @BDD-SC-714
  Scenario: Un traslado de repartidor no deja deuda histórica huérfana
    Given un repartidor tiene pedidos cash pendientes asignados en la sucursal Centro
    And después el repartidor cambia a otra sucursal o queda inactivo
    When el Cajero consulta y liquida la deuda en Centro
    Then el repartidor sigue disponible como candidato histórico en Centro
    And la deuda se liquida contra la asignación original sin trasladar los pedidos
```
