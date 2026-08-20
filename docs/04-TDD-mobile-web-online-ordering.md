# TDD: Pruebas de Pedidos en Línea y Autoservicio Web Móvil

## TDD-TS-095

### TDD-TC-164
- Archivo: `apps/api/tests/test_platform_api.py::test_public_online_ordering_workflow`
- Propósito: Verificar flujo completo de consulta de catálogo público y creación de pedidos con cálculo exacto de precios.

### TDD-TC-165
- Archivo: `apps/api/tests/test_platform_api.py::test_public_online_order_without_active_shift_or_missing_price`
- Propósito: Verificar manejo estricto de precios inexistentes y asociación segura de turnos de caja sin ligar a turnos cerrados.
