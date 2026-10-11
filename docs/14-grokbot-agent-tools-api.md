# Kiwi Agent Tools API v1 RC1 — Guía de integración para GrokBot

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

El contrato es una **candidata v1 (`1.0.0-rc.1`)** y el runtime permanece `Scaffold`, apagado por
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
       -> herramienta Administrador: contexto, productos y ventas agregadas
       -> herramienta Cocinero: productos, insumos y recetas
       -> herramienta Inventarios: insumos, existencias y propuestas de insumo
       -> herramienta Compras: insumos, proveedores, necesidades y borradores de compra
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
| `administrator` | contexto, catálogo, ventas agregadas y propuestas de catálogo |
| `kitchen` | contexto, catálogo, insumos, recetas y propuestas de receta |
| `inventory` | contexto, insumos, recetas, existencias y propuestas de insumo |
| `purchasing` | contexto, insumos, proveedores, necesidades y borradores de compra |

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
| `GET /api/v1/agent-tools/inventory/items` | Insumos administrativos minimizados |
| `GET /api/v1/agent-tools/inventory/stock` | Existencia resumida de una sucursal |
| `GET /api/v1/agent-tools/recipes` | Recetas efectivas y componentes permitidos |
| `GET /api/v1/agent-tools/suppliers` | Proveedores habilitados sin contactos personales |
| `GET /api/v1/agent-tools/purchase-needs` | Necesidades de compra calculadas por Kiwi |
| `GET /api/v1/agent-tools/operations/{operation_id}` | Estado autoritativo de una operación propia |

Las colecciones aceptan `limit` de 1 a 100 y `cursor`. Para solicitar la siguiente página se debe
enviar exactamente el `next_cursor` recibido; el cursor no debe interpretarse ni modificarse.

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

## 7. Reglas que debe seguir el Administrador Kiwi

1. Consultar `context` antes de elegir sucursal o herramienta; usar la zona IANA devuelta para
   convertir expresiones como “hoy” al intervalo UTC correcto.
2. Pedir aclaración cuando el usuario no indique sucursal y tenga más de una autorizada.
3. Usar Administrador para productos y ventas; Cocinero para recetas; Inventarios para existencias;
   Compras para proveedores, necesidades y borradores.
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
9. Activar los demás especialistas uno a uno; dejar las escrituras para un canary posterior.

La migración, configuración de secretos, activación, despliegue y canary son gates independientes.
El contrato OpenAPI no autoriza ninguno de ellos por sí mismo.

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
