import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const products = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');
const recipe = readFileSync('apps/admin-web/src/features/catalog/RecipeManager.tsx', 'utf8');
const decimalSource = readFileSync('apps/admin-web/src/features/catalog/recipeDecimal.ts', 'utf8');
const decimalModule = await import(`data:text/javascript;base64,${Buffer.from(ts.transpileModule(decimalSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText).toString('base64')}`);

assert.match(products, /import \{ RecipeManager, type RecipeWorkspaceItem \}/,
  'Productos reutiliza el escritor canónico de recetas');
assert.match(products, /\/recipes\/workspace\?branch_id=/,
  'Productos carga insumos mediante el workspace autorizado');
assert.match(products, /Guardar y configurar receta/,
  'El alta permite continuar directamente con la receta');
assert.match(products, /continueToRecipeAfterSaveRef\.current[\s\S]*saved\?\.id/,
  'El editor sólo abre después de recibir el ID persistido');
assert.match(products, /setActiveTab\('Receta'\)/,
  'La continuación activa la pestaña Receta');
assert.match(products, /<RecipeManager[\s\S]*productId=\{recipeEditorProduct\.id\}[\s\S]*branchId=\{branchId\}[\s\S]*items=\{recipeWorkspaceQuery\.data\.items\}/,
  'El editor recibe producto, sucursal e insumos exactos');
assert.doesNotMatch(products, /navigate\('\/recipes'\)/,
  'Editar una receta desde Productos no obliga a buscar el producto de nuevo');
assert.doesNotMatch(products, /Tipo de producto:/,
  'La pestaña no muestra campos aparentes sin contrato');
assert.doesNotMatch(products, /Almacén ventas:/,
  'La pestaña no muestra almacén sin contrato');

assert.match(decimalSource, /export const rateToPercent/,
  'La conversión visible de merma está aislada y verificable');
assert.match(decimalSource, /export const percentToRate/,
  'La conversión al payload fraccional está aislada y verificable');
assert.equal(decimalModule.rateToPercent('0.125'), '12.5');
assert.equal(decimalModule.rateToPercent('0.000001'), '0.0001');
assert.equal(decimalModule.percentToRate('12.5'), '0.125');
assert.equal(decimalModule.percentToRate('12,5'), '0.125');
assert.equal(decimalModule.percentToRate('99.9999'), '0.999999');
assert.equal(decimalModule.percentToRate(''), '');
assert.equal(decimalModule.percentToRate('-1'), '');
assert.equal(decimalModule.percentToRate('1e2'), '');
assert.match(recipe, /placeholder="Filtrar insumos por nombre o unidad"/,
  'Los insumos se pueden filtrar');
assert.match(recipe, /Rendimiento[\s\S]*Unidad de rendimiento/,
  'El rendimiento muestra cantidad y unidad');
assert.match(recipe, /Merma \(%\)/,
  'La merma usa lenguaje porcentual');
assert.match(recipe, /Cantidad bruta/,
  'El operador puede revisar la cantidad bruta estimada');
assert.match(recipe, /Vista previa del navegador/,
  'Los cálculos cliente se distinguen de la autoridad backend');
assert.match(recipe, /Volver al producto/,
  'El cierre después de guardar es explícito');
assert.match(recipe, /loadedRecipeKeyRef\.current === recipeKey/,
  'Un refetch del mismo baseline no reemplaza el borrador capturado');
assert.match(recipe, /if \(error && !hasVersionConflict\)[\s\S]*intentKey\.current = `recipe-/,
  'Editar después de un error incierto inicia una intención nueva');
assert.match(recipe, /const invalidWaste = formData\.components\.some/,
  'La merma visible inválida bloquea el guardado en lugar de convertirse silenciosamente en cero');
assert.match(recipe, /return !visiblePercent[\s\S]*\|\| !component\.waste_rate/,
  'Vaciar la merma también bloquea el guardado');
assert.match(recipe, /errorCode === 'recipe_version_conflict'/,
  'El conflicto se reconoce por el código estructurado de ApiError');
assert.match(recipe, /recipeLoadFailed[\s\S]*No fue posible consultar la receta vigente/,
  'Un fallo de lectura bloquea el formulario canónico');
assert.match(products, /recipeQuery\.isError[\s\S]*Reintentar lectura[\s\S]*disabled=\{[\s\S]*recipeQuery\.isError/,
  'Productos mantiene bloqueada la edición hasta recuperar la receta vigente');
assert.doesNotMatch(recipe, /setTimeout\(\(\) => \{[\s\S]*onClose\(\)/,
  'Un guardado confirmado no cierra automáticamente');
assert.match(recipe, /expected_active_recipe_id: recipe\?\.id \|\| null/,
  'La nueva experiencia conserva control de concurrencia');
assert.match(recipe, /'Idempotency-Key': intentKey\.current/,
  'La nueva experiencia conserva idempotencia');

console.log('test_recipe_product_flow.mjs PASSED');
