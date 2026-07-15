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

La pantalla corporativa muestra un textarea amplio arriba y, debajo, búsqueda de productos,
selección múltiple, filtro por categoría, “Seleccionar resultados”, chips removibles y conteo de
destinos. `POST /api/v1/catalog/order-comments/bulk/preview` sólo calcula el preview y
`POST /api/v1/catalog/order-comments/bulk` crea o reactiva comentarios y agrega relaciones sin
retirar relaciones no incluidas. `GET /api/v1/catalog/order-comments` lista el catálogo global y
`PUT /api/v1/catalog/order-comments/{id}/products` reemplaza el conjunto de productos sólo después
de mostrar el impacto. Crear, editar, archivar o relacionar exige `catalog.manage`; no existe
`branch_id` ni override local en ninguno de estos contratos. Supervisor y Cajero sólo leen y usan.

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

Las relaciones `ingredient_variation_products` se conservan para pedidos e historial antiguos, pero
no autorizan ni limitan ventas nuevas. Si las asignaciones antiguas de un adicional discrepan en
cantidad, precio o estación, la migración lo deja `needs_review`; no elige valores arbitrariamente ni
lo publica al POS. El administrador resuelve el conflicto y lo activa.

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

### 34.3 POS-ORD-002 — retiro de carrito y enmienda de pedidos no pagados

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

Historial abre todas las filas. Las no editables muestran detalle y motivo del bloqueo. Las editables
ofrecen **Editar pedido**, navegan al POS en modo edición con banner y folio, y usan el endpoint de
enmienda en lugar de crear otro pedido. Guardar no confirma un pago automáticamente.

### 34.4 POS-SEC-001 — ajuste de cortesía con autorización reforzada

El “subtotal” editable es una proyección visual, no un campo contable libre. El subtotal de líneas se
conserva y las cortesías se modelan en `order_total_adjustments`, append-only: pedido, secuencia,
subtotal calculado, total anterior, delta negativo, total resultante, justificación, solicitante,
Supervisor autorizador, autorización, timestamp y eventual reversa referenciada. `orders.total_cents`
es la proyección cobrable vigente; nunca se modifica un pago confirmado.

Sólo se permiten reducciones entre cero y el subtotal calculado. Para aumentar el cobro se agrega un
producto o ingrediente adicional. La justificación es obligatoria, se recorta y admite de 10 a 240
caracteres. Cada nuevo objetivo crea otro ajuste; no sobrescribe el anterior.

El permiso `orders.adjust_total` pertenece a Supervisor de sucursal y Administrador, nunca a Cajero.
El Cajero puede solicitar la acción, pero debe seleccionar a un Supervisor elegible de la sucursal y
éste captura su contraseña. `POST /api/v1/auth/supervisor-authorizations` verifica credenciales y
alcance y devuelve un token opaco, hasheado en almacenamiento, de un solo uso, con expiración máxima
de dos minutos y limitado a `order.adjust_total`, pedido y sucursal. La contraseña no se guarda, no
se registra y se borra del estado del navegador al cerrar el diálogo. Los intentos fallidos se
limitan y registran sin distinguir “usuario” de “contraseña”.

`POST /api/v1/orders/{order_id}/adjustments` exige `Idempotency-Key`, token reforzado, nuevo subtotal
y justificación. Consumir, reutilizar, expirar o cambiar el recurso del token falla de forma atómica.
El backend crea eventos `ORDER_TOTAL_ADJUSTED` y auditoría con importes e IDs, nunca credenciales.
El pago posterior debe coincidir con la proyección resultante.

El modal del POS muestra subtotal de líneas, ajustes previos, nuevo subtotal, diferencia, justificación,
selector de Supervisor y contraseña. Tras confirmar, el carrito presenta por separado “Subtotal de
productos”, “Cortesías” y “Total a pagar”.

### 34.5 PUR-OPS-001 — proveedores y compras desde la sucursal

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

### 34.6 Migraciones, permisos, observabilidad y orden de entrega

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
cantidad, precio, estación u orden queda `needs_review`, sin elegir un valor. El downgrade elimina
solamente las tablas y campos de `0028`; nunca borra pedidos, pagos, movimientos, snapshots,
`modifier_groups`, `modifier_options`, `branch_modifier_options` ni
`ingredient_variation_products`.

Los nuevos permisos son `orders.amend`,
`orders.adjust_total`, `suppliers.create` y `purchase_presentations.create`; Administrador recibe
todos, Supervisor recibe los cuatro con alcance operativo, Cajero recibe únicamente `orders.amend`.

Los comandos emiten logs estructurados y métricas por resultado para alta masiva de comentarios,
configuración de adicionales, enmiendas, ajustes, reautenticación, proveedores y compras. Logs y
auditoría nunca incluyen contraseñas, tokens completos, RFC, teléfonos ni payloads personales.
