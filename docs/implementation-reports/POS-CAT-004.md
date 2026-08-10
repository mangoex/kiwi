# POS-CAT-004 — evidencia de implementación

## Estado de auditoría

Implementación aprobada por la auditoría final de Sol y lista para solicitar autorización Git. No se
hizo commit, staging, merge, push ni deploy. El gate PostgreSQL se ejecutó de forma independiente
contra PostgreSQL 16.14 x86-64 en una instancia efímera accesible sólo por socket Unix local.

## Trazabilidad

| Capa | Evidencia |
| --- | --- |
| Requisito | `PRD-FR-213`, preservando la jerarquía de `PRD-FR-019`. |
| Diseño | `POS-CAT-004` en SDD: autoridad Python, permisos, editor explícito, proyección, schema y rollback. |
| BDD | `BDD-FEAT-074`, `BDD-SC-255..264`. |
| TDD | `TDD-TS-075` y `TDD-TC-071`, con comandos y frontera de prueba ejecutable. |
| Matriz | `PRD-FR-213` está `Implementado`; SQLite, PostgreSQL, contrato, frontend y flujo visual tienen evidencia verde. |

## Implementación comprobada

- La migración lineal `0034_category_option_selection` conserva grupos single/required, valores y
  asignaciones explícitas, sin inferir nombres ni alterar productos, precios, recetas, pedidos o
  snapshots. `size` puede repetirse en categorías distintas de la misma organización.
- Python valida categoría existente y organización, relaciones grupo/valor/producto, permisos,
  código/estado/orden, duplicados, transacciones y auditoría. Rechaza relaciones cruzadas, valores
  inactivos y archivar un valor que rompería un grupo activo, sin mutación parcial.
- Coverage corporativo muestra todos los productos relevantes, asignación actual o `null` e
  `incomplete`; el editor puede crear, editar explícitamente código/nombre/orden/estado, cancelar y
  reasignar. La hidratación usa una clave de `id+code+name+status`, por lo que un grupo actualizado
  con el mismo ID no conserva estado obsoleto.
- La proyección POS compartida filtra elegibilidad por sucursal y falla cerrada. Registra
  `category_option_projection_incomplete` y `category_option_projection_error` sin PII.
- `pos-catalog-projection-v1.schema.json` se ejerce con un validador recursivo sin dependencia
  nueva: tipos, const, mínimo, required, `additionalProperties`, objetos activos y nulos, y
  fixtures negativos de precio y selección inválidos.
- `transitionCatalogNavigation` es consumida por POS y prueba que categoría/opción limpia sólo
  personalización transitoria, preservando carrito y búsqueda. Seleccionar una opción no añade
  producto ni calcula precio.
- Cambiar y Reintentar tienen controles propios con mínimo 44 px y foco visible, sin alterar grilla
  ni carrito.
- `alembic/env.py` delega el URL a un adaptador tipado que duplica `%` sólo al escribir en
  `Config.set_main_option`; ConfigParser recupera el URL lógico original y el driver no recibe una
  transformación adicional.

## Evidencia red → verde

1. Rojo de ronda 2: categoría inexistente devolvía 200 y duplicate de value code exponía un
   `IntegrityError` de SQLite en vez de un error de dominio.
2. Rojo posterior: la matriz usó un estado no normalizado; la suite completa lo detectó.
3. Verde final: categoría inexistente responde `category_not_found`; duplicate responde
   `category_option_duplicate`; relación cruzada, permisos, orden inválido, rollback, auditoría,
   edición, schema activo/nulo y fixtures negativos pasan. La matriz usa `Implementado` válido.
4. `BDD-SC-264`: una URL SQLAlchemy con `%2F`/credenciales URL-encoded fallaba en ConfigParser
   antes de conectar. Verde: la prueba real de `alembic.config.Config` recupera exactamente el URL
   lógico, tanto con porcentajes como sin ellos, sin registrar credenciales.

## Validación ejecutada

| Comando | Exit | Conteo / resultado |
| --- | ---: | --- |
| `python3 -m pytest apps/api/tests/test_platform_api.py -k 'category_option or pos_catalog_schema' tests/architecture/test_pos_category_options.py` | 0 | 14 passed, 52 deselected |
| `python3 -m pytest apps/api/tests/test_migrations.py -k percent_encoded_database_url` | 0 | 1 passed, 12 deselected; `%40`, `%25`, `%2F` y URL sin `%` preservados |
| `python3 -m pytest apps/api/tests/test_migrations.py` | 0 | 13 passed en 60.46 s |
| `python3 -m pytest tests/architecture` | 0 | 111 passed en 18.12 s |
| `python3 -m pytest -q` | 0 | 219 passed en 165.81 s |
| `python3 -m ruff check apps/api tests` | 0 | All checks passed |
| `python3 -m pytest tests/test_migrations.py -k category_option` desde `apps/api` | 0 | 1 passed, 11 deselected; roundtrip SQLite `0033 → head → 0033 → head` |
| `python3 -m alembic heads -v` desde `apps/api` | 0 | una sola head `0034_category_option_selection` |
| `pnpm typecheck` con Node 24 aislado | 0 | ui, admin-web, pos-web y kds-web |
| build `@restaurantos/admin-web` | 0 | Vite producción verde |
| build `@restaurantos/pos-web` | 0 | Vite producción verde |
| build `@restaurantos/kds-web` | 0 | Vite producción verde |
| `pnpm test:ingredient-variation-money` | 0 | verde |
| `pnpm test:pos-global-comments-extras` | 0 | verde |
| `pnpm test:pos-order-edit-restore` | 0 | verde |
| `pnpm test:pos-category-options` | 0 | verde |
| `pnpm test:admin-category-options` | 0 | verde |
| `git diff --check` | 0 | sin whitespace errors |

## Evidencia PostgreSQL independiente de Sol

- PostgreSQL 16.14 x86-64 se obtuvo del archivo binario EDB enlazado por la página oficial de
  PostgreSQL para macOS. SHA-256 del ZIP:
  `b5b7f920470fdcc4f4c8029c6da30fda64c11caf0b14e75674684356443f4bbe`.
- Una base vacía avanzó por toda la cadena Alembic hasta `0033_restore_superadmin_role` y luego a
  `0034_category_option_selection`, usando DDL transaccional PostgreSQL real.
- En `0034` se comprobaron tres tablas, 16 constraints y ocho índices. Pruebas negativas reales
  rechazaron `selection_mode` distinto de `single`, grupo no requerido, estado inválido,
  duplicados grupo/categoría, valor/código y producto/grupo, además de una FK huérfana.
- El ciclo `0034 → 0033 → 0034` fue verde: el downgrade retiró sólo las tres tablas nuevas,
  restauró 72 tablas preexistentes y el segundo upgrade dejó de nuevo la head `0034`.
- El flujo FastAPI productivo contra PostgreSQL creó el grupo Tamaño inactivo y el valor Chica,
  rechazó activación incompleta con 409, asignó dos productos explícitos, activó el grupo, validó
  `pos-catalog-projection-v1` y obtuvo `coverage_complete=true`.
- Datos, socket, binarios y scripts de prueba se mantuvieron fuera del repositorio bajo un directorio
  temporal aislado y se eliminaron después de detener el servidor; no se usó ni modificó una base real.

## Evidencia visual independiente de Sol

Sol verificó localmente, con fixture SQLite desechable y asignaciones explícitas:

- Ensaladas → Tamaño → Chica mostró sólo el producto asignado.
- Elegir Chica conservó el carrito en `$0.00`.
- Tocar Ensalada Del Chef agregó `$125.00`.
- Al provocar un error de proyección, API devolvió 503 y POS mostró "No se pudo cargar…" y
  **Reintentar**, sin fallback; al restaurar la base, Reintentar recargó 30 productos.

Las capturas permanecen fuera del repositorio:

- `/Users/renatavictoriagonzalez/.codex/visualizations/2026/08/09/019fe6f6-1b9d-7d02-b962-eb9fc50493c0/pos-cat-004-selector-1440.png`
- `/Users/renatavictoriagonzalez/.codex/visualizations/2026/08/09/019fe6f6-1b9d-7d02-b962-eb9fc50493c0/pos-cat-004-cart.png`

## Exclusiones y riesgo residual

- No se añadieron dependencias, `pos_display_name`, familia de producto, price delta ni autoridad
  paralela de precio/tamaño.
- La observabilidad disponible es logging estructurado; el módulo no dispone aún de contador o
  alerta de métricas dedicada.
- No queda riesgo residual de interpolación ConfigParser: el adaptador conserva URLs SQLAlchemy
  percent-encoded sin cambiar el valor lógico que consumirá el driver.
