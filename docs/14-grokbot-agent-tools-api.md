<!-- SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-grokbot-agent-tools-doc-v1 -->
# Kiwi Agent Tools API v1 RC4 — Guía de integración para GrokBot

## 1. Objetivo

Kiwi expone una API REST versionada para que un único **Administrador Kiwi** visible en GrokBot
coordine cuatro especialistas privados: Administrador, Cocinero, Inventarios y Compras. GrokBot no
accede a PostgreSQL ni reutiliza sesiones humanas. Cada herramienta se autentica con la identidad
técnica del especialista que la ejecuta y Kiwi vuelve a validar capacidades y sucursales en cada
solicitud.

Contrato importable:

`packages/contracts/openapi/kiwi-agent-tools-v1.openapi.yaml`

URL base de producción:

`https://<HOST-KIWI>`

Todas las solicitudes deben usar HTTPS. Los secretos de los ejemplos son ficticios.

### Estado de esta entrega

El contrato es una **candidata v1 (`1.0.0-rc.4`)** y el runtime permanece `Scaffold`, apagado por
defecto y sin despliegue productivo verificado. Está listo para que GrokBot prepare sus herramientas
y para ejecutar, después de la autorización operativa correspondiente, un canary de sólo lectura con
Administrador. No debe presentarse todavía como integración productiva general.

Los callbacks salientes no forman parte de RC1: GrokBot debe consultar
`GET /api/v1/agent-tools/operations/{operation_id}`. La entrega automática firmada, sus reintentos,
protección SSRF/DNS y el ciclo `Drenando`/`Pausado` siguen siendo gates de una versión posterior. Las
escrituras mediadas existen para pruebas controladas, pero no deben habilitarse en el primer canary.

## 2. Topología recomendada en GrokBot

```text
Usuario
  -> Administrador Kiwi (única conversación visible)
       -> herramienta Administrador: contexto, productos, ventas agregadas y cortes finalizados
       -> herramienta Cocinero: productos, insumos y recetas
       -> herramienta Inventarios: insumos, existencias y propuestas de insumo
       -> herramienta Compras: insumos, proveedores, costos, historial, necesidades y borradores
```

No debe existir una credencial maestra. Cada herramienta conserva su propio `client_id` y
`client_secret`. El perfil, organización, capacidades y sucursales nunca se aceptan desde el prompt
ni desde el cuerpo enviado por GrokBot.

## 3. Autenticación

Cada identidad intercambia sus credenciales por un bearer token de cinco minutos:

```bash
curl --request POST 'https://<HOST-KIWI>/api/v1/agent-auth/token' \
  --user '<CLIENT_ID>:<CLIENT_SECRET>' \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data 'grant_type=client_credentials'
```

Respuesta:

```json
{
  "access_token": "<TOKEN-CORTO>",
  "token_type": "Bearer",
  "expires_in": 300
}
```

GrokBot debe mantener el secreto fuera de prompts, logs y base de conocimiento. Puede conservar el
token sólo durante su vigencia y solicitar otro al vencer; no debe reintentar indefinidamente una
credencial revocada.

## 4. Capacidades por identidad

| Identidad | Capacidades máximas de v1 |
|---|---|
| `administrator` | contexto, catálogo, ventas agregadas, cortes finalizados con permiso explícito y propuestas de catálogo |
| `kitchen` | contexto, catálogo, insumos, recetas y propuestas de receta |
| `inventory` | contexto, insumos, recetas, existencias, movimientos y propuestas de insumo |
| `purchasing` | contexto, insumos, proveedores, costos actuales, historial de compras, necesidades y borradores |

La configuración de Kiwi puede reducir esas capacidades y limitar cada identidad a una o más
sucursales. Una respuesta `403 agent_capability_denied` o `agent_branch_denied` es definitiva para
esa solicitud: el bot no debe intentar otra ruta para evadirla.

## 5. Operaciones disponibles

### Lecturas

| Método y ruta | Uso |
|---|---|
| `GET /api/v1/agent-tools/context` | Identidad, capacidades y sucursales efectivas |
| `GET /api/v1/agent-tools/catalog/items` | Productos, categoría, estación, precio y disponibilidad |
| `GET /api/v1/agent-tools/sales/summary` | Ventas confirmadas agregadas por sucursal y periodo UTC |
| `GET /api/v1/agent-tools/cash/cuts` | Cortes finalizados minimizados por sucursal y periodo UTC |
| `GET /api/v1/agent-tools/inventory/items` | Insumos administrativos minimizados |
| `GET /api/v1/agent-tools/inventory/stock` | Existencia y umbrales mínimo/máximo de una sucursal |
| `GET /api/v1/agent-tools/inventory/movements` | Movimientos minimizados de una sucursal y periodo UTC |
| `GET /api/v1/agent-tools/recipes` | Recetas efectivas y componentes permitidos |
| `GET /api/v1/agent-tools/suppliers` | Proveedores habilitados sin contactos personales |
| `GET /api/v1/agent-tools/purchase-presentations` | Presentaciones y costos vigentes por proveedor |
| `GET /api/v1/agent-tools/purchases/history` | Historial confirmado de compras y costos por sucursal |
| `GET /api/v1/agent-tools/purchase-needs` | Necesidades de compra calculadas por Kiwi |
| `GET /api/v1/agent-tools/operations/{operation_id}` | Estado autoritativo de una operación propia |

Las colecciones aceptan `limit` y `cursor`; el máximo general es 100 y los historiales de compras y
cortes se limitan a 25 registros por página. Para solicitar la siguiente página se debe enviar exactamente el
`next_cursor` recibido y no debe interpretarse ni modificarse. El cursor del historial está firmado
y ligado a sucursal y periodo.
Los movimientos exigen además `branch_id`, `from_utc` inclusivo y `to_utc` exclusivo; el periodo
debe ser positivo y no exceder 31 días.

### Umbrales por insumo

`GET /api/v1/agent-tools/inventory/stock?branch_id=<UUID>` usa `agent.inventory.read`, disponible
para la identidad técnica `inventory` según su allowlist vigente. Cada fila añade `min_quantity`
y `max_quantity` del almacén activo de esa sucursal; son cadenas decimales exactas en la misma
unidad base `unit_id` que `available_quantity`. Por ejemplo:

```json
{
  "item_id": "018f6f73-2d0a-74f0-8f1c-000000000311",
  "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",
  "available_quantity": "3.000000",
  "min_quantity": "5.000000",
  "max_quantity": "20.000000",
  "as_of": "2026-10-27T12:00:00Z"
}
```

Sin configuración, ambos campos son `null`; cero sí es un umbral configurado. El listado conserva
insumos sin stock o sin umbral. `as_of` fecha la existencia, no la edición del umbral. No existe un
`par_quantity` adicional. Para listar configurados, filtrar `min_quantity != null` y recorrer todas
las páginas. Relacionar `item_id` con `inventory/items` para obtener nombre y SKU. Si no hay almacén
activo, la API responde `503 dependency_unavailable`; no debe interpretarse como stock cero.
La lectura no permite crear ni modificar umbrales, existencias o movimientos.

### Escrituras mediadas

| Método y ruta | Resultado permitido |
|---|---|
| `POST /api/v1/agent-tools/proposals/catalog` | Propuesta de producto para revisión humana |
| `POST /api/v1/agent-tools/proposals/inventory-items` | Propuesta de insumo para revisión humana |
| `POST /api/v1/agent-tools/proposals/recipes` | Propuesta de versión de receta para revisión humana |
| `POST /api/v1/agent-tools/purchase-drafts` | Compra en estado `DRAFT` |

No existen rutas para aplicar propuestas, confirmar o recibir compras, pagar, mover inventario,
operar caja o administrar usuarios. Esas decisiones permanecen en Kiwi y requieren una persona
autenticada.

Todo `POST` exige un `Idempotency-Key` único de 8 a 180 caracteres. Ante timeout, GrokBot debe
repetir el mismo cuerpo con la misma clave o consultar el `operation_id`; nunca debe anunciar éxito
sin estado canónico.

## 6. Ejemplos de consulta

Primero se confirma el contexto efectivo:

```bash
curl 'https://<HOST-KIWI>/api/v1/agent-tools/context' \
  --header 'Authorization: Bearer <TOKEN>'
```

Productos efectivos de una sucursal:

```bash
curl --get 'https://<HOST-KIWI>/api/v1/agent-tools/catalog/items' \
  --header 'Authorization: Bearer <TOKEN-ADMINISTRATOR>' \
  --data-urlencode 'branch_id=<BRANCH_UUID>' \
  --data-urlencode 'limit=20'
```

Cada producto indica `sku`, `name`, `category_name`, `station`, `price_cents`, `currency`,
`available`, `sellable`, `active` y `version`. Los importes monetarios están en centavos enteros;
`12500` representa `$125.00`.

Ventas confirmadas de un día, con límite de diez productos por moneda:

```bash
curl --get 'https://<HOST-KIWI>/api/v1/agent-tools/sales/summary' \
  --header 'Authorization: Bearer <TOKEN-ADMINISTRATOR>' \
  --data-urlencode 'branch_id=<BRANCH_UUID>' \
  --data-urlencode 'from_utc=2026-10-10T06:00:00Z' \
  --data-urlencode 'to_utc=2026-10-11T06:00:00Z' \
  --data-urlencode 'top_limit=10'
```

El periodo es `[from_utc, to_utc)`, debe incluir zona horaria y no puede exceder 31 días. La
respuesta usa snapshots inmutables de ventas confirmadas, separa correcciones posteriores y agrupa
por moneda. No incluye folios, pedidos, pagos, caja, método de pago, clientes ni personal.

Movimientos de inventario de una sucursal:

```bash
curl --get 'https://<HOST-KIWI>/api/v1/agent-tools/inventory/movements' \
  --header 'Authorization: Bearer <TOKEN-INVENTORY>' \
  --data-urlencode 'branch_id=<BRANCH_UUID>' \
  --data-urlencode 'from_utc=2026-10-10T06:00:00Z' \
  --data-urlencode 'to_utc=2026-10-11T06:00:00Z' \
  --data-urlencode 'limit=50'
```

La respuesta ordena por fecha efectiva descendente y sólo incluye `id`, `item_id`, `warehouse_id`,
`movement_type`, `quantity_delta`, `unit_id`, `effective_at` y `status`. No devuelve costos,
documentos, referencias, motivos, notas, actores, origen interno, claves de idempotencia ni datos de
otra sucursal. Para continuar se reenvía el `next_cursor` sin modificarlo.

Costos actuales de las presentaciones habilitadas para una sucursal:

```bash
curl --get 'https://<HOST-KIWI>/api/v1/agent-tools/purchase-presentations' \
  --header 'Authorization: Bearer <TOKEN-PURCHASING>' \
  --data-urlencode 'branch_id=<BRANCH_UUID>' \
  --data-urlencode 'limit=50'
```

La respuesta usa decimales exactos en texto e incluye `last_net_price`, `cost_per_base_unit`,
`currency`, rendimiento, impuesto y unidades. Sólo la identidad `purchasing` con la capacidad
`agent.purchases.read` puede consultar estos campos.

Historial confirmado de compras y costos:

```bash
curl --get 'https://<HOST-KIWI>/api/v1/agent-tools/purchases/history' \
  --header 'Authorization: Bearer <TOKEN-PURCHASING>' \
  --data-urlencode 'branch_id=<BRANCH_UUID>' \
  --data-urlencode 'from_utc=2026-10-01T06:00:00Z' \
  --data-urlencode 'to_utc=2026-10-11T06:00:00Z' \
  --data-urlencode 'limit=25'
```

El periodo es `[from_utc, to_utc)`, con zona horaria y máximo de 31 días. Sólo aparecen documentos
`confirmed` o `cancelled` que fueron confirmados dentro del periodo, junto con sus partidas y costos.
No se exponen folio, forma de pago, caja, evidencia, notas, actores ni claves de idempotencia. Como
el documento histórico todavía no guarda una instantánea de moneda, `currency_source` vale
`current_supplier`: GrokBot debe decir que la moneda procede de la configuración actual del
proveedor y no presentarla como dato histórico inmutable.
El nombre de la presentación procede del snapshot de la compra cuando está disponible; los campos
`supplier_name_source`, `item_name_source` y `presentation_name_source` indican expresamente cuándo
un nombre procede de la configuración vigente.

Cortes de caja finalizados:

```bash
curl --get 'https://<HOST-KIWI>/api/v1/agent-tools/cash/cuts' \
  --header 'Authorization: Bearer <TOKEN-ADMINISTRATOR>' \
  --data-urlencode 'branch_id=<BRANCH_UUID>' \
  --data-urlencode 'from_utc=2026-10-01T06:00:00Z' \
  --data-urlencode 'to_utc=2026-10-11T06:00:00Z' \
  --data-urlencode 'limit=25'
```

Sólo la identidad `administrator` con `agent.cash_cuts.read` puede usar esta ruta. Kiwi devuelve
cortes `FINALIZED` cuyo inicio cae en `[from_utc, to_utc)`, con apertura, pagos en efectivo,
depósitos, retiros, efectivo esperado, contado y diferencia como enteros en centavos. Si hubo una
compensación autorizada, los valores contado/diferencia son los efectivos más recientes y
`compensated=true`. No se exponen cajero, creadores, autorizadores, operaciones, reaperturas,
motivos ni evidencia. La ruta no permite abrir, contar, finalizar, reabrir ni compensar caja.
Si dos compensaciones comparten el timestamp máximo, Kiwi responde `503 dependency_unavailable`
para evitar escoger una corrección ambigua; GrokBot no debe fabricar un resultado.

## 7. Reglas que debe seguir el Administrador Kiwi

1. Consultar `context` antes de elegir sucursal o herramienta; usar la zona IANA devuelta para
   convertir expresiones como “hoy” al intervalo UTC correcto.
2. Pedir aclaración cuando el usuario no indique sucursal y tenga más de una autorizada.
3. Usar Administrador para productos, ventas y cortes; Cocinero para recetas; Inventarios para existencias
   y movimientos; Compras para proveedores, costos, historial, necesidades y borradores.
4. No transferir tokens entre especialistas ni enviar `profile` o capacidades en un body.
5. Explicar que una propuesta o compra `DRAFT` todavía no está aplicada.
6. No inferir cero cuando Kiwi reporte datos incompletos o importes desconocidos.
7. No inventar resultados ante `401`, `403`, `409`, `429`, `503` o timeout.

## 8. Errores estables

| HTTP | Código | Acción del cliente |
|---|---|---|
| 400 | `agent_schema_invalid` | Corregir parámetros o body; no repetir sin cambios |
| 401 | `agent_unauthorized` | Renovar token una vez; después escalar credencial |
| 403 | `agent_disabled` | Detener y solicitar habilitación humana |
| 403 | `agent_capability_denied` | No intentar otra identidad salvo delegación allowlist |
| 403 | `agent_branch_denied` | Solicitar una sucursal permitida |
| 404 | `operation_not_found` | No afirmar éxito ni existencia |
| 409 | `idempotency_conflict` | Generar una clave nueva sólo para una intención nueva |
| 409 | `stale_reference` | Volver a leer y solicitar revisión humana |
| 413 | `agent_schema_invalid` | Reducir el body a menos de 64 KiB |
| 429 | `rate_limited` | Respetar `Retry-After` |
| 503 | `dependency_unavailable` | Reintento acotado; estado incierto no equivale a éxito |

## 9. Checklist de canary

1. Aplicar la migración autorizada antes de habilitar los flags.
2. Activar inicialmente una sola sucursal y únicamente la identidad Administrador.
3. Guardar el secreto mostrado una vez en el gestor seguro de GrokBot.
4. Validar `context` y comparar capacidades/sucursal con el panel Kiwi.
5. Consultar cinco productos y verificar manualmente SKU, precio y disponibilidad.
6. Consultar un periodo de ventas conocido y comparar totales con Ventas y Reportes.
7. Intentar otra sucursal y confirmar el rechazo `agent_branch_denied`.
8. Intentar ventas con Cocinero y confirmar `agent_capability_denied`.
9. Confirmar que Inventarios conserva `agent.inventory.read` y el alcance correcto de sucursales;
   Cocina y Compras deben recibir `agent_capability_denied` al intentar consultar movimientos.
10. Activar los demás especialistas uno a uno; dejar las escrituras para un canary posterior.
11. En Especialistas técnicos → Compras, habilitar explícitamente **Permitir leer costos e historial
    de compras**. Confirmar después que `context` contiene `agent.purchases.read`, comparar un costo
    vigente y un documento confirmado con Compras y Gastos, y verificar que otra sucursal responda
    `agent_branch_denied`. El redeploy no amplía por sí solo una política existente.
12. En Especialistas técnicos → Administrador, habilitar explícitamente **Permitir leer cortes de
    caja finalizados**. Solicitar un token nuevo, confirmar que `context` contiene
    `agent.cash_cuts.read`, comparar un corte finalizado y verificar el rechazo de otra sucursal.
    El redeploy no concede esta capacidad a una identidad ya configurada.

La migración, configuración de secretos, activación, despliegue y canary son gates independientes.
El contrato OpenAPI no autoriza ninguno de ellos por sí mismo.

Antes de habilitar estas lecturas en producción se debe confirmar en `pg_index` que existen con
`indisvalid=true` los índices `ix_inventory_movements_org_branch_effective_id`,
`ix_agent_purchase_history_org_branch_confirmed_id`, `ix_agent_purchase_lines_document_id` e
`ix_agent_cash_cut_compensations_org_cut_created_id`. Si una
interrupción deja alguno inválido o una creación concurrente parcial, se pausa el rollout, se elimina
fuera de una transacción con `DROP INDEX CONCURRENTLY IF EXISTS <índice>` y se reintenta la migración.
No se activa Agent Tools hasta completar esa verificación.

### Configuración requerida por Kiwi

Build argument no secreto usado al compilar Admin:

```text
VITE_GROKBOT_AGENT_TOOLS_ENABLED=true
```

Variables runtime del backend:

```text
RESTAURANTOS_GROKBOT_AGENT_TOOLS_ENABLED=true
RESTAURANTOS_REDIS_URL=redis://<HOST>:6379/0
RESTAURANTOS_GROKBOT_AGENT_RATE_LIMIT_HMAC_SECRET=<SECRETO-ALEATORIO-DE-32+-CARACTERES>
RESTAURANTOS_GROKBOT_AGENT_GLOBAL_RATE_LIMIT_PER_MINUTE=600
RESTAURANTOS_GROKBOT_AGENT_IDENTITY_RATE_LIMIT_PER_MINUTE=120
```

En producción Kiwi no inicia Agent Tools si falta Redis o el secreto dedicado del limitador. El flag
`VITE_...` se evalúa al compilar Admin; cambiarlo exige reconstruir el frontend. No se debe pegar el
secreto HMAC ni los `client_secret` en el repositorio, en esta guía o en prompts.

La emisión de tokens y las herramientas usan buckets Redis separados: intentos Basic inválidos se
limitan por señal de red y nunca por el `client_id` declarado; las herramientas autenticadas se
limitan por identidad firmada. Kiwi registra cada solicitud aceptada o denegada con ruta normalizada,
sucursal válida, resultado y duración, sin conservar Authorization, secretos o cuerpos.
