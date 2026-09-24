# TDD - Continuidad de Producto a Receta

## TDD-TS-119 Editor contextual sobre el contrato PCO-007

La prueba semántica `tests/frontend/test_recipe_product_flow.mjs` verifica que Productos monta
`RecipeManager` con producto, sucursal, precio e insumos del workspace; que la continuación posterior
al alta depende de `saved.id`; y que la pestaña omite controles sin contrato. La regresión PCO-007
conserva permiso, alcance, `expected_active_recipe_id` e idempotencia. TypeScript y build verifican
integración real de props y JSX; QA de navegador cubre escritorio y ancho reducido.

## TDD-TC-277 Producto guardado abre su editor exacto

Given un borrador válido y una sucursal autorizada
When Guardar y configurar receta recibe un producto persistido
Then selecciona ese ID, activa Receta y abre el `RecipeManager` con el workspace de la sucursal.
Un error no cambia de pestaña, no abre el diálogo y conserva el formulario.

## TDD-TC-278 Captura legible conserva payload canónico

El editor expone filtro de insumos, rendimiento y unidad. Merma visible `12.5 %` produce exactamente
`0.125` en el payload; `0`, decimales y límites válidos no pasan por aritmética binaria para la
conversión enviada. Vacío, negativo, notación exponencial o porcentaje igual/mayor a 100 bloquean el
PUT. Bruto/costo se rotulan como vista previa y no forman parte del PUT. Precio y costo no autorizan
ninguna decisión ni escritura adicional.

## TDD-TC-279 Éxito y rechazo conservan control humano

Un PUT confirmado invalida receta/workspace, renueva la clave de la siguiente intención y muestra
éxito sin temporizador de cierre. Error o conflicto conserva el formulario y la clave necesaria para
un replay seguro; conflicto bloquea guardar hasta reabrir. La IA sólo aplica un borrador editable.
Un GET fallido bloquea el acceso de escritura hasta que la relectura recupere el baseline vigente.

## RED esperado

Antes de implementar, falla porque Productos no monta `RecipeManager`, navega a `/recipes`, no ofrece
Guardar y configurar receta, la merma usa fracción visible y el éxito cierra automáticamente.

## Gates focales

```bash
node tests/frontend/test_recipe_product_flow.mjs
node tests/frontend/test_admin_productos_master_detail.mjs
node tests/frontend/test_admin_product_flow.mjs
node tests/frontend/test_pco007_recipe.mjs
node tests/frontend/test_product_capsule_tabs.mjs
pnpm --filter @restaurantos/admin-web typecheck
pnpm --filter @restaurantos/admin-web build
node tests/browser/test_recipe_product_flow.mjs
python3 -m pytest tests/architecture/test_traceability.py -q
git diff --check
```

La suite completa frontend queda para CI. No hay migración ni cambio backend; PostgreSQL/SQLite no
son gates activados por este incremento. La auditoría independiente y la QA visual son obligatorias
por el alcance R3 del flujo.
