# TDD - Configuración confiable de productos

## TDD-TS-115 Comando canónico de configuración de producto

Cobertura backend y contrato:

- `apps/api/tests/test_admin_product_flow.py` prueba creación y actualización con permiso
  `catalog.manage`, aislamiento de organización y payload estricto;
- `apps/api/tests/test_admin_product_flow_postgres.py` prueba locks, carrera de versión,
  idempotencia y rollback real en PostgreSQL;
- `tests/contract/test_admin_product_configuration_contract.py` valida request/response y rechaza
  propiedades no declaradas;
- la suite verifica que categoría y subgrupo usan IDs estables y pertenecen a la misma organización;
- la suite inyecta un fallo después de insertar producto, después de versionar precio y antes de
  asignar subgrupo, y en todos los casos comprueba cero efectos persistidos;
- la suite comprueba que un precio idéntico no abre versión nueva y que un cambio cierra exactamente
  una versión vigente;
- la suite ejecuta paridad SQLite/PostgreSQL sólo para las invariantes y migración afectadas, sin
  presentar SQLite como evidencia suficiente de concurrencia.

## TDD-TC-258 Creación atómica con subgrupo

Given una categoría corporativa con selector activo y un subgrupo activo
When se envía `POST /api/v1/catalog/product-configurations` con datos válidos e `Idempotency-Key`
Then existen exactamente un producto, un precio vigente, una asignación, un evento de auditoría y un
resultado de comando relacionados.
And la respuesta reconsultada coincide con lo persistido.

Cada punto de fallo inyectado antes del commit debe dejar los cinco conteos en cero.

## TDD-TC-259 Replay, conflicto de clave y concurrencia

Given un comando confirmado
When se repite con misma organización, actor, clave y hash
Then devuelve el resultado almacenado sin filas adicionales.
When cambia el payload bajo la misma clave
Then responde `idempotency_key_conflict` sin mutación.
When dos sesiones PostgreSQL actualizan desde el mismo `expected_updated_at`
Then una confirma y la otra responde `product_configuration_version_conflict`.

## TDD-TC-260 Precio versionado y campos estrictos

Given un producto con precio vigente
When se guarda el mismo precio
Then conserva una sola versión abierta.
When cambia el precio
Then cierra la anterior y abre exactamente una nueva con centavos enteros.
When el payload incluye `tax_rate`, `unit`, `service_dining`, `loyalty_accrual` u otra propiedad no
declarada
Then responde un error de contrato y no descarta el campo silenciosamente.

## TDD-TC-261 Estación, categoría y subgrupo canónicos

La prueba acepta `kitchen`, `drinks` y `packing`; rechaza etiquetas como `1 - BEBIDAS`. Rechaza una
categoría ajena, un subgrupo de otro grupo, un valor inactivo, falta de valor con selector activo y
valor presente sin selector activo. Cada rechazo conserva el estado previo completo.

## TDD-TS-116 Editor progresivo y comprobación POS

Cobertura frontend e integración:

- `tests/frontend/test_admin_product_flow.mjs` inspecciona la semántica del editor, borrador,
  mapeo estación-etiqueta, validación, errores, cambios pendientes y ausencia de defaults locales;
- `tests/frontend/test_product_capsule_tabs.mjs` verifica teclado, foco, paginación visual, sección
  activa y cantidad de cápsulas adaptada al ancho;
- `tests/frontend/test_admin_product_recipe.mjs` prohíbe `sampleDagNodes` y exige carga/estado vacío
  desde el contrato real;
- `tests/frontend/test_admin_product_pos_preview.mjs` prueba elegible, no elegible, error recuperable
  y falta de sucursal sin mutaciones de pedido o disponibilidad;
- una prueba de integración API/UI confirma que el mensaje de éxito usa la respuesta persistida y
  que un timeout permite reintentar con la misma clave;
- QA visual cubre escritorio, 200% de zoom y ancho estrecho con datos vacíos, error, borrador,
  guardado, receta ausente y producto no elegible.

## TDD-TC-262 Receta efectiva, permiso y ausencia real

Given un producto sin receta
When se abre Receta
Then aparece el estado vacío y no existen Fresa, Agua, Jarabe ni costo demostrativo.
Given una receta efectiva
Then componentes, versión, alcance y costo provienen de la respuesta API.
And editar sólo está disponible con `recipes.manage`.

## TDD-TC-263 Vista previa POS sin efectos

Given un producto guardado y una sucursal autorizada
When se consulta `pos-preview`
Then la elegibilidad coincide con las proyecciones canónicas de categorías y productos.
And los motivos de exclusión son estables.
And los conteos de pedidos, líneas, disponibilidad y reservas no cambian.

## TDD-TC-264 Borrador, navegación y verdad de persistencia

Given un alta nueva
Then se anuncia Borrador sin guardar, SKU está vacío y no aparecen valores financieros locales.
When el usuario navega por teclado o cambia la página visual de pestañas
Then foco, `aria-selected`, panel activo y datos capturados permanecen consistentes.
When intenta salir con cambios
Then puede continuar editando o descartar explícitamente.
When el backend rechaza o tarda
Then se conserva el borrador y nunca aparece confirmación de guardado.

## TDD-TC-265 Selección de producto y detalle principal

Given un producto está en edición
When el usuario acepta descartarlo y selecciona otra fila
Then `isEditing` termina antes de sincronizar el formulario.
And se activa Principal / Varios.
And nombre, SKU, grupo, precio, estación, estado e imagen provienen del producto seleccionado.
When el usuario rechaza descartar
Then la selección y el borrador permanecen sin cambios.

## TDD-TC-266 Alta contextual de grupo y subgrupo

Given un producto en edición con datos aún no guardados
When el usuario abre el botón más de Grupo
Then aparece un diálogo accesible dentro de Productos y no cambia la ruta.
When la API confirma el nuevo grupo
Then se refresca el catálogo, se selecciona el grupo creado y sólo se limpia el subgrupo incompatible.
Given un grupo seleccionado
When el usuario abre el botón más de Subgrupo
Then el diálogo identifica ese grupo y no permite reasignarlo durante el alta rápida.
When la API confirma el nuevo subgrupo
Then se refresca su cobertura y se selecciona el valor creado.
When el usuario cancela o cualquiera de las APIs falla
Then el formulario del producto y sus demás campos permanecen sin cambios.

## RED esperado

Antes de implementar, deben fallar por las razones siguientes:

1. el endpoint de configuración aún no existe;
2. el guardado actual confirma producto antes de asignar subgrupo;
3. el backend ignora propiedades enviadas por la UI;
4. la UI envía etiquetas de estación incompatibles;
5. `sampleDagNodes` presenta receta/costo ficticios;
6. el navegador genera SKU y defaults demostrativos;
7. no existe comprobación directa contra la proyección POS.

Una prueba que falle por rutas inexistentes, fixtures rotos o falta de dependencias no acredita RED.

## Comandos focalizados previstos

```bash
python3 -m pytest apps/api/tests/test_admin_product_flow.py tests/contract/test_admin_product_configuration_contract.py -q
ADMIN_PRODUCT_TEST_POSTGRES_URL=... python3 -m pytest apps/api/tests/test_admin_product_flow_postgres.py -q
node --test tests/frontend/test_admin_product_flow.mjs tests/frontend/test_product_capsule_tabs.mjs tests/frontend/test_admin_product_recipe.mjs tests/frontend/test_admin_product_pos_preview.mjs
pnpm --filter @restaurantos/admin-web typecheck
python3 -m ruff check apps/api/restaurant_os apps/api/tests/test_admin_product_flow.py apps/api/tests/test_admin_product_flow_postgres.py
python3 -m pytest tests/architecture/test_traceability.py -q
git diff --check
```

La suite completa aplicable se ejecuta una vez en CI. El build de Admin se ejecuta antes de release
porque el incremento cambia contratos, rutas y empaquetado. Migración PostgreSQL upgrade/downgrade,
QA visual y auditoría Sol independiente son gates obligatorios del cierre R3.
