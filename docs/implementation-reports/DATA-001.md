# DATA-001 — catálogos heredados de Constitución

## Resultado del análisis

Los archivos se analizaron en modo lectura. Son libros Office Open XML aunque usan extensión
`.XLS`; todos contienen una hoja y encabezado en la fila 5. No se imprimieron datos personales ni se
modificaron los archivos.

| Fuente | Filas | Resultado estructural |
|---|---:|---|
| CLIENTES.XLS | 33,219 | Clave, nombre y dirección libre; no contiene teléfono, correo ni campos fiscales. Hay una clave duplicada. |
| INSUMOS.XLS | 156 | Clave, descripción, grupo, unidad, costos e impuesto; las claves son únicas. |
| PRESENTACIONES.XLS | 159 | Rendimiento, unidad, costos e impuesto; no contiene proveedor. |
| PRODUCTOS.XLS | 317 | Clave, categoría, precios e indicadores de canal; no contiene estación operativa. |
| RECETAS.XLS | 317 | Encabezados y filas iguales a PRODUCTOS; no contiene componentes, cantidades, unidad ni rendimiento de receta. |

Checksum del manifiesto normalizado: `9f428bf50ee868e9f8170598dc36f9ccf05389dc601f39bc7496d9e870626096`.

Checksums SHA-256 de las fuentes privadas:

- CLIENTES: `4362dea83fa2b34cd4436687e01f22387783841aa22a0e94d3cbfba68e1389cc`;
- INSUMOS: `580a2968bc1449de836662aee7579d5bde1be38abe2467c9536dd2d19619c409`;
- PRESENTACIONES: `6285e622cfe69cd221f8b42617a6b433ca9eaeeee9c3c2f1510afa9e84cff56c`;
- PRODUCTOS: `26cec323b8c18fe8bc2497cb6383279fe8518e7e93876863980e814ea913f361`;
- RECETAS: `e2be225e09668602c97838f3d9eac20c6fa8e6b4d8e91b8cbf202f7a799e6f4d`.

## Adecuaciones

- Migración `0025_legacy_branch_catalog_import` con alcance explícito de catálogo por sucursal.
- Lotes y filas idempotentes con payload original, normalizado, estado, motivo y destino.
- Clientes e insumos materializables para Constitución sin inventar direcciones ni costos.
- Productos en `needs_review` hasta asignar estación; precio heredado preservado como versión.
- Presentaciones sin proveedor y recetas inválidas conservadas en revisión, sin registros operativos
  ficticios.
- Directorio de clientes filtrado, buscable y paginado para evitar cargar 33 mil registros y eliminar
  el patrón N+1 en la consulta paginada.
- Pantalla corporativa de importaciones y formulario de productos capaz de ajustar categoría,
  estación, estado, precio e imagen.
- Etiqueta visual en el POS para distinguir productos propios de la sucursal.
- Adaptador local sin dependencias adicionales; los Excel no forman parte del repositorio.

## Trazabilidad

- Requisitos: PRD-FR-190 a PRD-FR-197.
- Escenarios: BDD-FEAT-053, BDD-SC-144 a BDD-SC-151.
- Pruebas: TDD-TS-053, TDD-TC-046 y `apps/api/tests/test_legacy_import.py`.

## Estado operativo

La estructura y el cargador están preparados. La carga productiva sólo debe ejecutarse después de
integrar, desplegar y llevar PostgreSQL a `0025_legacy_branch_catalog_import`. El procedimiento y la
verificación de aislamiento están en `docs/10-operacion-easypanel.md`.

## Evidencia local

- `python3 tools/import_legacy_branch_catalogs.py .`: validación exitosa de 34,168 filas, sin carga.
- `python -m pytest`: 106 pruebas aprobadas.
- `python -m ruff check apps/api tests tools`: sin hallazgos.
- `pnpm typecheck`: Admin, POS, KDS y UI aprobados.
- builds de producción de Admin, POS y KDS: aprobados.
- `git diff --check`: limpio.
- Los cinco Excel, `.zcode/` y las imágenes de WhatsApp quedaron fuera del commit.
