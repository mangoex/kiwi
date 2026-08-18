# BDD: Reportes de Conciliación de Corte Diario y Consolidado Multi-Sucursal

## BDD-FEAT-088: Conciliación Diaria de Corte de Sucursal

@BDD-SC-343
Scenario: Generación automática de balance de corte diario
  Given un turno de caja abierto en la sucursal con fondo inicial
  When se consulta el reporte de conciliación diaria para la fecha activa
  Then el sistema calcula las ventas totales con impuestos y desglose por método de pago

@BDD-SC-344
Scenario: Desglose de egresos por compras a proveedores de insumos
  Given compras directas confirmadas y pagadas en efectivo durante el turno
  When se genera el reporte de conciliación de sucursal
  Then cada partida se desglosa por proveedor, monto y folio de compra

@BDD-SC-345
Scenario: Desglose de gastos fijos y sueldos pagados en efectivo
  Given movimientos de caja clasificados con conceptos de gastos operativos
  When se consulta el corte diario
  Then el reporte lista cada tipo de gasto con su observación y monto

@BDD-SC-346
Scenario: Registro de cobros por transferencias y clientes a crédito
  Given pedidos cobrados mediante transferencia SPEI o crédito corporativo
  When se consolida la conciliación del día
  Then el reporte desglosa el cliente, teléfono, ticket y monto

@BDD-SC-347
Scenario: Cálculo exacto de efectivo teórico y sobrante o faltante
  Given el arqueo físico de efectivo registrado al cierre de turno
  When el sistema evalúa la fórmula matemática de conciliación
  Then determina la diferencia exacta en centavos (sobrante, faltante o cuadrada)

## BDD-FEAT-089: Consolidado Multi-Sucursal, Auditoría y Exportación

@BDD-SC-348
Scenario: Consolidación de gastos e ingresos entre múltiples sucursales
  Given movimientos y cortes en múltiples sucursales de la organización
  When el Administrador consulta el consolidado para un rango de fechas
  Then el sistema agrupa los totales acumulados por proveedor y tipo de gasto

@BDD-SC-349
Scenario: Filtro por sucursal individual o toda la cadena
  Given el tablero corporativo de conciliación
  When se selecciona una sucursal específica o todas las sucursales
  Then la vista actualiza los KPIs y tablas en tiempo real

@BDD-SC-350
Scenario: Actualización del estado de auditoría gerencial
  Given un corte diario pendiente de revisión
  When el auditor marca el corte como revisado con una nota
  Then el sistema almacena el usuario auditor, fecha UTC y nota explicativa

@BDD-SC-351
Scenario: Exportación fiel a libro Excel con hojas y fórmulas Kiwi
  Given un periodo mensual seleccionado para una sucursal
  When se solicita la descarga del archivo de conciliación
  Then el backend genera un archivo binario .xlsx con estructura tabular idéntica al formato oficial

@BDD-SC-352
Scenario: Descarga directa desde terminal POS y panel administrativo
  Given un operador autorizado en la interfaz de reportes
  When presiona el botón de exportación a Excel
  Then recibe el stream .xlsx con cabeceras de descarga de adjunto
