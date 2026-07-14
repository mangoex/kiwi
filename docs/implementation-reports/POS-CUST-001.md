# POS-CUST-001 — identificación telefónica de clientes en checkout

## Problema observado

El checkout permitía texto libre por nombre, correo o teléfono. Esto producía una experiencia
ambigua: un nombre sin coincidencias dejaba un formulario de cobro genérico, no ofrecía registrar
al cliente y el tipo de pedido quedaba oculto detrás del modal. Los domicilios sólo aparecían si el
usuario había elegido previamente A domicilio fuera del modal.

La revisión estructural de `CLIENTES.XLS` confirmó 33,219 filas y sólo tres columnas: `CLAVE`,
`NOMBRE` y `DIRECCION`. No existe una columna telefónica. Por ello no es válido convertir la clave
heredada en teléfono ni afirmar que los clientes importados ya pueden localizarse por número.

## Solución

- El checkout usa un teléfono mexicano válido como criterio exacto y primario.
- No ejecuta solicitudes con números incompletos; acepta 10 dígitos nacionales o 12 con prefijo
  `52`.
- La consulta usa `phone`, `branch_id` canónico y `limit`, con debounce y cancelación.
- Si hay coincidencias, muestra cada nombre por separado con teléfono y cantidad de domicilios.
- Si no hay coincidencias, permite registrar nombre, correo opcional y el teléfono ya capturado.
- El cliente creado queda seleccionado sin perder carrito, tipo de pedido ni total.
- El tipo de pedido se puede confirmar dentro del modal.
- Al elegir A domicilio se muestran los domicilios activos como tarjetas legibles y se permite
  seleccionar uno o agregar otro.
- El importador mantiene `CLAVE` como evidencia de origen y no la convierte en teléfono.

Los contratos existentes ya soportaban la búsqueda exacta y el alta. `POST /customers` conserva
la auditoría `customer.created`; `POST /customers/{id}/addresses` conserva
`customer.address_added`. No hubo migraciones, dependencias ni modificaciones de datos importados.

## Trazabilidad

- Requisitos: PRD-FR-024, PRD-FR-031, PRD-FR-032, PRD-FR-195 y PRD-FR-198.
- Escenarios: BDD-FEAT-056 y BDD-SC-163 a BDD-SC-167.
- Pruebas: TDD-TS-056, TDD-TC-049,
  `tests/architecture/test_pos_phone_customer_flow.py`,
  `tests/architecture/test_pos_operational_ux.py`,
  `apps/api/tests/test_platform_api.py` y `apps/api/tests/test_legacy_import.py`.

## Evidencia

- `python3 -m pytest`: 129 pruebas aprobadas.
- Pruebas de arquitectura del flujo telefónico: 17 aprobadas junto con POS-UX-001.
- `python3 -m ruff check apps/api tests`: sin hallazgos.
- `pnpm typecheck`: UI, Admin, POS y KDS aprobados.
- Builds de producción de POS, Admin y KDS aprobados.
- `git diff --check`: limpio.
- Node local 20 muestra la advertencia esperada frente al requisito 22; CI utiliza Node 22.

## Operación y privacidad

- Los errores de búsqueda y alta se presentan en español sin imprimir el teléfono en logs.
- Los datos del Excel se usaron sólo para validar estructura y conteos; no se agregaron al commit.
- Los clientes heredados sin teléfono requieren captura humana posterior; el sistema no inventa
  ni deriva números desde `CLAVE`.
