# TDD — remediación previa a piloto

**Estado:** estrategia R3 aprobada el 2026-08-19; toda implementación inicia con RED observable y
termina con auditoría independiente de Sol.
**Regla aritmética:** centavos `int` y cantidades/conversiones `Decimal` en Python. TypeScript sólo
valida interacción y presenta DTO autoritativo.

## TDD-TS-089 Frontera operacional, impresión y política de repositorio

Pruebas de contrato/API:

- parametrizar cada ruta sensible sin token, con token inválido, revocado, de capacidad distinta y
  de otra sucursal; todas fallan antes del servicio;
- comprobar que las rutas HTTP de seed no existen y el comando interno valida/dry-run/aplica/replay;
- KDS y sync aceptan exclusivamente comandos de su allowlist e identidad de dispositivo;
- list/retry/ack de impresión separan actor humano y agente; retry no puede escribir `PRINTED`;
- el mismo retry devuelve el intento persistido; payload distinto con la clave falla conflicto;
- fallos inyectados antes/después de enqueue o ack no dejan transición parcial.

Pruebas de repositorio/CI:

- enumeración determinista por path, extensión, tamaño y firma sensible, sin leer/mostrar valores en
  el reporte;
- fixture permitido debe estar en allowlist mínima y pasar validación sintética;
- base, backup, clave o patrón sensible introducidos intencionalmente hacen fallar CI;
- `.gitignore` sin retirar un archivo tracked no satisface el gate;
- comprobar que el workflow cubre pull request y rama protegida, sin credenciales en artifacts.

### TDD-TC-141 Denegación uniforme de rutas operacionales

Given la tabla completa de rutas de BDD-SC-355 y cero autoridad
When cada ruta se invoca con un payload válido
Then todas responden 401/403 estable y sus tablas conservan las mismas huellas y conteos.

### TDD-TC-142 Seed interno idempotente sin superficie HTTP

Given una base aislada vacía y un actor operacional explícito
When dry-run, apply y replay usan el mismo manifest
Then sólo apply crea el snapshot esperado una vez y el router no contiene endpoints seed.

### TDD-TC-143 Scope y capacidad de dispositivo

Given credenciales independientes para impresión, KDS y gateway en dos sucursales
When se cruzan capacidad, sucursal, organización, revocación y replay
Then sólo la combinación exacta opera y toda denegación deja cero efecto.

### TDD-TC-144 Máquina de estado de impresión

Given un trabajo FAILED
When retry idempotente, claim, ack alterado y ack válido se ejecutan
Then transita FAILED a QUEUED a CLAIMED a PRINTED sólo por el ack válido y conserva cada intento.
También cubre pull por scope persistido, CLAIMED a FAILED con rollback/replay y rechazo de retry
con clave nueva mientras exista intento activo.

### TDD-TC-145 Gate sensible no filtra el secreto detectado

Given fixtures temporales con base, backup, clave simulada y fixture sintético permitido
When se ejecuta el scanner en dos órdenes de filesystem
Then produce el mismo conjunto ordenado de clases/paths, falla por los tres prohibidos y nunca
incluye su contenido.

## TDD-TS-090 Cortesía, proveedores, compras y reimpresión autoritativas

Pruebas backend/dominio:

- reautenticación real de Supervisor, token hasheado de un uso/TTL/acción/pedido/sucursal y rate
  limit; no aceptar PIN local;
- subtotal, ajuste y total derivados en Python, pago por total exacto y rollback de ajuste/evento;
- `suppliers.create` y `purchase_presentations.create` separados de `catalog.manage`;
- alta atómica de proveedor, contacto y términos; duplicidad y branch ajena sin filas parciales;
- compra de al menos dos líneas con `Decimal`, idempotencia, recepciones, costo promedio, retiro cash
  y cancelación compensatoria completa;
- reimpresión crea trabajo real, auditado y no presenta `PRINTED` antes del agente.

Pruebas frontend/E2E:

- Cajero, Supervisor y actor de otra sucursal ejercen casos positivos y negativos reales;
- el modal de cortesía limpia credencial, no calcula el total y no cambia UI ante error;
- proveedor recién creado conserva términos y presentación; compra renderiza dos líneas;
- reimpresión muestra Encolado/referencia, resultado incierto y error sin éxito falso;
- typecheck/build y QA visual 1440x900 y 1000x800 para vacío, carga, datos, denegación y error.

### TDD-TC-146 Cortesía backend y pago reconciliado

Given subtotal 15000, autorización válida y total solicitado 12000
When se aplica y se confirma pago
Then Python persiste ajuste -3000 y pago 12000; token inválido/reusado deja total 15000.

### TDD-TC-147 UI no acepta PIN simulado ni diverge del backend

Given el modal abierto y una cadena local de cuatro caracteres
When la API rechaza o queda incierta
Then no cambia subtotal/total, conserva la venta y no emite mensaje de éxito.

### TDD-TC-148 Proveedor y términos atómicos por permiso específico

Given Supervisor con suppliers.create sin catalog.manage
When crea proveedor, contacto y términos, y se inyecta fallo en cada escritura
Then el caso normal confirma todo y cada fallo o actor Cajero/branch ajena confirma nada.

### TDD-TC-149 Presentación y compra de dos líneas exactas

Given dos presentaciones con conversiones Decimal y pago cash
When se confirma dos veces con la misma clave
Then totales, cantidades base y costo promedio coinciden con el oráculo Python y existen dos
recepciones, un documento y un retiro.

### TDD-TC-150 Cancelación compensa compra completa

Given la compra de TDD-TC-149 confirmada
When se cancela y se repite el comando
Then cada recepción tiene una reversa, el retiro una compensación y nada original se edita o duplica.

### TDD-TC-151 Reimpresión real con resultado incierto

Given un pedido imprimible
When el POS reintenta tras timeout con la misma clave
Then existe un solo intento consultable y la UI no muestra Impreso hasta ack válido.

## TDD-TS-091 Ingreso y aceptación de pedido público

Pruebas frontera/dominio:

- JSON Schema estricto, límites, clave pública activa, rechazo de UUID/total/precio/turno/actor;
- precios y totales desde catálogo vigente en Python; entradas aleatorias se contrastan contra un
  oráculo Python con centavos enteros y `Decimal`, incluyendo límites y redondeo explícito;
- command log por clave/hash, replay estable, conflicto y recuperación tras timeout;
- rate limiter Redis y fallback fail-closed de escritura; logs/métricas sin PII;
- persistencia de intent no toca `cash_shifts`, `payments`, reservas ni tareas;
- aceptación autenticada llama al servicio canónico y crea exactamente un pedido/reserva/tareas/
  eventos/outbox; carrera accept/accept produce un solo resultado;
- WhatsApp se sustituye por fake adapter y nunca condiciona commit ni usa número hardcodeado.

Pruebas mobile-web/E2E:

- build y script de tests entran a CI;
- éxito real limpia carrito; 4xx, 5xx, timeout y respuesta inválida conservan carrito/clave;
- estado incierto consulta referencia y no fabrica folio;
- QA visual móvil 360x800 y 390x844: catálogo, carrito, enviando, pendiente, error y reintento.

### TDD-TC-152 Sucursal y total sólo desde backend

Given catálogo público conocido y payload con branch_id/precio/total manipulados
When se envía por una public_key válida
Then campos extra se rechazan; sin ellos Python deriva sucursal y total exactos.

### TDD-TC-153 Persistencia idempotente y recuperación de timeout

Given una clave nueva y un fallo de respuesta después del commit
When el cliente consulta y reintenta con la misma clave
Then recupera una sola referencia PENDING_REVIEW y no duplica líneas ni command result.

### TDD-TC-154 Frontend conserva carrito ante cualquier no-éxito

Given un carrito no vacío
When fetch rechaza, expira, devuelve 4xx/5xx o JSON inválido
Then carrito y clave permanecen, no hay folio aleatorio y el usuario puede consultar/reintentar.

### TDD-TC-155 Esquema, límites, rate y redacción

Given casos inválidos de BDD-SC-372 y datos personales marcadores
When se procesan en paralelo
Then todos fallan sin filas parciales y ninguna salida de log/métrica contiene los marcadores.

### TDD-TC-156 Captura pública no toca caja ni producción

Given cero turnos abiertos y uno cerrado histórico
When se persiste una intención
Then huellas y conteos de turnos/pagos/reservas/tareas no cambian y el intent no referencia turno.

### TDD-TC-157 Aceptación canónica concurrente

Given una intención PENDING_REVIEW
When dos actores autorizados intentan aceptarla concurrentemente con claves distintas
Then PostgreSQL produce un pedido enlazado, una reserva por componente y un conjunto de tareas/outbox;
el perdedor recupera resultado o conflicto sin efecto parcial.

## TDD-TS-092 Integración y publicación de PCO-008/008R

PCO-008P importa primero ADR-028/029, `BDD-SC-343..354` y `TDD-TC-129..140` desde el worktree
aprobado. Después reconstruye quirúrgicamente su diff sobre la head vigente; no aplica a ciegas el
archivo en conflicto ni amplía la allowlist `cash.movement.create.v1`.

### TDD-TC-158 Trasplante PCO-008 sin regresión de remediaciones

Given la head con SEC-001, OPS-WAVE-001R y MOB-ORD-001 verdes
When se integra PCO-008/008R y se ejecutan sus suites SQLite/PostgreSQL/gateway/Windows
Then TDD-TC-129..140 y TDD-TC-141..157 permanecen verdes, CI incluye edge-gateway y ninguna ruta
operacional vuelve a quedar anónima.

## Gates y evidencia mínima

1. Guardar salida RED focal antes de runtime; un test de texto no sustituye comportamiento.
2. GREEN focal de dominio/API/contrato/frontend por paquete.
3. Migración `head -> nueva -> head -> nueva` en SQLite y PostgreSQL aislado cuando aplique.
4. PostgreSQL usa sólo `SEC001_TEST_POSTGRES_URL`, `OPSWAVE001R_TEST_POSTGRES_URL`,
   `MOBORD001_TEST_POSTGRES_URL` o `PCO008_TEST_POSTGRES_URL`, con base de prefijo equivalente;
   SEC-001 omite visiblemente si falta y rechaza antes de conectar una URL que no sea PostgreSQL
   con base `sec001_*`.
   ausencia se reporta omitida, nunca verde. Prohibido `DATABASE_URL`.
5. Ruff, typecheck/build de cada app cambiada, pruebas mobile y edge explícitas en CI.
6. QA visual autenticada/pública según paquete, arquitectura/trazabilidad y `git diff --check`.
7. Suite completa una vez en CI del PR; localmente focales y diagnóstico proporcional.
8. Terra entrega evidencia exacta y Sol reejecuta una selección independiente; R3 no cierra por
   avance parcial, skips no explicados o sólo CI histórica.
