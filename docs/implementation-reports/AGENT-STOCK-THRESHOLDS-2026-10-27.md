# Agent Tools: lectura de umbrales de inventario

## Alcance final

R3 acotado a `GET /api/v1/agent-tools/inventory/stock`. Añade `min_quantity` y
`max_quantity` como cadenas decimales exactas o null. `unit_id` es la unidad base de
existencia y umbrales. Se conserva `agent.inventory.read` y el perfil `inventory`;
no se conceden permisos nuevos ni escritura.

Autoridad: PRD-FR-271, SDD §59.4, BDD-SC-650, TDD-TC-358/360. Los cambios de
especificación, matriz, guía y OpenAPI se limitan a ese contrato. Los únicos ajustes
de la allowlist son las firmas ya existentes de la guía y el OpenAPI modificados;
no se agregan excepciones ni se cambia el scanner.

Se retiraron del diff todas las reparaciones generales de CI, cambios de frontend,
fixtures ajenos y refactors de otros módulos. No hay migraciones, nuevas dependencias,
configuración productiva ni cambios en caja, pagos, costos o movimientos.

## Evidencia y revisión

- RED original: campos ausentes en respuesta/OpenAPI y almacén inactivo devolviendo 200
  en lugar del 503 documentado. La implementación conserva stock/umbrales del almacén
  activo de la organización y sucursal autorizadas.
- Pruebas focales: `test_agent_stock_thresholds.py`, `test_agent_tools.py`,
  `test_agent_tools_contract.py` y `tests/architecture/test_traceability.py`.
  Se verifican nulidad, cero, precisión, paginación, autorización, aislamiento y no escritura.
  Después de reducir el alcance: **31 aprobadas, sin omisiones**, incluidos dos casos PostgreSQL
  (109.81 s). Ruff de `agent_tools.py` y su nueva prueba, y `git diff --check`: aprobados.
- Mypy normal de `agent_tools.py` no aprueba por la dependencia restaurada
  `inventory_ai.py:284`: asignación `dict[str, Any] | None` a `RowMapping`. Ese archivo es
  idéntico a la base y queda fuera del cambio; no se silencia ni se declara aprobado el gate.
- PostgreSQL usa una base local `grokbot_stock_test`, puerto 55439 y esquema aislado por
  caso mediante `GROKBOT_TEST_POSTGRES_URL`; no utiliza datos productivos.
- Auditoría R3 independiente original: sin hallazgos accionables en la lectura de umbrales.
  El seguimiento final confirmó que retirar el alcance ajeno no cambia esa implementación,
  que 23 archivos ajenos vuelven exactamente a la base y que el único runtime modificado es
  `agent_tools.py`. Sin hallazgos accionables.

| Afirmación | Evidencia e intento de refutación | Límite residual |
|---|---|---|
| Sólo devuelve el alcance autorizado | Guardas previas al SELECT y señuelos de organización, sucursal y almacén | Conserva la reautorización existente |
| Cantidades exactas; ausencia distinta de cero | Decimal→str, LEFT JOIN, seis decimales, sin stock/umbral y paginación de una fila | No añade snapshot entre páginas durante ediciones concurrentes |
| Lectura sin efectos de dominio | Snapshots antes/después de umbrales, estados, movimientos e insumos | No requiere compensaciones ni migración |
| Contrato aditivo documentado | Esquemas runtime y compartible con campos anulables | Clientes estrictos deben aceptar propiedades nuevas |

## CI y publicación

La suite global del run [420](https://github.com/mangoex/kiwi/actions/runs/40627277696)
registró 83 fallos, 2878 aprobadas y 8 omitidas; las siete pruebas de umbrales y las quince
pruebas de Agent Tools/contrato pasaron. Ese run incluía reparaciones generales que ya
se retiraron. No acredita el estado completo del diff reducido. No se ha demostrado la
atribución de todos los fallos al baseline; resolver caja, permisos, migraciones o
concurrencia queda fuera de este paquete. No se ocultan fallos ni se desactivan gates.

Preguntas operativas: ¿la lectura falla por autorización o almacén? HTTP, código estable y
correlación de solicitudes existentes distinguen el motivo. ¿cambia la latencia? La duración
existente del endpoint permite comparar el SELECT paginado antes/después, sin consultas por insumo.

PR #91 permanece sin merge. El usuario hará el redeploy. La verificación productiva pendiente
consiste en consultar con perfil inventory un insumo con umbral y otro sin él, contrastar unidad,
ceros/null y denegación de sucursal ajena. No escribir datos para ese canary.
La API de Kiwi está en `https://kiwipos.mimenu.onl/docs`; la URL de Asistto corresponde a otro servicio.
