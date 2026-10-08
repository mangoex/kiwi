# BDD — Gastos operativos independientes de inventario

## BDD-FEAT-129 Conceptos de gasto y registro por sucursal

EXP-001 implementado localmente. Accesos definidos en PRD-FR-262/263; evidencia y límites en el plan EXP-001.

```gherkin
@PRD-FR-262 @PRD-FR-263 @PRD-FR-264 @expenses
Feature: Registrar gastos operativos sin compras ni inventario

  @BDD-SC-599
  Scenario: Catálogo propio conserva historia
    Given un Dueño autorizado crea el concepto Luz
    When renombra o archiva el concepto después de confirmar un gasto
    Then el gasto conserva código y nombre snapshot originales
    And el concepto archivado no permite nuevas confirmaciones
    And no se crea proveedor ni concepto de caja manual ni movimiento financiero

  @BDD-SC-600
  Scenario: Borrador de gasto sin dependencias de compra
    Given una sucursal autorizada y un concepto activo
    And no existen insumos ni presentaciones ni proveedores configurados
    When un usuario autorizado guarda un gasto con fecha, importe y método de pago
    Then se crea un borrador editable con versión y folio interno
    And no cambia caja, estadísticas confirmadas, inventario o costo
    And la API rechaza campos de compra o inventario ajenos a este contrato

  @BDD-SC-601
  Scenario: Confirmar efectivo afecta sólo caja y estadísticas
    Given un gasto de Luz por 300 pesos y efectivo esperado de 2000 pesos
    And la caja revisada pertenece a la sucursal y su turno permanece abierto
    And el actor tiene permisos y referencia y evidencia del egreso
    When confirma el gasto
    Then se registra un retiro de 300 pesos enlazado al gasto
    And el efectivo esperado queda en 1700 pesos
    And las estadísticas registran un gasto de 300 pesos una sola vez
    And permanecen idénticos inventario, costos y catálogo e historial de proveedores

  @BDD-SC-602
  Scenario: Otro medio registra gasto sin caja
    Given un gasto por transferencia, tarjeta u otro medio permitido
    And no hay caja ni turno abierto
    When el actor autorizado confirma el pago registrado
    Then el gasto integra estadísticas por el importe completo
    And no crea retiro ni requiere permisos de movimiento de caja
    And no crea recepción ni altera inventario, costo o proveedores
    And no ejecuta transferencia bancaria ni genera una cuenta por pagar

  @BDD-SC-603
  Scenario: Autoridad y contexto se validan antes de actuar
    Given un usuario sólo autorizado en la sucursal A
    When solicita cajas, conceptos o documentos de otra organización o confirma con una caja ajena
    Then no obtiene datos ni genera efectos fuera de su alcance
    And sólo permiso de compra o de retiro no concede permiso para registrar gastos
    And cambiar contexto en UI descarta respuestas viejas sin reasignar un comando ya enviado
    And sin turno o permiso de retiro se permite borrador pero no confirmación cash
    And un turno cerrado y reemplazado no se sustituye silenciosamente

  @BDD-SC-604
  Scenario: Reintentos y competencia no duplican gasto
    Given una confirmación cuya respuesta puede perderse
    When se reintenta la misma intención o compiten dos claves para el mismo documento
    Then como máximo una transición, un retiro y un evento positivo quedan confirmados
    And una clave con otra intención se rechaza
    And cierre, edición, archivo de concepto o cancelación concurrentes tienen un resultado consistente
    And un fallo tras cualquier escritura revierte movimiento, estado, auditoría y recibo

  @BDD-SC-605
  Scenario: Anulación conserva historia y compensación
    Given un gasto confirmado en efectivo con turno original abierto
    And un Dueño autorizado acredita la devolución física con motivo y evidencia
    When anula el gasto
    Then se conserva el retiro original y se crea un único depósito compensatorio enlazado
    And estadísticas agregan una reversa en la fecha de anulación sin borrar el evento original
    And no cambia inventario ni costos
    But con turno original cerrado no se anula ni compensa en otra caja
    And anular un gasto no efectivo sólo revierte su registro sin mover caja o banco
    And descartar un borrador no genera reversa ni movimiento

  @BDD-SC-606
  Scenario: Estadísticas separan medios y evitan doble conteo
    Given gastos confirmados de Luz por 300 pesos en efectivo y Renta por 1000 por transferencia
    And existen además compras y retiros manuales históricos
    When consulta estadísticas de Gastos de la sucursal para el periodo
    Then el total operativo es 1300 pesos con 300 en efectivo y 1000 en otros medios
    And caja disminuye sólo 300 pesos y sus movimientos enlazados no duplican gastos
    And compras y retiros manuales permanecen identificados aparte en el reporte general
    And filtros y totales abarcan todos los resultados, no sólo la página visible
    And renombrar un concepto no altera historia y un usuario sin reports.expenses.read no consulta estadísticas
```
