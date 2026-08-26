# RECIPES-0054 — handoff de publicación gobernada

Riesgo: R3. Alcance local: manifiesto JSON, resolvedor dry-run y pruebas. No existe migración
Alembic, auto-run, despliegue ni autorización para base productiva.

Procedencia: el JSON se recuperó del commit histórico `bd19faf`; no se reutilizó su loader ni su
migración, que permanecen rechazados. La cuarentena se levantó sólo para el blob cuya huella es
`34f9bf8bde3f523abeed0d5e87f38b5d9e26a6b30b92f3876c1a637df2cea492`, después de verificar 329
filas, 14 modificadores excluidos, 315 recetas publicables, 1,413 componentes positivos, ausencia de
duplicados, precisión `NUMERIC(18,6)`, longitudes de columnas y compatibilidad de unidades. El
dry-run sobre el baseline observado resolvió 307/315 productos y 132/135 insumos; los faltantes
exactos 8/3 quedaron especificados explícitamente.

Para esos ocho productos el precio comercial no se deriva del precio neto del JSON: se conserva la
tabla explícita del loader histórico (`11057=3000`; `24001..24007=5000,5500,7500,7000,7500,10000,11000`
centavos). Los componentes usan siempre `inventory_items.base_unit_id`; los alias `KILO/LITRO/PZA`
sólo validan compatibilidad y no sustituyen la unidad base persistida.

La publicación puede crear exclusivamente la categoría canónica `CAFE Y MACCHA` con
`display_order=2` cuando falta; la categoría histórica `Café y Matcha` archivada y `BEBIDAS` activa
no son equivalencias autorizadas. Los tres insumos nuevos no incluyen `inventory_cost_states` ni
`purchase_presentations`: el cálculo usa costo promedio existente o cero y el residual afecta ocho
recetas (`001026`: 5, `001027`: 2, `001028`: 1). Crear precios de compra/costos queda fuera de este
paquete y requiere una publicación separada.

El módulo `restaurant_os.recipe_catalog_seed` exige el baseline catalogado: 307 productos y 132
insumos fuente activos; sólo puede crear `11057`, `24001..24007` y `001026..001028`. Rechaza SKU
ambiguo, inactivo o unidad incompatible. El dry-run productivo esperado conserva `06002`, propone
314 recetas y excluye sus nueve componentes fuente. Replay propone cero inserciones y 314 recetas
revalidadas campo por campo. `publish_recipe_catalog` exige la huella SHA-256 canónica, actor activo
con `recipes.manage` y `organization_all_permissions`, entorno confirmado y el plan exacto de 314
inserciones con `06002` preservado; serializa por
organización y escribe la auditoría en la misma transacción. La sesión llamadora conserva la
responsabilidad de commit o rollback.

El entrypoint `python -m restaurant_os.recipe_catalog_seed` usa exclusivamente la base configurada
de la aplicación, opera como dry-run por defecto y exige actor, entorno y SHA-256. `--apply` además
exige confirmar literalmente `314-recipes-preserve-06002`; sólo admite el head revisado
`0053_cash_offline_sync`.

El procedimiento operativo está en `RECIPES-CATALOG-PUBLICATION-RUNBOOK.md`; permanece sin ejecutar.
Pendiente de la autoridad de release: PostgreSQL aislado contra una copia segura y completar ese
runbook con identificadores reales de imagen, operador, respaldo y mecanismo ensayado de pausa. La
auditoría independiente debe repetirse después de ese gate. Ninguna de estas evidencias implica listo
para producción.
