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

## 5. Módulos de dominio

### 5.1 Identity and Access
Usuarios, roles, permisos, sesiones, dispositivos y auditoría.

### 5.2 Organization
Organización, razones sociales, sucursales, almacenes y ubicaciones.

### 5.3 Catalog
Productos, variantes, combos, modificadores, precios, horarios y mapeos externos.

### 5.4 Orders
Pedidos, líneas, eventos, estados, pagos previstos y cancelaciones.

### 5.5 Production
Tareas por estación, KDS, tiempos, incidencias y finalización.

### 5.6 Cash
Turnos, movimientos, arqueos, cortes, reaperturas y depósitos.

### 5.7 Inventory
Artículos, unidades, conversiones, lotes, movimientos, reservas y conteos.

### 5.8 Recipes and Costing
Recetas, versiones, subrecetas, explosión, costo estándar y promedio.

### 5.9 Batch Production
Órdenes, consumo de lotes, rendimiento, merma y lote resultante.

### 5.10 Purchasing
Proveedores, recepciones, XML, equivalencias, cuentas por pagar y pagos.

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
