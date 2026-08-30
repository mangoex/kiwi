# SDD — Software Design Document

## 1. Objetivo

Definir la arquitectura, componentes, límites, modelo de datos, sincronización y decisiones técnicas que implementan el PRD.

## 2. Principios de diseño

1. Dominio primero.
2. Monolito modular inicial.
3. Integraciones por adaptadores.
4. Offline como capacidad de dominio, no como caché.
5. Eventos y comandos idempotentes.
6. Datos financieros e inventariables inmutables.
7. Versionado de catálogos sensibles.
8. Observabilidad desde la primera entrega.
9. Despliegue reproducible.
10. Evolución gradual hacia servicios separados solo cuando exista necesidad operativa.

## 3. Arquitectura lógica

```text
Clientes web
├── Admin
├── POS
├── KDS
└── Despacho

Gateway local
├── API local
├── SQLite
├── Sync engine
├── Print service
└── WebSocket hub

Nube
├── API central
├── PostgreSQL
├── Redis
├── Worker
├── Integraciones
├── Route adapter
├── Export adapter
└── Observabilidad
```

## 4. Decisiones arquitectónicas

### SDD-ADR-001 Monorepo
Se utilizará monorepo para compartir contratos, tipos, fixtures, UI y herramientas.

### SDD-ADR-002 Frontend
React + TypeScript + Vite para POS, KDS y administración.

### SDD-ADR-003 Backend
Python + FastAPI, con Pydantic y tipado estricto.

### SDD-ADR-004 Base central
PostgreSQL como fuente transaccional principal.

### SDD-ADR-005 Base local
SQLite en modo WAL dentro del gateway de sucursal.

### SDD-ADR-006 Cache y coordinación
Redis para locks, rate limiting, cache, jobs y coordinación no durable.

### SDD-ADR-007 Monolito modular
Un backend desplegable con módulos bien definidos en la primera etapa. No microservicios prematuros.

### SDD-ADR-008 Sincronización
Outbox/inbox, command log, idempotency keys y checkpoints por sucursal.

### SDD-ADR-009 Inventario
Ledger de movimientos; existencia calculada y materializada para lectura.

### SDD-ADR-010 Dinero y cantidades
`Decimal` en Python y tipos exactos en PostgreSQL.

### SDD-ADR-011 Impresión
Agente Windows local con spooler, ESC/POS opcional y colas persistentes.

### SDD-ADR-012 Rutas
Puerto interno `RouteOptimizationProvider` con adaptadores externos.

### SDD-ADR-013 CONTPAQi
Modelo canónico y adaptadores de exportación.

### SDD-ADR-014 Eventos
Eventos de dominio internos y eventos de integración separados.

### SDD-ADR-015 Autorización
RBAC con alcance de organización, razón social y sucursal.

Permisos operativos mínimos para fase POS/caja:

- `admin.manage`: administrar usuarios, roles y permisos.
- `catalog.manage`: administrar sucursales, almacenes, productos, categorías y recetas.
- `inventory.adjust`: registrar ajustes administrativos de inventario.
- `orders.cancel`: cancelar pedidos y clasificar cancelaciones producidas.
- `cash.shift.read`: consultar turnos y resumen de caja.
- `cash.shift.open`: abrir turno de caja.
- `cash.shift.close`: cerrar turno de caja y generar corte.
- `orders.read`: consultar pedidos.
- `orders.create`: crear pedidos desde POS.
- `payments.read`: consultar pagos.
- `payments.confirm`: confirmar pagos.
- `dashboard.read`: consultar indicadores operativos.
- `pos.operate`: entrar a la aplicación POS.
- `purchases.read`: consultar compras de la sucursal.
- `purchases.manage`: registrar y confirmar compras directas de la sucursal.
- `cash.withdraw`: registrar retiros autorizados de efectivo.
- `inventory.read`: consultar existencias y kardex de la sucursal.
- `inventory.waste`: registrar mermas reales autorizadas.
- `inventory.transfer.send`: iniciar y confirmar envíos entre sucursales.
- `inventory.transfer.receive`: confirmar recepción y diferencias de un traspaso.
- `inventory.count`: iniciar y capturar conteos físicos.
- `production.manage`: crear y confirmar lotes de producción de elaborados.
- `audit.read`: consultar auditoría sin alterar operaciones.
- `branch.admin.access`: entrar al centro administrativo operativo de la sucursal.
- `branch.staff.read`: consultar el personal asignado a la sucursal.
- `catalog.branch.manage`: modificar únicamente disponibilidad y excepciones de catálogo para una sucursal autorizada.

Los roles semilla deben asignarse por permisos, no por comparaciones de nombre en UI. `Administrador corporativo` recibe todos los permisos. `Cajero` recibe `pos.operate`, lectura/apertura/cierre de caja, creación/lectura de pedidos y confirmación de pagos en su sucursal asignada. Por compatibilidad operacional, un rol legacy llamado `Caja` debe recibir el mismo perfil de permisos que `Cajero` hasta que los datos productivos sean normalizados. Los endpoints sensibles deben resolver actor desde `Authorization: Bearer <token>` o `X-Actor-User-Id` solo para pruebas/herramientas internas. Si falta actor en una acción sensible, la API debe rechazar la operación; no se debe asumir el administrador semilla.

Admin y POS usan las mismas entidades centrales para productos, categorías, insumos, sucursales y
usuarios. `branch_product_availability` es únicamente una excepción por sucursal: un registro ausente
hereda disponibilidad central y un registro `false` la deshabilita. La consulta administrativa usa
unión exterior con el precio vigente para no perder productos incompletos; POS sólo presenta productos
activos, disponibles y con precio vigente positivo.

El contexto de sucursal se persiste con una selección canónica compartida por Admin y POS. Una cuenta
con alcance de sucursal no puede sustituir su asignación localmente. Una cuenta corporativa puede elegir
entre sucursales válidas; todos los módulos que consultan compras, proveedores, costos, producción,
mermas, traspasos, conteos, recetas o modificadores deben resolver esa misma selección.

El centro administrativo accesible desde el shell POS distingue entre administración corporativa y
administración operativa por sucursal. La administración corporativa se protege con `admin.manage` o
`catalog.manage`; la administración operativa de sucursal se protege con `branch.admin.access`,
`branch.staff.read` y `catalog.branch.manage`. Su elemento de navegación y su ruta se protegen por
permisos; ocultar el enlace no reemplaza el guard de ruta.

Deuda técnica: `is_superadmin` se determina actualmente por comparación del correo electrónico del
usuario (`mangoex@gmail.com`) en `authenticate_user`. Esta regla se conserva por compatibilidad de
firma del token y perfil de login, pero la fuente operativa de autoridad son los permisos y roles
persistidos en la base de datos, resueltos en backend mediante `require_permission` y
`authorize_branch_scope`. No se debe confiar en `is_superadmin` emitido desde el cliente como regla
de autorización.

`Supervisor de sucursal` recibe los permisos de Cajero más lectura de inventario, compras,
retiros, mermas, envío de traspasos y conteos, siempre limitado a su sucursal. Además recibe
`branch.admin.access`, `branch.staff.read`, `catalog.branch.manage` y `production.manage`, que le
permiten operar la administración de su sucursal sin equivaler a administrador corporativo; no
recibe `admin.manage` ni `catalog.manage`. `Receptor de traspaso` recibe lectura de inventario y
recepción de traspasos. `Auditor` recibe consultas de dashboard, inventario, pagos, pedidos,
compras y auditoría, sin permisos de mutación.

### SDD-ADR-016 Unidad de negocio

La jerarquía persistida es `organization -> legal_entity -> business_unit -> branch -> warehouse`.
`business_units` pertenece a una organización y una razón social, tiene código único por
organización y tipo `restaurant`, `bakery`, `production` u `other`. La validación de `unit_type`
se realiza en el dominio; no se crean registros productivos automáticamente. `branches.business_unit_id` es obligatorio después de
la migración de datos. Se conserva temporalmente `branches.legal_entity_id` como referencia
desnormalizada para compatibilidad y se valida que coincida con la razón social de la unidad.

El dialogo de login es unico. Tras autenticar, el cliente debe identificar permisos y dirigir al usuario administrativo al Admin y al usuario de caja al POS. Si el usuario tiene sucursal asignada, el cliente debe configurar esa sucursal en POS y usar `CAJA-01` como caja predeterminada cuando no exista un identificador local.

## 5. Módulos de dominio

### 5.1 Identity and Access
Usuarios, roles, permisos, sesiones, dispositivos y auditoría.

La capa HTTP centraliza autenticación en una dependencia reutilizable que:

1. valida token de sesión,
2. obtiene actor activo,
3. resuelve permisos,
4. aplica alcance de sucursal cuando el comando recibe `branch_id`,
5. registra auditoría `authorization.denied` cuando rechaza una acción sensible.

### 5.2 Organization
Organización, razones sociales, sucursales, almacenes y ubicaciones.

### 5.3 Catalog
Productos, variantes, combos, modificadores, precios, horarios y mapeos externos.

### 5.4 Orders
Pedidos, líneas, eventos, estados, pagos previstos y cancelaciones.

Los pedidos creados por POS se aceptan solo si el actor tiene `orders.create`, tiene alcance sobre la
sucursal solicitada y existe un turno abierto para la caja. El total persistido por el backend es la
fuente de verdad para el cobro. `POST /api/v1/orders` exige `Idempotency-Key`; PostgreSQL conserva
organización, sucursal, actor, hash canónico de la intención, pedido y respuesta estable. El replay
revalida actor, permiso y alcance antes de consultar la respuesta. Clave con actor, alcance, caja,
cliente, entrega, pago previsto, conductor o líneas distintos falla `order_create_idempotency_conflict`.
La fila de comando se confirma en la misma transacción que pedido, reservas, tareas, eventos y
auditoría. SQLite reserva la escritura antes de leer folio/outbox y PostgreSQL toma un advisory lock
transaccional derivado de organización y clave antes de buscar o crear el comando; así dos misses
concurrentes no exponen conflicto de folio ni una excepción de unicidad. El POS conserva la misma
clave durante un resultado incierto, bloquea doble submit y sólo
genera otra cuando cambia la intención o existe una respuesta definitiva.
`order_create_commands.response_snapshot` conserva únicamente la parte técnica estable de la
respuesta: no duplica `owner_name`, identificadores/snapshots de cliente o domicilio, nombres de
repartidor ni notas libres de línea. Un replay rehidrata esos campos exclusivamente desde las filas
históricas inmutables del pedido, sus líneas y su asignación; si falta una fuente, falla cerrado con
`order_create_replay_incomplete` en vez de devolver una respuesta parcial.
Antes de crear, POS guarda en `sessionStorage` sólo sucursal, caja, método y UUIDs de pedido/pago;
no persiste carrito, nombre, cliente, domicilio, notas ni el fingerprint de la intención. Tras una
recarga, `POST /orders/recover` recibe cuerpo vacío y la clave original, vuelve a autenticar actor,
permiso y alcance y resuelve la respuesta desde el command log. Si el pedido existía, POS confirma
el pago con su clave original; si no existe, informa que puede recapturarse. Un error incierto
conserva la intención técnica, y logout la elimina.

### 5.4.1 Customer directory

`Customer` conserva identidad interna y datos generales. `CustomerPhone`, `CustomerAddress` y
`CustomerTaxProfile` son entidades separadas. Los teléfonos mexicanos se guardan como valor
capturado y valor normalizado E.164; la búsqueda puede devolver varias coincidencias y nunca hace
merge automático. Las direcciones no tienen un límite por cliente.

`Order` guarda `customer_id` como referencia opcional y snapshots JSON de cliente y dirección.
El snapshot se construye dentro de la misma transacción que acepta el pedido. Para `delivery`, la
dirección debe pertenecer al cliente seleccionado. Cambiar o desactivar el directorio no modifica
el snapshot. El gateway debe transportar IDs y snapshots en el comando idempotente.

### 5.5 Production
Tareas por estación, KDS, tiempos, incidencias y finalización.

### 5.6 Cash
Turnos, movimientos, arqueos, cortes, reaperturas y depósitos.

Abrir y cerrar turnos requiere permisos `cash.shift.open` y `cash.shift.close`; consultar turno o resumen requiere `cash.shift.read`. La auditoría de apertura/cierre debe guardar el usuario real que ejecutó la acción y la sucursal afectada.

El pago confirmado conserva un `method` normalizado. Las ventas nuevas del POS usan `cash`,
`debit_card`, `credit_card` o `transfer`; `card` se acepta sólo por compatibilidad histórica. Débito y
crédito permanecen separados en el pago, el evento `PAYMENT_CONFIRMED` y la auditoría. El cálculo de
efectivo esperado sólo suma pagos cuyo método sea `cash`.

`POST /api/v1/orders/{order_id}/payments` publica y exige `Idempotency-Key`. Python calcula una
huella canónica de organización, actor, pedido, importe, método normalizado y caja. La misma clave e
intención devuelve el resultado persistido después de reautorizar al actor, aun si la respuesta
original se perdió; cualquier diferencia falla `payment_idempotency_conflict`. El comando, pago,
snapshot de venta, líneas históricas, evento, trabajos/intentos de impresión y auditoría se confirman
en una sola transacción. El POS conserva la clave del pago junto con la intención de checkout hasta
recibir resultado definitivo y bloquea el doble envío mientras la petición está en curso.

### 5.7 Inventory
Artículos, unidades, conversiones, lotes, movimientos, reservas y conteos.

`WasteReason` es catálogo central configurable y `WasteRecord` es un documento con estados `draft`,
`confirmed`, `reversed` o `cancelled`. El borrador no genera movimiento. `confirm` bloquea la política
de existencia negativa, toma el costo promedio vigente y crea un único `WASTE_REAL` negativo mediante
idempotency key. El documento conserva cantidad, costo, etapa, motivo, evidencia, fecha efectiva,
capturista y autorizador. `reverse` no edita el original: crea `WASTE_REVERSAL` positivo con
`reversal_of_id`, restaura la cantidad en el estado de costo sin recalcular su promedio y exige motivo.
Merma de receta y cancelación producida permanecen como categorías distintas para reporte.

`InventoryTransfer` separa origen y destino y contiene `InventoryTransferLine`. El documento es el
sublibro de inventario en tránsito: al pasar de `draft` a `sent`, cada línea congela cantidad y costo
promedio de origen, crea `TRANSFER_OUT` y reduce el estado de costo de origen. No existe entrada
automática. Un usuario con alcance en destino confirma cantidades por línea; el servicio crea
`TRANSFER_IN` solo por lo recibido y calcula el nuevo promedio ponderado del destino usando el costo
congelado. `sent = received + difference`; una diferencia exige motivo y queda valorizada en la línea.
Enviar y recibir son comandos idempotentes independientes. Un borrador puede cancelarse sin
movimientos; un envío no se cancela ni se edita y debe concluir por recepción normal o con diferencia.

`PhysicalCountSession` usa estados `counting`, `submitted`, `approved`, `closed` o `cancelled` y
contiene una línea por artículo incluido. Al abrir, congela cantidad teórica, costo promedio y valor;
durante `counting`, las respuestas de captura ocultan esos valores para mantener conteo ciego. Cada
línea conserva cantidad física, capturista y fecha. `submit` exige todas las líneas capturadas, calcula
`snapshot_difference = counted - theoretical_snapshot` y revela la conciliación sin mover inventario.
`approve` requiere `inventory.count` e idempotency key; vuelve a leer el ledger y calcula
`adjustment = counted - current_ledger_quantity`, de modo que compras, ventas o traspasos posteriores
a la fotografía no sean sobrescritos. Cada ajuste no cero crea `COUNT_ADJUSTMENT` con costo promedio
vigente y actualiza el estado de costo sin recalcular su costo unitario. `close` inmoviliza el reporte.
Un conteo activo por sucursal evita fotografías competidoras; solo `counting` puede cancelarse.

### 5.8 Recipes and Costing
Recetas, versiones, subrecetas, explosión, costo estándar y promedio.

Una receta tiene tipo `sale` cuando produce un producto vendible y `production` cuando produce un
artículo elaborado. Sus componentes siempre apuntan a artículos inventariables; un elaborado puede
ser componente, pero la activación valida que el grafo sea acíclico. La cantidad bruta persistida se
calcula con `net / (1 - waste_rate)` usando `Decimal`.

`RecipeCostCalculation` conserva sucursal, versión, costos y desglose. Recalcular costo no modifica
pedidos históricos. `OrderLineConsumptionSnapshot` congela receta, componentes brutos, costos y
modificadores efectivos al aceptar el pedido.

Los modificadores se modelan como `ModifierGroup` ligado al producto y `ModifierOption`. La opción
declara un efecto de dominio (`remove`, `add`, `substitute`, `quantity`, `variant`, `instruction`),
artículo afectado/reemplazo y cantidades exactas. `BranchModifierOption` solo sobreescribe habilitación
y precio, sin copiar el catálogo. Al aceptar una línea, el servicio valida mínimo/máximo, resuelve la
configuración de sucursal, calcula precio y componentes finales, y persiste ambos en la línea y en
`OrderLineConsumptionSnapshot`. Reserva, consumo y cancelación leen ese snapshot. KDS recibe el texto
congelado; `instruction` se audita pero no produce movimiento.

El formulario corporativo convierte el precio adicional desde texto MXN a centavos mediante el
parser decimal exacto compartido; no usa `float` ni redondeo. La creación espera la promesa real de
la mutación HTTP antes de cerrar el formulario. Un rechazo conserva los datos capturados y muestra
el mensaje del servidor, mientras una respuesta exitosa invalida y recarga el catálogo central.

`PATCH /modifier-groups/{id}` y `PATCH /modifier-options/{id}` modifican únicamente el catálogo
vigente con `catalog.manage`; pedidos aceptados conservan el snapshot anterior. Los `DELETE` homólogos
son retiros lógicos auditados: archivar un grupo archiva sus opciones activas en la misma transacción,
y archivar una opción falla si las opciones restantes no cubren el mínimo del grupo. Altas y
renombres de grupos serializan el namespace con bloqueo de producto antes del grupo; las mutaciones
de opciones bloquean y revalidan grupo antes de opción, mientras el retiro completo bloquea el grupo
antes de archivar sus opciones. `GET /products/{id}/modifier-groups` exige
`catalog.manage` y devuelve el catálogo central completo, sin ocultar opciones deshabilitadas ni
aplicar sobreprecios de una sucursal. Toda escritura limita organización y registra auditoría
corporativa con `branch_id=null`. Los nombres archivados conservan su identidad y una recreación
homónima falla con conflicto estable, no con error de base de datos. Opciones de comentarios o
ingredientes adicionales responden `modifier_catalog_managed_elsewhere` porque su ciclo de vida
pertenece a sus catálogos canónicos; nunca se borran físicamente filas históricas.

### 5.9 Batch Production
Órdenes, consumo de lotes, rendimiento, merma y lote resultante.

Confirmar `ProductionBatch` crea `PRODUCTION_INPUT` por componente y `PRODUCTION_OUTPUT` para el
elaborado. El costo unitario del elaborado es el costo real total consumido dividido entre el
rendimiento real. La receta de venta que usa ese elaborado descarga únicamente el elaborado; nunca
vuelve a explotar sus materias primas. Confirmación y reintentos usan idempotency key.

### 5.10 Purchasing
Proveedores, recepciones, XML, equivalencias, cuentas por pagar y pagos.

`Supplier` es catálogo central. `SupplierContact` separa contactos operativos; `SupplierBranchTerms`
define disponibilidad y condiciones particulares por sucursal. `PurchasePresentation` relaciona
proveedor, artículo inventariable y unidad comercial con un rendimiento exacto en la unidad base.

Los campos monetarios, cantidades, porcentajes y conversiones usan `NUMERIC`/`Decimal`. Caja,
bolsa, paquete o frasco no definen conversión universal: la conversión vive en cada presentación.
El costo informativo por unidad base es `precio_neto / contenido_aprovechable`. Editar precio crea
`SupplierPriceHistory`, pero no escribe costo promedio ni movimientos de inventario. Sólo una
recepción confirmada puede producir esos efectos.

`PurchaseDocument` se captura en borrador con renglones snapshot de presentación y conversión.
Confirmar se ejecuta en una transacción: valida idempotencia, recalcula totales, crea
`PURCHASE_RECEIPT`, actualiza `InventoryCostState` y opcionalmente crea `CashMovement(WITHDRAWAL)`
con motivo `SUPPLY_PURCHASE`. Compra y retiro se enlazan uno a uno; consultar cualquiera permite
conciliar el otro. La cantidad recibida se registra como `Decimal`.

Política base aprobada para este incremento:

- costo inventariable de línea = subtotal menos descuento;
- impuestos permanecen separados y no incrementan costo promedio;
- flete y gastos adicionales deben ser cero hasta definir su distribución;
- existencia cero usa directamente el costo de la entrada;
- existencia negativa produce `negative_inventory_cost_policy_required` y no confirma parcialmente;
- una cancelación confirmada genera movimientos `PURCHASE_REVERSAL` y `CASH_REVERSAL` referenciados;
- las operaciones usan idempotency key y no se resuelven con última escritura gana.

### 5.11 Delivery (PRD-FR-210 y PRD-FR-211)
Zonas, direcciones, repartidores, rutas, asignaciones y liquidación.

`Driver` es un registro corporativo asignado a una sucursal y separado de `User`: estar en el
catálogo no concede acceso al sistema. Conserva `name`, `license_number`, `motorcycle_plate`,
`branch_id`, `phone`, `address`, `emergency_contact_name`, `status`, timestamps y organización.
La API administrativa devuelve también `branch_name`.

El catálogo usa `admin.manage`. Crear y editar exige que la sucursal pertenezca a la organización y
esté activa. Los campos solicitados se recortan y no se aceptan vacíos. La acción eliminar es una
desactivación lógica para preservar futuras referencias de rutas, entregas y liquidaciones. Los
eventos de auditoría registran identificador, sucursal, acción y nombres de campos modificados; no
repiten teléfono, domicilio, licencia ni placas en el payload.

`DeliveryAssignment` se crea únicamente durante `create_local_order` para pedidos `delivery`.
`driver_id` es opcional; si se proporciona, el repartidor debe estar activo y pertenecer a la misma
sucursal autorizada del pedido. En la misma transacción se congela `driver_name_snapshot`,
`customer_name_snapshot`, `delivery_address_snapshot`, `order_total_cents`, `currency`,
`line_count`, `item_quantity`, `assigned_by` y `assigned_at`. La tabla tiene una asignación por
pedido y no se actualiza ni elimina; una futura reasignación requerirá un evento compensatorio.

`GET /delivery/drivers/available?branch_id=...` usa `orders.create`, valida alcance y sólo devuelve
repartidores activos de esa sucursal. El modal de cobro consume esa lectura únicamente cuando el
tipo ya seleccionado es `delivery`; no vuelve a renderizar controles para cambiar tipo de pedido.
El administrador consulta `GET /drivers/{driver_id}/deliveries`, protegido por `admin.manage`, para
ver folio, cliente, total, cantidades, sucursal, estado y fecha sin recalcular historia.

### 5.12 Integrations
WhatsApp, chatbot, marketplaces, webhooks, reintentos y dead-letter queue.

### 5.13 Exports
Modelo canónico, lotes, layouts, validación y conciliación.

### 5.14 Sync
Comandos locales, eventos remotos, checkpoints, conflictos y reintentos.

## 6. Modelo de datos principal

Entidades centrales:

- `organizations`
- `legal_entities`
- `branches`
- `warehouses`
- `warehouse_locations`
- `users`
- `roles`
- `permissions`
- `devices`
- `registers`
- `stations`
- `printers`
- `products`
- `product_variants`
- `modifiers`
- `combos`
- `price_versions`
- `external_product_mappings`
- `customers`
- `customer_addresses`
- `orders`
- `order_lines`
- `order_events`
- `production_tasks`
- `payments`
- `cash_shifts`
- `cash_movements`
- `inventory_items`
- `units`
- `unit_conversions`
- `inventory_lots`
- `inventory_reservations`
- `inventory_movements`
- `recipe_versions`
- `recipe_components`
- `production_batches`
- `production_batch_inputs`
- `suppliers`
- `supplier_product_mappings`
- `purchase_receipts`
- `purchase_receipt_lines`
- `supplier_invoices`
- `accounts_payable`
- `supplier_payments`
- `delivery_zones`
- `drivers`
- `delivery_routes`
- `delivery_route_stops`
- `integration_messages`
- `sync_commands`
- `sync_events`
- `export_batches`
- `audit_events`

Todas las tablas operativas deberán incluir, según corresponda:

- `id` UUID o UUIDv7.
- `organization_id`.
- `branch_id`.
- `created_at`.
- `updated_at`.
- `created_by`.
- `version`.
- `source_device_id`.
- `correlation_id`.
- `causation_id`.

## 7. Máquinas de estado

### 7.1 Pedido

```text
DRAFT
→ ACCEPTED
→ SENT_TO_PRODUCTION
→ IN_PRODUCTION
→ READY
→ IN_DELIVERY
→ DELIVERED
→ CLOSED
```

Estados alternos:

- `CANCELLED`
- `REJECTED`
- `FAILED`
- `RETURNED`

Cada transición tendrá:

- actor permitido,
- precondiciones,
- evento,
- efecto en inventario,
- efecto en pago,
- efecto en producción,
- efecto en entrega,
- auditoría.

### 7.2 Tarea de producción

```text
PENDING → IN_PROGRESS → COMPLETED
```

Alternos:

- `BLOCKED`
- `CANCELLED`
- `REOPENED`

### 7.3 Turno de caja

```text
OPEN → COUNTING → CLOSED
```

Alternos:

- `REOPENED`
- `VOIDED`

### 7.4 Entrega

```text
UNASSIGNED
→ ASSIGNED
→ WAITING_PRODUCTION
→ READY_FOR_DISPATCH
→ IN_ROUTE
→ DELIVERED
→ SETTLED
```

Alternos:

- `FAILED`
- `RETURNED`
- `CANCELLED`

## 8. Inventario

### 8.1 Ledger

Tipos iniciales:

- `OPENING_BALANCE`
- `PURCHASE_RECEIPT`
- `PRODUCTION_INPUT`
- `PRODUCTION_OUTPUT`
- `SALE_RESERVATION`
- `SALE_CONSUMPTION`
- `RESERVATION_RELEASE`
- `WASTE`
- `TRANSFER_OUT`
- `TRANSFER_IN`
- `COUNT_ADJUSTMENT`
- `SUPPLIER_RETURN`
- `CUSTOMER_RETURN`
- `RECOVERY`

Los movimientos no se editan. Se revierten con nuevos movimientos.

### 8.2 Reserva

Al aceptar pedido:

1. Resolver receta vigente.
2. Explotar componentes.
3. Normalizar unidades.
4. Seleccionar lotes según política FEFO/FIFO configurable.
5. Crear reservas.
6. Permitir advertencia o bloqueo según política de stock.

Al confirmar preparación:

1. Consumir reservas.
2. Crear movimientos de consumo.
3. Liberar sobrantes.
4. Registrar diferencias.

## 9. Costeo

### 9.1 Costo promedio

```text
nuevo_promedio =
(valor_existencia_anterior + valor_entrada)
/
(cantidad_anterior + cantidad_entrada)
```

Debe manejar:

- cantidades cero,
- devoluciones,
- ajustes,
- transferencias,
- moneda,
- redondeo definido,
- trazabilidad por movimiento.

### 9.2 Costo estándar

- Versionado por producto o receta.
- Vigencia.
- Simulación sin afectar histórico.
- Comparación estándar vs real.

### 9.3 Recursividad

El grafo de recetas debe ser acíclico. Se validará con:

- detección de ciclo antes de guardar,
- consulta recursiva,
- límite de profundidad defensivo,
- pruebas property-based.

## 10. Sincronización offline

### 10.1 Flujo local

1. El POS envía comando al gateway.
2. El gateway valida y persiste localmente.
3. Se genera evento local.
4. Se actualizan POS/KDS por WebSocket local.
5. El comando entra a outbox.
6. Cuando hay conectividad, se envía a nube.
7. La nube valida idempotencia.
8. La nube confirma y asigna checkpoint.
9. El gateway marca comando confirmado.
10. El gateway descarga eventos remotos pendientes.

### 10.2 Conflictos

- Pedidos y pagos: append-only.
- Catálogo: nube prevalece.
- Configuración: nube prevalece.
- Turnos: autoridad por caja.
- Inventario: movimientos reconciliados.
- Clientes: merge explícito.
- Impresiones: idempotencia por `print_job_id`.
- Exportaciones: solo nube.

### 10.3 Identificadores

- UUIDv7.
- Folio humano compuesto por sucursal, caja y secuencia local.
- Clave idempotente por comando.
- Checkpoint monotónico por sucursal.

### 10.4 Contrato local de replay

El gateway valida el sobre cash completo de `command-envelope.schema.json` antes de persistirlo.
Rechaza propiedades adicionales, UUID o `date-time` inválidos, versiones no soportadas, payload vacío
y cualquier `command_type` distinto de `cash.movement.create.v1`. El contrato exacto exige actor,
`accepted_at`, grant offline y el payload PCO-003; no admite correlación, causación ni extensiones.

La intención idempotente local se deriva de organización, sucursal, dispositivo, actor, tipo y payload
canónico. Reutilizar `idempotency_key` o identidad de comando con otra intención devuelve un conflicto
estable; un reintento técnico conserva el sobre original y la inserción concurrente idéntica se
normaliza a la misma fila sin exponer la violación de unicidad de SQLite.

La reconciliación PostgreSQL central implementa únicamente `cash.movement.create.v1`: revalida
credencial técnica, grant, alcance, permiso, turno y concepto, y confirma movimiento, command log,
inbox, evento, auditoría y checkpoint de forma atómica. Todo otro tipo permanece **fail-closed**; la
persistencia local por sí sola no demuestra continuidad end-to-end ni autorización central.

## 11. Impresión

Componentes:

- `PrintJob`
- `PrinterProfile`
- `Template`
- `SpoolerAdapter`
- `EscPosAdapter`
- `PrintRetryPolicy`

Estados:

```text
PENDING → PRINTING → PRINTED
```

Alternos:

- `FAILED`
- `RETRYING`
- `CANCELLED`

Cada reimpresión debe indicar motivo y usuario.

## 12. Integraciones

Cada adaptador debe implementar:

- autenticación,
- recepción,
- normalización,
- idempotencia,
- mapeo de productos,
- confirmación,
- rechazo,
- cancelación,
- health check,
- métricas,
- rate limiting,
- reintentos,
- DLQ.

## 13. Rutas

Interfaz:

```python
class RouteOptimizationProvider:
    def optimize(request: OptimizationRequest) -> OptimizationResult: ...
    def geocode(address: Address) -> GeoPoint: ...
    def estimate_route(route: RouteRequest) -> RouteEstimate: ...
```

El resultado debe incluir:

- asignaciones,
- secuencia,
- ETAs,
- costos,
- pedidos no asignados,
- restricciones violadas,
- explicación básica.

Siempre debe existir operación manual.

## 14. Exportaciones

Modelo canónico:

- issuer,
- branch,
- customer,
- document,
- lines,
- taxes,
- payments,
- global_invoice_batch,
- control.

El adaptador define layout, columnas, catálogos y validaciones.

## 15. Seguridad

- TLS.
- Tokens de corta duración.
- Refresh tokens protegidos.
- RBAC.
- Scope por sucursal.
- Secrets en Easypanel.
- Hash seguro de contraseñas.
- Auditoría.
- Rate limiting.
- Sanitización de archivos XML.
- Validación de firmas y UUID fiscal cuando aplique.
- Políticas de retención.

## 16. Easypanel y Hostinger

Servicios mínimos:

- `api`
- `worker`
- `postgres`
- `redis`
- `object-storage` o proveedor externo
- `reverse-proxy`
- `monitoring`
- `backup-job`

Recomendaciones:

- PostgreSQL en volumen dedicado.
- Backups fuera de la VPS.
- Separar secretos por ambiente.
- Staging y producción.
- Health checks.
- Migraciones controladas.
- Rollback documentado.
- No desplegar gateway Windows en Easypanel; se instala en cada sucursal.

## 17. Observabilidad

- Logs JSON.
- Correlation IDs.
- Métricas por módulo.
- Trazas.
- Panel por sucursal.
- Estado de gateway.
- Lag de sincronización.
- Errores de impresión.
- Pedidos externos fallidos.
- Rutas sin asignar.
- Diferencias de caja.
- Exportaciones rechazadas.

## 18. Riesgos técnicos

- `RISK-001`: Pérdida total de conectividad externa.
- `RISK-002`: Impresoras incompatibles.
- `RISK-003`: APIs de marketplaces limitadas.
- `RISK-004`: Layouts variables de CONTPAQi.
- `RISK-005`: Complejidad de sincronización.
- `RISK-006`: Recetas históricas inconsistentes.
- `RISK-007`: Direcciones no geocodificables.
- `RISK-008`: Optimización costosa o lenta.
- `RISK-009`: Despliegue en una sola VPS.
- `RISK-010`: Cambios fiscales.

## 19. Repositorio

```text
apps/
  api/
  worker/
  edge-gateway/
  pos-web/
  admin-web/
  kds-web/
packages/
  contracts/
  ui/
  domain-types/
  test-fixtures/
docs/
infra/
tests/
```

La integridad documental forma parte del gate de arquitectura. Los analizadores deben distinguir
definiciones formales de menciones históricas y comprobar como mínimo:

- una sola definición de cada requisito, feature, escenario, suite y caso;
- exactamente un `BDD-SC-xxx` inmediatamente antes de cada `Scenario` o `Scenario Outline`;
- una sola fila de matriz por requisito definido en el PRD;
- ausencia de referencias TDD en la columna BDD y de referencias BDD en la columna TDD;
- existencia de cada escenario, suite o caso referenciado por la matriz;
- referencia desde la matriz para cada escenario BDD y suite TDD formalmente definidos;
- estados de matriz limitados al vocabulario documentado.

Las menciones en reportes históricos no crean definiciones. Una prueba de mera presencia global de
texto no satisface este gate porque no detecta colisiones ni referencias ubicadas en la columna
incorrecta.

## 20. Criterio de aceptación del diseño

El SDD se considera implementable cuando:

- todas las entidades críticas tienen propietario de dominio,
- las transiciones están definidas,
- existe estrategia offline,
- existe modelo de errores,
- existen contratos de integración,
- las pruebas pueden mapearse a requisitos,
- el despliegue es reproducible,
- no hay dependencia directa del dominio con proveedores externos.

## 21. Gate frontend de integración continua

El gate de frontend valida, en integración continua, cualquier cambio en Admin, POS, KDS o paquetes TypeScript compartidos. Cumple `PRD-NFR-016`.

Stack y pasos obligatorios del gate:

- Node.js 22.
- pnpm 10, con la versión determinada exclusivamente por `packageManager` en `package.json` (`pnpm@10.0.0`); el workflow no declara una versión paralela.
- instalación con `pnpm install --frozen-lockfile`.
- TypeScript sin emitir archivos mediante `pnpm typecheck` (`pnpm -r typecheck`).
- build de Admin (`@restaurantos/admin-web`).
- build de POS (`@restaurantos/pos-web`).
- build de KDS (`@restaurantos/kds-web`).
- la suite autoritativa completa se ejecuta una sola vez en `pull_request`; `main` sólo puede integrarse por PR protegido con checks requeridos.
- despliegue y verificación productiva son gates separados del gate de integración continua.
- ningún build depende de secretos.
- las aplicaciones compilan contra los paquetes compartidos del monorepo mediante el protocolo `workspace:`.

No se introduce otro gestor de paquetes.

## 22. Capacidad de identificadores de revisión Alembic

Cumple `PRD-NFR-017`. La tabla `alembic_version.version_num` limitaba la longitud del identificador de revisión, impidiendo registrar revisiones con nombres descriptivos largos.

- `alembic_version.version_num` usa `VARCHAR(128)` en PostgreSQL, ampliado por una migración puente antes de la primera revisión cuyo identificador supera 32 caracteres.
- La expansión ocurre antes de la primera revisión mayor a 32 caracteres, para que la cadena pueda avanzar desde una base productiva detenida en `0013_pos_cash_rbac_permissions`.
- PostgreSQL usa DDL transaccional, por lo que la expansión es atómica y reversible.
- SQLite no requiere alteración porque no impone el límite de longitud declarado, pero conserva la misma cadena de revisiones.
- Las futuras revisiones no pueden superar 128 caracteres.
- No se permite resolver este problema con `alembic stamp`; la cadena debe avanzar con una migración real.
- No se modifica información de negocio.

El adaptador Alembic preserva la URL SQLAlchemy recibida por el driver. Sólo al escribirla en
`Config.set_main_option("sqlalchemy.url", ...)` duplica `%` a `%%`, porque ConfigParser interpreta
el porcentaje como interpolación. Al recuperar el valor desde `Config`, éste vuelve a ser idéntico
al URL lógico original, incluidos sockets codificados (`%2F`) y credenciales URL-encoded. El URL no
se registra ni se imprime.

## 23. Backend de administración operativa por sucursal

El backend distingue autoridad corporativa de operación administrativa local. Los permisos
`branch.admin.access`, `branch.staff.read` y `catalog.branch.manage` se asignan al rol canónico
`Supervisor de sucursal` con alcance `branch`, sin concederle `admin.manage` ni `catalog.manage`.
`Cajero` y el rol legacy `Caja` no reciben esos permisos.

Contratos:

- `GET /api/v1/auth/session` reconstruye usuario, roles, permisos efectivos, sucursales permitidas
  y sucursal activa desde PostgreSQL. Sólo admite token Bearer; no confía en roles o permisos del
  cliente.
- `GET /api/v1/branch-administration/context` devuelve sucursal, unidad de negocio, razón social y
  almacén autorizados.
- `GET /api/v1/branch-administration/staff` devuelve únicamente usuarios con asignación a la
  sucursal autorizada y nunca credenciales.
- `GET /api/v1/branch-administration/catalog/products` conserva el catálogo central y calcula
  precio vigente, disponibilidad efectiva, fuente de disponibilidad y condición vendible.
- `PUT /api/v1/branch-administration/catalog/products/{product_id}/availability` sólo crea,
  actualiza o elimina la excepción en `branch_product_availability`; `inherit` elimina la excepción
  local y registra auditoría.

Las lecturas de productos POS, inventario, kardex, recetas, sucursales, unidades de negocio,
usuarios, roles, permisos y almacenes requieren actor. Una petición sin autenticación recibe 401;
un actor autenticado sin permiso o fuera de alcance recibe 403. Para cuentas de sucursal, omitir
`branch_id` resuelve la sucursal activa asignada y enviarlo explícitamente no permite sustituirla.
Las consultas de inventario incluyen todos los insumos centrales con existencia cero cuando no hay
movimientos, pero fijan almacén, movimientos y costo a la sucursal autorizada.

Las mutaciones de disponibilidad producen `branch_product_availability.updated` y los rechazos
sensibles producen `authorization.denied` en la auditoría. Estos eventos son la señal operacional
estructurada de BA-001 para logs y métricas por acción y sucursal; la plataforma de observabilidad
general continúa definida en la sección 17.

## 24. Frontend de administración operativa por sucursal

El frontend de administración operativa por sucursal vive dentro de la aplicación POS (no en
`admin-web`) y permite al Supervisor de sucursal administrar su sucursal sin abandonar el layout
del POS ni entrar al administrador corporativo. Cumple los contratos backend definidos en la
sección 23.

Fuente canónica de sesión:

- Al iniciar el POS, el cliente conserva únicamente el token como credencial y llama a
  `GET /api/v1/auth/session` para obtener usuario, roles, permisos, alcance y `active_branch`
  desde PostgreSQL.
- El frontend no confía en el objeto `user` recibido por query string, ni en `is_superadmin`,
  ni en roles o permisos guardados en `localStorage`. Las decisiones de autorización se toman
  exclusivamente a partir de la sesión canónica.
- Para `scope.level == "branch"`, el `active_branch.id` reemplaza cualquier `branch_id` local;
  el Supervisor no tiene un selector habilitado para cambiar de sucursal.
- Para `scope.level == "organization"`, el selector se limita a `allowed_branch_ids`. El cambio
  solicita otra sesión a `GET /api/v1/auth/session?branch_id=...` y sólo actualiza contexto y
  almacenamiento local cuando la respuesta confirma el mismo `active_branch.id`. Si falla, se
  conserva la sesión canónica anterior y ninguna operación usa la selección pendiente.
- El parámetro legacy `user` de la URL se elimina y no se usa como autoridad.
- Admin nunca construye una URL con token de sesión o perfil. Antes de abrir POS solicita mediante
  Bearer un `pos_handoff_code` aleatorio; PostgreSQL conserva únicamente su SHA-256, usuario, destino,
  expiración máxima de 60 segundos y consumo. El navegador transporta el código de un solo uso en el
  fragmento `#handoff=...`, lo elimina con `history.replaceState` antes de cualquier petición y lo
  canjea por `POST /api/v1/auth/pos-handoffs/exchange`. El canje es atómico, auditable y falla ante
  ausencia, expiración, consumo previo o usuario inactivo. Ningún log o auditoría conserva código o
  token completo.

Guardas por permiso:

- Entrada al POS: permiso efectivo `pos.operate`.
- Menú y centro de Administración: `branch.admin.access`.
- Consulta de personal: `branch.staff.read`.
- Cambio de disponibilidad: `catalog.branch.manage`.
- Un usuario sin `branch.admin.access` no ve el menú Administración; si escribe la ruta
  directamente, recibe una vista de acceso denegado o es redirigido a `/pos/pos`.

Rutas internas (dentro de `PosLayout`, bajo `basename="/pos"`):

- `/pos/administration` — centro de tarjetas.
- `/pos/administration/products` — productos y disponibilidad.
- `/pos/administration/staff` — personal de sucursal.
- `/pos/administration/branch` — sucursal activa.

BA-002 habilitó inicialmente productos, insumos, contexto de sucursal y personal. Ese estado queda
registrado como antecedente histórico: BA-003, definido en la sección 25, reemplaza las tarjetas
diferidas por ocho accesos operativos y retira del POS los accesos de identidad corporativa
(sucursales, usuarios y roles).

Manejo de errores:

- 401: limpiar tokens y redirigir una sola vez a `/admin/login`.
- 403: pantalla "Tu cuenta no tiene acceso a esta operación", sin bucle.
- Error de red/503: error recuperable con botón Reintentar.
- No se usa `alert()` para errores normales.

Prohibiciones:

- Ninguna tarjeta o enlace del centro de administración puede redirigir a `/admin` ni usar
  `window.location` hacia módulos administrativos corporativos.
- No se duplican componentes completos de `admin-web`.
- No se determina autoridad comparando nombres de rol ni leyendo permisos del navegador.

## 25. BA-003 — módulos operativos dentro de la administración POS

BA-003 amplía el centro administrativo de sucursal sin convertir al Supervisor en administrador
corporativo. El elemento **Administración** permanece en `PosLayout` y depende exclusivamente de
`branch.admin.access` obtenido de la sesión canónica. No se habilita por nombre de rol, correo ni
datos de `localStorage`.

El centro muestra ocho tarjetas operativas con el mismo sistema visual del POS:

- Productos y recetas — `/pos/administration/products`;
- Insumos — `/pos/inventory`;
- Proveedores — `/pos/administration/suppliers`;
- Compras — `/pos/administration/purchases`;
- Producción — `/pos/administration/production`;
- Mermas — `/pos/administration/waste`;
- Traspasos — `/pos/administration/transfers`;
- Conteos físicos — `/pos/administration/counts`.

No existen tarjetas ni rutas locales para Sucursales, Usuarios o Roles. El contexto de sucursal ya
visible en el encabezado sustituye una pantalla separada de administración de sucursal. Las nuevas
rutas se renderizan dentro de `PosLayout`, conservan el regreso al centro y no redirigen a
`admin-web`.

Guardas por ruta:

- Proveedores y Compras: `purchases.read`;
- Producción: `production.manage`;
- Mermas: `inventory.waste`;
- Traspasos: `inventory.transfer.send`;
- Conteos físicos: `inventory.count`.

Las vistas consultan los contratos operativos existentes con el `active_branch.id` canónico. En
este incremento, Proveedores es consulta del catálogo central autorizado y las demás vistas ofrecen
un resumen operativo de la sucursal; no duplican formularios corporativos ni conceden mutaciones de
catálogo central. Las operaciones sensibles continúan en incrementos específicos y en todos los
casos el backend vuelve a aplicar permiso, alcance, idempotencia y auditoría.

La migración `0024_branch_admin_scope` es requisito operacional: después de desplegarla, el
Supervisor debe iniciar una sesión nueva para que `GET /api/v1/auth/session` incluya
`branch.admin.access`. Si producción permanece en `0023_physical_counts`, ocultar Administración es
el comportamiento seguro esperado; nunca se corrige omitiendo la guarda frontend.

## 26. DATA-001 — importación trazable de catálogos heredados por sucursal

La importación de archivos heredados no escribe directamente en tablas operativas desde Excel.
Un adaptador local convierte cada fila a un contrato JSON normalizado y la API registra primero un
`legacy_import_batch` y sus `legacy_import_records`. El par sucursal, sistema origen y checksum de
manifiesto identifica el lote; el par lote, tipo y clave origen identifica cada fila. Ambos son
idempotentes.

Alcance canónico:

- Productos, categorías e insumos importados pertenecen a la organización. `catalog_scope` queda
  en `organization` y `source_branch_id` queda nulo; seleccionar una sucursal no cambia el conjunto
  del catálogo, sólo disponibilidad, existencias y operación local.
- El administrador corporativo edita el catálogo compartido. Un Supervisor sólo puede administrar
  la excepción de disponibilidad de su sucursal y no puede alterar identidad, categoría, precio o
  estación del catálogo central.
- `customers.origin_branch_id` gobierna el directorio local; los clientes centrales con origen nulo
  siguen siendo compartidos.

Política de materialización:

- Clientes: nombre y clave origen se materializan; la dirección libre se conserva en el registro de
  importación hasta que un administrador la estructure. No se inventan calle, colonia o número.
- Insumos: se materializan con unidad normalizada y categoría heredada. Último costo y costo promedio
  permanecen como referencia del registro importado; no crean movimientos ni alteran costos.
- Productos: categoría, SKU, nombre y precio se conservan. Un adaptador aprobado puede normalizar
  la comilla inicial del SKU y asignar estación mediante la política determinista de DATA-003; si
  no satisface esa política, queda rechazado o `needs_review`. Sólo `active`, con precio vigente
  positivo y disponible, puede aparecer en POS.
- Presentaciones: sin proveedor quedan `needs_review` y no crean `purchase_presentations`.
- Recetas: sin componentes, cantidades, unidad y rendimiento quedan `needs_review`; no crean recetas.

El directorio de clientes expone búsqueda paginada (`q`, `limit`, `offset`) y devuelve
`items`, `total`, `limit` y `offset`. Teléfonos, direcciones, perfil fiscal y resumen de pedidos se
obtienen mediante consultas agrupadas para la página, nunca mediante una consulta por cliente.

La UI administrativa muestra lote, fuente, conteos y razones de revisión. Los ajustes canónicos
continúan usando los contratos de productos e insumos y producen auditoría. El Supervisor puede
modificar únicamente disponibilidad de su sucursal mediante `catalog.branch.manage`; no puede editar
identidad, categoría, precio, estación ni alcance del catálogo compartido.
El centro POS muestra al Supervisor un resumen sin datos personales de las entidades importadas y
sus conteos; el detalle crudo y la conciliación permanecen reservados al administrador corporativo.

Los Excel y cualquier exportación con datos personales son insumos operativos privados: no se
commitean, no se incluyen en imágenes y no se imprimen en logs. El cargador transmite chunks
normalizados por TLS usando una cuenta corporativa autorizada.

## 27. DATA-002 — bandeja accionable de revisión de importaciones

La revisión corporativa no debe presentar una lista técnica homogénea sin contexto. Cada lote
expone un `entity_summary` por tipo y estado; el endpoint de registros acepta `entity_type`, además
de estado, límite y desplazamiento. Esto permite que el cliente consulte una cola acotada sin
cargar las 793 filas ni confundir presentaciones, productos y recetas.

La UI separa los pendientes en tres flujos:

- Producto: muestra nombre y SKU, explica que debe asignarse estación, validarse categoría y precio,
  y activarse mediante el editor canónico de Productos. Nunca activa en lote sin una decisión de
  estación.
- Presentación: muestra nombre, SKU, unidad y rendimiento heredados; dirige a Proveedores para crear
  o vincular una presentación real. No inventa proveedor ni convierte el costo heredado en costo
  operativo.
- Receta: muestra nombre y SKU y dirige al editor de receta del producto. Componentes, cantidades,
  unidades y rendimiento deben ser capturados antes de considerar resuelto el pendiente.

Cada flujo ofrece instrucciones visibles, búsqueda local sobre la página, paginación del servidor
y un enlace de trabajo. El catálogo de Productos acepta `?search=<sku>` para abrir la lista ya
filtrada. La bandeja sigue siendo una vista de conciliación: las mutaciones se realizan mediante los
contratos canónicos existentes, que conservan permisos, alcance y auditoría.

## 28. POS-UX-001 — experiencia operativa en español

El POS debe ser operativa y visualmente íntegro en español de México para cajeros y supervisores.
Los códigos internos (`dine-in`, `takeout`, `delivery`, `ingredient`, `active`) permanecen estables
en el dominio, pero sus etiquetas visibles se traducen (`En sucursal`, `Para llevar`, `A domicilio`,
`Insumo`, `Activo`).

Búsqueda remota y paginada de clientes:

- El checkout no precarga clientes al iniciar; consulta al completar un teléfono mexicano válido,
  con debounce aproximado de 300 ms y cancelación de solicitudes anteriores (`AbortController`).
- La búsqueda del checkout es exacta por teléfono capturado o normalizado y no fusiona clientes
  por coincidencia telefónica. El directorio administrativo conserva su búsqueda paginada `q` por
  nombre, correo o teléfono.

Conservación independiente del cliente seleccionado:

- El cliente seleccionado se guarda en estado independiente de los resultados de búsqueda.
- Al cambiar la búsqueda o limpiar resultados, el cliente seleccionado se conserva.
- Al cambiar de cliente, el domicilio anterior se limpia.

Domicilios estructurados y referencia heredada:

- Para clientes importados, `legacy_import_records.normalized_payload["legacy_address"]` se expone
  como `legacy_address_reference` en el read model paginado de clientes.
- El texto heredado se muestra como "Domicilio heredado por confirmar"; puede copiarse al campo
  Referencias, pero no se convierte en domicilio operativo ni se divide automáticamente.
- Sólo se devuelven `customer_addresses` con `status == "active"`.

Creación de domicilio dentro del checkout:

- El formulario usa `POST /customers/{customer_id}/addresses` con los campos estructurados de México.
- Después de guardar, el domicilio se selecciona automáticamente y el checkout permanece abierto.
- Un pedido a domicilio exige cliente y domicilio activo perteneciente a ese cliente.

Sucursal obtenida de `session.active_branch`:

- Catálogo, búsqueda de clientes, inventario, creación de pedidos y domicilios usan
  `session.active_branch.id` de la sesión canónica.
- `pos_register_id` puede seguir siendo configuración local de la caja.

Inventario teórico derivado del ledger:

- La pantalla de Inventario consulta únicamente `GET /inventory/stock?branch_id={active_branch.id}`.
- La existencia teórica distingue positivo (verde), cero (neutro) y negativo (rojo con advertencia).

Ausencia de controles ficticios:

- No se muestran botones sin implementación (`Tables`, `Discount`, `Save Bill`, `Voucher`).
- No se agregan reglas, descuentos, mesas ni funciones que no existan en el dominio.

Privacidad del domicilio heredado:

- No se devuelve `raw_payload` de `legacy_import_records`; sólo `legacy_address_reference`.
- No se imprimen domicilios en logs ni se exponen referencias de otra sucursal.

## 29. POS-CUST-001 — identificación telefónica y alta durante el checkout

El checkout identifica clientes mediante un teléfono mexicano válido. La interfaz conserva el
valor capturado, elimina caracteres de presentación para validar 10 dígitos nacionales o 12 con
prefijo `52`, y sólo entonces consulta `GET /customers` con `phone`, `branch_id` y `limit`. No usa
`q` para buscar por nombre o correo durante el cobro.

El backend normaliza el teléfono con la regla existente y devuelve una página. El teléfono no es
una llave única: si existen coincidencias múltiples, cada cliente conserva su identidad y se
presenta como una opción separada con nombre, teléfono capturado y cantidad de domicilios activos.

Si la respuesta exacta queda vacía, el POS ofrece un formulario corto para nombre y correo
opcional. `POST /customers` recibe la sucursal canónica y el teléfono ya capturado como teléfono
primario. La operación usa `orders.create`, produce `customer.created`, mantiene el carrito y
selecciona el nuevo cliente. No se permite el alta mientras el teléfono sea incompleto o inválido.

El modal permite confirmar el tipo de pedido sin depender de controles ocultos detrás de él. Al
elegir `delivery`, muestra todos los domicilios activos del cliente mediante opciones legibles. Si
no hay domicilios, o se necesita otro, el formulario estructurado permanece dentro del checkout y
selecciona el registro creado.

La fuente heredada de Constitución sólo declara `CLAVE`, `NOMBRE` y `DIRECCION`. Por tanto:

- `CLAVE` se conserva como evidencia de origen y no se materializa como teléfono;
- no se inventan teléfonos para los clientes importados;
- un cliente heredado sin teléfono requiere captura humana posterior antes de poder localizarse
por teléfono en el checkout.

## 30. POS-VAR-001 — variaciones preestablecidas

> Para escrituras nuevas, el catálogo corporativo y sus relaciones se rigen por la sección 34.1.
> Este diseño por grupo de producto permanece sólo como compatibilidad e historial.

**Norma vigente POS-VAR-003.** La presentación anterior de esta sección queda sustituida por
**Comentarios del pedido** en administración y por el modal `Personaliza {producto}`. Las notas
son `preset_instruction`: no cambian precio, receta, inventario ni costo. Los términos visuales
"Variaciones y cambios" de este texto son únicamente contexto histórico de POS-VAR-001.

Las variaciones preestablecidas reutilizan `modifier_groups`, `modifier_options` y
`branch_modifier_options`; no introducen tablas ni un motor paralelo. Cada producto que tenga al
menos una nota posee un grupo estable, visible y activo llamado **Variaciones y cambios**, opcional
(`minimum_selections=0`) y con máximo igual al número de notas activas del grupo. Las notas usan
`effect_type=preset_instruction` dentro de la columna VARCHAR existente.

El nombre visible del grupo no identifica por sí solo un grupo de presets. Antes de reutilizarlo,
el backend exige que sea opcional, tenga mínimo cero y que todas sus opciones sean
`preset_instruction`. Si un grupo homónimo contiene una opción avanzada o cardinalidad incompatible,
el alta rechaza `variation_group_conflict` sin mutar grupo, cardinalidad ni opciones existentes.
Sólo un grupo previamente verificado puede sincronizar su máximo con las notas preset activas.

El alta fuerza en servidor `price_delta_cents=0`, `inventory_effect=false`,
`affected_item_id=null`, `replacement_item_id=null`, `remove_quantity=0`, `add_quantity=0` y
`kitchen_text` igual a la etiqueta normalizada. La etiqueta es requerida, se recorta al límite ya
existente y se rechaza duplicada por producto ignorando mayúsculas, minúsculas y espacios
periféricos. La actualización corporativa sólo acepta nombre, orden y estado `active|archived`;
archivar y reactivar conservan el registro. `instruction` sigue permitiendo texto libre y no se
altera. `display_order` es un entero no booleano dentro del rango operativo existente; entradas
malformadas generan un error de negocio explícito y no modifican registros.

Contratos:

- `GET /api/v1/catalog/variation-notes?product_id=...` lista el catálogo corporativo de notas,
  incluyendo archivadas para administración;
- `POST /api/v1/products/{product_id}/variation-notes` recibe `{name, display_order?}` y fuerza
  las invariantes anteriores;
- `PUT /api/v1/variation-notes/{option_id}` recibe únicamente `name`, `display_order` y/o
  `status: active|archived`;
- `GET /api/v1/branch-administration/catalog/variation-notes` entrega producto, nota, estado
  central, `effective_enabled` y `override` de la sucursal canónica;
- `PUT /api/v1/branch-administration/catalog/variation-notes/{option_id}` recibe
  `action: available|unavailable|inherit`; `inherit` elimina el override;
- `GET /api/v1/products/{product_id}/modifiers` continúa siendo la única fuente efectiva del POS.

El administrador corporativo requiere `catalog.manage` para crear, renombrar, ordenar, archivar y
reactivar. La administración de sucursal requiere `branch.admin.access` para consultar y
`catalog.branch.manage` para cambiar únicamente la excepción del `active_branch` autorizado. La
lectura efectiva del POS requiere `pos.operate`. No se acepta una sucursal arbitraria del navegador
ni se usa `localStorage` como autoridad.

Al crear un pedido, una selección `preset_instruction` toma exclusivamente el `kitchen_text`
congelado de la opción; un `text` enviado por cliente se ignora. Por ello no altera componentes,
reservas, consumo ni `modifier_total_cents`, pero queda en `selected_modifiers` y en el snapshot.
El read model/API de KDS expone ese snapshot y cada print job de cocina/comanda incluye
`selected_modifiers` por línea, sin datos personales ni modificación de importes. Este incremento
no conecta la pantalla `kds-web` estática con datos reales. Se auditan alta, edición,
archivado/reactivación y disponibilidad por sucursal; los rechazos de autorización usan la
auditoría existente.

En administración corporativa, `/admin/variations` vive en `AdminLayout` y permite seleccionar o
buscar producto, crear, editar, ordenar, archivar/reactivar y ver estados de carga, vacío y error,
sin exponer precio, receta, ingredientes, cantidades ni inventario. La sesión y autorización de
backend siguen siendo la autoridad; la visibilidad del shell administrativo existente no la
sustituye. En POS, el hub de sucursal ofrece `/pos/administration/variations` sólo con
`branch.admin.access` y `catalog.branch.manage`. Muestra la sucursal canónica y permite buscar
producto o nota y marcar Disponible, No disponible o Heredar.

Al seleccionar un producto en POS, si no tiene grupos se agrega directamente. Si tiene grupos, el
modal conserva los modificadores avanzados. `preset_instruction` se muestra con botones táctiles
multiselección, no con input ni checkbox: dos columnas (una en estrecho), `aria-pressed`, foco
visible, altura mínima de 48 px y los colores operativos verde/blanco. El encabezado es
`Variaciones y cambios · {producto}`, contiene la ayuda `Puedes elegir varias` y el botón
`Agregar al pedido`. Cerrar cancela sin afectar el carrito. Si falla la carga de modificadores, el
POS muestra un error recuperable y no agrega el producto silenciosamente.

## 31. POS-VAR-002 — catálogo y relaciones de variaciones de insumos

> Para ventas y configuración nuevas, los adicionales universales se rigen por la sección 34.2.
> `ingredient_variation_products` permanece como evidencia histórica y deja de limitar en qué
> producto puede utilizarse un adicional.

**Norma vigente POS-VAR-003.** Esta sección describe la migración y los datos legados de 0026.
Sus campos y opciones `remove` se preservan para compatibilidad e historial, pero no gobiernan
ventas ni configuración nuevas: la sección 32 prevalece. El catálogo operativo se llama
**Ingredientes adicionales**, materializa sólo `add`; cualquier `allow_remove=true` falla con
`ingredient_extra_add_only`. Las referencias posteriores a Con/Sin, retiro de receta o exclusión
mutua son comportamiento histórico sustituido, no reglas activas.

POS-VAR-002 conserva el antecedente técnico de POS-VAR-001 y de las asignaciones de insumo. Para
la operación vigente, POS-VAR-003 presenta **Comentarios del pedido** y **Ingredientes
adicionales** como catálogos separados y reutiliza el motor existente, sin crear un segundo
ejecutor de modificadores.

La migración lineal `0026_ingredient_variations`, descendiente de
`0025_legacy_branch_catalog_import`, crea `ingredient_variations` (organización, insumo, etiquetas
normalizadas, estado y timestamps) con unicidad por organización e insumo. La asignación por
producto se guarda en `ingredient_variation_products` con acciones, cantidades `NUMERIC(18,6)`,
cargo explícito, estado y referencias a opciones runtime. Sus checks impiden acciones vacías,
cantidades inválidas y precios sin un Con cobrable. No hay borrado físico. El downgrade quita sólo
estos metadatos después de desvincular/archivar y no borra opciones ni snapshots históricos.

La misma migración crea `ingredient_variation_commands`: registra `organization_id`, `variation_id`,
actor, `idempotency_key` único, hash canónico de la solicitud, resultado JSON sin datos personales,
estado y timestamps. La reserva de la llave y la aplicación viven en una transacción. Un reintento
con hash igual devuelve el resultado persistido sin materializar ni auditar de nuevo; con hash
distinto responde `idempotency_conflict`.

En la frontera del catálogo, las cantidades sólo aceptan `Decimal` interno o una cadena decimal
finita y exacta; `float`, booleanos, `NaN` e infinito responden
`invalid_variation_quantity`. Las etiquetas explícitamente nulas responden
`invalid_ingredient_variation_label`; omitirlas conserva los defaults normalizados.

Cada asignación operativa materializa idempotentemente una opción `add` en el grupo opcional
**Cambios de ingredientes**. Usa insumo afectado, inventario, cantidad configurada y precio
explícito o cero. Las opciones `remove` de 0026 son sólo datos históricos. El pedido reutiliza
`_apply_order_modifiers` y `_add_modifier_component`: el costo promedio vigente por
sucursal/almacén se congela en el snapshot, pero el precio al cliente proviene exclusivamente de
`price_delta_cents`; un retiro heredado enviado manualmente falla con
`ingredient_extra_add_only`.
Un grupo existente con el mismo nombre sólo se reutiliza si pertenece a la organización y producto
autorizados, es opcional y todas sus opciones históricas están referenciadas por asignaciones de
insumos; cualquier opción ajena o capacidad/estado incompatible responde `variation_group_conflict`
sin mutación. Si no quedan opciones activas, el grupo se archiva con máximo cero para no exponer un
grupo vacío; al reactivar una relación se reutilizan sus IDs y se recalcula la capacidad.

El catálogo exige `catalog.manage`; sus endpoints versionados listan, crean, editan y archivan
definiciones, hacen preview y aplican asignaciones ADD. Preview expande categorías a productos
activos actuales, deduplica e informa compatibilidad; el producto requiere receta de venta activa.
Aplicar revalida, es all-or-nothing e idempotente mediante `Idempotency-Key`, y audita definición
y asignaciones. `GET /products/{product_id}/modifiers` sigue como fuente POS y sólo enriquece los
adicionales ADD efectivos.
El Supervisor, con sucursal canónica, sólo administra Disponible/No disponible/Heredar por acción;
el Cajero sólo selecciona las opciones efectivas. Preview, aplicación, replay, conflicto y error
emiten logs estructurados con IDs de variación, actor y sucursal canónica, conteo de destinos y
correlation/idempotency key; nunca contienen nombres ni otros datos personales.

El read model corporativo reporta asignaciones ADD activas y puede advertir el conteo histórico de
retiros sin ofrecerlos. El read model de sucursal incluye nombre, SKU y unidad base del insumo; el
supervisor sólo administra disponibilidad ADD y nunca la configuración corporativa.

La UI corporativa captura el cargo adicional como texto MXN (pesos enteros o con uno o dos
decimales) y lo convierte exactamente a `price_delta_cents` entero seguro para la API. No usa
`float`, no redondea ni acepta valores negativos, no finitos o con más de dos decimales; al editar,
el valor almacenado en centavos vuelve a mostrarse con dos decimales MXN. Si no hay cargo, la UI
envía cero. La configuración ADD ocurre exclusivamente por asignación de producto, no al crear la
definición reutilizable.

## 32. POS-VAR-003 — separación de comentarios e ingredientes adicionales

> La separación conceptual continúa vigente; la sección 34 sustituye únicamente el alcance por
> sucursal y las relaciones obligatorias producto-adicional para escrituras nuevas.

POS-VAR-003 conserva íntegramente el esquema y la única head
`0026_ingredient_variations`: no crea migración, no reescribe tablas, IDs, endpoints, snapshots ni
opciones históricas. Los comentarios del pedido reutilizan POS-VAR-001: son
`preset_instruction`, con `price_delta_cents=0`, `inventory_effect=false`, cantidades cero y sólo
`kitchen_text` congelado en `selected_modifiers`, KDS e impresión. El texto de una etiqueta no
determina su efecto: “Sin …” es comentario si fue creado por el catálogo de comentarios.

Las `ingredient_variations` existentes se presentan como **Ingredientes adicionales** para ventas
nuevas. Preview, bulk apply y actualización individual sólo aceptan `allow_add=true`,
`allow_remove=false`, `add_quantity` Decimal exacto mayor que cero, `remove_quantity=0` y el cargo
explícito existente (`add_price_delta_cents` positivo sólo si se cobra). `allow_remove=true` falla
con `ingredient_extra_add_only`; no se usan float, booleanos ni valores no finitos. Materializan
únicamente opciones `add` con inventario, costo promedio del snapshot, reserva y consumo del motor
actual. La reactivación sólo revive `add_option_id` de asignaciones activas permitidas.

Las opciones `remove` materializadas por POS-VAR-002 se preservan archivadas o activas como datos
heredados, pero se excluyen del read model efectivo del POS y de la administración normal de
ingredientes adicionales; un `option_id` enviado manualmente en una venta nueva falla con
`ingredient_extra_add_only`. Esta defensa sólo identifica opciones vinculadas a
`ingredient_variation_products`, por lo que `remove` o `substitute` legítimos de otros módulos no
se alteran. Pedidos, snapshots, KDS e impresión históricos continúan leyéndose sin mutación.

`/admin/variations` y `/pos/administration/variations` se llaman **Comentarios del pedido** y sólo
administran preset instructions. `/admin/ingredient-extras` y
`/pos/administration/ingredient-extras` son **Ingredientes adicionales**; conservan
`catalog.manage` o `branch.admin.access` + `catalog.branch.manage`, respectivamente, y derivan la
sucursal canónica de sesión. El POS clasifica `preset_instruction` y extras `add` en bloques
visuales separados, sin exponer costo interno ni bloques vacíos. Los comandos y disponibilidad
conservan auditoría, idempotencia, permisos y alcance organizacional existentes.

## 33. DATA-003 — depuración y unificación del catálogo operativo

La revisión de las fuentes privadas de Constitución confirma 156 insumos con SKU numérico y 317
productos cuyo SKU queda numérico al retirar una comilla inicial de importación. Sus 23 categorías
de producto y nombres válidos están en mayúsculas. Los archivos privados no se incorporan al
repositorio ni se imprimen en logs.

La migración `0027_catalog_cleanup` aplica una política cerrada:

- SKU numérico significa exclusivamente `[0-9]+`; los ceros iniciales se conservan como texto.
- En productos se recortan espacios y todas las comillas iniciales `'`, `´`, `‘` o `’` antes de
  validar. En insumos no se corrige un SKU no numérico: se retira.
- Un nombre está en mayúsculas cuando coincide con su transformación Unicode a mayúsculas.
- Un producto se conserva sólo cuando su SKU normalizado es numérico y su nombre está en
  mayúsculas. Colisiones después de normalizar conservan primero el SKU ya canónico y retiran los
  duplicados.
- Categorías no mayúsculas se archivan. Si un producto conservado todavía las referencia, se
  reasigna a la categoría mayúscula equivalente; si no existe, la migración crea esa categoría
  canónica antes de archivar la anterior.
- `drinks` corresponde a las categorías `AGUAS`, `BEBIDAS`, `EXTRA JUGOS`, `EXTRA LICUADOS`,
  `JUGOS`, `LICUADOS`, `SMOOTHIES Y EXTRACTOS` o a nombres inequívocos de bebida.
- `packing` corresponde a `SERVICIOS A DOMICILIO` o a nombres inequívocos de empaque como bolsa,
  empaque, contenedor, cubierto o servilleta. Lo demás usa `kitchen`.
- Insumos conservados quedan activos y corporativos. Los de `PLASTICOS Y DESECHABLES` usan
  `item_type=packaging`; los demás conservan su tipo operativo.

Productos e insumos conservados quedan `catalog_scope=organization` y `source_branch_id=NULL`.
La migración elimina excepciones de `branch_product_availability` de productos conservados para que
todas las sucursales hereden disponibilidad central. El selector de sucursal permanece porque
existencias, almacén y disponibilidad futura siguen siendo locales; no filtra la identidad del
catálogo compartido. Productos sin precio vigente positivo permanecen visibles en administración,
pero POS no los ofrece para cobrar ni inventa un precio.

La eliminación solicitada es un retiro lógico reversible: `status=archived` y exclusión de los read
models normales. No se hace `DELETE` físico de productos, categorías o insumos porque pueden estar
referenciados por pedidos, recetas, movimientos, costos o snapshots históricos. Las tablas
`catalog_cleanup_runs` y `catalog_cleanup_records` conservan resumen y valores previos; el downgrade
restaura campos, categorías creadas y excepciones locales. La migración no modifica ni elimina
movimientos, existencias, costos, pedidos, pagos o snapshots.

Los registros de importación de productos que quedan normalizados pasan a `imported`, se limpian sus
motivos de estación pendiente y se recalcula el resumen del lote. Presentaciones y recetas
incompletas continúan en revisión. Un evento `catalog.cleanup.applied` registra sólo conteos e ID de
ejecución, sin datos privados. `GET /api/v1/catalog/cleanup-status` requiere `catalog.manage` y
expone el último resumen para verificación operativa.

Las importaciones y altas posteriores aplican la misma frontera: categorías y nombres de producto
en mayúsculas, SKU numérico normalizado, alcance corporativo y estación determinista. Los clientes
continúan aislados por sucursal.

## 34. OPS-WAVE-001 — comentarios, adicionales, pedidos y compras de sucursal

Esta ola se divide en cuatro incrementos lineales. Ningún incremento puede abrir una migración
paralela desde `0027_catalog_cleanup`; cada uno comienza sobre el `main` integrado del anterior.
Las pantallas conservan `PosLayout`, tipografía, verde operativo, tarjetas, tamaños táctiles e
iconografía existentes. Los códigos internos permanecen en inglés y las etiquetas visibles usan
español de México.

### 34.1 POS-CAT-002 — comentarios corporativos relacionados con productos

Los comentarios dejan de depender de sucursal y dejan de duplicarse como definición independiente
por producto. Para escrituras nuevas se crean:

- `order_comment_presets`: organización, texto, texto normalizado, orden, estado, creador,
  actualizador y timestamps;
- `order_comment_products`: comentario, producto, estado, actor y timestamps, con unicidad por
  pareja.

La normalización recorta espacios, colapsa espacios internos y compara sin distinguir mayúsculas ni
acentos sólo para detectar duplicados; el texto visible conserva la forma confirmada por el usuario.
Cada comentario admite hasta 120 caracteres. El alta masiva acepta como separadores coma o salto de
línea, descarta entradas vacías, limita cada comando a 100 valores y muestra un preview con creados,
existentes y duplicados antes de confirmar. Una coma literal dentro de un comentario no se admite en
esta versión.

La pantalla corporativa se divide en dos columnas. La izquierda agrupa las subcategorías reales de
`product_categories` bajo categorías operativas desplegables derivadas de la estación de sus
productos activos: `kitchen` se presenta como **Alimentos**, `drinks` como **Bebidas** y `packing`
o cualquier estación no reconocida como **Otros**. Cada subcategoría tiene una casilla y muestra
cuántos productos activos alcanzará; no se persiste una jerarquía paralela ni se modifica el
catálogo. La derecha contiene el textarea y la vista previa de comentarios y destinos. El lote
acepta coma, salto de línea o dos o más espacios como separadores, de modo que un solo espacio puede
seguir formando parte de comentarios como “Sin cebolla”.

La UI convierte las subcategorías seleccionadas en el conjunto deduplicado de productos activos y
muestra los conteos de subcategorías, productos y comentarios antes de confirmar. Cambiar texto o
selección invalida el preview. El contrato `GET /api/v1/catalog/products` incluye `category_id`
además de `category_name`; la UI relaciona productos y subcategorías por ese identificador estable
y considera únicamente productos con `status=active`. La carga del árbol es independiente de la
lectura de comentarios, de modo que un error en comentarios no se representa como catálogo vacío.
`POST /api/v1/catalog/order-comments/bulk/preview` sólo calcula el preview y
`POST /api/v1/catalog/order-comments/bulk` crea o reactiva comentarios y agrega relaciones sin
retirar relaciones no incluidas. `GET /api/v1/catalog/order-comments` lista el catálogo global y
`PUT /api/v1/catalog/order-comments/{id}/products` reemplaza el conjunto de productos sólo después
de mostrar el impacto. Crear, editar, archivar o relacionar exige `catalog.manage`; no existe
`branch_id` ni override local en ninguno de estos contratos. Supervisor y Cajero sólo leen y usan.
El cliente liga el preview al texto exacto y al conjunto ordenado de destinos; cambiar cualquiera de
ellos invalida la confirmación hasta pedir un preview nuevo. Al seleccionar comentarios en POS, el
carrito conserva y muestra sus textos elegidos, mientras que el backend conserva el snapshot final.

Cada línea de creación o enmienda de pedido envía `comment_preset_ids`. El backend verifica que el
comentario y su relación con el producto estén activos y congela en `selected_modifiers` un snapshot
con `kind=order_comment`, ID, texto y `effect_type=preset_instruction`. Precio, cantidades, artículos
y efecto de inventario son siempre cero o nulos. KDS, impresión e historial leen el snapshot.

La migración `0028_global_order_comments_extras` deduplica los presets existentes y crea relaciones
desde las opciones históricas `preset_instruction`. No elimina `modifier_groups`,
`modifier_options`, `branch_modifier_options`, pedidos ni snapshots previos. El downgrade elimina
únicamente los datos nuevos y restaura los campos ampliados de adicionales.

### 34.2 POS-CAT-003 — ingredientes adicionales universales

`ingredient_variations` continúa como identidad corporativa del adicional, pero recibe configuración
canónica: `portion_quantity` `NUMERIC(18,6)`, `sale_price_cents`, estación, orden y estado. El precio
puede ser cero, pero siempre es explícito; nunca se deriva del costo promedio. El insumo, unidad y
cantidad gobiernan reserva, consumo y costo teórico de la sucursal. `status=needs_review` es un
estado no publicable para conflictos o configuraciones incompletas heredadas.

Toda alta corporativa nueva exige los tres valores canónicos completos: porción Decimal positiva,
precio entero no negativo en centavos y estación `kitchen`, `drinks` o `packing`. El control POS
acepta de una a 99 porciones enteras por adicional y el backend impone el mismo límite. Los importes
del carrito se calculan y presentan desde centavos enteros, sin `float` ni redondeo implícito.

Las relaciones `ingredient_variation_products` se conservan para pedidos e historial antiguos, pero
no autorizan ni limitan ventas nuevas. Si las asignaciones antiguas de un adicional discrepan en
cantidad, precio o estación, la migración lo deja `needs_review`; no elige valores arbitrariamente ni
lo publica al POS. El administrador resuelve el conflicto y lo activa. La pantalla canónica sólo
configura el adicional universal; no crea, edita ni retira relaciones históricas por producto ni las
presenta como condición de disponibilidad. Desde `0028`, cualquier `add_option_id` o
`remove_option_id` enlazado a esas relaciones queda excluido del read model de ventas y una selección
manual falla tempranamente con `ingredient_extra_add_only`; esto no oculta modificadores `add`,
`remove` o `substitute` ordinarios que no estén enlazados. Los endpoints heredados de preview,
aplicación, actualización y archivo de asignaciones responden
`ingredient_variation_assignments_read_only` sin crear, modificar ni archivar datos; la consulta de
asignaciones históricas permanece disponible para auditoría.

El POS coloca **Ingredientes adicionales** junto a **Cliente**. El botón se deshabilita sin líneas en
el carrito. Al abrirlo:

1. si existe una sola línea, queda seleccionada como destino;
2. si hay varias, el cajero elige la línea de producto;
3. el cajero selecciona uno o más adicionales y número entero de porciones;
4. el carrito muestra cada adicional bajo la línea destino, su cargo y un control para retirarlo.

No existe relación previa producto-adicional. `GET /api/v1/catalog/ingredient-extras/available`
requiere `pos.operate`, deriva la sucursal autorizada sólo para validar el alcance y devuelve las
definiciones activas globales; no devuelve overrides ni filtra por producto. La línea de pedido envía
`ingredient_extras=[{extra_id, portions}]`; el backend valida el catálogo global, multiplica cantidad
y precio, construye el componente de consumo y congela ID, nombre, insumo, unidad, cantidad, precio,
costo vigente y estación. IDs de asignaciones históricas o acciones `remove` se rechazan con
`ingredient_extra_add_only`. La venta no confía en precios ni costos enviados por el navegador.

### 34.3 POS-ORD-002 — catálogo compacto, retiro de carrito y enmienda de pedidos no pagados

El POS presenta categorías y, debajo, una única cuadrícula de tarjetas de producto. Se elimina la
banda redundante que repetía los nombres de los mismos productos entre ambos niveles.

Antes de crear un pedido el botón menos sobre cantidad uno retira la línea y un botón con icono de
papelera permite retirarla directamente. Ambos tienen `aria-label`, foco visible y objetivo táctil
mínimo de 44 px. Esta operación es local y no genera auditoría porque aún no existe pedido.

`GET /api/v1/orders/{order_id}` devuelve líneas activas, snapshots, eventos, pagos, `version`,
`editable` y `edit_block_reason`. El detalle siempre requiere `orders.read` y alcance de sucursal.
Una enmienda requiere `orders.amend`, ausencia de pago confirmado, estado `ACCEPTED` y todas las
tareas productivas en `PENDING`. Producción iniciada, pedido cerrado o cancelado son sólo lectura.

`POST /api/v1/orders/{order_id}/amendments` recibe `Idempotency-Key`, `expected_version` y la imagen
completa deseada de líneas. El backend recalcula productos, comentarios, adicionales y totales. No
borra historia: `orders` recibe `version`; `order_lines` recibe estado, revisión,
`supersedes_line_id`, `updated_at` y `removed_at`; `order_amendments` conserva before/after,
solicitante y versión. Las líneas sustituidas se retiran lógicamente, las tareas pendientes se
cancelan y se crean nuevas, y la diferencia de reserva se registra con movimientos compensatorios.
El comando crea `ORDER_AMENDED` y auditoría. Un conflicto de versión responde
`order_version_conflict` sin cambios parciales.

La navegación y el encabezado usan **Pedidos**, no **Historial**. Todas las filas se pueden abrir.
En escritorio la vista usa un patrón maestro–detalle: la lista ocupa la columna principal, conserva
la fila seleccionada resaltada y `GET /orders/{id}` alimenta un panel lateral derecho con folio,
cliente, tipo, estado, líneas, total y acciones. No se usa un modal. Sin selección, el panel presenta
un estado vacío que explica cómo revisar un pedido; mientras carga, el estado permanece contenido en
esa columna sin desplazar la lista. Las no editables muestran detalle y motivo del bloqueo. Las
editables ofrecen **Editar pedido**, navegan al POS en modo edición con banner y folio, y usan el
endpoint de enmienda en lugar de crear otro pedido. Guardar no confirma un pago automáticamente. En
anchos reducidos ambas columnas se apilan conservando el detalle dentro del flujo de la página. La
navegación usa la ruta explícita `pos/orders/:editOrderId/edit`; el POS obtiene el identificador del
segmento de ruta y conserva temporalmente `edit_order_id` sólo para compatibilidad con enlaces
anteriores. La carga del pedido no espera al catálogo para reconocer y mostrar el modo edición. Para
reconstruir el carrito se prefiere el producto vigente del catálogo por `product_id`; cuando no está
visible, se usa el snapshot inmutable de `order_lines` (`product_id`, `product_name`,
`unit_price_cents`, `station`). Este fallback sólo alimenta la interfaz: la enmienda continúa
enviando IDs y el backend recalcula disponibilidad, precio, modificadores, consumo y total.

### 34.4 POS-PAY-003 — cobro diferido para llevar y domicilio

`orders.status` conserva el ciclo operativo. El cobro es un eje separado: la lectura de pedidos
devuelve `payment_status=CONFIRMED|PENDING`, `payment_method` confirmado y
`payment_method_intent`. La proyección visible es **Pendiente de pago** cuando `order_type` es
`takeout` o `delivery` y todavía no existe un pago `CONFIRMED`; esto no impide crear tareas de cocina
ni reservar inventario.

Al confirmar el checkout diferido, `POST /api/v1/orders` recibe `payment_method_intent`, valida uno
de `cash|debit_card|credit_card|transfer`, crea el pedido `ACCEPTED` y no inserta en `payments`.
Pedidos `dine-in` conservan el flujo inmediato de pedido seguido por pago. Desde **Pedidos**,
`POST /api/v1/orders/{id}/payments` registra el método realmente recibido, exige el total vigente,
crea el pago inmutable, eventos y auditoría sin cerrar ni entregar la orden.

### 34.5 POS-NAV-001 — navegación de caja y categorías agrupadas

El menú lateral del POS sólo expone **Punto de Venta**, **Clientes**, **Pedidos** y, cuando el
permiso lo habilita, **Administración**. Las rutas heredadas `/dashboard` e `/inventory` redirigen
sin mostrar superficies paralelas: la primera vuelve a `/pos` y la segunda abre
`/administration/inventory`. La tarjeta **Inventario** vive dentro del centro de Administración y
su ruta exige `branch.admin.access`.

La franja superior es una cuadrícula fija de cinco controles: **Todo**, **Alimentos**, **Bebidas**,
**Otros** y **Favoritos**. Un segundo panel adaptable muestra las categorías concretas del grupo
activo. La proyección `categoriesForCatalogMenuGroup` parte de
`categoriesWithAvailableProducts`, excluye categorías vacías y no repite la categoría sintética
**Todas**. La proyección de productos usa `station`: `kitchen` pertenece a **Alimentos**, `drinks`
a **Bebidas** y cualquier otra estación a **Otros**. **Todo** no filtra por estación.

**Favoritos** conserva IDs de productos concretos por usuario y sucursal en la clave local
`pos_product_favorites_v1:${user_id}:${branch_id}`. Es una preferencia de presentación, no
autoridad del catálogo: no crea categorías, no altera productos y omite IDs que ya no pertenecen a la
proyección. `productsForCatalogMenuGroup` filtra Favoritos sólo por `product.id`; la proyección de
categorías no modela Favoritos. Por ello FAVORITOS inicia directamente en productos y no renderiza el
panel de categorías. Cada tarjeta concreta expone un botón de estrella hermano del botón de selección
del producto —nunca anidado— con `aria-label` y `aria-pressed`; una variante/tamaño es un `product_id`
independiente. Quitar una estrella desde Favoritos oculta únicamente esa tarjeta y conserva carrito y
búsqueda. Cambiar de grupo limpia únicamente la personalización transitoria y conserva búsqueda y
carrito. Los controles usan iconos de la librería existente y foco visible; no requieren controles
**Siguiente** o **Regresar**.

### 34.6 POS-SEC-001 — ajuste de cortesía con autorización reforzada

El subtotal del carrito es una proyección visual, no un campo contable libre. Para el flujo previo a
crear el pedido, las cortesías se autorizan en `order_adjustment_authorizations`: conserva hash
canónico del carrito, subtotal Python, tipo/valor normalizados, delta en centavos, total resultante,
justificación, solicitante, Supervisor autorizador, expiración y eventual pedido consumidor. Sus
importes son inmutables; sólo cambia atómicamente de `AUTHORIZED` a `CONSUMED`. `orders.total_cents`
se crea con la proyección cobrable autorizada y nunca se modifica un pago confirmado.

Sólo se permiten reducciones entre cero y el subtotal calculado. Para aumentar el cobro se agrega un
producto o ingrediente adicional. La justificación es obligatoria y se recorta. Cambiar cualquier
línea invalida la autorización y exige una nueva; nunca se recalcula el dinero en el navegador.

El Cajero autenticado solicita la acción y un Supervisor elegible de la misma sucursal captura su
PIN/código. `POST /api/v1/orders/adjustments/authorize` verifica credenciales y alcance, calcula con
`Decimal` y persiste una autorización identificada, de un solo uso y expiración máxima de dos
minutos, limitada a actor solicitante, organización, sucursal y hash del carrito. La credencial no se
guarda ni se registra y se borra del estado del navegador al cerrar el diálogo.

`POST /api/v1/orders/quote` puede proyectar la autorización sin consumirla. `POST /api/v1/orders`
recalcula el mismo carrito, exige que subtotal y hash continúen idénticos y consume la autorización
mediante compare-and-swap dentro de la creación. Reutilizar, expirar, cambiar actor/sucursal/carrito
o variar precios falla de forma atómica. La auditoría conserva importes e IDs, nunca credenciales, y
el pago posterior debe coincidir con `orders.total_cents`.

El modal del POS muestra tipo, valor, justificación y credencial de Supervisor. Tras confirmar, el
carrito presenta por separado “Subtotal”, “Cortesía / Descuento” y “Total”; todos son DTO del backend.

### 34.7 PUR-OPS-001 — proveedores y compras desde la sucursal

La página de Proveedores dentro del POS continúa leyendo el catálogo corporativo, pero agrega
**Nuevo proveedor** para usuarios con `suppliers.create`. El alta exige código y nombre comercial;
RFC y contacto son opcionales. Se valida duplicidad por código o RFC en la organización, se crea el
registro central y se habilita para la sucursal canónica mediante `supplier_branch_terms`. El evento
`supplier.created_from_branch` registra actor y sucursal. Supervisor no puede editar proveedores
existentes ni condiciones de otra sucursal; Cajero sólo opera POS.

Para que un proveedor nuevo pueda comprarse, la misma página ofrece **Nueva presentación** con
insumo, unidad comercial, contenido aprovechable y precio. El permiso
`purchase_presentations.create` permite al Supervisor crear una presentación central auditada desde
su sucursal, pero no modificar precios históricos ajenos ni inventar conversiones.
Mientras ese permiso granular no exista como permiso persistido en la migración correspondiente,
la compatibilidad temporal para la alta usa `purchases.manage` con alcance de sucursal; la lectura
usa `purchases.read`. La edición y el precio histórico permanecen bajo `admin.manage`.

Compras deja de ser sólo lectura. Con `purchases.manage` el Supervisor crea un borrador con proveedor,
folio, documento, fecha, método de pago y una o más líneas. La etiqueta visible **Producto/Insumo**
selecciona realmente una presentación de compra para conservar conversiones exactas. Cada línea
captura cantidad de presentaciones, precio unitario, descuento e impuesto informativo. El backend
recalcula subtotal, total y cantidad base con `Decimal`; el navegador no es fuente de verdad.

Los métodos de este incremento son `cash`, `card` y `transfer`. Efectivo es el predeterminado y
establece `paid_from_cash=true`; confirmar exige turno abierto, `cash.withdraw` e idempotencia y crea
un retiro `SUPPLY_PURCHASE` enlazado. Tarjeta y transferencia no escriben caja. `credit` permanece
bloqueado hasta implementar la cuenta por pagar de `PRD-FR-105`, evitando deuda sin sublibro.
Confirmar genera `PURCHASE_RECEIPT` y actualiza costo promedio; cancelar usa las compensaciones ya
definidas. La sucursal del payload nunca reemplaza la sucursal canónica de sesión.

### 34.8 Migraciones, permisos, observabilidad y orden de entrega

La cadena prevista es:

1. `0028_global_order_comments_extras` — comentarios globales y configuración canónica de extras;
2. `0029_order_amendments` — versiones, líneas retiradas y enmiendas;
3. `0030_supervisor_order_adjustments` — autorización reforzada, ajustes y permisos de pedidos;
4. `0031_branch_supplier_purchase_permissions` — permisos y procedencia de altas de proveedores.

Cada migración debe tener downgrade probado, conservar una sola head y no alterar pedidos, pagos,
movimientos o snapshots históricos. `0028` crea `order_comment_presets` y
`order_comment_products` sin `branch_id`, agrega los campos canónicos de
`ingredient_variations` y conserva intactos los grupos, opciones y asignaciones históricas. En la
consolidación, sólo una configuración ADD consistente se publica; cualquier discrepancia de
cantidad, precio, estación u orden queda `needs_review`, sin elegir un valor. Antes de cambiar ese
estado, `0028` guarda en su tabla propia `ingredient_variation_0028_status_backups` el estado
anterior de cada variación afectada. El downgrade restaura ese estado exactamente antes de retirar
el respaldo, tablas y columnas propias de `0028`, de modo que `0027 -> 0028 -> 0027 -> 0028`
repite la detección sin perder `active` ni `archived`. Nunca borra pedidos, pagos, movimientos,
snapshots, `modifier_groups`, `modifier_options`, `branch_modifier_options` ni
`ingredient_variation_products`. La migración registra un resumen de consolidación por cada
organización afectada, sin nombres de productos, textos de pedidos ni datos personales.

Los nuevos permisos son `orders.amend`,
`orders.adjust_total`, `suppliers.create` y `purchase_presentations.create`; Administrador recibe
todos, Supervisor recibe los cuatro con alcance operativo, Cajero recibe únicamente `orders.amend`.

Los comandos emiten logs estructurados y métricas por resultado para alta masiva de comentarios,
configuración de adicionales, enmiendas, ajustes, reautenticación, proveedores y compras. Logs y
auditoría nunca incluyen contraseñas, tokens completos, RFC, teléfonos ni payloads personales.

## 35. POS-CAT-004 — selección previa de opción por categoría

`category_option_groups` pertenece a una organización y categoría, con `code` estable,
`name` visible, `selection_mode='single'`, `is_required=true`, orden y estado. La unicidad por
`organization_id + category_id` permite como máximo un grupo histórico por categoría; un grupo
archivado se reactiva o actualiza, no se reemplaza por una segunda configuración. El código sólo es
único dentro de esa categoría: dos categorías corporativas pueden usar `size`. Sus
`category_option_values` tienen código único dentro del grupo, orden y estado. La relación explícita
`product_option_value_assignments(product_id, group_id, option_value_id)` admite a lo sumo un valor
por producto y grupo. No contiene precio, receta, disponibilidad, inventario, texto de cocina ni
`price_delta_cents`.

Python es la autoridad de las invariantes: organización común de categoría, grupo y producto; el
producto debe pertenecer a la categoría del grupo; y el valor debe pertenecer al grupo. Toda
escritura corporativa exige `catalog.manage`, se ejecuta en una transacción, registra un
`audit_event` append-only y usa errores de dominio estables. Las lecturas corporativas requieren
solamente `catalog.manage` y no dependen de `pos.operate`; el enlace y la ruta también se protegen
en UI. Activar un grupo primero calcula la
cobertura de productos activos vendibles de su categoría y rechaza `category_option_group_incomplete`
sin mutación parcial si falta una asignación válida. Administración corporativa puede consultar la
cobertura y los incompletos, incluyendo cada producto relevante con su asignación actual o `null`;
Administración de sucursal no recibe estas rutas. No se puede asignar un valor inactivo/archivado.
Mientras un grupo esté activo no se puede inactivar/archivar un valor que deje un producto sin valor
activo; la validación se realiza antes de escribir y revierte la transacción ante duplicados,
relaciones cruzadas, códigos, estados, modos u órdenes inválidos.

El editor corporativo permite crear y editar explícitamente `code`, `name`, orden y estado de cada
valor. Los cambios de texto se guardan por una acción explícita y pueden cancelarse; no se escriben
automáticamente al perder foco. La hidratación del formulario se deriva de `id`, código, nombre y
estado canónicos del grupo, de modo que una actualización del mismo grupo no conserva estado
obsoleto ni revierte el estado recién persistido. La cobertura se titula "Productos de la categoría"
y separa un conteo y marca de los incompletos, sin afirmar que toda la lista sea incompleta.

La proyección pública se centraliza en Python. Un producto elegible conserva las reglas existentes:
activo, en alcance de sucursal, disponible y con `price_cents` entero positivo. Para una categoría
con grupo activo, sólo se publica un producto cuya asignación activa coincide con un valor activo del
grupo; no hay fallback a todos los productos. `GET /categories?branch_id=` devuelve
`selection_group: null` o un grupo con valores ya ordenados y sólo valores que tienen al menos un
producto elegible. `GET /catalog/products?branch_id=` añade `selection: null` o los IDs, códigos,
nombres y orden del grupo/valor. Ambos endpoints usan la misma proyección. Un fallo de proyección se
registra `category_option_projection_error` sin PII y se propaga como error recuperable, nunca como
catálogo sin filtro.

El POS mantiene estado local mínimo: categoría activa, opción seleccionada y búsqueda. Al entrar a
una categoría configurada sin opción muestra tarjetas del grupo; la selección no llama al flujo de
modificadores ni al carrito. Al cambiar categoría u opción se limpia únicamente el estado
transitorio de modificadores. Si una recarga invalida el valor seleccionado, lo limpia y vuelve a
pedirlo; la búsqueda se conserva y se aplica después. La carga falla con una tarjeta explícita y
**Reintentar**, que repite ambas proyecciones; un selector activo sin valores visibles muestra un
estado vacío recuperable. El contrato de pedido no cambia: sólo envía
`product_id` concreto y `operations.py` vuelve a resolver precio, snapshot, disponibilidad y total.

La migración lineal `0034_category_option_selection` crea exclusivamente las tres tablas e índices
nuevos y no infiere ni migra asignaciones por texto. Su downgrade retira únicamente esas tablas;
por tanto un ciclo upgrade/downgrade/upgrade conserva exactamente las tablas e historia previas en
PostgreSQL y SQLite. Rollback operativo: archivar el grupo para restaurar el flujo de categoría sin
selector, manteniendo la configuración y auditoría. Observabilidad mínima: `category_option_projection_incomplete`
y `category_option_projection_error` se registran estructuradamente sin PII; la infraestructura no
expone aún métricas dedicadas.

El schema `pos-catalog-projection-v1` es un contrato ejecutable: sus objetos de categoría y producto
verifican tipos, mínimos, `additionalProperties`, `selection_mode='single'`, `is_required=true` y
las variantes nulas y activas de `selection_group`/`selection`. Las pruebas negativas del validador
forman parte del contrato y no se sustituyen por una comparación superficial de llaves.

## 36. POS-ATT-001 — checador de personal por código

La migración lineal `0032_attendance_clock`, descendiente de `0031_delivery_assignments`, agrega
`employee_code` nullable de longitud seis a `users` y `drivers`, además del registro central
`employee_code_registry`. Los valores se recortan, convierten a mayúsculas y deben satisfacer
`^[A-Z0-9]{6}$`. El registro central reserva atómicamente cada código para un único
`subject_type + subject_id` y su restricción única por organización y código evita colisiones entre
ambos catálogos, incluso ante escrituras concurrentes por la API. Las columnas de catálogo tienen
restricción de longitud y una referencia compuesta al código reservado para la misma persona. Los
registros heredados quedan con `NULL`: no se inventan claves ni se altera su vigencia; todo registro
nuevo requiere código. El UUID sigue siendo la identidad técnica usada por relaciones y auditoría.

La migración correctiva `0033_restore_superadmin_role` repara de forma idempotente la asignación
del rol `Administrador corporativo` de la cuenta superadministradora canónica cuando una edición
propia fallida de una versión anterior la hubiera eliminado. No cambia contraseñas, códigos,
usuarios, roles ni permisos. La denegación de permisos revierte primero cualquier mutación pendiente
de la sesión y sólo después confirma su evento `authorization.denied`, para que la auditoría no
pueda convertir una respuesta 403 en una escritura parcial.
El `INSERT` correctivo tipa explícitamente sus parámetros como `VARCHAR(36)` para que PostgreSQL y
Psycopg no infieran tipos incompatibles al reutilizarlos en la inserción y en `NOT EXISTS`.

`attendance_checks` es append-only y conserva `organization_id`, `branch_id`, `subject_type`,
`subject_id`, snapshots de código y nombre, `local_date`, `daily_sequence` (1 entrada, 2 salida),
`checked_at` UTC y `created_by`. Una restricción única por organización, persona, fecha local y
secuencia impide duplicar la misma posición diaria. El downgrade se bloquea si existen checadas,
o códigos asignados, porque retirarlos destruiría historial o identidad operativa; sin esos datos,
quita tabla, índices y columnas.

`POST /api/v1/attendance/checks` exige actor autenticado con `pos.operate`, resuelve la sucursal con
`authorize_branch_scope` y nunca acepta hora, fecha, nombre ni tipo desde el navegador. El backend
normaliza y valida los seis caracteres, resuelve la reserva central hacia exactamente un Usuario o
Repartidor activo, obtiene `datetime.now(UTC)` y
calcula `local_date` con la zona IANA persistida en `branches.timezone`. Una clave ausente o ambigua,
una zona inválida o una tercera checada del mismo día falla sin insertar. El evento de auditoría
incluye ID de checada, tipo y secuencia, pero no copia la clave ni el nombre.

`GET /api/v1/attendance/checks` exige `branch.staff.read`. Acepta `employee_code`, `day` ISO,
`month` `YYYY-MM` y `branch_id`; día y mes son excluyentes. Un actor con alcance de sucursal queda
forzado a su sucursal, mientras un actor corporativo puede consultar todas o seleccionar una activa.
La respuesta se ordena por fecha y hora descendente e incluye `display_state=single|entry|exit`: la
proyección recalcula `single` cuando sólo existe la primera checada y la convierte en `entry` cuando
aparece la segunda.

El shell POS abre el checador como diálogo, actualiza el reloj cada segundo y contiene un único campo
`password` para la clave, botón de registro, estados de envío, error y confirmación. El enlace vive
entre Pedidos y Administración y está disponible para sesiones POS válidas. Administración agrega
la tarjeta y ruta `/administration/attendance`, protegidas por `branch.staff.read`, con filtros de
código, día/mes mutuamente excluyentes y sucursal autorizada. La interfaz asigna azul a `single`,
verde a `entry` y rojo a `exit`; los colores siempre se acompañan con texto, no son el único medio
de interpretación.

## 37. POS-UX-002 — jerarquía visual de tarjetas sin fotografía

La presentación de imagen de una tarjeta se determina exclusivamente en el frontend mediante el
helper puro `productCardPresentation(image_url)`: `null`, `undefined`, una cadena vacía o una cadena
que queda vacía después de `trim()` producen `fallback`; una cadena no vacía produce `image`. El
helper no interpreta datos de catálogo ni cambia disponibilidad, selección, precio o carrito.

Sólo `filteredProducts.map(product)` —la cuadrícula de productos concretos ya proyectados por el
backend— consume el helper. Esa tarjeta recibe modificadores explícitos con/sin imagen. En fallback
el visual mide 52 px y el icono existente de `lucide-react` mide 32 px; el nombre usa 14 px,
`line-height: 1.25`, peso 700 y ajuste de palabra para admitir tres líneas sin elipsis ni recorte.
El precio conserva `formatMxnCents` y sus reglas existentes. La tarjeta puede crecer verticalmente
para evitar solape en el grid de escritorio y su variante `minmax(132px, 1fr)` hasta 1120 px.

Una URL no vacía conserva `img`, `alt={product.name}`, contenedor visual de exactamente 72 px y
`object-fit: contain`; el contenedor es un ítem flex rígido (`height`, `min-height` y
`flex-basis` de 72 px), recorta su contenido y su `img` no puede exceder sus dimensiones. La
evidencia visual mide tanto el contenedor como el elemento `img`. No recibe la tipografía especial
del fallback. Las tarjetas del selector previo
`activeSelectionGroup.values` no invocan el helper ni los modificadores: conservan icono de 48 px y
la transición local que no agrega al carrito. No hay contrato API, backend, migración, asset ni
dependencia nueva.

## 38. POS-CASH-OPS-001 — caja, cuentas, corte y perfiles acumulativos

**Estado:** decisiones de producto aprobadas el 2026-08-10. PCO-001 implementa perfiles, permisos y
alcance; PCO-002 implementa conceptos de caja versionados y lectura efectiva; PCO-003 implementa el
ledger, compensaciones y efectivo esperado. PCO-004 queda autorizado el 2026-08-12 para cierre
operativo y monitor de ventas. Corte final, reapertura, reportes PCO-007 y offline siguen
definidos/no implementados. `SDD-ADR-015` sigue siendo la
regla de autorización; esta sección no compara nombres de rol en clientes ni API.

### 38.1 Perfiles, permisos y alcance

La semilla propuesta conserva roles especializados y agrega los perfiles acumulativos como conjuntos
de permisos. Todos los permisos se evalúan en Python con `require_permission` y
`authorize_branch_scope`; el cliente recibe sólo una proyección de capacidades. Dueño recibe de forma
explícita cada permiso persistido vigente de su organización, incluidos `admin.manage`,
`catalog.manage` y permisos especializados/corporativos, más `access.organization.all_branches`.
No existe wildcard que el cliente pueda afirmar y aun Dueño no cruza organizaciones. Los demás perfiles
usan `assigned_branch` aprobado y niegan una sucursal ausente o ajena. La pertenencia de Dueño se
representa por concesión persistida de autoridad de organización, no por el texto `Dueño`; no se
asigna ningún usuario a ese perfil durante la migración. PCO-001 incorpora
`role_authority_grants(authority_kind=organization_all_permissions)` para que el backend conceda a
Dueño cada permiso persistido actual o futuro de su organización; `profile_transition_mappings`
reserva el mapeo individual reversible/auditable, sin conversión automática de Administrador
corporativo ni de usuarios legacy.

Un rol con `scope=branch` exige `user_roles.branch_id` explícito, activo y perteneciente a la misma
organización del usuario/rol; crear o reemplazar una asignación sin él responde
`branch_assignment_required` sin escritura. En runtime, un dato legacy `branch_id=NULL` nunca entra
en `scoped_role_ids` y se audita como `no_scoped_role`. Un rol con
`organization_all_permissions` sólo puede ser asignado o revocado por un actor que ya posea esa misma
concesión persistida en la organización; `admin.manage`, un nombre de rol o payload no sustituyen esa
autoridad. La semilla deja cero Dueños, por lo que la asignación normal falla cerrada. El único camino
inicial es el comando interno de bootstrap aprobado y explícito, que no se invoca desde Alembic ni
contra datos reales dentro de PCO-001.

El rol con esa concesión tiene el invariante `scope=organization`. Un actor sin la misma concesión no
puede cambiar su alcance, borrarlo ni reemplazar sus permisos; devuelve respectivamente
`owner_authority_required` o, para el actor ya autorizado, `owner_role_scope_immutable`,
`owner_role_delete_forbidden` y `owner_role_permissions_immutable`, con auditoría de denegación. El
actor con la misma autoridad puede renombrarlo: la etiqueta sigue sin ser autoridad y el grant mantiene
los permisos persistidos actuales/futuros. `create_role` y el reemplazo de permisos no pueden crear
`role_authority_grants`; un rol organizacional con el permiso ordinario
`access.organization.all_branches` conserva sólo ese permiso explícito y no obtiene autoridad dinámica.

El bootstrap inicial se expone sólo como comando interno de mantenimiento `bootstrap_initial_owners`,
no como ruta HTTP. Recibe `organization_id` explícito, `operational_actor_user_id`, `provenance` y
los dos correos exactos configurados como input (`aniacuestas@gmail.com`, `mangoex@gmail.com`). Valida
primero organización activa, actor operacional preexistente de la misma organización, rol único con
grant y ambos usuarios existentes/activos. La inspección externa de sólo lectura confirmó que los dos
usuarios preservan Administrador corporativo legacy; el comando no lo remueve ni lo convierte.
Después inserta ambas asignaciones y eventos en una transacción.
No crea usuarios, contraseñas, organizaciones, roles ni grants. Cualquier conflicto de conjunto
(correo faltante/duplicado, otra organización, Dueño externo, parcialidad o rol ambiguo) responde un
error estable sin asignación parcial y deja auditoría de rechazo cuando ya existe alcance para auditar.
Antes de escribir esa auditoría, el comando revierte la transacción pendiente del llamador: la denegación
nunca confirma una escritura ajena. La misma regla protege una denegación de autoridad de transición y
mantiene el `organization_id` solicitado en el evento. Para actor existente pero inactivo o de otra
organización, `authorization.denied` conserva su ID como actor real; si el actor no existe, el evento
usa `actor_user_id=NULL` y sólo la razón estable `actor_not_authorized`, respetando la FK y sin
inventar identidad.
Un rerun con exactamente el mismo conjunto ya aplicado produce `already_bootstrapped` y sólo auditoría
de replay. La revisión Alembic nunca invoca ese comando.

`profile_transition_mappings` implementa el workflow de mantenimiento explícito con `PENDING ->
MAPPED -> REVERSED`: `organization_id`, `target_branch_id`, snapshot JSON de roles, procedencia y
keys de idempotencia de creación/aplicación/reversión. Un índice único parcial sobre
`pending|mapped` impide dos operaciones abiertas por usuario/perfil; múltiples `reversed` conservan
historia append-only. El dry-run devuelve únicamente IDs, scope y códigos/nombres de rol, nunca email,
nombre visible ni otra PII. Crear, aplicar y revertir requieren actor con la misma autoridad
organizacional y validan primero una organización existente/activa, incluso al cargar un mapping ya
existente. Organización ausente/inactiva revierte trabajo pendiente y devuelve
`profile_transition_organization_invalid` sin intentar auditoría ni insertar mapping. Aplicar valida
alcance, agrega sólo el perfil destino y conserva especialidades;
aplicar revalida que el rol legacy continúe asignado al usuario con el mismo `branch_id` capturado en
`role_snapshot`. Revertir elimina únicamente la fila
destino con el mismo `role_id` y `target_branch_id` que creó el mapping; ausencia o cambio de sucursal
es `profile_transition_target_assignment_conflict`, se audita y no cambia a `REVERSED`.
Reintentos, incluidos los que llegan después de una colisión de inserción, comparan `user_id`, roles,
sucursal y procedencia: sólo payload idéntico devuelve el estado/auditoría de replay; otro es
`profile_transition_idempotency_conflict`. Conflicto de key/payload o transición ilegal, incluido rol
legacy fuera de la organización, falla cerrado. Administrador corporativo legacy no se convierte automáticamente en Dueño: una
solicitud sólo existe por llamada explícita de mantenimiento y sigue las mismas validaciones.

Antes de sembrar, la revisión `0035` hace preflight fail-closed de los 19 permisos y seis perfiles
reservados: cualquier ID/código de permiso o ID/nombre organizacional de rol preexistente aborta la
revisión. El downgrade sólo borra por IDs reservados de esta revisión, nunca por código ambiguo, y se
bloquea si hay grants, asignaciones, mappings o concesiones externas.

| Capacidad / permiso estable | Cajero | Cajero jefe | Líder | Supervisor | Administrador | Dueño |
|---|---:|---:|---:|---:|---:|---:|
| `pos.operate`, `orders.create/read`, `payments.read/confirm` | sí | sí | sí | sí | sí | sí |
| `cash.concept.read`, `cash.movement.withdraw` | sí | sí | sí | sí | sí | sí |
| `cash.shift.read/open/close`, `cash.movement.deposit/read`, `cash.reconciliation.perform` | no | sí | sí | sí | sí | sí |
| `orders.amend`, `purchases.read/manage`, `inventory.waste` | no | sí | sí | sí | sí | sí |
| `cash.user_cut.read/create`, `orders.cancel` | no | no | sí | sí | sí | sí |
| `recipes.manage`, `inventory.read`, `reports.ingredient_sales.read`, `reports.waste.read` | no | no | no | sí | sí | sí |
| `reports.sales.read`, `reports.expenses.read` | no | no | no | no | sí | sí |
| `admin.manage`, `catalog.manage` y cada permiso corporativo/especializado persistido de organización | no | no | no | no | no | sí |
| `access.organization.all_branches` | no | no | no | no | no | sí |

`cash.movement.withdraw` sustituye gradualmente el nombre previo `cash.withdraw`; la migración debe
mantener una compatibilidad explícita y temporal, no permisos implícitos. Nuevos permisos atómicos:
`cash.movement.withdraw`, `cash.movement.deposit`, `cash.movement.read`, `cash.movement.compensate`,
`cash.concept.read`, `cash.concept.manage`,
`cash.reconciliation.perform`, `cash.user_cut.read`, `cash.user_cut.create`,
`cash.user_cut.reopen.request`, `cash.user_cut.reopen.authorize`, `orders.reopen.request`,
`orders.reopen.authorize`, `reports.sales.read`, `reports.expenses.read`,
`reports.ingredient_sales.read`, `reports.waste.read` y `access.organization.all_branches`.
`cash.concept.read` corresponde a cualquier perfil que pueda retirar/depositar; `cash.concept.manage`
y `cash.movement.compensate` corresponden a Dueño. `orders.reopen.request` corresponde a Cajero jefe
y superiores; `orders.reopen.authorize` corresponde sólo a Dueño. `cash.user_cut.reopen.request` y
`cash.user_cut.reopen.authorize` corresponden sólo a Dueño. PCO-001 los siembra como permisos sin
implementar las rutas de los incrementos posteriores. Ningún
permiso compuesto como `cash.manage` sustituye estas facultades.

### 38.2 Modelo, invariantes y cálculos autoritativos

Entidades propuestas: `cash_movement_concepts` (código, tipo permitido, versión, vigencia,
evidencia/referencia requerida), `cash_movements` (turno, caja, sucursal, tipo `DEPOSIT|WITHDRAWAL`,
concept snapshot, importe en centavos, referencia/evidencia, actor, idempotency key y compensación),
`cash_shift_closures`, `user_cash_cuts`, `user_cash_cut_operations`, `order_reopen_requests` y
proyecciones de `sales_monitor`/`ingredient_sales` de sólo lectura.

#### 38.2.1 PCO-002 — catálogo de conceptos sin activar el ledger

El catálogo separa identidad e historia. `cash_movement_concepts` conserva `id`, organización,
`code` inmutable, estado `active|archived`, actor y marcas UTC. `cash_movement_concept_versions`
conserva una fila append-only por publicación: `id`, `concept_id`, entero `version`, nombre visible,
`allowed_movement_type=deposit|withdrawal|both`, `valid_from`, requisitos de referencia/evidencia,
actor y marca UTC. La pareja `(concept_id, version)` es única. Archivar sólo cambia el estado y la
marca de la identidad; nunca elimina versiones ni reutiliza el código.

`cash_concept_commands` gobierna las mutaciones con unicidad `(organization_id, idempotency_key)`,
tipo de comando, hash SHA-256 del payload canónico, resultado estable, actor y marcas UTC. Un replay
idéntico devuelve el resultado persistido; la misma clave con comando, objetivo o payload diferente
falla `idempotency_conflict`. El hash y la respuesta se calculan/persisten en Python; la UI no decide
versión, vigencia efectiva ni estado.

La lectura efectiva recibe `movement_type`, fecha UTC y alcance de sucursal autorizado. Excluye
identidades archivadas, versiones futuras y tipos incompatibles; entre versiones elegibles devuelve
sólo la de mayor número. La lista administrativa conserva toda la historia. PCO-002 no modifica la
tabla legacy `cash_movements`, no crea movimientos, no calcula esperado y no implementa outbox;
esas escrituras comienzan únicamente en PCO-003.

El control administrativo `datetime-local` presenta y precarga componentes de la zona local del
navegador. No puede derivar su valor visible con `Date.toISOString().slice(...)`, porque esa cadena UTC
se reinterpretaría como hora local. Al construir el comando, el frontend convierte una sola vez el
valor local capturado a ISO UTC; el backend conserva la autoridad sobre la efectividad contra `now UTC`.

#### 38.2.2 PCO-003 — ledger manual, compras y efectivo esperado

PCO-003 extiende `cash_movements` de forma compatible; no crea un ledger paralelo ni reescribe filas
legacy. Agrega campos nullable para `concept_id`, `concept_version_id`, `concept_snapshot`,
`reference`, `evidence_refs` y `compensates_movement_id`. Los comandos manuales nuevos exigen todos
los campos de concepto/referencia/evidencia; las compras del sistema preservan `source_type=PURCHASE`
y `source_id` sin fingir un concepto de usuario. La cancelación de una compra crea `deposit` exacto
enlazado al retiro; filas históricas `cash_reversal` siguen proyectándose como entrada.

`cash_movement_commands` conserva organización, actor, command type `create|compensate`, objetivo,
Idempotency-Key, hash SHA-256 canónico, estado y resultado JSON estable. La unicidad es por
organización. El hash incluye actor, sucursal, caja, tipo, concepto, centavos, referencia, evidencias
y objetivo de compensación. Replay idéntico devuelve el resultado persistido aunque después existan
otros movimientos; cualquier diferencia falla `idempotency_conflict`. La columna legacy
`cash_movements.idempotency_key` recibe una clave técnica determinista derivada, nunca el texto
secreto ni la autoridad del comando.

El cliente envía `branch_id` y `register_id`; Python autoriza el alcance y resuelve el único turno
`OPEN`. La migración hace preflight y aborta si ya existen dos turnos OPEN para la misma pareja; crea
un índice único parcial por sucursal/caja y runtime devuelve `cash_shift_ambiguous` si una base dañada
vuelve a violar el invariante, nunca selecciona `.first()` silenciosamente. La confirmación de una
compra cash recibe `register_id` explícito y no cae por defecto a `CAJA-01`. No acepta
`organization_id`, `actor_user_id`, `cash_shift_id`, snapshot, signo,
`expected_cash_cents` ni diferencia desde el navegador. Un movimiento manual usa el concepto efectivo
de mayor versión con `valid_from <= now UTC`, tipo compatible e identidad activa. Copia un snapshot
inmutable con identidad, código, versión, nombre, tipo, requisitos y vigencia.

La compensación sólo requiere `cash.movement.compensate`, usa mismo turno/sucursal e importe exacto,
crea el tipo opuesto, copia la procedencia conceptual del original y exige motivo y evidencia. Se
rechaza compensar una compensación, una fila ajena, una fila no confirmada, un original ya compensado
o un turno no abierto. `reversal_of_id` legacy y `compensates_movement_id` nuevo describen la misma
relación económica: si existe cualquier reversa/compensación hacia el original, otra se rechaza. Un
índice único parcial sobre `compensates_movement_id`, más preflight/consulta de `reversal_of_id`,
impide doble compensación concurrente. Nuevas cancelaciones de compra escriben `deposit` y ambos
campos apuntan al retiro para compatibilidad; filas históricas `cash_reversal` no se reescriben.

La lista canónica proyecta para cada fila un `compensation_state` derivado en backend
(`eligible|compensated|compensation|ineligible`) y `compensated_by_movement_id` nullable. `eligible`
exige original confirmado `deposit|withdrawal`, turno todavía `OPEN` y ausencia de reversa o
compensación entrante/saliente; nunca se confía en una deducción parcial de la página actual. La
proyección no concede autoridad: el POST vuelve a autorizar y revalidar bajo el guard del turno.

El POS muestra `Compensar` sólo cuando la sesión contiene `cash.movement.compensate` y la proyección
es `eligible`. El formulario inline/modal solicita exclusivamente motivo y una o más referencias de
evidencia; importe, signo, concepto, sucursal, turno y vínculo se derivan en Python. Cada intención
conserva su Idempotency-Key hasta respuesta confirmada o conflicto explícito. Cancelar o abrir otra
fila descarta por completo la intención anterior (vínculo, motivo, evidencia y clave); durante un
envío no se permite abandonar ni sustituir la intención. Tras crear o compensar,
el cliente vuelve a consultar el ledger y muestra el `current_summary` recibido; no deja una fila
confirmada ausente hasta recarga manual. Fallo de red mantiene la intención reintentable y no declara
éxito. Filas `compensated|compensation|ineligible` muestran estado y vínculo, pero no acción.

`evidence_refs` es un arreglo JSON no vacío de máximo 10 strings opacos; cada referencia se recorta,
debe tener 1..600 caracteres y no se interpreta como archivo ni URL confiable. El contrato rechaza
propiedades adicionales. Referencia, evidencias, Idempotency-Key y hashes nunca se copian a logs ni al
payload de auditoría; auditoría conserva IDs, tipo, centavos, resultado y procedencia mínima.

Como `cash_movements.reason_code` legacy admite 48 caracteres y el código de concepto 64, PCO-003 no
lo copia ciegamente: usa `MANUAL_DEPOSIT`, `MANUAL_WITHDRAWAL` o un código sistémico corto y conserva
el código completo del concepto sólo en el snapshot. Movimiento manual, compra cash, compensación y
el cierre vigente comparten un guard de serialización sobre el turno. Sin adelantar los estados de
PCO-004, un movimiento que gana el guard queda incluido antes del resumen; un cierre que lo gana
primero deja el turno no OPEN y el movimiento falla sin escritura. La implementación debe normalizar
la carrera en errores de negocio, no en excepción SQL.

`calculate_expected_cash` es una función Python autoritativa: fondo inicial + pagos confirmados cuyo
método es `cash` + `deposit` - `withdrawal`; interpreta `cash_reversal` legacy como depósito. No suma
compras ni cancelaciones por otra consulta: participan sólo mediante su `cash_movement`. Todo importe
es entero de centavos y la respuesta expone componentes reconciliables.

La suma se itera en Python sobre filas confirmadas; un tipo desconocido falla cerrado. Estados legacy
distintos de `confirmed`, incluido `completed`, no participan y se reportan como excluidos sin
normalización silenciosa. Un replay conserva `summary_at_commit` como evidencia histórica y puede
incluir además `current_summary` recalculado; nunca etiqueta el snapshot persistido como total actual.
La cancelación de compra conserva permiso `purchases.manage` y crea su compensación interna en la misma
transacción; no exige `cash.movement.compensate`, que pertenece exclusivamente al endpoint manual de
Dueño. `source_type` legacy en minúsculas se preserva en almacenamiento y se proyecta a un enum
canónico en la API; no se reescribe historia sólo para cambiar mayúsculas.

La revisión `0037_cash_movement_ledger` desciende linealmente de `0036_cash_concepts`, añade columnas,
tabla e índices sin sembrar conceptos ni alterar filas legacy. El downgrade se bloquea si existe un
comando PCO-003 o cualquier fila usa los campos nuevos; sólo una base sin historia PCO-003 puede volver
a `0036`. Debe pasar `0036 -> 0037 -> 0036 -> 0037` en SQLite y PostgreSQL aislado, conservando una
huella determinista de filas legacy. PCO-003 no agrega outbox/inbox: ante falta de red el POS muestra
fallo no confirmado y PCO-008 resolverá `pending_sync`.

#### 38.2.3 PCO-004 — cierre operativo y monitor de ventas trazable

PCO-004 no reutiliza `cash_shift_cuts` para nuevas escrituras y no crea `user_cash_cuts`. Agrega
`cash_shift_closures` como artefacto append-only uno-a-uno con turno: identidad organizacional,
sucursal, caja, turno, actor, fecha UTC y `summary_snapshot` canónico. El snapshot contiene al menos
ventas y pagos confirmados, pagos cash, fondo, depósitos, retiros, movimientos excluidos, efectivo
esperado y conteos de operaciones. `cash_shift_commands` conserva comandos `open|close`, actor,
objetivo, `Idempotency-Key`, hash SHA-256 del payload canónico, resultado estable y estado
`completed`, con unicidad por organización. Replay idéntico devuelve el mismo turno/cierre; cambio de
actor, sucursal, caja, importe inicial u objetivo bajo la misma clave falla `idempotency_conflict`.

El cierre canónico recibe el ID del turno en la ruta y un objeto JSON vacío; sucursal, caja, actor,
estado, resumen, esperado y fecha se resuelven en Python. Rechaza propiedades adicionales, en
particular `counted_cash_cents`, `expected_cash_cents`, `difference_cents`, actor, organización,
sucursal, caja o estado. Bajo el guard compartido cambia internamente `OPEN -> CLOSING`, calcula e
inserta el cierre y confirma `OPERATIVELY_CLOSED` en una sola transacción. Un fallo recuperable
revierte cierre, auditoría y estado a `OPEN`. El evento `cash_shift.operationally_closed` registra
IDs, actor y componentes seguros; no contiene clave idempotente ni payload completo. El endpoint
legacy `POST /cash-shifts/close` permanece sólo como alias de transición con payload exacto
`branch_id, register_id`; usa la misma semántica e idempotencia y rechaza cualquier contado o campo
extra con `cash_shift_counted_cash_forbidden`. Nunca ignora el contado ni escribe un corte legacy.

Pago, movimiento manual, compra cash y cierre usan el mismo guard. `POST /orders/{id}/payments`
recibe `register_id`, autoriza la sucursal del pedido y resuelve el turno `OPEN` de esa caja en el
momento de confirmar. `payments.cash_shift_id` representa el turno que cobró; `orders.cash_shift_id`
continúa representando el turno que capturó. El resumen y monitor atribuyen venta al pago confirmado,
no al turno de captura. Si el pago gana el guard se incluye antes del cierre; si el cierre gana, el
pago devuelve `cash_shift_not_open` sin pago, eventos, snapshot ni cierre de pedido. Esta regla aplica
también al cobro inmediato y corrige la carrera de cobro diferido sin reescribir pagos históricos.

`order_lines` congela `family_id_snapshot`, `family_name_snapshot` y
`family_snapshot_source=captured|legacy_catalog_backfill` al crear o enmendar. La revisión
`0038_cash_shift_closures_sales_monitor` hace preflight y completa líneas legacy mediante la FK
producto-categoría vigente durante la migración; una relación ausente o incoherente aborta. El origen
`legacy_catalog_backfill` queda visible porque es determinista, pero no afirma que el catálogo actual
sea idéntico al de la venta histórica.

Cada pago confirmado obtiene en la misma transacción un `sales_operation_snapshot` append-only y sus
`sales_operation_line_snapshots`. La cabecera conserva pago, pedido, turno de cobro, caja, folio,
servicio, moneda, fecha, totales y calidad. Cada línea conserva producto/familia, cantidad e importes
`gross_cents`, `discount_cents`, `courtesy_cents`, `tax_cents`, `net_cents`. PCO-004 registra cero
sólo cuando el dominio de la operación conoce explícitamente que no hubo descuento, cortesía o
impuesto registrado; un dato histórico sin fuente queda `NULL` con
`quality_status=legacy_backfill|incomplete`. Nunca calcula IVA por tasa supuesta ni interpreta la
diferencia pago-líneas como cortesía. Las rutas futuras de ajustes/impuestos deben alimentar estos
campos antes de activar su mutación.

`ReportingProjectionService` filtra el intervalo semiabierto `[from_utc,to_utc)` y exige
`from_utc < to_utc`. Acepta sucursal, caja, turno de cobro, familia snapshot y servicio
`dine-in|takeout|delivery`. Python itera centavos enteros y IDs distintos: suma líneas coincidentes,
cuenta cada pedido una vez aunque contenga varias familias y devuelve, por indicador, `known_cents`
y `unknown_operation_count`. Los desgloses por familia y servicio reconcilian contra el filtro
aplicado; el drill-down usa exactamente los mismos filtros y un cursor estable
`confirmed_at,payment_id`, no expone PII y devuelve folio existente sólo como referencia de la
operación. La UI no usa `reduce`, `parseFloat` ni fórmulas financieras: sólo convierte filtros
locales una vez a UTC y presenta la proyección autoritativa.

La UI exige una sucursal autorizada concreta con zona IANA válida antes de construir límites locales;
no ofrece “todas las autorizadas” como una zona ambigua. El API exige datetimes con zona y los
normaliza a UTC. La lista de turnos usa `limit` inclusivo de `1..100` y cursor
`opened_at_utc|cash_shift_id`, ordenado descendentemente por esa tupla; el drill-down usa
`confirmed_at_utc|payment_id`, con timestamp con zona y UUID válidos. Ambos rechazan cursores o
límites inválidos sin devolver una página parcial. El preflight de `0038` también rechaza pago/pedido
con moneda ausente, no ISO-3 o distinta tras normalizar mayúsculas: la migración no puede crear un
snapshot de ventas con una moneda inventada. Apertura, cierre, conflictos del guard y consultas del
monitor emiten logs estructurados con `metric`, `result`, `branch_id` y, para rechazos, `error_code`,
sin clave de idempotencia, filtros, payloads ni PII.

El preflight de servicio acepta para pagos **confirmados** históricos sólo `dine-in`, `takeout`,
`delivery` y el alias legado exacto `takeaway`. Durante el backfill, una expresión determinista
proyecta únicamente `takeaway -> takeout` en `sales_operation_snapshots.service_type_snapshot`; no
actualiza `orders.order_type`, no habilita `takeaway` en comandos nuevos y conserva el constraint del
snapshot en los tres valores canónicos. Cualquier otra variante, mayúscula, espacio o tipo desconocido
falla antes de crear snapshots o cambiar las filas legacy.

El monitor canónico vive en POS `/sales-monitor`, visible y guardado sólo con
`reports.sales.read`; Administrador conserva alcance de sucursal y Dueño puede elegir cualquiera de
sus sucursales autorizadas, siempre revalidada por backend. Settings muestra estados
`loading|open|closed|submitting|error`, cierra por ID, conserva la clave ante fallo incierto y muestra
el resumen congelado y la leyenda “el corte final queda pendiente”. Un error de consulta falla
cerrado. La UI es española, navegable por teclado y contenida a 1440x900 y 1000x800. No se agregan
estación, impresión, Excel/descarga ni formato especial de nota de consumo.

La revisión `0038` desciende sólo de `0037`, crea tablas/índices y columnas compatibles, y no cambia
permisos. Debe pasar `0037 -> 0038 -> 0037 -> 0038` en SQLite y PostgreSQL aislado conservando una
huella de turnos, pagos, pedidos y líneas legacy. El downgrade elimina sólo snapshots generados por
backfill; se bloquea si existe cierre/comando PCO-004, snapshot capturado o línea con origen
`captured`. Rollback de aplicación desactiva rutas nuevas conservando historia `0038`; jamás vuelve a
habilitar el cierre legacy con contado cero.

- Un movimiento confirmado requiere turno `OPEN`, sucursal/caja canónicas, importe positivo y
  concepto efectivo vigente compatible. Es inmutable. Su corrección crea **otro** movimiento con
  `amount_cents` positivo, tipo opuesto y `compensates_movement_id`; por ejemplo, compensar un retiro
  de 3000 crea depósito de 3000. Original y compensación participan una vez con su signo natural.
  Una clave idempotente reutilizada con otro payload devuelve `idempotency_conflict`.
- El efectivo esperado se calcula exclusivamente en Python como `opening_float + SUM(signed_amount)`:
  `CASH_PAYMENT` y `DEPOSIT` tienen signo positivo; `WITHDRAWAL` tiene signo negativo. Una compra
  cash confirmada debe crear exactamente un `WITHDRAWAL` con `source_type=PURCHASE` y su documento
  como `source_id`; **no existe** el término separado `cash_purchase_withdrawals`. Compensaciones
  ya están incluidas por ser movimientos del signo opuesto. Para ejemplo: fondo 10,000 + pago cash
  5,000 + depósito 1,000 - retiro manual 2,000 - compra cash 3,000 = esperado 11,000 centavos.
  El importe contado y la diferencia son enteros de centavos; nunca `float` ni total del navegador.
- `CashShift` conserva `OPEN -> CLOSING -> OPERATIVELY_CLOSED`. El comando transaccional deja el
  cierre y resumen juntos o revierte a `OPEN` ante fallo recuperable; no persiste un resumen parcial.
  El cierre operativo no crea corte final. `UserCashCut` es `DRAFT -> COUNTED -> FINALIZED`; si
  una reapertura autorizada, sólo permite `FINALIZED -> REOPEN_REQUESTED ->
  REOPEN_APPROVED|REOPEN_REJECTED` y únicamente `REOPEN_APPROVED -> COMPENSATED`. Mientras el gate
  no estén implementadas, esas transiciones y rutas quedan fail-closed. Una operación que llegó a estar
  asociada a un corte `FINALIZED` conserva esa asociación immutable de por vida: una reapertura o
  compensación crea artefactos referenciados, pero nunca la libera ni permite asociarla a otro corte.
  La unicidad histórica sobre asociación de operación (más lock) impide solapamiento parcial aunque
  varíen inicio/fin. Las fechas se almacenan UTC; zona/día operativo y tolerancia siguen en
  la zona de sucursal; el día operativo es inicialmente 00:00–23:59 local y la tolerancia cero.
- `OrderReopenRequest` permite exactamente `REQUESTED -> APPROVED|REJECTED|EXPIRED` y sólo
  `APPROVED -> APPLIED`; `REJECTED`, `EXPIRED` y `APPLIED` son terminales. Solicitud corresponde a
  Cajero jefe o superior y autorización a Dueño. `PCO-005A` implementa consulta, creación,
  aprobación y rechazo sin mutar la historia; reserva `EXPIRED` sin TTL automático y mantiene
  `APPROVED -> APPLIED` fail-closed con `order_reopen_policy_pending`. `PCO-005B` sustituye ese gate
  sólo mediante `OrderCorrection`, conforme a `SDD-ADR-027`; edición directa de pagado, cerrado o
  producción iniciada continúa rechazada.

#### 38.2.5 PCO-005A — cuentas y workflow request-only

`GET /orders/accounts` recibe intervalo UTC consciente y semiabierto, sucursal, turno, caja, tipo de
servicio, búsqueda folio/cliente, límite `1..100` y cursor opaco. Python valida y liga el cursor al
hash de filtros y ordena por `(created_at, id)` descendente. Para pagos confirmados proyecta operación
y líneas desde los snapshots de venta; no consulta catálogo vigente ni completa faltantes. El DTO
expone elegibilidad y estado de solicitud activa, pero nunca claves de idempotencia o evidencia.

La revisión `0039_order_reopen_requests` agrega `order_reopen_requests` y
`order_reopen_commands`. La solicitud conserva organización, sucursal, pedido, versión/estado,
`before_snapshot`, motivo, referencias opacas de evidencia, solicitante, decisión y timestamps UTC.
Un índice parcial admite una sola solicitud `REQUESTED|APPROVED` por pedido. El command log conserva
tipo `request|approve|reject|apply`, hash SHA-256 canónico, respuesta estable y unicidad
`(organization_id, idempotency_key)`. Replay idéntico devuelve el mismo resultado; key/payload o
objetivo distinto falla `idempotency_conflict`.

Una solicitud sólo es necesaria cuando existe pago confirmado, estado `CLOSED` o producción fuera
de `PENDING`. Un pedido editable responde `order_reopen_not_required`; estados cancelado, rechazado,
fallido o devuelto responden `order_reopen_not_eligible`. Crear, aprobar o rechazar nunca modifica
`orders`, líneas, pagos, movimientos de inventario, tareas, cierres, cortes o snapshots. Aprobar o
rechazar compara la versión vigente con la capturada; divergencia devuelve `order_version_conflict`
y conserva `REQUESTED`. El downgrade de `0039` se bloquea cuando exista solicitud o comando; sólo
una base sin historia PCO-005A puede regresar a `0038`.

#### 38.2.6 PCO-005B — aplicación mediante corrección compensatoria

`OrderCorrection` es el agregado append-only que materializa una solicitud aprobada sin cambiar el
pedido, pago, snapshot de venta, turno, cierre o corte originales. Conserva organización, sucursal,
pedido y solicitud, versión capturada, folio de corrección, `before_snapshot`, `after_snapshot`,
moneda, total corregido, delta financiero, actor y timestamps UTC. Una solicitud admite exactamente
una corrección y sólo se marca `APPLIED` dentro de la transacción que escribe todos sus resultados.

`OrderCorrectionLine` conserva la imagen deseada y el enlace nullable a la línea original. La parte
retenida de una línea usa producto, precio, familia y consumo del snapshot original; una adición usa
producto, precio y receta vigentes como operación nueva, con snapshot nuevo. El backend nunca
consulta catálogo vigente para reconstruir la porción histórica. La proyección de cuenta devuelve
por separado original y corrección; no cambia el folio ni el total histórico original.

`OrderPaymentAdjustment` enlaza el único pago confirmado original y registra `CHARGE|REFUND`, importe
positivo, método, moneda, estado, turno actual cuando aplica y evidencia opaca. Python calcula
`corrected_total_cents - original_paid_cents`. Delta positivo crea `CHARGE`; negativo crea `REFUND`
por el valor absoluto; cero no crea ajuste y queda conciliado en la corrección. Cash exige un turno
`OPEN` actual y crea exactamente un movimiento enlazado del signo correspondiente; tarjeta débito,
crédito o transferencia exigen confirmación manual y evidencia mientras no exista adaptador. La
corrección pertenece al periodo actual; nunca mueve el pago original ni libera su asociación a corte.

`OrderProductionAdjustment` registra por línea/tarea y cantidad
`RELEASE|WASTE|RECOVERY|ADDITION`. Reducir una tarea `PENDING` cancela la tarea mediante transición y
libera sólo su reserva; cualquier tarea `IN_PROGRESS` afectada responde `production_in_progress` sin
escritura; reducir una tarea `COMPLETED` exige `waste|recovery`. `WASTE` conserva el consumo y agrega
clasificación/evidencia; `RECOVERY` agrega el movimiento positivo enlazado. Toda adición crea reserva,
snapshot de consumo y tarea `PENDING` nuevos.

`POST /orders/reopen-requests/{id}/apply` exige Dueño, `Idempotency-Key`, versión esperada, imagen de
líneas, disposiciones productivas, `register_id` y método/evidencia de liquidación cuando el delta no
es cero. `register_id` es una selección de caja, no autoridad sobre el turno: es obligatorio sólo
para delta cash y el backend deriva el único turno `OPEN` de esa sucursal/caja. El navegador no envía
actor, organización, totales, moneda, `cash_shift_id` ni IDs de movimientos. El servicio bloquea
solicitud, pedido y turno cash aplicable; revalida estado, versión, alcance, snapshot, pago,
moneda, producción y hash canónico. Corrección, líneas, ajuste financiero, movimientos, tareas,
eventos, auditoría, command log y `APPLIED` se confirman juntos. Replay idéntico devuelve la respuesta
almacenada sólo después de reautorizar; clave con otro objetivo o plan falla `idempotency_conflict`.

La siguiente revisión desde `0039` es aditiva. Agrega tablas de corrección y ajustes, checks, claves
foráneas, consulta por organización/sucursal/UTC, unicidad por solicitud y command hash. El downgrade
sólo funciona sin correcciones ni ajustes; con historia falla cerrado. PostgreSQL valida locks e
índices con `PCO005B_TEST_POSTGRES_URL` explícita y base aislada con prefijo `pco005b_`; nunca usa
`DATABASE_URL`. SQLite valida semántica de dominio/migración, no sustituye la evidencia PostgreSQL de
concurrencia.

#### 38.2.7 PCO-006 — corte final por usuario y reapertura compensatoria

`UserCashCut` materializa un corte final sin reutilizar `cash_shift_cuts`. La tupla canónica es
organización, sucursal, caja, turno, cajero responsable y periodo UTC semiabierto. El cajero
responsable no lo afirma el navegador: es el actor persistido al abrir el turno. PCO-006 agrega
`cashier_user_id` a `cash_shifts`; la apertura nueva lo captura en la misma transacción y la migración
intenta completarlo únicamente desde un comando de apertura inequívoco. Un turno legado sin una sola
fuente autoritativa queda no elegible con `cash_cut_cashier_unknown`; nunca se asigna por nombre,
correo, última venta o actor del corte.

La revisión `0041_user_cash_cuts` agrega `user_cash_cuts`, `user_cash_cut_operations`,
`user_cash_cut_commands`, `user_cash_cut_reopen_requests` y `user_cash_cut_compensations`. El corte
conserva los IDs canónicos, zona IANA, inicio/fin UTC, estado `DRAFT|COUNTED|FINALIZED`, fondo,
componentes del efectivo esperado, contado, diferencia, tolerancia, cajero, creador/finalizador,
versión y timestamps. Crear borrador y capturar contado son comandos idempotentes separados; un
borrador o conteo no reserva operaciones. Finalizar exige turno `OPERATIVELY_CLOSED`, periodo exacto
`[opened_at, closure.closed_at)`, estado `COUNTED`, tolerancia inicial cero y permiso
`cash.user_cut.create` de Líder o superior dentro de la sucursal.

Al finalizar, Python bloquea turno, cierre y corte, revalida organización/sucursal/caja/cajero y
calcula el snapshot desde el fondo del turno, pagos cash `CONFIRMED` y movimientos cash `confirmed`
del mismo turno. El navegador sólo envía alcance, contado y versión esperada; nunca esperado,
diferencia, tolerancia, operaciones, actor o estado. `difference_cents = counted_cash_cents -
expected_cash_cents` usa enteros. Cada pago y movimiento incluido crea una asociación append-only con
tipo, ID, importe firmado y timestamp snapshot. La unicidad global por organización, tipo e ID de
operación, más el lock, impide doble contabilización aun si otro corte usa un periodo distinto. Fondo
y componentes se congelan en el reporte; una fila confirmada desconocida o una operación fuera del
periodo/turno falla antes de escribir el corte.

Historial y detalle devuelven el snapshot inmutable, operaciones incluidas y estado de reapertura,
con límite `1..100`, cursor ligado a filtros y alcance revalidado. No exponen idempotency keys, hashes,
evidencia ni texto libre completo. El POS integra el flujo en la administración de caja existente:
selecciona un turno cerrado elegible, muestra cajero/caja/periodo derivados, captura sólo contado,
pide confirmación y refresca desde API. No calcula importes ni presenta éxito antes de confirmar.

Sólo Dueño puede crear una solicitud de reapertura con contado corregido, motivo y referencias opacas
de evidencia, y aprobarla o rechazarla. No se exige un actor distinto porque esa regla no fue
aprobada. Una solicitud activa por corte conserva el snapshot propuesto y transita
`REQUESTED -> APPROVED|REJECTED`; únicamente `APPROVED -> COMPENSATED`. Compensar no edita el corte
ni el ledger: crea un artefacto enlazado con contado corregido, esperado/tolerancia originales,
diferencia corregida y delta contra la diferencia original, calculados por Python. Las asociaciones
de operaciones permanecen ocupadas de por vida y el corte original continúa consultable.

Todos los comandos reautorizan antes de replay, comparan hash canónico y confirman agregado,
asociaciones, command log, auditoría y estado juntos. Un fallo inyectado después de cualquier
escritura revierte todo. Logs y métricas usan IDs técnicos, sucursal, acción, resultado y código de
error; omiten contado, diferencia individual, motivo, evidencia, clave y PII. PostgreSQL aislado usa
exclusivamente `PCO006_TEST_POSTGRES_URL` con base `pco006_*`; SQLite prueba semántica y migración, no
sustituye locks PostgreSQL. El downgrade sólo procede sin historia PCO-006; con cortes, comandos,
asociaciones, solicitudes o compensaciones falla cerrado sin borrar filas.

#### 38.2.8 PCO-007 — recetas por alcance y reportes históricos

PCO-007 completa `OPEN-016/017` sin reconstruir el monitor de ventas de PCO-004. La mutación de
receta existente deja de depender de `catalog.manage`: exige `recipes.manage`, actor autenticado y
alcance resuelto en backend. Supervisor y perfiles superiores crean una versión únicamente para una
sucursal asignada. `branch_id=NULL` significa receta corporativa y sólo se acepta cuando el actor
posee la concesión persistida `organization_all_permissions`; nunca se infiere por correo, nombre de
rol, `is_superadmin` ni permiso ordinario. Dueño puede crear versión corporativa o una excepción de
sucursal propia. La lectura administrativa devuelve la receta efectiva y su procedencia
`branch|organization`; una excepción de sucursal prevalece sólo en esa sucursal.

Crear una versión de receta exige `Idempotency-Key`, `expected_active_recipe_id`, rendimiento,
unidad y componentes estrictos. El navegador no envía versión, cantidades brutas, costos, estado,
actor u organización. Python normaliza con `Decimal`, valida unidades/componentes, bloquea producto y
receta activa, retira únicamente la versión activa del mismo alcance y crea la siguiente versión sin
reescribir historia. Un editor obsoleto falla `recipe_version_conflict`; replay idéntico reautoriza y
devuelve el resultado persistido, mientras clave con actor, producto, alcance o payload distinto
falla `idempotency_conflict`. `recipe_version_commands` conserva hash y respuesta redactada. La
auditoría registra IDs técnicos, versión y alcance; no componentes completos ni costos.

La publicación excepcional del catálogo histórico de recetas no es una migración Alembic ni corre al
arranque. Un publicador manual primero construye un dry-run desde un manifiesto JSON versionado,
sin PDF/XLS ni inferencias por nombre. Sólo acepta el baseline productivo resuelto de 307 productos
y 132 insumos activos. Las recetas `11057` y `24001..24007`, que dependen de los insumos sin costo
`001026..001028`, permanecen pendientes: el publicador no crea sus productos, precios, insumos,
recetas ni la categoría `CAFE Y MACCHA`; por ausencia de producto activo no figuran en menú ni están
disponibles para venta. Si cualquiera de esos SKU ya existe en el catálogo, falla cerrado. Su alta
posterior requiere otro paquete gobernado con presentación de compra y costo promedio autorizado.
Cada componente elegible persiste la unidad base real de su insumo, aunque el manifiesto utilice un
alias compatible. Toda receta que ya tenga historia queda preservada, incluido `06002` con sus
versiones y comandos. El publicador verifica la huella SHA-256 del manifiesto, exige actor activo con
`recipes.manage` y concesión persistida `organization_all_permissions`, confirma exactamente el
entorno, serializa por organización y registra la auditoría en la misma
transacción después de las inserciones. Un replay revalida todos los campos deterministas sin borrar,
relinkear ni editar componentes y sólo se acepta si existe la auditoría de la aplicación original.
El reporte y la auditoría fijan las listas exactas de ocho recetas y tres insumos pendientes para que
un cambio de alcance no pueda incorporarlos silenciosamente.

`ingredient_sales` toma como autoridad ventas confirmadas de `sales_operation_snapshots`, sus líneas
y `order_line_consumption_snapshots`. Cada componente congelado ya representa el total histórico de
su línea: Python suma su cantidad bruta `Decimal` sin volver a multiplicarla por la cantidad de línea,
y agrega sólo por la misma tupla
`item_id, unit_id`. La respuesta conserva nombre/código/unidad snapshot, cantidad decimal como texto,
operaciones conocidas y procedencia de receta. Una unidad ausente o dos unidades incompatibles del
mismo insumo jamás se suman: permanecen en grupos separados y aumentan
`incomplete_operation_count`; componente sin identidad, cantidad válida o snapshot produce
`historical_snapshot_missing` para esa operación y nunca se sustituye por cero ni por receta vigente.

Las ventas originales se atribuyen a `confirmed_at`. Una corrección PCO-005B se atribuye a
`applied_at` como delta de cantidades: las reducciones escalan el snapshot histórico original y las
adiciones usan el snapshot nuevo de `operational_order_line_id`. La disposición productiva
`WASTE|RECOVERY` no cambia por sí misma la cantidad vendida; su efecto pertenece al reporte de merma.
Así, consultar ambos periodos reconcilia la venta corregida sin mover ni recalcular la operación
original.

`expense_report` emite eventos documentales canónicos, no una suma ciega del ledger. Una compra
confirmada crea una fuente `purchase` en `confirmed_at` con subtotal, descuento, impuesto y total
separados; su retiro cash `PURCHASE` se enlaza pero no crea otra fila. Cancelar la compra agrega en
`cancelled_at` un evento inverso enlazado, sin borrar el original ni contar el depósito compensatorio.
Un retiro manual confirmado y no enlazado a compra/corrección constituye fuente `cash_movement`; su
compensación agrega el inverso. Depósitos ordinarios, ajustes de pedido y movimientos de inventario no
son gastos. Un movimiento sin impuesto canónico devuelve `tax_cents=NULL` y aumenta
`unknown_tax_source_count`; Python nunca infiere IVA. Totales monetarios se expresan en centavos y
derivan con `Decimal` desde la fuente persistida.

Ambos reportes aceptan periodo UTC semiabierto, `branch_id` explícita, límite `1..100` y cursor opaco
ligado a filtros. Sin `branch_id`, sólo la autoridad organizacional puede solicitar consolidado; un
perfil de sucursal debe enviar una sucursal asignada. La UI convierte una vez el día local usando la
zona IANA de la sucursal y React/TypeScript se limita a presentar DTO, advertencias y paginación. El
backend emite `ingredient_sales_projection_total` y `expense_report_request_total` con resultado,
sucursal y código de error, sin filtros completos, nombres, componentes, razones libres ni PII.

La revisión `0042_recipe_reports` parte de `0041_user_cash_cuts`, agrega
`recipe_version_commands` e índices de consulta sobre compras, movimientos y snapshots; no copia ni
recalcula historia. El downgrade elimina índices y la tabla sólo cuando no contiene comandos; con
historia de versionado falla cerrado. SQLite valida semántica/migración y PostgreSQL aislado, mediante
`PCO007_TEST_POSTGRES_URL` y una base `pco007_*`, valida locks, unicidad, planes e índices. Nunca usa
`DATABASE_URL`.

### 38.3 Componentes, contratos y errores

`CashOperationsService`, `CashMovementLedger`, `UserCashCutService`, `OrderReopenWorkflow` y
`ReportingProjectionService` viven en backend Python; POS/Admin sólo solicitan candidatos y muestran
respuesta, explicación de elegibilidad y estado de sincronización. Contratos versionados propuestos:
Toda ruta resuelve actor y alcance canónico; toda mutación lleva `Idempotency-Key` y ante error
devuelve código estable sin escritura parcial.

| Método y ruta | Permiso mínimo | Contrato / resultado |
|---|---|---|
| `GET /api/v1/cash/concepts/effective` | `cash.concept.read` | alcance canónico, tipo y fecha; sólo conceptos vigentes devueltos por backend |
| `GET /api/v1/cash/concepts` | `cash.concept.manage` | catálogo corporativo con identidad, estado e historia completa; especificado para PCO-002 |
| `POST /api/v1/cash/concepts`, `PUT /{id}/versions`, `POST /{id}/archive` | `cash.concept.manage` | mutaciones con `Idempotency-Key`, código inmutable, versionado/archivo sin borrar historia; especificado para PCO-002 |
| `POST /api/v1/cash/movements` | retiro o depósito | `Idempotency-Key`, caja/turno canónicos, tipo, `concept_id`, importe, referencia/evidencia; devuelve movimiento y esperado actualizado |
| `POST /api/v1/cash/movements/{id}/compensations` | `cash.movement.compensate` | Dueño, `Idempotency-Key`, motivo/evidencia; crea importe positivo de tipo opuesto referenciado |
| `GET /api/v1/cash/movements` | `cash.movement.read` | filtros de sucursal, caja, turno, fecha y tipo; cursor y DTO redactado sin Idempotency-Key |
| `POST /api/v1/cash/shifts/open` | `cash.shift.open` | apertura idempotente con sucursal/caja y fondo inicial en centavos; backend deriva actor/estado/fecha |
| `GET /api/v1/cash/shifts/current`, `/cash/shifts` y `/cash/shifts/{id}` | `cash.shift.read` | turno actual o último cierre; lista/detalle paginados por alcance y snapshots inmutables |
| `POST /api/v1/cash/shifts/{id}/close-operationally` | `cash.shift.close` | `Idempotency-Key`, body vacío estricto, cierre separado y resumen autoritativo; sin contado ni corte final |
| `POST /api/v1/cash-shifts/open`, `GET /cash-shifts/current|summary`, `POST /cash-shifts/close` | permiso canónico equivalente | aliases temporales fail-closed; misma autoridad/respuesta, cierre sólo sucursal/caja y rechazo explícito de contado/extras |
| `GET /api/v1/orders/accounts` y `GET /api/v1/orders/{id}` | `orders.read` | mismos filtros canónicos/cursor y el detalle existente reutilizado con snapshots, alcance y elegibilidad |
| `POST /api/v1/orders/{id}/reopen-requests` | `orders.reopen.request` | solicitud request-only idempotente de Cajero jefe+; PCO-005A captura snapshot y no muta el pedido |
| `GET /api/v1/orders/reopen-requests`, `POST /{id}/approve`, `/reject` | `orders.reopen.authorize` | consulta y decisión idempotentes de Dueño; PCO-005A compara versión y conserva historia |
| `POST /api/v1/orders/reopen-requests/{id}/apply` | `orders.reopen.authorize` | Dueño, `Idempotency-Key`, versión, líneas, compensaciones y caja seleccionada para cash; backend deriva turno y crea corrección enlazada con transición `APPROVED -> APPLIED` atómica |
| `POST /api/v1/cash/user-cuts`, `POST /{id}/counted-cash` | `cash.user_cut.create` | crea borrador/captura contado con `Idempotency-Key`, alcance UTC explícito y sin finalizar implícitamente |
| `POST /api/v1/cash/user-cuts/{id}/finalize` | `cash.user_cut.create` | finaliza idempotente, usa lock/asociaciones exclusivas y no deja corte parcial |
| `GET /api/v1/cash/user-cuts`, `GET /api/v1/cash/user-cuts/{id}` | `cash.user_cut.read` | historial/detalle con alcance, operaciones incluidas y snapshot |
| `POST /api/v1/cash/user-cuts/{id}/reopen-requests` | `cash.user_cut.reopen.request` | solicitud de Dueño, idempotente y definida para PCO-006 |
| `POST /api/v1/cash/user-cuts/reopen-requests/{id}/approve`, `/reject`, `/compensate` | `cash.user_cut.reopen.authorize` | Dueño aprueba/rechaza/compensa idempotentemente en PCO-006; compensar conserva asociaciones históricas |
| `GET /api/v1/reports/sales-monitor` y `/sales-monitor/drill-down` | `reports.sales.read` | intervalo UTC semiabierto y mismos filtros de sucursal, caja, turno de cobro, familia snapshot y servicio; conocidos/faltantes, facetas, cursor y operaciones trazables |
| `GET /api/v1/products/{id}/recipe?branch_id=...` | `recipes.manage` | receta efectiva y procedencia; sucursal explícita o corporativa sólo para autoridad organizacional |
| `PUT /api/v1/products/{id}/recipe` | `recipes.manage` | nueva versión idempotente con alcance y versión esperada; nunca edita historia ni acepta cálculos cliente |
| `GET /api/v1/reports/ingredient-sales` | `reports.ingredient_sales.read` | periodo UTC, alcance, cursor, cantidades Decimal por unidad snapshot, correcciones como delta e incompletos explícitos |
| `GET /api/v1/reports/expenses` | `reports.expenses.read` | eventos documentales canónicos, compra/retiro únicos, reversas enlazadas e impuestos separados |
| `GET /api/v1/reports/waste` | `reports.waste.read` | alcance, periodo UTC y drill-down a merma/corrección sin editar historial |

Errores estables: `actor_required`, `permission_denied`, `branch_scope_denied`,
`cash_shift_not_open`, `cash_shift_ambiguous`, `cash_concept_invalid`, `cash_reference_required`, `cash_evidence_required`,
`cash_shift_not_found`, `cash_shift_busy`, `cash_shift_counted_cash_forbidden`,
`sales_monitor_period_invalid`, `sales_monitor_filter_invalid`, `sales_monitor_cursor_invalid`,
`idempotency_conflict`, `cash_movement_already_compensated`, `cash_cut_scope_invalid`,
`cash_cut_already_finalized`, `cash_cut_in_progress`, `order_reopen_not_eligible`,
`cash_cut_cashier_unknown`, `cash_cut_shift_not_closed`, `cash_cut_period_invalid`,
`cash_cut_transition_invalid`, `cash_cut_version_conflict`, `cash_cut_operation_conflict`,
`cash_cut_reopen_active`, `cash_cut_reopen_transition_invalid`,
`order_reopen_policy_pending`, `order_reopen_transition_invalid`, `order_reopen_plan_invalid`,
`production_in_progress`, `production_disposition_required`, `payment_adjustment_invalid`,
`order_version_conflict`, `recipe_branch_required`, `recipe_corporate_scope_denied`,
`recipe_version_conflict`, `report_period_invalid`, `report_cursor_invalid` y
`historical_snapshot_missing`. Todos son
respuestas sin escritura parcial y generan auditoría de denegación para acciones sensibles.

### 38.4 Compatibilidad de permisos y límites de receta

La migración no cambia autoridad por nombre. `cash.withdraw -> cash.movement.withdraw` conserva
compatibilidad temporal explícita. `orders.amend`, actualmente concedido a Cajero, se mantiene sólo
durante la ventana aprobada y luego migra de forma mapeada a Cajero jefe; no se revoca implícitamente.
`dashboard.read` conserva dashboards heredados, mientras `reports.sales.read` y
`reports.expenses.read` son reportes nuevos y no se infieren uno del otro. `catalog.manage` conserva
catálogo corporativo; `recipes.manage` es permiso separado. Supervisor sólo puede editar una versión
de receta dentro de sucursal/alcance aprobado, nunca mutar silenciosamente receta corporativa/global;
Dueño administra la receta corporativa y la ruta queda para PCO-007.

### 38.5 Offline, seguridad, observabilidad y migración

El gateway SQLite WAL persiste comando, actor autenticado, alcance observado, idempotency key,
payload canónico, resultado local y outbox; la nube PostgreSQL revalida actor, permiso y alcance antes
de confirmar inbox. Un éxito local se marca `pending_sync`, no éxito final. Los conflictos de permiso,
turno cerrado o corte ya finalizado quedan visibles y no se compensan automáticamente.

Acciones R3: movimientos de efectivo, compras en efectivo, cancelación, reapertura, merma,
confirmación de corte y modificación de receta. Exigen actor real, auditoría append-only con antes/
después seguros, correlation/causation id, UTC y step-up cuando la política aprobada lo indique.
Logs nunca contienen contraseña, token, evidencia binaria, cliente o referencias completas. Métricas:
`cash_command_total{action,result}`, `cash_cut_difference_cents`, `cash_authorization_denied_total`,
`cash_outbox_lag_seconds`, `order_reopen_request_total` y `ingredient_sales_projection_error_total`.

La migración se secuencia después de la head integrada vigente: (1) permisos/perfiles y tabla de
mapeo reversible de roles semilla en PCO-001; (2) conceptos y ledger de movimientos sin reescribir
`CashMovement` existente; (3) cierres/cortes y solicitudes; (4) índices/proyecciones de reporte;
(5) replicación SQLite/outbox. Cada revisión PostgreSQL/SQLite debe hacer upgrade/downgrade en una
cadena única, preservar pagos, movimientos, snapshots, auditoría y roles especializados. La
alternativa de convertir automáticamente Administrador corporativo en Dueño queda **descartada**;
el mapeo individual explícito se registra y audita antes de cualquier asignación.

## 39. Remediación previa a piloto

Esta sección diseña los hallazgos de la auditoría de 2026-08-19. `SDD-ADR-028/029` permanecen
reservadas para el paquete PCO-008/008R ya aprobado y todavía no publicado en `main`; las nuevas
decisiones comienzan en 030 para evitar colisiones al trasplantar ese paquete.

### 39.1 SDD-ADR-030 Aprobada — frontera operacional default-deny y artefactos sensibles

**Estado: aprobada por el Dueño de producto el 2026-08-19 mediante la instrucción exacta
“Apruebo SDD-ADR-030, SDD-ADR-031 y los paquetes SEC-001A, OPS-WAVE-001R, MOB-ORD-001 y PCO-008P
para implementación y pruebas aisladas por Terra, con auditoría posterior de Sol”.** Se elige una frontera
default-deny para toda ruta de mantenimiento, KDS, sincronización e impresión. Una ruta no se vuelve
interna por carecer de enlace en la UI: debe declarar una clase de autenticación, capacidades
granulares y alcance. Las identidades humanas reutilizan RBAC; gateway, KDS y agente de impresión
usan credenciales de dispositivo rotables y ligadas a organización/sucursal/dispositivo. El backend
rechaza credencial ausente, inválida, revocada o de otro alcance antes de consultar replay o mutar.

`seed_menu` y `seed_branches` dejan de ser HTTP y se convierten en comandos internos idempotentes,
con confirmación explícita de entorno, dry-run, actor operacional y auditoría redactada. No se
habilita un bypass por encabezado secreto genérico ni por red privada. El retry de impresión sólo
encola un intento enlazado; `PRINTED` exige acuse autenticado del agente. KDS y sync aceptan
únicamente transiciones/comandos incluidos en su allowlist y revalidan alcance en servidor.

El repositorio sólo conserva fixtures sintéticos. CI ejecuta un inventario determinista de paths y
contenido prohibido para bases, respaldos, claves y credenciales, con allowlist versionada mínima.
Eliminar una base o backups del árbol futuro no borra copias históricas. Hacer privado el repositorio,
rotar credenciales y reescribir historia son operaciones distintas, potencialmente disruptivas y
fuera del cambio de código: cada una requiere inventario, respaldo, responsables, ventana y
autorización humana separada.

Alternativas descartadas: confiar en rutas ocultas; conservar seeds HTTP con un booleano de entorno;
usar una credencial compartida para todas las sucursales; marcar impresión como completada al pedir
retry; o declarar saneada la exposición sólo con `.gitignore`.

### 39.2 SDD-ADR-031 Aprobada — ingreso público canónico y confirmaciones veraces

**Estado: aprobada por el Dueño de producto el 2026-08-19 con la misma instrucción registrada en
SDD-ADR-030 y ampliada el 2026-08-25 mediante “Adelante con todo el plan hasta completar para merge
y push”.** La ampliación autoriza rechazo por actor con `orders.create` y alcance de sucursal,
revalidación operacional sin repricing, límites global/cliente seudonimizados y publicación GitHub;
no autoriza despliegue ni migración productiva. Se separa
`PublicOrderIntent` de `Order`. El endpoint público
`POST /api/v1/public/branches/{public_key}/order-intents` exige `Idempotency-Key`, body estricto y una
`public_key` opaca que el servidor resuelve a organización y sucursal activas. Nunca acepta
`branch_id`, precio, total, folio, actor, turno, estado, reserva ni identificadores internos como
autoridad. El hash canónico incluye versión de contrato, sucursal resuelta y payload normalizado.

Python valida cada producto/variante/modificador contra la proyección pública vigente, cantidades
enteras acotadas y texto/teléfono mínimos; calcula importes en centavos y cantidades/conversiones con
`Decimal`. Una transacción persiste intención, líneas snapshot, command result, correlation id y
auditoría técnica. Replay idéntico devuelve el mismo resultado después de revalidar la ruta pública;
misma clave con otro payload responde `idempotency_conflict`. Timeout cliente conserva la clave y
consulta `GET /api/v1/public/order-intents/{public_reference}`; nunca genera folio aleatorio.

La escritura pública usa rate limiting Redis por clave pública y señales seudonimizadas, límites de
tamaño/cantidad y métricas sin PII. Si no puede verificarse el límite o la configuración de sucursal,
la escritura falla cerrada; la lectura de catálogo puede degradar de forma independiente. Teléfono,
nombre/dirección y texto libre no forman parte de etiquetas, logs o errores. WhatsApp es una
proyección opcional posterior al commit, configurada por sucursal mediante adaptador; su falla no
convierte el pedido en rechazado ni sustituye la persistencia.

Una intención válida queda `PENDING_REVIEW`. `POST /api/v1/order-intents/{id}/accept` exige actor con
`orders.create` y alcance de sucursal, `Idempotency-Key` y versión esperada. El servicio reutiliza el
dominio canónico para crear pedido, reservar inventario, crear tareas/eventos/outbox y enlazar la
intención exactamente una vez. No crea ni selecciona `CashShift`; el turno se resuelve sólo cuando
una operación autenticada realmente cobre conforme a PCO-004. Rechazar conserva la intención y
auditoría sin crear pedido.

El frontend móvil presenta éxito únicamente con la referencia persistida y estado devuelto. En
resultado incierto mantiene carrito y clave para consultar/reintentar; en rechazo conserva los datos
editables y muestra el código traducido. React/TypeScript no calcula precios autoritativos ni
transforma errores HTTP en éxito.

Alternativas descartadas: crear directamente una orden confiando en UUID/total del navegador;
fabricar un folio cuando falle la API; abrir/reutilizar el primer turno disponible; usar WhatsApp
como fuente de verdad; o duplicar reservas y producción dentro del controlador público.

### 39.3 Componentes, estados y contratos

- `OperationalRouteGuard`: resuelve identidad humana/dispositivo, capacidad, organización y
  sucursal antes del handler; las rutas sensibles no tienen fallback anónimo. KDS humano exige el
  permiso persistido `kds.tasks.operate`; KDS dispositivo deriva organización/sucursal de la
  credencial persistida, nunca de `BRANCH_ID` ni del cliente. La credencial sólo es válida si la
  sucursal pertenece a su organización y ambas continúan activas.
- `SyncService`: el replay de comandos se particiona por organización, sucursal y dispositivo
  autenticados. La descarga de eventos remotos pendientes es por organización y sucursal porque
  el diseño offline no garantiza un único gateway por sucursal; el dispositivo autenticado aporta
  ese scope persistido, pero no filtra eventos por su autoría. Un envelope ausente, malformado o
  ajeno se deniega antes de replay, escritura o auditoría con claves foráneas no confiables.
- `PrintJobService`: el agente `print.agent` hace pull sin scope cliente de intentos `QUEUED` de
  su credencial; estados `QUEUED -> CLAIMED -> PRINTED|FAILED`. Retry sólo abre intento desde
  `FAILED`, serializa la transición y conserva un único intento activo. Todo trabajo nuevo
  crea su intento inicial `QUEUED` en la misma transacción; `PRINTED` sólo procede del acuse y
  `FAILED` conserva código técnico redactado. Un claim vencido se reconcilia explícitamente a
  `FAILED` por el mismo scope tras el lease, con causa `CLAIM_LEASE_EXPIRED`; nunca se reencola ni
  reimprime silenciosamente. El pull usa índice por organización, sucursal, estado, creación e id.
- `InternalSeedService`: valida esquema, actor, organización y el manifest completo contra una
  allowlist versionada antes de escribir. Admite `ensure_organization.v1`,
  `ensure_branch_topology.v1` y `ensure_menu_catalog.v1`; el orden obligatorio es organización,
  razón social/unidad/sucursales/almacenes y después categorías/unidades/insumos/productos/precios,
  disponibilidad y recetas. Cada entidad recibe su ID explícito del manifest y toda referencia debe
  pertenecer al mismo manifest o existir ya dentro de la organización; no se generan IDs ni datos
  aleatorios. Dinero usa centavos enteros y cantidades usan `Decimal` serializado como texto.
  `dry-run` exige una base ya migrada y sólo hace lecturas/validación; no crea DDL. `apply` es una
  transacción atómica, idempotente y reproducible por hash canónico del manifest. La auditoría de
  operación organizacional usa `branch_id = NULL` y sólo registra actor, hash e inventario de tipos,
  sin contenido del catálogo. Los entrypoints legacy quedan fail-closed; ventas/mock y cualquier
  generación no determinista quedan excluidos y las capacidades estructurales pasan únicamente por
  el comando gobernado.
- `PublicOrderIntentService`: estados `PENDING_REVIEW -> ACCEPTED|REJECTED|EXPIRED`; no hay regreso
  a pendiente ni borrado. `ACCEPTED` guarda `order_id` único. `REJECTED` exige actor con
  `orders.create`, alcance de sucursal, versión esperada, clave idempotente y motivo interno; conserva
  decisión y auditoría sin crear `Order`, pago, reserva, tarea, evento u outbox. La consulta pública
  expone estado y versión, nunca el motivo. `EXPIRED` sigue reservado: no existe TTL, scheduler ni
  comando de expiración en este incremento.
- `OrderAcceptanceService`: puerto compartido por POS/canales para snapshots, reservas, tareas,
  eventos y outbox. Conserva snapshots calculados por Python al capturar un canal; HTTP sólo valida
  frontera y delega.
- `order_outbox_events` es el handoff durable local de la transacción de aceptación. Este incremento
  no incluye un publisher ni un destino externo porque no existe contrato aprobado de consumidor;
  `published_at` permanece nulo y el éxito HTTP depende sólo del commit local. Publicar/operar ese
  consumidor será un paquete posterior con adaptador, idempotencia y observabilidad propios.
- `RepositoryPolicyGate`: lista rutas prohibidas, detecta firmas sensibles y prueba que fixtures y
  excepciones sean sintéticos; escanea también fuentes de test, encabezados PEM/OpenSSH sin
  asignación, sidecars SQLite y dumps/exportes SQL. La allowlist exige path, hash y procedencia
  exactos y el reporte nunca imprime contenido ni hashes.
- `OrderAuthorityService`: `POST /orders/quote` reutiliza exactamente el pricer Python de creación
  para precio base, modificadores y extras. Pago, producción y fulfillment son ejes separados: el
  pago conserva el estado operativo; el primer trabajo KDS inicia producción, el último completa a
  `READY`; y `start_delivery|deliver|close` transicionan mediante máquina de estados, permiso
  `orders.fulfill`, scope de sucursal, CAS, command log e idempotencia estable.

Errores nuevos: `device_actor_required`, `device_scope_denied`, `operational_route_denied`,
`print_job_transition_invalid`, `print_ack_required`, `public_branch_not_found`,
`public_order_rate_limited`, `public_order_schema_invalid`, `public_order_unavailable`,
`public_order_result_unknown`, `public_order_transition_invalid` y `repository_artifact_forbidden`.
Todos producen cero escritura parcial y observabilidad redactada.

### 39.4 Migración, despliegue y rollback

`SEC-001` usa una migración aditiva para identidad de dispositivo, permiso KDS, intentos de impresión,
constraints de ownership/estado e índice de pull. Es reversible sólo mientras no exista historia; con
historia se bloquea el downgrade, se desactiva la ruta y se conserva auditoría. `OPS-WAVE-001R`
reutiliza migraciones/contratos de cortesía, proveedor, compra
e impresión ya definidos y agrega únicamente lo que falte en la head integrada; nunca reescribe
pagos, compras o trabajos históricos. `MOB-ORD-001` crea tablas aditivas de intent, líneas y command
log desde la head vigente, con downgrade bloqueado si hay historia.
La migración `0044_audit_fulfillment` agrega permisos granulares de impresión/fulfillment, el
command log de fulfillment y las autorizaciones de ajuste pre-pedido sobre la head `0043`; no
duplica las tablas SEC ya publicadas y bloquea downgrade cuando existe historia.

El proceso web no ejecuta migraciones al arrancar. `RESTAURANTOS_AUTO_MIGRATE` queda `false` por
defecto y no forma parte de esta publicación; cualquier promoción de esquema requiere una operación
separada y autorizada. En particular, publicar 0051 en GitHub no la ejecuta en producción.

El orden de promoción es: contención de repositorio y rutas; reparación POS; pedidos públicos; luego
trasplante PCO-008/008R sobre la head resultante. Cada paquete tiene feature flag default-off cuando
introduce una ruta nueva, migración SQLite y PostgreSQL aislado, canary sintético y rollback de
aplicación anterior a cualquier downgrade. `DATABASE_URL` y datos reales quedan prohibidos en pruebas;
cada gate PostgreSQL usa su variable `*_TEST_POSTGRES_URL` y base aislada con prefijo del paquete.

## 40. Conciliación y Auditoría Gerencial Multi-Sucursal (FIX-01..FIX-07)

### 40.1 Límites de Fecha y Zona Horaria Local de Sucursal
El cálculo de reportes de conciliación diaria (`/reports/branch-reconciliation/daily`) y consolidados
multi-sucursal (`/reports/branch-reconciliation/consolidated`) calcula exactamente los límites
temporales UTC a partir del huso horario oficial de cada sucursal (`00:00:00.000000` a
`23:59:59.999999` local convertido a UTC mediante `zoneinfo.ZoneInfo`). Esto previene el solapamiento
o duplicación de transacciones entre días contiguos.

### 40.2 Persistencia de Auditoría Gerencial (`0043_reconciliation_audit_log`)
El estado de revisión gerencial y notas de auditoría se persiste en la tabla `reconciliation_audit_logs`:
- `id`: UUID primario
- `organization_id`, `branch_id`: claves foráneas
- `date`: `YYYY-MM-DD`
- `reviewed`: booleano
- `audited_by_user_id`: clave foránea a `users.id`
- `notes`: texto de observaciones del auditor
- `audited_at`, `created_at`, `updated_at`: marcas temporales UTC
- Restricción única: `uq_reconciliation_audit_logs_branch_date (branch_id, date)`

### 40.3 Autorización Reforzada Step-Up para Cortesías y Descuentos
Para aplicar cortesías y excepciones en el POS sin persistir contraseñas, el endpoint
`POST /api/v1/auth/supervisor-authorize` valida el PIN de 4-6 dígitos o contraseña del supervisor,
verifica los permisos `orders.discount.authorize` y `branch.admin.access` para la sucursal activa, y
emite una autorización segura con `supervisor_user_id` y `supervisor_name`.

## 41. Captura asistida de pedidos en POS

### 41.1 SDD-ADR-032 Aprobada — borrador local, autoridad canónica intacta

La solicitud del 2026-08-28 aprueba el paquete `POS-AI-001` para reducir la recaptura del Cajero sin
delegar decisiones comerciales a un modelo. La primera versión es un intérprete local y
determinista, desacoplado del checkout: recibe texto ya visible/editable, normaliza español de México
y produce un `AssistedOrderDraft`. No persiste la frase, no crea una entidad de dominio y no invoca
un proveedor externo. El icono se presenta junto a la sucursal en el encabezado de venta y se
identifica como **Captura asistida**, no como mesero, porque mesas y meseros siguen fuera de alcance.

El borrador contiene `customer_name`, `phone`, `order_type`, candidatos de producto por ID efectivo,
cantidad e instrucciones capturadas. La resolución es fail-closed: sólo una coincidencia inequívoca
puede quedar lista para aplicar. Ambigüedad, ausencia, producto no disponible o instrucción no
configurada quedan visibles como `unresolved`; texto parecido nunca autoriza sustituciones. La
normalización de teléfono reutiliza 10 dígitos nacionales o 12 con prefijo `52`. `para recoger` y
`para llevar` proyectan `takeout`; `a domicilio` proyecta `delivery`; la ausencia conserva el tipo de
servicio vigente en vez de adivinarlo.

Aplicar copia exclusivamente datos resueltos al estado editable de React. El nombre se propone como
titular, el teléfono dispara la búsqueda exacta existente por `phone` y `branch_id`, y sólo una
respuesta selecciona cliente automáticamente. Cero resultados abre el flujo vigente de alta; más de
uno exige elección. Las líneas usan los mismos IDs, comentarios `preset_instruction`, modificadores y
extras del carrito. Si una línea requiere cardinalidades aún no resueltas, se abre la personalización
normal y no se agrega silenciosamente.

La cotización y `POST /orders` no aceptan el texto natural ni confían en importes derivados por el
intérprete. Continúan calculando en Python, validando permiso `orders.create`, sucursal, caja,
disponibilidad, snapshots e idempotencia. Cerrar o descartar el modal no cambia carrito, cliente,
tipo de servicio ni checkout. La captura por voz es una mejora progresiva: se muestra cuando la API
`SpeechRecognition` del navegador está disponible, inicia sólo por acción del Cajero y queda sujeta al
permiso de micrófono del navegador. Puede usar servicios de su fabricante, no OpenRouter. Si la API no
existe o el permiso se deniega, el campo de texto y el resto del POS permanecen operables; no existe
una variable de build o runtime necesaria para habilitar este control.

### 41.2 Frontera de extensión futura

`AssistedOrderInterpreter` es una función/puerto puro con entrada acotada y salida estructurada. Una
implementación futura basada en modelo debe vivir detrás de un adaptador de servidor y jamás dentro
del bundle web con secretos. Ese paquete deberá decidir proveedor, residencia/retención de datos,
consentimiento, redacción de PII, presupuesto, circuit breaker, evaluación contra corpus sintético y
fallback determinista. Ninguna respuesta externa podrá contener autoridad de precio, inventario,
cliente, sucursal o pedido; siempre se reconciliará contra proyecciones canónicas antes de mostrarse.

### 41.3 Despliegue y reversibilidad

`POS-AI-001` no agrega tabla, migración, permiso ni escritura. Se despliega como frontend POS y puede
revertirse retirando el control y el intérprete sin afectar pedidos existentes. El dictado se expone
sólo cuando existe capacidad del navegador, sin bandera runtime/build; el texto manual es el fallback obligatorio. No se autoriza
despliegue productivo en este paquete de implementación.

El dictado conserva una solicitud lógica durante 3000 ms desde su último resultado no vacío. Un timer
independiente detiene reconocimiento y reinicios al vencer; `onend` sólo reinicia antes de ese plazo.
Detener, cerrar el modal, error permanente o excepción al iniciar cancelan ambos timers sin borrar la
captura escrita. Cada sesión reemplaza únicamente su propio resultado acumulativo sobre una base de
texto manual, evitando duplicados entre resultados interim o reinicios técnicos.

### 41.4 SDD-ADR-033 Aprobada — OpenRouter redactado con guardas canónicas

La evolución `POS-AI-002` sustituye el intérprete léxico como fuente de candidatos por un adaptador
OpenRouter alojado exclusivamente en la API. El navegador envía la frase al backend autenticado con
`branch_id`; el backend extrae nombre y teléfono, los reemplaza antes de la frontera externa y envía
al modelo sólo texto redactado y una lista acotada de IDs/nombres del catálogo efectivo. La clave se
lee de `RESTAURANTOS_OPENROUTER_API_KEY`, nunca de una variable `VITE_*`.

El adaptador usa `POST /api/v1/chat/completions`, `response_format=json_schema` estricto y
`provider.require_parameters=true`. Su salida únicamente propone `product_id` y cantidad. El servicio
rechaza IDs ajenos, cantidades fuera de 1..99, productos inactivos/no disponibles, JSON inválido,
timeout y errores del proveedor. No acepta precios, clientes, modificadores libres ni comandos.

Después de resolver un producto, Python carga `list_product_modifiers` para la sucursal, reconoce sólo
opciones cuyos nombres efectivos aparecen en el texto redactado y calcula de manera determinista las
cardinalidades. Por cada grupo cuyo `minimum_selections` no esté satisfecho devuelve una pregunta con
sus `option_id` válidos. El POS puede seleccionar esas opciones, respetando `maximum_selections`, pero
no habilita **Agregar al pedido** hasta satisfacer todos los mínimos. La aplicación sólo modifica el
estado editable del carrito y dispara la búsqueda telefónica vigente; cotización y checkout conservan
su autoridad.

El endpoint no persiste conversaciones y los logs sólo pueden incluir resultado, modelo, latencia,
sucursal y código de error sin frase, nombre, teléfono ni payload del proveedor. La integración queda
apagada si falta la clave. Reversión: retirar las variables o volver a la versión anterior; no requiere
migración ni altera pedidos históricos. El fallback operativo es la captura manual normal del POS, no
una interpretación local permisiva.

## 42. POS-UX-003 — catálogo progresivo y modificadores por pestaña

`POS-UX-003` es una composición exclusiva de estado transitorio del frontend. El helper puro
`progressiveCatalogStage` recibe si existe una categoría concreta, si su selector previo ya es válido
y si hay un producto con modificadores abierto; devuelve `categories`, `selection`, `products` o
`modifiers`. No crea IDs de catálogo, no calcula precios ni altera disponibilidad, carrito, pedido o
las cardinalidades canónicas recibidas desde la API.

La barra `TODO/ALIMENTOS/BEBIDAS/OTROS/FAVORITOS` se mantiene visible y es el único reinicio global
del flujo: limpia categoría, valor previo y personalización transitoria mediante la transición POS
existente, preservando carrito y búsqueda. FAVORITOS inicia explícitamente en `products` sin una
categoría activa; los demás grupos inician en `categories`. Cada etapa posterior muestra un resumen compacto de las
decisiones anteriores con controles explícitos para cambiar o regresar. La región central sólo
renderiza el contenido de la etapa actual; por tanto no presenta categorías, productos y
complementos en paralelo. Loading, error, vacío y Reintentar siguen usando los estados de proyección
existentes y permanecen accesibles con `role=status` o `role=alert`.

Al abrir modificadores, el primer grupo disponible queda activo. Todos los grupos se renderizan como
pestañas grandes persistentes y sólo el grupo activo expone sus opciones. La pestaña comunica
`Obligatorio`/`Opcional`, `minimum_selections` y `maximum_selections` ya recibidos; no crea una nueva
obligatoriedad. La selección sigue pasando por `toggleModifier`, que conserva los máximos y la
exclusión ya existente para variaciones de ingredientes. `modifierSelectionsMeetMinimums` sólo
controla el estado disabled y el mensaje de Agregar: `confirmModifiers` mantiene su validación
defensiva. Tras agregar se limpia sólo la personalización y vuelve a `products` para la misma
categoría/valor; los productos sin grupos siguen entrando directamente al carrito.

## 43. AIA-001 — asistente administrativo de conocimiento y configuración

El asistente vive exclusivamente en `apps/admin-web` y su disparador sustituye el botón decorativo
`FileText` del encabezado por `UserRound`; el avatar conserva su autoridad de perfil. La UI envía
consultas a `/api/v1/admin-ai/proposals`. Una respuesta de conocimiento queda `DRAFT`; sólo una
salida de proveedor que supere el contrato backend puede quedar `READY_FOR_REVIEW`.

`AdminAiService` separa cuatro autoridades:

1. `CanonicalKnowledge`: allowlist versionada de reglas y referencias PRD/SDD para organización,
   catálogo, pedidos, recetas, inventario, caja, permisos, auditoría y operación.
2. `AdminAiProvider`: adaptador backend opcional, deshabilitado por defecto, con JSON Schema estricto,
   temperatura cero, timeout finito y transporte inyectable para pruebas sin red.
3. `ProposalValidator`: normaliza una única acción allowlist, comprueba evidencia textual para cada
   valor material, IDs/ownership/estado, fuentes conocidas y construye snapshot actual, propuesta,
   advertencias, ruta de revisión y fingerprint del contexto.
4. `ProposalApplier`: en aceptación vuelve a autenticar, exige el permiso canónico de la acción,
   bloquea/relee la propuesta, verifica estado, expiración, fingerprint e idempotencia y delega a
   `create_product`, `update_product`, `create_inventory_item`, `create_modifier_group`,
   `create_modifier_option` o `update_product_recipe_versioned`. El modelo nunca recibe un puerto de
   escritura ni controla commits.

La propuesta contiene una sola acción para que la transacción del servicio canónico siga siendo la
unidad atómica; configuraciones compuestas se expresan como una secuencia explícita de propuestas.
Estados: `DRAFT -> READY_FOR_REVIEW -> APPLIED|REJECTED|EXPIRED`. No hay regreso a un estado anterior.
Replay de la misma aceptación devuelve el resultado persistido; otra clave falla. Un fingerprint
distinto produce `admin_ai_proposal_stale` y cero escritura. Rechazo y expiración son terminales.

Persistencia aditiva `admin_ai_proposals`: organización, sucursal opcional, proponente, estado,
fingerprint, payload validado sin prompt/transcript, expiración, revisor, clave idempotente, resultado
y timestamps terminales. La auditoría registra creación de respuesta/propuesta, rechazo y aplicación
con tipo de acción y fuentes, sin prompt, secreto ni contenido completo. El downgrade se bloquea si
existe historia.

El contexto externo se limita a reglas allowlist y proyecciones mínimas de catálogo: IDs, nombres,
SKU/estado/versiones, grupos, unidades e insumos con su estado. Se excluyen tablas de clientes, usuarios,
roles, pedidos, pagos, caja, compras, producción, inventario físico y auditoría. Una respuesta local
cuando el proveedor está apagado puede orientar con fuentes canónicas, pero conserva `DRAFT`, un
warning explícito y un `change_set` vacío.

Errores explícitos: `admin_ai_disabled`, `admin_ai_provider_unavailable`,
`admin_ai_provider_invalid_response`, `admin_ai_prompt_invalid`, `admin_ai_source_unknown`,
`admin_ai_change_set_invalid`, `admin_ai_evidence_missing`, `admin_ai_reference_invalid`,
`admin_ai_proposal_not_found`, `admin_ai_proposal_not_ready`, `admin_ai_proposal_expired`,
`admin_ai_proposal_stale` e `idempotency_conflict`. Todos fallan antes de una escritura de dominio.

La liberación ejecuta concurrencia y migración en una base PostgreSQL aislada `aia001_*`; el test no
lee `DATABASE_URL`. Los eventos `admin_ai_proposal` y `admin_ai_review` registran resultado, IDs
técnicos, modo de proveedor, decisión, estado, tipo de acción o código de error, pero omiten prompt,
transcript, secreto e idempotency key. El despliegue entra con el flag apagado; habilitación de
staging, credencial y canary son acciones operativas separadas. Ante proveedor inestable o conflicto
inesperado se apaga el flag sin revertir la migración ni borrar historia.
