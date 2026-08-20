# Plan Sol — remediación previa a piloto

Fecha: 2026-08-19. Riesgo: R3. Estado: ADR-030/031 y los cuatro paquetes aprobados para
implementación/pruebas aisladas por Terra y auditoría Sol; publicación, infraestructura, historia Git
y datos reales conservan autorización separada.

## 1. Resultado buscado

Cerrar los huecos críticos detectados en `main` sin rehacer módulos sanos ni mezclar autoridades:

- repositorio y rutas operacionales dejan de exponer datos/capacidades;
- cortesía, proveedores, compras y reimpresión cumplen sus especificaciones reales;
- mobile-web deja de inventar éxito y entra por un canal canónico idempotente;
- PCO-008/008R se reconstruye sobre la head vigente y se publica con su evidencia preservada.

El plan no declara corregido ningún hallazgo. Produce autoridad documental y cuatro handoffs que sólo
pueden ejecutarse tras aprobar ADR-030/031 y los paquetes correspondientes.

## 2. Baseline y fuente de verdad

- Base remota auditada: `main` en `248c1a0` (PR #45 integrada).
- PCO-008/008R: implementación local no publicada, basada en una head anterior y con conflicto de
  integración conocido; sirve como evidencia y fuente quirúrgica, no como commit listo para merge.
- La matriz corrige FR-205/206/207 de `Implementado` a `Scaffold` hasta pruebas conductuales.
- `SDD-ADR-028/029`, `BDD-SC-343..354` y `TDD-TC-129..140` quedan reservados para PCO-008P.
- IDs nuevos asignados determinísticamente: FR-221..224, NFR-026..028, ADR-030..031,
  BDD-FEAT-081..083, BDD-SC-355..376, TDD-TS-089..092, TDD-TC-141..158 y CONS-024..032.

Antes de cualquier trabajo Terra debe volver a verificar remote/head, worktree limpio, archivos
ajenos, migrations head y documentos. Un cambio posterior en `main` invalida sólo el baseline de
integración, no las reglas aprobadas; Sol decide si requiere replanificación.

## 3. Orden y dependencias

```text
ADR-030 aprobada ──> SEC-001A código/CI ──> SEC-001B contención externa autorizada
                          │
                          └──> OPS-WAVE-001R ──┐
ADR-031 aprobada ─────────────> MOB-ORD-001 ───┼──> PCO-008P ──> auditoría final de piloto
                                               ┘
```

`SEC-001A` precede a todo porque reduce exposición y define guards reutilizados. `SEC-001B` puede
coordinarse después de preparar inventario, pero el repositorio no puede considerarse saneado hasta
cerrarla. `OPS-WAVE-001R` y `MOB-ORD-001` comparten la regla de resultado autoritativo, pero se
integran uno por uno para aislar regresiones. PCO-008P va al final porque su diff toca frontera sync y
debe adaptarse a los guards ya vigentes.

## 4. Paquetes y tareas atómicas

### 4.1 SEC-001 — contención de seguridad

Autoridad: FR-221/222, NFR-006/026/027, ADR-030, SC-355..360, TS-089/TC-141..145.

1. Registrar RED para el inventario exacto de rutas anónimas y archivos prohibidos, sin imprimir
   contenido sensible.
2. Crear `OperationalRouteGuard` y credencial de dispositivo mínima, sin cambiar RBAC humano.
3. Retirar seeds del router y exponer comando interno idempotente con dry-run/auditoría.
4. Proteger KDS, sync, list/retry/ack de impresión por capacidad y scope; mantener allowlists.
5. Separar estado de trabajo e intento de impresión; retry nunca escribe `PRINTED`.
6. Agregar policy gate CI y `.gitignore`; retirar artefactos tracked del árbol futuro sin borrar ni
   reescribir historia en este paso.
7. GREEN SQLite/API/contratos/CI; PostgreSQL aislado sólo si se agrega persistencia de dispositivo.
8. Sol audita diff, rutas, logs y evidencia. Terra corrige sólo hallazgos materiales.
9. `SEC-001B`, bajo autorización distinta: cambiar visibilidad, inventariar exposición, rotar lo que
   corresponda y decidir historia. Verificar clones/branches/releases y documentar residual.

Salida: ninguna ruta listada acepta anonimato; CI bloquea artefactos; repo actual aún se etiqueta
“pendiente de saneamiento histórico” hasta SEC-001B.

### 4.2 OPS-WAVE-001R — reparación POS

Autoridad: FR-205..207/222, NFR-019/021/027, SC-361..367, TS-090/TC-146..151 y especificaciones
históricas 218..229/060..062.

1. RED de cortesía real: step-up, token, ajuste, pago exacto, denegaciones y fallo atómico.
2. Implementar servicio Python/contratos; TypeScript elimina PIN local y sólo presenta DTO.
3. RED de proveedor por `suppliers.create`/`purchase_presentations.create`, branch y atomicidad.
4. Reparar DTO/servicio transaccional para proveedor+contacto+términos y presentación Decimal.
5. RED de compra de dos líneas, scope Supervisor/Cajero, idempotencia y cancelación completa.
6. Reparar cálculo/recepciones/costo/retiro/compensaciones en Python sin reescribir historia.
7. Conectar Reimprimir a `PrintJobService`; estados de UI Encolado/resultado incierto/error.
8. GREEN focal backend/frontend, migración requerida, QA visual y CI; actualizar matriz a
   `Implementado` sólo por capacidad realmente verde.
9. Auditoría Sol independiente e iteración acotada.

Salida: UI y backend concilian total, permisos y estados; no quedan mensajes de éxito simulados.

### 4.3 MOB-ORD-001 — pedidos públicos gobernados

Autoridad: FR-223/224, NFR-027/028, ADR-031, SC-368..376, TS-091/TC-152..157.

1. RED de schema, public key, campos de autoridad, cálculo Python, idempotencia y rate limit.
2. Migración aditiva `public_order_intents`, líneas y command log desde la head integrada; downgrade
   vacío y bloqueo con historia.
3. Implementar `PublicOrderIntentService` y endpoints create/status; Redis fail-closed para write.
4. Extraer/reutilizar `OrderAcceptanceService` sin alterar el comportamiento POS existente.
5. Implementar accept/reject autenticado, lock/version/idempotencia y prueba concurrente PostgreSQL.
6. Corregir mobile-web: misma key durante incertidumbre, no random folio, no clear ante error, total
   del servidor y estados accesibles.
7. Sustituir número fijo por configuración/adaptador; evento post-commit y reintento independiente.
8. Integrar build/tests mobile a CI y QA 360x800/390x844.
9. Sol audita PII, caja, snapshots/reservas/tareas/eventos/outbox y rollback.

Salida: toda confirmación pública es recuperable y trazable; ninguna captura crea turno/pago.

### 4.4 PCO-008P — trasplante y publicación

Autoridad: ADR-028/029 aprobadas, SC-343..354, TC-129..140 y TS-092/TC-158.

1. Crear branch/worktree nuevo desde la head posterior a los tres paquetes; no reutilizar el detached
   worktree como destino.
2. Inventariar allowlist exacta de archivos y hashes del paquete local; importar primero docs/tests.
3. Ejecutar RED para confirmar ausencia del runtime PCO-008 en la nueva head.
4. Reconstruir por componente, no aplicar el diff completo a ciegas; resolver `api.py` y cualquier
   conflicto semántico contra los guards de SEC-001.
5. Mantener allowlist de comandos exactamente `cash.movement.create.v1`; no incorporar pedidos,
   pagos, compras, correcciones, cortes, KDS o impresión.
6. Ejecutar TC-129..140, migración 0043 desde la head real, PostgreSQL aislado, SQLite, package edge,
   safe join/stop, WinSW/installer, typecheck/build/QA.
7. Ampliar CI con edge y `PCO008_TEST_POSTGRES_URL`; ejecutar TC-141..157 de regresión.
8. Sol audita diff vs fuente local y vs head, verifica que el runner termine y registra residual de
   rollout Windows.
9. Sólo con aprobación: commit/PR/CI/merge/push; deploy/migración/rollout de sucursal siguen gates
   separados.

Salida: PCO-008 existe en GitHub/CI con historia documental completa, no sólo en un worktree local.

## 5. Flujo mínimo suficiente por paquete

1. Sol entrega handoff aprobado y branch/base exactos.
2. Terra ejecuta RED focal y guarda comando/salida.
3. Terra aplica migración/implementación mínima y GREEN focal.
4. Terra ejecuta gates obligatorios una vez; no repite suite completa sin diagnóstico.
5. Sol revisa diff y reejecuta pruebas de mayor riesgo de forma independiente.
6. Si hay hallazgo material, Sol entrega lista concreta y Terra itera en la misma tarea.
7. Con auditoría verde, se solicita autorización única para commit/PR/merge/push del paquete.
8. Deploy, migración productiva, canary, historia Git y rotación conservan autorización independiente.

No se exige reporte duplicado por cada micro-paso. Una sola evidencia Terra y una sola auditoría Sol
por iteración bastan; se abre nueva iteración sólo si cambia código o falla un gate material.

## 6. Gates comunes y definición de terminado

| Gate | Evidencia exigida | No sustituye |
|---|---|---|
| Documental | PRD/SDD/BDD/TDD/matriz/ADR aprobada e IDs únicos | Código o conversación |
| RED | Fallo conductual por ausencia/defecto objetivo | Búsqueda de strings |
| Backend | Unit/integration/contract, negativos, idempotencia y fallos inyectados | UI oculta |
| Datos | Migración reversible vacía, bloqueo con historia, PostgreSQL/SQLite aislados | `DATABASE_URL` |
| Cálculo | Oráculo Python `int`/`Decimal`, bordes y propiedades deterministas | Fórmula JS |
| Frontend | Tests de interacción, typecheck, build y estados inciertos | Build sin comportamiento |
| Visual | Tamaños/estados definidos y sesión real cuando aplique | Captura de pantalla única |
| CI | Apps/paquetes afectados y suite completa una vez en PR | CI de commit anterior |
| Operación | métricas/logs/errores redactados, rollback y canary sintético | Health solamente |
| Auditoría | revisión Sol del diff + reejecución focal | Autorreporte Terra |

Un paquete R3 no está terminado con skips no explicados, PostgreSQL omitido, migración sin rollback,
QA visual requerida no ejecutada, CI incompleta o matriz adelantada. Puede estar “implementado local,
pendiente de gate”, pero no `Implementado`/`Probado` como cierre.

## 7. Riesgos y rollback

| Riesgo | Control | Rollback |
|---|---|---|
| Romper agentes existentes al autenticar | inventario de clientes, flag default-off y canary por dispositivo | volver aplicación compatible conservando credenciales/auditoría |
| Reescritura Git destruye referencias | SEC-001B separada, backup y ventana | restaurar remote protegido; rotación no se revierte |
| Cortesía/purchase alteran dinero o inventario | Python, locks, idempotencia, compensaciones, PostgreSQL | desactivar rutas; no editar historia; compensar operación canary |
| Pedido público duplica o reserva dos veces | intent+command log+unique order link+lock | apagar flag; conservar intents; no bajar esquema con historia |
| PCO-008 reabre rutas anónimas o amplía comandos | integración después de SEC, allowlist exacta y regresión TC-158 | revertir app/servicio; conservar outbox y reconciliar pendientes |

## 8. Auditoría final antes del piloto

Después de los cuatro paquetes, Sol debe comparar GitHub `main`, CI, deployment y esquema real como
capas separadas; ejecutar flujo Cajero/Supervisor/Dueño, cortesía, compra/cancelación, reimpresión,
pedido público/aceptación y movimiento offline; revisar métricas/logs y confirmar cero PII/secreto.
Respaldos productivos se configuran antes del lanzamiento como ya acordado, pero el piloto no inicia
sin restore drill, owners, RPO/RTO y canary/rollback documentados.

## 9. Autorización registrada y límites pendientes

El Dueño de producto aprobó el 2026-08-19, mediante la instrucción exacta:

> Apruebo SDD-ADR-030, SDD-ADR-031 y los paquetes SEC-001A, OPS-WAVE-001R, MOB-ORD-001 y PCO-008P
> para implementación y pruebas aisladas por Terra, con auditoría posterior de Sol.

La aprobación habilita edición y pruebas aisladas Terra, seguidas por auditoría Sol. No incluye
SEC-001B, commit, push, PR, merge, deploy, migración productiva, historia Git, cambio de visibilidad,
rotación ni datos reales.
