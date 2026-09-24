# TDD - Grupos y subgrupos integrados

## TDD-TS-114 ADMIN-CAT-005 integración administrativa y lenguaje POS

Casos:

- `tests/frontend/test_admin_group_subgroup_workspace.mjs` verifica que Categorías componga la
  edición del grupo, el selector previo, sus valores y la cobertura de productos en una estación;
- la prueba rechaza `INITIAL_SUBGROUPS` y cualquier alta de subgrupos conservada únicamente en
  estado React dentro de Productos;
- Productos consulta la cobertura de la categoría seleccionada y persiste la asignación mediante el
  endpoint canónico de `product_option_value_assignments` después de guardar el producto concreto;
- la operación muestra un error si la segunda escritura falla y no anuncia un guardado completo;
- la ruta heredada `/category-options` conserva acceso a la estación integrada sin duplicar una
  fuente de administración;
- el POS conserva su máquina de estados y autoridad de catálogo, pero presenta las etapas visibles
  como Grupos y Subgrupos;
- las regresiones de `TDD-TS-075` y `TDD-TS-098` siguen verificando asignación explícita, fallo
  cerrado, carrito, búsqueda y producto concreto.

## TDD-TC-257 Edición integrada y persistencia canónica de subgrupo

Given una categoría con selector previo y valores activos
When el administrador abre Grupos y subgrupos
Then puede editar el grupo, sus subgrupos y la cobertura de productos sin navegar a otro catálogo.
When abre Productos, selecciona uno de esos subgrupos y guarda
Then la API de producto conserva la identidad del producto
And Python valida y persiste la asignación explícita con el endpoint canónico.
When el cajero abre el mismo grupo en POS
Then ve primero Subgrupos y después sólo los productos concretos elegibles.

## Comandos focalizados

```bash
pnpm test:admin-groups-subgroups
pnpm test:admin-category-options
pnpm test:pos-category-options
python3 -m pytest tests/architecture/test_pos_category_options.py tests/architecture/test_traceability.py -q
pnpm --filter @restaurantos/admin-web typecheck
pnpm --filter @restaurantos/pos-web typecheck
```
