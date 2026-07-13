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

Los pedidos creados por POS se aceptan solo si el actor tiene `orders.create`, tiene alcance sobre la sucursal solicitada y existe un turno abierto para la caja. El total persistido por el backend es la fuente de verdad para el cobro.

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

### 5.11 Delivery
Zonas, direcciones, repartidores, rutas, asignaciones y liquidación.

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
- ejecución en `pull_request` y en `push` a `main`.
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
