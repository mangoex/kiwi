# TDD: Pruebas de Conciliación de Corte Diario y Consolidado Multi-Sucursal

## TDD-TS-093

### TDD-TC-159
- Archivo: `apps/api/tests/test_branch_reconciliation_reports.py::test_daily_reconciliation_calculation_and_balance`
- Propósito: Validar cálculo exacto de ventas, desglose de métodos de cobro, egresos en efectivo, efectivo teórico y sobrante/faltante.

### TDD-TC-160
- Archivo: `tests/frontend/test_reconciliation_reports.mjs::testBranchDailyReconciliationReportComponent`
- Propósito: Verificar componentes de resumen de balance, desglose de partidas y botones en interfaz POS.

## TDD-TS-094

### TDD-TC-161
- Archivo: `apps/api/tests/test_branch_reconciliation_reports.py::test_multi_branch_consolidated_report`
- Propósito: Verificar agrupación consolidada multi-sucursal por proveedor y tipo de gasto en rangos de fecha.

### TDD-TC-162
- Archivo: `apps/api/tests/test_branch_reconciliation_reports.py::test_reconciliation_audit_status_update`
- Propósito: Validar mutación del estado de auditoría gerencial con registro de usuario y nota.

### TDD-TC-163
- Archivo: `apps/api/tests/test_branch_reconciliation_reports.py::test_reconciliation_excel_export`
- Propósito: Validar generación del libro binario Excel `.xlsx` compatible con formato oficial Kiwi.
