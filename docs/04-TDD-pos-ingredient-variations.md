# TDD - Variaciones de insumos relacionadas con productos

## TDD-TS-058 Catálogo, materialización y ejecución de cambios de insumos

Casos:

- upgrade/downgrade/upgrade `0025↔0026` en SQLite temporal, una sola head y SQL PostgreSQL
  verificable; constraints, FK, unicidad y cantidades `Decimal` sin `float`;
- definición única por insumo, etiquetas normalizadas, item inmutable con relaciones y archivo no
  destructivo;
- preview producto/categoría deduplicado, sólo activos actuales, incompatibilidades explicadas y
  aplicación atómica, revalidada e idempotente;
- materialización idempotente de grupo separado y opciones `add`/`remove`, actualización por
  producto, reactivación segura y preservación de POS-VAR-001;
- remover todo o cantidad exacta sin negativos; Con calcula costo promedio y snapshot, reserva y
  consumo exactos; azúcar sin cargo no altera venta y cargo explícito sí;
- selección simultánea Con/Sin rechazada en backend, y disponibilidad `available`, `unavailable`,
  `inherit` por acción y sucursal canónica;
- archivo/desvinculación conserva snapshots, KDS y print kitchen; auditoría cubre definición y
  bulk/edición/archivo de asignación con actor, alcance y clave de idempotencia;
- permisos de administrador, Supervisor y Cajero; no regresión de `preset_instruction`, instrucción
  libre, ModifierManager, POS-CUST-001 y collision guard de POS-VAR-001;
- TypeScript estricto y pruebas puras de preview, selección y exclusión mutua, con rutas y permisos
  canónicos, estados loading/error/empty/retry y sin `localStorage` como autoridad.
- La entrada corporativa de cargo acepta MXN exacto con cero, uno o dos decimales y lo convierte a
  `price_delta_cents` sin `float`; prueba `20→2000`, `20.5/20.50→2050`, la representación inversa
  `2000→20.00`, y rechaza vacío cobrado, negativos, texto, no finitos, más de dos decimales y
  valores fuera del entero seguro. La prueba ejecutable usa el toolchain Node en el gate
  `frontend`; las pruebas Python sólo verifican el contrato estructural independiente de Node.

## TDD-TC-051 Cambio de insumo mantiene precio explícito e histórico

Given una receta activa de hamburguesa, costo promedio de aguacate y una variación Con/Sin
When el administrador aplica Con aguacate con cargo explícito y el cajero crea una orden
Then el backend congela cantidad, costo y kitchen_text, cobra sólo el delta explícito y reserva el
consumo resultante
And un importe UI de `20.50` MXN se envía como `2050` centavos y se muestra/cobra como `$20.50`
When la relación se archiva o la sucursal deshabilita Con
Then el pedido anterior permanece inmutable, Sin y las otras sucursales conservan su estado efectivo
And una petición con Con y Sin de la misma variación es rechazada antes de crear reservas.
