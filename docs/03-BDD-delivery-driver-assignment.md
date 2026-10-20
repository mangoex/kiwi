# BDD - Asignación de repartidor desde el POS

## BDD-FEAT-071 Repartidor de la sucursal para pedidos a domicilio

```gherkin
@PRD-FR-211 @pos @delivery @drivers
Feature: Cajero asigna un repartidor al pedido a domicilio

  @BDD-SC-243
  Scenario: Cobro conserva el tipo seleccionado previamente
    Given un Cajero que seleccionó A domicilio en la cuenta
    When abre Cobrar pedido
    Then el modal no vuelve a mostrar controles de tipo de pedido
    And conserva cliente y domicilio seleccionados

  @BDD-SC-244
  Scenario: Selector muestra únicamente repartidores disponibles de la sucursal
    Given un pedido a domicilio en la sucursal Centro
    And existen repartidores activos e inactivos en varias sucursales
    When el Cajero selecciona Asignar repartidor
    Then sólo ve repartidores activos de Centro
    And puede seleccionar uno antes de guardar

  @BDD-SC-245
  Scenario: Otro tipo de pedido no presenta asignación
    Given un pedido En sucursal o Para llevar
    When el Cajero abre Cobrar pedido
    Then no aparece Asignar repartidor
    And enviar driver_id para ese pedido es rechazado

  @BDD-SC-246
  Scenario: Crear pedido registra la asignación completa
    Given un pedido a domicilio con cliente, domicilio y repartidor válido
    When el Cajero guarda el pedido
    Then pedido y asignación se crean en una sola transacción
    And la asignación congela repartidor, pedido, cliente, domicilio, total, moneda y cantidades
    And se crean evento de pedido y auditoría de asignación

  @BDD-SC-247
  Scenario: Administrador consulta historial por repartidor
    Given un repartidor con pedidos asignados
    When el Administrador abre su historial
    Then ve folio, cliente, importe, líneas, unidades, estado y fecha de cada pedido
    And desactivar el repartidor no elimina asignaciones anteriores

  @BDD-SC-735
  Scenario: Aceptación web crea pedido y asignación en una transacción
    Given una intención PENDING_REVIEW de tipo A domicilio
    And un repartidor activo de la misma sucursal
    When el Cajero lo selecciona y acepta el pedido web
    Then el pedido operativo y su única asignación quedan confirmados juntos
    And un repartidor inactivo, ajeno o inexistente no deja pedido ni efectos operativos parciales

  @BDD-SC-736
  Scenario: Pedido aceptado sin repartidor recibe su primera asignación
    Given un pedido A domicilio aceptado, todavía no despachado y sin asignación
    When el Cajero selecciona un repartidor activo de la sucursal desde el detalle de Pedidos
    Then se crea una asignación inmutable con evento y auditoría
    And repetir el mismo repartidor devuelve la misma asignación sin duplicarla
    But elegir otro repartidor no sobrescribe la historia existente

  @BDD-SC-737
  Scenario: Baja concurrente del repartidor no deja una asignación obsoleta
    Given un pedido A domicilio elegible y un repartidor activo de su sucursal
    When la baja del repartidor compite con la primera asignación
    Then ambas operaciones se serializan sobre el registro del repartidor
    And si la baja confirma primero la asignación falla sin evento ni auditoría parcial
    And si la asignación confirma primero conserva su snapshot histórico

  @BDD-SC-738
  Scenario: Despacho concurrente no interbloquea la primera asignación
    Given un pedido A domicilio listo y todavía sin repartidor
    When iniciar reparto compite con su primera asignación
    Then ambas operaciones respetan el orden de bloqueo sucursal, pedido y repartidor
    And si iniciar reparto confirma primero la asignación falla por estado sin efecto parcial
```
