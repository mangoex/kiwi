# POS-UX-001 — POS operativo en español, clientes, domicilios e inventario

## Problema observado

El POS mezclaba etiquetas en inglés, mostraba controles sin operación real y no resolvía el flujo
de entrega: el buscador no consultaba clientes de forma remota, los domicilios confirmados no se
presentaban correctamente y los domicilios libres de la importación no tenían una ruta segura de
captura. Inventario presentaba una tabla densa, traducía incompletamente los tipos y aplicaba una
señal visual de stock bajo sin una regla de dominio.

## Solución

- El checkout usa exclusivamente `session.active_branch.id` para productos, modificadores,
  clientes, domicilios y pedidos; la configuración local se conserva sólo para `pos_register_id`.
- La búsqueda remota de clientes inicia con dos caracteres, aplica debounce de 300 ms, cancela la
  solicitud anterior y consulta nombre, correo o teléfono mediante `q` y paginación.
- El cliente seleccionado vive separado de los resultados. Al cambiarlo se limpia el domicilio
  anterior y se selecciona el predeterminado o el único domicilio activo.
- El checkout permite crear un domicilio estructurado sin perder el carrito. Incluye entrecalles,
  referencias e instrucciones de entrega, envía el alcance canónico y selecciona el domicilio
  recién guardado.
- El domicilio heredado se expone sólo como `legacy_address_reference`. La persona puede copiarlo
  explícitamente al campo Referencias, pero el sistema nunca lo divide ni lo usa automáticamente
  como domicilio operativo.
- El backend devuelve sólo domicilios activos y rechaza el alta de un domicilio si el cliente no
  pertenece a la sucursal autorizada. La referencia heredada se obtiene por lote y sucursal sin
  exponer `raw_payload`.
- Inventario consulta solamente el contrato de existencia teórica de la sucursal, presenta
  resumen, búsqueda, filtros, paginación, almacén y último movimiento, y distingue positivo, cero
  y negativo sin umbral arbitrario.
- Se retiraron controles ficticios y las cadenas operativas se presentan en español de México.

La creación de domicilios conserva la auditoría existente `customer.address_added`. No hubo
migraciones, dependencias, cambios de saldos ni movimientos de inventario.

## Trazabilidad

- Requisitos: PRD-FR-019, PRD-FR-020, PRD-FR-024, PRD-FR-031, PRD-FR-032, PRD-FR-034,
  PRD-FR-070, PRD-FR-195 y PRD-NFR-018.
- Escenarios: BDD-FEAT-055 y BDD-SC-156 a BDD-SC-162.
- Pruebas: TDD-TS-055, TDD-TC-048, `apps/api/tests/test_platform_api.py`,
  `apps/api/tests/test_legacy_import.py` y
  `tests/architecture/test_pos_operational_ux.py`.

## Evidencia

- `python3 -m pytest`: 122 pruebas aprobadas.
- `python3 -m pytest tests/architecture/test_pos_operational_ux.py -q`: 10 aprobadas.
- `python3 -m ruff check apps/api tests`: sin hallazgos.
- `pnpm typecheck`: UI, Admin, POS y KDS aprobados.
- Builds de producción de Admin, POS y KDS aprobados.
- `git diff --check`: limpio.
- Node local 20 muestra la advertencia esperada frente al requisito 22; CI utiliza Node 22.

## Operación y errores

- Los fallos de catálogo, búsqueda, inventario y alta de domicilio muestran mensajes en español.
- Inventario permite reintentar su consulta sin recargar la aplicación completa.
- Un pedido a domicilio no puede cobrarse sin cliente y domicilio activo.
- No se registran en logs domicilios heredados, payloads crudos ni datos personales de búsqueda.
