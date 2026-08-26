# RECIPES-0054 — handoff de publicación gobernada

Riesgo: R3. Alcance local: manifiesto JSON, resolvedor dry-run y pruebas. No existe migración
Alembic, auto-run, despliegue ni autorización para base productiva.

Procedencia: el JSON se recuperó del commit histórico `bd19faf`; no se reutilizó su loader ni su
migración, que permanecen rechazados. La cuarentena se levantó sólo para el blob cuya huella es
`34f9bf8bde3f523abeed0d5e87f38b5d9e26a6b30b92f3876c1a637df2cea492`, después de verificar 329
filas, 14 modificadores excluidos y 315 recetas candidatas con 1,413 componentes positivos. El lote
autorizado se reduce de forma fail-closed a 307 recetas y 1,395 componentes: excluye `11057` y
`24001..24007`, junto con los insumos `001026..001028`, mientras no tengan costo gobernado.

Los ocho productos pendientes no se crean, no reciben precio y no pueden aparecer en el menú ni
venderse. Tampoco se crean sus tres insumos ni la categoría `CAFE Y MACCHA`; cualquier preexistencia
de esos SKU detiene el publicador. Reincorporarlos exige un paquete posterior con presentación de
compra y costo promedio autorizado. Los componentes elegibles usan siempre
`inventory_items.base_unit_id`; los alias `KILO/LITRO/PZA` sólo validan compatibilidad.

La dependencia queda fijada en el código y la auditoría: `001026` afecta cinco recetas
(`24001..24005`), `001027` dos (`24006,24007`) y `001028` una (`11057`). El manifiesto permanece
inmutable como evidencia de origen; el reporte separa candidatos históricos de recetas elegibles y
lista los pendientes explícitamente.

El módulo `restaurant_os.recipe_catalog_seed` exige el baseline catalogado: 307 productos y 132
insumos fuente activos y no permite crear faltantes. Rechaza SKU ambiguo, inactivo, pendiente
preexistente o unidad incompatible. El dry-run productivo esperado conserva `06002` y propone 306
recetas con 1,386 componentes; los otros nueve componentes elegibles pertenecen a `06002` y no se
insertan. Replay propone cero inserciones y 306 recetas revalidadas campo por campo.
`publish_recipe_catalog` exige la huella SHA-256 canónica, actor activo
con `recipes.manage` y `organization_all_permissions`, entorno confirmado y el plan exacto de 306
inserciones con `06002` preservado y ocho recetas pendientes; serializa por
organización y escribe la auditoría en la misma transacción. La sesión llamadora conserva la
responsabilidad de commit o rollback.

El entrypoint `python -m restaurant_os.recipe_catalog_seed` usa exclusivamente la base configurada
de la aplicación, opera como dry-run por defecto y exige actor, entorno y SHA-256. `--apply` además
exige confirmar literalmente `306-recipes-preserve-06002-exclude-8-pending-cost`; sólo admite el
head revisado `0053_cash_offline_sync`.

El procedimiento operativo está en `RECIPES-CATALOG-PUBLICATION-RUNBOOK.md`; permanece sin ejecutar.
La validación PostgreSQL aislada anterior cubrió el paquete de 314 inserciones y quedó invalidada por
este cambio de alcance. Debe repetirse sobre una copia fresca con 306 inserciones, sin los ocho
productos ni los tres insumos. Después se repite auditoría independiente. Ninguna evidencia previa
autoriza producción.
