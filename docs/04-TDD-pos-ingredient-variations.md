# TDD - Ingredientes adicionales relacionados con productos

> Suite de regresión histórica hasta `0027_catalog_cleanup`. Desde `0028`, `TDD-TS-063` verifica
> adicionales universales y esta suite sólo protege asignaciones y snapshots anteriores.
>
> Norma POS-VAR-003: esta suite conserva los IDs POS-VAR-002 para el esquema 0026, pero verifica
> ADD-only para ventas y configuración nuevas. `remove_option_id` se conserva sólo como legado
> legible y debe fallar con `ingredient_extra_add_only` si se intenta seleccionar.

## TDD-TS-058 Catálogo, materialización y ejecución de ingredientes adicionales

Casos:

- upgrade/downgrade/upgrade `0025↔0026`, una sola head y cantidades `Decimal` sin `float`;
- definición única por insumo, etiqueta de adicional, item inmutable y archivo no destructivo;
- preview producto/categoría deduplicado, sólo activos actuales, aplicación atómica y idempotente;
- materialización idempotente de grupo separado y opción `add`, actualización por producto,
  reactivación sólo del add permitido y preservación de POS-VAR-001;
- `allow_remove=true`, cantidad remove distinta de cero y uno o varios `remove_option_id` heredados
  responden `ingredient_extra_add_only`, sin pedido, snapshot, reserva ni consumo parcial;
- adicional Decimal calcula costo promedio, snapshot, reserva y consumo; azúcar sin cargo no altera
  venta y cargo explícito sí;
- disponibilidad `available`, `unavailable`, `inherit` sólo para ADD y sucursal canónica;
- archivo/desvinculación conserva snapshots, KDS y print kitchen; auditoría, permisos y command
  log se preservan;
- TypeScript estricto, rutas separadas de Comentarios del pedido/Ingredientes adicionales y sin
  `localStorage` como autoridad;
- el cargo MXN exacto se convierte a `price_delta_cents` sin `float` y el runner Node verifica
  `20→2000`, `20.5/20.50→2050`, inversa `2000→20.00` y entradas inválidas.

## TDD-TC-051 Ingrediente adicional mantiene precio explícito e histórico

Given una receta activa de hamburguesa, costo promedio de aguacate y Porción extra de aguacate
When el administrador aplica el adicional ADD con cargo explícito y el cajero crea una orden
Then el backend congela cantidad, costo y kitchen_text, cobra sólo el delta explícito y reserva el
consumo resultante
And un importe UI de `20.50` MXN se envía como `2050` centavos y se muestra/cobra como `$20.50`
When la relación se archiva o la sucursal deshabilita el adicional
Then el pedido anterior permanece inmutable y las otras sucursales conservan su estado efectivo
And una petición con uno o varios retiros heredados falla antes de crear reservas.
