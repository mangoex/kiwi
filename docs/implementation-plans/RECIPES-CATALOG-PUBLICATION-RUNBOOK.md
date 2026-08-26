# Runbook — publicación gobernada del catálogo de recetas

Estado: borrador ejecutable, no autorizado para producción. Riesgo R3. Este procedimiento no es una
migración de esquema y nunca debe agregarse al arranque de la aplicación.
El snapshot y la validación PostgreSQL aislada siguen pendientes; este documento no autoriza su
ejecución ni constituye evidencia productiva.

## 1. Gates previos obligatorios

1. Usar una imagen identificada por commit que contenga `restaurant_os.recipe_catalog_seed` y el
   manifiesto con SHA-256
   `34f9bf8bde3f523abeed0d5e87f38b5d9e26a6b30b92f3876c1a637df2cea492`.
2. Obtener aprobación separada para deploy, dry-run sobre datos productivos y `--apply`.
3. Aprobar en PostgreSQL aislado el mismo head y un snapshot reciente: dry-run, aplicación,
   concurrencia multi-sesión, replay, auditoría y rollback por fallo inyectado.
4. Registrar operador de consola, `actor_user_id` de un usuario activo con `recipes.manage` y
   `organization_all_permissions`, ventana, commit, imagen y respaldo verificable.
5. Confirmar `alembic_version = 0053_cash_offline_sync`. Otro head debe detener el procedimiento.
6. Confirmar `RESTAURANTOS_AUTO_MIGRATE=false` y que `/health/version` reporta el commit aprobado.
7. Definir y probar cómo congelar todo tráfico mutante durante la ventana. El RPO de esta operación
   es cero: si pedidos, caja, inventario, catálogo u otra escritura no pueden pausarse y drenarse, no
   se aplica. El lock del publicador serializa publicadores, no reemplaza esta pausa global.

## 2. Respaldo y línea base

Antes de la ventana, ensayar el mecanismo de snapshot/restauración y registrar como evidencia los
conteos de productos, insumos, recetas, componentes y commands de receta. El snapshot recuperable
final se toma en la sección 4 después de congelar y drenar todas las escrituras; no continuar si no
puede garantizarse RPO cero. Los conteos no sustituyen el dry-run.

```sql
SELECT 'products' AS entity, count(*) FROM products
 WHERE organization_id = '018f6f73-2d0a-74f0-8f1c-000000000001'
UNION ALL SELECT 'inventory_items', count(*) FROM inventory_items
 WHERE organization_id = '018f6f73-2d0a-74f0-8f1c-000000000001'
UNION ALL SELECT 'recipes', count(*) FROM recipes
 WHERE organization_id = '018f6f73-2d0a-74f0-8f1c-000000000001'
UNION ALL SELECT 'recipe_components', count(*)
 FROM recipe_components rc JOIN recipes r ON r.id = rc.recipe_id
 WHERE r.organization_id = '018f6f73-2d0a-74f0-8f1c-000000000001'
UNION ALL SELECT 'recipe_version_commands', count(*) FROM recipe_version_commands
 WHERE organization_id = '018f6f73-2d0a-74f0-8f1c-000000000001';
```

## 3. Dry-run desde la imagen candidata

El comando no acepta una URL por argumento. En el job aislado configurar explícitamente sólo
`RESTAURANTOS_DATABASE_URL` y eliminar `DATABASE_URL` para evitar seleccionar una base implícita.

```bash
python -m restaurant_os.recipe_catalog_seed \
  --actor <ACTOR_USER_ID> \
  --confirm-environment production \
  --confirm-manifest-sha256 34f9bf8bde3f523abeed0d5e87f38b5d9e26a6b30b92f3876c1a637df2cea492
```

El primer dry-run autorizado debe reportar exactamente: `applied=false`, `dry_run=true`,
`recipes_to_seed=314`, `recipes_replayed=0`, `preserved_skus=["06002"]`, productos a crear
`11057,24001..24007` e insumos `001026..001028`. Cualquier diferencia detiene el cambio; no se
ajustan constantes ni datos productivos durante la ventana. El mismo reporte debe incluir
`categories_to_create=["CAFE Y MACCHA"]`: se crea con `display_order=2`. No reutiliza `BEBIDAS` ni
reactiva la categoría histórica archivada `Café y Matcha`; una categoría exacta inactiva o ambigua
detiene el cambio.

## 4. Aplicación

Congelar todo tráfico mutante con el mecanismo previamente ensayado y confirmar mediante telemetría
que no existen requests en curso. Tomar entonces el snapshot final, registrar su identificador fuera
del contenedor y mantener la pausa global. Mantener disponible un único job/consola con la misma
imagen candidata y ejecutar sólo tras la autorización explícita de `--apply`:

```bash
python -m restaurant_os.recipe_catalog_seed \
  --actor <ACTOR_USER_ID> \
  --confirm-environment production \
  --confirm-manifest-sha256 34f9bf8bde3f523abeed0d5e87f38b5d9e26a6b30b92f3876c1a637df2cea492 \
  --confirm-plan 314-recipes-preserve-06002 \
  --apply
```

El proceso hace commit una sola vez al concluir. Una excepción antes del commit revierte productos,
precios, insumos, recetas, componentes y auditoría juntos.

## 5. Verificación antes de reabrir escrituras

1. Repetir el comando sin `--apply`: debe reportar `recipes_to_seed=0`,
   `recipes_replayed=314`, `preserved_skus=["06002"]` y listas de creación vacías. Este replay
   valida campos, cantidades `Decimal`, unidades base y componentes de las 314 recetas.
2. Confirmar exactamente una auditoría para la huella y el actor autorizado:

```sql
SELECT count(*) AS exact_audit_count
FROM audit_events
WHERE organization_id = '018f6f73-2d0a-74f0-8f1c-000000000001'
  AND action = 'recipe_catalog.applied'
  AND actor_user_id = '<ACTOR_USER_ID>'
  AND payload ->> 'manifest_sha256' =
      '34f9bf8bde3f523abeed0d5e87f38b5d9e26a6b30b92f3876c1a637df2cea492';
```

`exact_audit_count` debe ser `1`; además conservar como evidencia el evento completo por su
`entity_id` determinista.

3. Confirmar que `06002` conserva cuatro versiones, sus cuatro commands y once componentes en la
   versión activa observada. Si los datos cambiaron desde el levantamiento, detenerse y auditar; no
   forzar esos números.
4. Confirmar los precios comerciales de los ocho productos nuevos: `11057=3000` y
   `24001..24007=5000,5500,7500,7000,7500,10000,11000` centavos.
5. Confirmar `CAFE Y MACCHA` activa con orden `2`, su ID determinista y los siete vínculos
   `24001..24007`; confirmar también que `11057` permanece en `INGREDIENTE EXTRA`. La auditoría
   debe registrar la estructura `name`, `id`, `display_order` de la categoría creada. Una desviación
   exige mantener la pausa y restaurar el snapshot; no relinkear productos manualmente.
6. Registrar el residual de costo: `001026`, `001027` y `001028` se enlazan como insumos, pero esta
   publicación no crea `inventory_cost_states` ni `purchase_presentations`. `calculate_recipe_cost`
   usa el `average_unit_cost` existente o cero; por ello ocho recetas quedan relacionadas pero no
   obtienen un costo comercial completo (`001026`: 5, `001027`: 2, `001028`: 1). No inventar precios
   de compra ni aprobar costo teórico/comercial hasta completar una carga de costos separada.
7. Ejecutar una lectura canary desde el workspace administrativo para un producto preexistente y uno
   nuevo. Verificar receta, cantidades/unidades y ausencia de errores; no crear ni versionar recetas.
8. Reabrir escrituras sólo cuando todos los checks y la observabilidad sean verdes.

## 6. Fallo y recuperación

- Si el comando falla antes del commit, conservar logs sanitizados, comprobar que el dry-run inicial
  continúa proponiendo 314 inserciones y no reintentar hasta clasificar la causa.
- Si una verificación posterior al commit falla, mantener escrituras pausadas. Como el snapshot final
  se tomó después del freeze global, restaurarlo conserva RPO cero dentro de la ventana. Usar esa
  recuperación aprobada y ensayada, o diseñar una compensación forward-only separada; no ejecutar
  `DELETE`/`UPDATE` manual sobre categorías, productos, insumos, recetas, componentes, precios o
  auditoría.
- Registrar resultado, timestamps UTC, commit, imagen, snapshot, actor y operador. Un deploy sano no
  demuestra que el catálogo fue aplicado; el audit y el replay tampoco sustituyen el canary.
