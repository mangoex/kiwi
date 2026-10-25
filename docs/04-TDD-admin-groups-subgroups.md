# TDD - Grupos y subgrupos integrados

## TDD-TS-114 ADMIN-CAT-005 integración administrativa y lenguaje POS

Casos:

- `tests/frontend/test_admin_group_subgroup_workspace.mjs` verifica que Categorías componga la
  edición del grupo, el selector previo, sus valores y la cobertura de productos en una estación;
- la superficie primaria no presenta nombre del nivel, código interno, estado del nivel ni dos
  acciones equivalentes de publicación; sólo solicita el nombre del subgrupo y ofrece una transición
  visible para mostrarlo u ocultarlo en POS;
- `apps/api/tests/test_platform_api.py` prueba que Python crea los defaults del selector, deriva un
  código normalizado y el siguiente orden al crear un valor, y conserva los campos técnicos cuando
  una edición envía únicamente el nombre;
- la prueba rechaza `INITIAL_SUBGROUPS` y cualquier alta de subgrupos conservada únicamente en
  estado React dentro de Productos;
- Productos consulta la cobertura de la categoría seleccionada e incluye la asignación en el comando
  transaccional de configuración del producto;
- la estación calcula el conteo por `assignment.value_id`, distingue un subgrupo vacío de uno
  meramente activo y enlaza un alta contextual sin escribir producto ni asignación;
- Productos consume una sola vez `create=1`, `category_id` y `subgroup_id`, resuelve los IDs contra
  el catálogo cargado, preselecciona el borrador y limpia esos parámetros de navegación;
- una asignación inválida revierte producto, precio, asignación y auditoría de éxito, y la operación
  muestra el error sin anunciar un guardado completo;
- la ruta heredada `/category-options` conserva acceso a la estación integrada sin duplicar una
  fuente de administración;
- el POS conserva su máquina de estados y autoridad de catálogo, pero presenta las etapas visibles
  como Grupos y Subgrupos;
- las regresiones de `TDD-TS-075` y `TDD-TS-098` siguen verificando asignación explícita, fallo
  cerrado, carrito, búsqueda y producto concreto.

## TDD-TC-257 Edición integrada y persistencia canónica de subgrupo

Given una categoría con selector previo y valores activos
When el administrador abre Grupos y subgrupos
Then puede editar el grupo, capturar subgrupos sólo por nombre y revisar la cobertura sin navegar a
otro catálogo.
And Python gobierna código, orden, relación, estado y la transición de publicación.
When abre Productos, selecciona uno de esos subgrupos y guarda
Then la API de configuración conserva la identidad del producto
And Python valida y persiste producto, precio y asignación explícita en una transacción.
When el cajero abre el mismo grupo en POS
Then ve primero Subgrupos y después sólo los productos concretos elegibles.

## TDD-TC-472 Conteo y alta contextual desde un subgrupo vacío

Given un subgrupo activo sin productos asignados
When se renderiza su fila en Grupos y subgrupos
Then muestra `0 productos asignados`, advierte que no aparecerá en POS y ofrece crear un producto en
ese contexto.
When Productos recibe los IDs canónicos desde esa acción
Then abre un alta nueva con el grupo y subgrupo preseleccionados sin persistir nada todavía
And elimina los parámetros consumidos para que una recarga posterior no descarte el trabajo actual.

## Comandos focalizados

```bash
pnpm test:admin-groups-subgroups
pnpm test:admin-category-options
pnpm test:pos-category-options
python3 -m pytest tests/architecture/test_pos_category_options.py tests/architecture/test_traceability.py -q
python3 -m pytest apps/api/tests/test_platform_api.py -k category_option_simplified_admin_defaults -q
python3 -m pytest apps/api/tests/test_admin_product_flow.py -k subgroup -q
pnpm --filter @restaurantos/admin-web typecheck
pnpm --filter @restaurantos/pos-web typecheck
```
