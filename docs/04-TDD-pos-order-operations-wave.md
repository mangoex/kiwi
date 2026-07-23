# TDD - Operación POS, ajustes y compras de sucursal

## TDD-TS-063 Comentarios corporativos e ingredientes adicionales universales

Pruebas unitarias:

- parsear coma, salto de línea y dos o más espacios, conservar espacios simples dentro de cada
  comentario, recortar vacíos, deduplicar normalizado y conservar texto visible;
- rechazar comentario vacío, mayor a 120 caracteres o lote mayor a 100;
- calcular porciones con `Decimal` y cargos con centavos enteros, nunca `float`;
- impedir que costo promedio determine el precio de venta.
- rechazar `branch_id`/override en el catálogo global y rechazar destinos de otra organización;
- exigir configuración canónica completa al crear un adicional y rechazar escala Decimal no exacta;
- rechazar porciones duplicadas, cero, negativas, fraccionarias o fuera de `1..99`.

Pruebas de integración API y base de datos:

- el catálogo de productos entrega `category_id` y `category_name`, y el identificador coincide con
  el catálogo de categorías para permitir el agrupamiento estable de la UI;
- alta masiva hace upsert idempotente y agrega relaciones sin retirar las no enviadas;
- preview de alta masiva reporta creados, existentes y duplicados antes de mutar;
- confirmación de comentarios falla en UI si cambia el texto o los destinos desde el preview;
- reemplazo explícito de productos conserva auditoría y no cruza organización;
- Supervisor y Cajero no mutan comentarios; dos sucursales leen la misma definición;
- pedido acepta sólo `comment_preset_ids` activos y relacionados y congela snapshot sin inventario;
- endpoint de adicionales universales no exige relación producto-adicional y no expone overrides;
- adicionales se aplican a cualquier línea sin consultar `ingredient_variation_products`;
- precio, cantidad, reserva, consumo, costo y estación se recalculan en backend;
- precio manipulado, extra sin línea destino y porciones no enteras se rechazan;
- una línea con cantidad uno y otra mayor a uno preservan total, costo, reserva, consumo, KDS e
  impresión con el adicional multiplicado exactamente una vez por unidad vendida;
- acciones históricas `remove` o IDs de asignación fallan con `ingredient_extra_add_only`.
- cualquier `add_option_id` o `remove_option_id` de `ingredient_variation_products`, incluso si la
  variación está `needs_review`, incompleta o la opción heredada sigue activa, no aparece y falla
  antes de crear un pedido; modificadores ajenos se conservan;
- preview, alta, actualización y archivo de asignaciones históricas devuelven
  `ingredient_variation_assignments_read_only` y los fixtures insertan esos datos directamente
  cuando una regresión necesita historial.

Pruebas de migración PostgreSQL/SQLite:

- `0027 -> 0028 -> 0027 -> 0028` conserva una sola head;
- presets antiguos se deduplican y relacionan sin cambiar pedidos ni snapshots;
- configuraciones de adicional consistentes se consolidan;
- configuraciones contradictorias quedan `needs_review` y no se publican;
- upgrade/downgrade/upgrade conserva las tablas históricas y elimina sólo los objetos propios de `0028`;
- la auditoría de migración se registra con los conteos de cada organización afectada;
- downgrade restaura campos y el `status` exacto previo (`active` y `archived`) antes de eliminar
  el respaldo propio de `0028`, y no elimina tablas históricas de modificadores.

Pruebas frontend:

- la selección filtra productos con `status=active` y los relaciona por `category_id`;
- un fallo de comentarios se muestra aparte y no impide presentar categorías y productos cargados;
- categorías operativas se despliegan y agrupan subcategorías por `station` sin crear una segunda
  jerarquía persistida;
- cada subcategoría tiene casilla accesible, conteo de productos activos y selección múltiple por
  teclado;
- textarea muestra comentarios detectados, conteos de subcategorías/productos y preview antes de
  confirmar;
- botón Ingredientes adicionales está junto a Cliente y deshabilitado con carrito vacío;
- una línea se autoselecciona; varias exigen destino; cada extra puede retirarse;
- comentario y extra se muestran en bloques distintos y en español;
- el carrito despliega cada comentario elegido y todos los importes se calculan desde centavos;
- la pantalla canónica de adicionales no administra ni presenta relaciones históricas por producto
  como requisito de venta.

## TDD-TC-058 Catálogos globales sin dependencia de sucursal

Given comentarios, adicionales, dos productos y dos sucursales
When el Administrador relaciona comentarios y configura un adicional corporativo
Then ambas sucursales leen las mismas definiciones
And sólo los comentarios se filtran por relación de producto
And el adicional se aplica a cualquier línea con precio e inventario calculados por backend
And no existe override por sucursal ni mutación histórica de asignaciones legacy.

## TDD-TS-064 Carrito y enmiendas versionadas de pedido

Pruebas unitarias y frontend:

- no existe una banda de accesos que duplique los productos de la cuadrícula;
- menos sobre cantidad uno y papelera retiran la línea y recalculan total;
- controles tienen `aria-label`, foco y objetivo táctil mínimo;
- la navegación se llama Pedidos, abre todas las filas y traduce estados;
- modo edición muestra folio, evita crear un segundo pedido y separa Guardar de Pagar.

Pruebas de integración:

- detalle requiere `orders.read` y misma sucursal;
- enmienda requiere `orders.amend`, `Idempotency-Key` y `expected_version`;
- versión vigente retira lógicamente líneas, crea reemplazos, tareas y compensaciones de reserva;
- reintento devuelve el mismo resultado y versión obsoleta falla sin efectos parciales;
- pago confirmado, estado distinto de `ACCEPTED` o tarea no `PENDING` bloquea edición;
- total, comentarios y adicionales se recalculan desde catálogo vigente y snapshots nuevos;
- eventos, auditoría y líneas anteriores permanecen consultables.

Pruebas de migración:

- `0028 -> 0029 -> 0028 -> 0029` preserva pedidos existentes como versión uno;
- downgrade falla de forma segura si perdería enmiendas no representables o conserva su respaldo
  según la estrategia aprobada en la migración;
- no se eliminan pagos, tareas, movimientos o snapshots.

## TDD-TC-059 Enmienda atómica antes de producción

Given un pedido ACCEPTED sin pago con tareas PENDING y versión uno
When se reemplaza una línea usando versión uno
Then queda versión dos con enmienda, reservas compensadas y tareas actualizadas
And un segundo comando con versión uno falla sin cambios parciales
And el pedido previo permanece auditable.

## TDD-TS-073 Panel lateral de revisión de pedidos

Pruebas frontend y arquitectura:

- Pedidos no importa ni renderiza `Modal` para el detalle;
- la página mantiene simultáneamente lista y panel lateral con estado vacío, carga y detalle;
- seleccionar una fila la resalta y actualiza el panel sin navegación ni popup;
- el panel muestra folio, cliente, tipo, estado, líneas y total;
- pago pendiente conserva selección de método y **Confirmar pagado**;
- `editable=true` conserva **Editar pedido** y los pedidos bloqueados muestran su motivo;
- en anchos reducidos el panel se apila dentro de la página.

## TDD-TC-069 Revisión y acciones desde maestro–detalle

Given pedidos pagados, pendientes y editables en la misma sucursal
When el Cajero cambia la fila seleccionada
Then la lista no desaparece y el panel derecho refleja sólo el pedido vigente
And confirmar pago refresca lista y detalle
And editar navega al POS con el identificador del pedido.

## TDD-TS-069 Pedidos con pago diferido

Pruebas API y dominio:

- `takeout` y `delivery` aceptan un método previsto válido sin insertar un pago;
- `dine-in` no cambia su confirmación inmediata en el cliente POS;
- el listado y detalle proyectan `payment_status`, método previsto y **Pendiente de pago**;
- confirmar desde Pedidos exige `payments.confirm`, total exacto y ausencia de pago previo;
- la enmienda conserva el método previsto y no crea pago;
- método previsto inválido se rechaza antes de crear orden.

Pruebas frontend:

- Para llevar/A domicilio cambia la acción a **Guardar pedido pendiente**;
- Pedidos reemplaza Historial en navegación y encabezado;
- cada fila abre detalle y una pendiente ofrece **Confirmar pago**;
- sólo pedidos con `editable=true` ofrecen **Editar pedido** y el POS guarda una enmienda.

## TDD-TC-065 Cobro diferido confirmado al entregar

Given un pedido takeout ACCEPTED con payment_method_intent cash y sin pago
When se confirma desde Pedidos el total vigente por debit_card
Then queda un pago CONFIRMED debit_card, la orden CLOSED y los eventos auditables
And no se conserva cash como si hubiera sido el método realmente recibido.

## TDD-TS-065 Reautenticación y ajustes append-only

Pruebas de seguridad:

- sólo Supervisor de la misma sucursal o Administrador con alcance emite autorización;
- Cajero no se autoautoriza y los errores no enumeran usuarios;
- contraseña no aparece en tablas, auditoría, logs, excepciones ni estado persistido del navegador;
- token se almacena hasheado, expira en dos minutos, es de un uso y está ligado a acción, pedido y
  sucursal;
- token expirado, consumido, alterado o de otro pedido falla atómicamente;
- intentos repetidos pasan por limitación y evento de seguridad sin credenciales.

Pruebas de dominio e integración:

- total objetivo debe estar entre cero y subtotal calculado;
- justificación recortada debe medir entre 10 y 240 caracteres;
- validación de datos ocurre antes de consumir un token válido;
- ajuste crea fila append-only, evento, auditoría y actualiza la proyección cobrable;
- ajustes sucesivos agregan deltas y no sobrescriben historia;
- pago exige exactamente el total resultante y luego bloquea ajustes.

Pruebas frontend:

- modal muestra subtotal, ajustes, nuevo total, diferencia, Supervisor y justificación;
- contraseña se limpia al cerrar, fallar o completar;
- carrito distingue Subtotal de productos, Cortesías y Total a pagar.

## TDD-TC-060 Cortesía de adicional sin borrar su precio

Given una línea con adicional de 3000 centavos y subtotal de 15000
When un Supervisor autoriza nuevo total 12000 con una justificación válida
Then el adicional conserva precio, costo, reserva y consumo en su snapshot
And se agrega un ajuste de -3000 separado
And el pago confirmado es de 12000
And auditoría identifica solicitante y autorizador sin credenciales.

## TDD-TS-066 Proveedores y presentaciones creados desde sucursal

Pruebas API:

- lectura devuelve catálogo corporativo para la sucursal autorizada;
- `suppliers.create` crea proveedor central y términos de sucursal en una transacción;
- código o RFC duplicado revierte proveedor, contacto y términos;
- `purchase_presentations.create` valida insumo, unidades y conversión `Decimal`;
- Supervisor no edita proveedor existente ni otra sucursal; Cajero no crea;
- cada alta produce auditoría con procedencia, sin datos fiscales en logs.

Pruebas frontend:

- Proveedores conserva layout POS y ofrece modales Nuevo proveedor y Nueva presentación sólo con
  permiso;
- errores de duplicidad o validación se muestran sin cerrar el formulario;
- proveedor recién creado queda seleccionado y la presentación recién creada queda disponible.

## TDD-TC-061 Alta transaccional de proveedor de sucursal

Given un Supervisor de Constitución con suppliers.create
When registra un proveedor único con contacto y habilitación local
Then se crean proveedor, contacto opcional, términos y auditoría en una transacción
And un Cajero o un código duplicado no dejan datos parciales.

## TDD-TS-067 Compras multi-línea y conciliación de caja

Pruebas de dominio e integración:

- borrador exige proveedor, folio único, fecha y al menos una presentación válida;
- cantidades, precios, descuento, impuesto, subtotal y total usan `Decimal` exacto;
- navegador no puede imponer cantidad base, costo promedio ni total;
- confirmación multi-línea idempotente crea un `PURCHASE_RECEIPT` por línea;
- efectivo exige turno abierto y crea exactamente un retiro `SUPPLY_PURCHASE`;
- tarjeta y transferencia no crean movimiento de caja;
- crédito responde `purchase_credit_not_supported` mientras no exista cuenta por pagar;
- cancelación confirmada crea reversas referenciadas y nunca elimina movimientos;
- sucursal de sesión prevalece sobre cualquier `branch_id` del payload.

Pruebas frontend:

- Nueva compra permite agregar, editar y retirar múltiples renglones;
- proveedor filtra presentaciones y la etiqueta visible muestra insumo y presentación;
- Efectivo es predeterminado y explica que afectará caja;
- Confirmar usa idempotency key estable hasta recibir éxito;
- estados y errores se traducen a español y la tabla muestra nombre, no UUID de proveedor.

## TDD-TC-062 Compra en efectivo afecta inventario, costo y caja una vez

Given un Supervisor con turno abierto y una compra de dos presentaciones
When confirma dos veces con la misma idempotency key
Then existe una recepción por línea, un solo retiro de caja y un solo documento confirmado
And costo promedio y existencia se actualizan una vez
And cancelar crea compensaciones sin borrar los originales.

## Comandos mínimos de verificación por incremento

```bash
python -m pytest apps/api/tests -q
python -m pytest tests/architecture/test_traceability.py -q
python -m ruff check apps/api tests
pnpm typecheck
pnpm --filter @restaurantos/admin-web build
pnpm --filter @restaurantos/pos-web build
pnpm --filter @restaurantos/kds-web build
git diff --check
```

Cada incremento debe añadir pruebas negativas específicas y reportar el total exacto. Una prueba de
arquitectura por texto no sustituye una prueba de comportamiento API, dominio o componente.
