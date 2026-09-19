# TDD — pedidos offline ORD-OFF-001

## TDD-TS-113 Dominio y transporte de pedidos offline

Pruebas dirigidas de contexto determinista, catálogo congelado, autorización y unidad de trabajo;
integración real de SQLite gateway y PostgreSQL central, sin simular el cálculo del dominio.
PCO-008 conserva sus pruebas cash y ningún tipo nuevo entra en ese contrato por fallback.

### TDD-TC-249 Atomicidad e identidades

Crear con UUIDv7/folio deterministas en SQLite y PostgreSQL y comparar pedido, líneas, tareas,
snapshots y movimientos. Inyectar fallo tras dominio y antes de outbox/inbox/checkpoint: cero
escrituras parciales. Dos cajas y dos workers compiten: un ganador por intención. El replay con
payload distinto rechaza y el idéntico devuelve resultado original. Sesión online conserva contrato.

### TDD-TC-250 Catálogo autoritativo y combos

Bundle inmutable scope correcto; cambiar precio/receta/composición central y reconciliar contra
bundle original. Probar producto local ajeno, unidades/costos exactos, extras/comentarios, combo
multidestación y componentes de igual nombre. Rechazar hash/schema/firma alterados; no aceptar
filas/saldos/precios del payload cliente. Inventario deriva de movimientos y snapshots.

### TDD-TC-251 Ciclo operacional y autoridad

Crear/aceptar POS una vez, preparar, pagar, entregar, editar/cancelar con sus guardas actuales.
Permisos mínimos diferenciados; grant caducado, actor ajeno/revocado, binding dispositivo/sucursal,
turno cerrado y pago concurrente. Autorización técnica nunca reemplaza actor humano. No cambios
productivos para probar; sólo fixtures reproducibles y credenciales sintéticas.

### TDD-TC-252 Causalidad, pérdida de confirmación y recuperación

Caída antes/después de commit; reinicio con SYNCING; ack perdido; secuencia fuera de orden;
conflicto de un pedido no bloquea otros; replay estable tras cambios mutables. Resultado e inbox
se confirman atómicamente. Un conflicto conserva evidencia sin compensación automática.
Fecha de aceptación futura: cero efectos/inbox; el mismo sobre se acepta al alcanzar el reloj
central su fecha firmada. La primera adquisición de lease se serializa con escritores online
aunque todavía no exista fila de lease. Un command distinto que reutiliza intención de creación
no puede confirmar un aggregate inexistente.

### TDD-TC-253 POS/KDS e impresión offline

Navegador real con cloud desconectada, gateway disponible, recursos precargados y grant vigente:
recargar, crear, preparar y cobrar; visualización textual de pendiente/conflicto/confirmado.
Timeout de escritura nunca provoca fallback central ni clave nueva. Impresión usa identidad
local y confirmación de agente, no confunde queued con printed. Typecheck, semántica y build.

### TDD-TC-254 Instalación y frontera local

Instalar paquete gateway con dependencia Python interna en entorno aislado. SQLite WAL y FK
activas, rutas privadas y recuperación después de reinicio. Loopback sigue por defecto; LAN
requiere TLS/config explícitos, origen exacto y grants. No cachear API autenticada/secretos mediante
service worker. Pruebas PostgreSQL sólo en bases locales con prefijo de prueba guardado.

### TDD-TC-255 Cierre y devolución de autoridad

El fence usa la organización persistida de la sucursal, incluso fuera de la organización
predeterminada: sin lease conserva la operación y con lease ACTIVE la bloquea.
Lease activo o caducado bloquea cierre canónico y alias; cero cierres parciales. La devolución
prueba congelación durable, completitud de comandos y recibos confirmados. ACK perdido y reinicio
no reabren aceptación local. Serializar cierre/adquisición por sucursal y preservar idempotencia.

### TDD-TC-256 Renovación y recuperación durable

Dos conexiones/procesos compiten con freeze: cero aceptación posterior al watermark. Manifest
incompleto, alterado, ajeno o con conflicto no libera autoridad. ACK perdido conserva FROZEN y
replay estable. Recovery incrementa epoch, conserva evidencia anterior y rechaza grants viejos.
Renovar con pedido abierto conserva precio/snapshots/pago/outbox; crash antes/después de publicar
catálogo recupera un único bundle activo. Inyectar fallo de fsync/publicación: la operación
permanece REFRESHING hasta completar la recuperación. Al omitir un actor o rol del seed nuevo,
sus enlaces de autorización desaparecen y sus referencias históricas permanecen. Namespaces
cash y order permanecen independientes.

Auditoría Sol independiente y CI aplicable al final; TDD-TC-248/BDD-SC-501 sólo se acreditan con
el recorrido local→central real y conservación de snapshots, no por soportar ambos dialectos.
