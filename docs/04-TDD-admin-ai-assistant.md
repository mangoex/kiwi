# AIA-001 — estrategia de pruebas

## TDD-TS-099 — frontera, lifecycle y autoridad del asistente Admin

### TDD-TC-194 — contrato y transporte del proveedor

Verifica esquema estricto, contexto mínimo, fuentes allowlist, temperatura cero, timeout y redacción
de PII antes del transporte.

### TDD-TC-195 — validación desconfiada

Verifica evidencia humana e IDs existentes; invención, multiacción y fuente desconocida fallan.

### TDD-TC-196 — propuesta sin escritura anticipada

Verifica que una propuesta válida quede READY_FOR_REVIEW sin alterar entidades canónicas.

### TDD-TC-197 — aplicación por servicios canónicos

Verifica que producto, insumo, modificador y receta deleguen en permisos y servicios existentes.

### TDD-TC-198 — idempotencia y obsolescencia

Verifica que un replay idéntico devuelva el resultado y que otra clave o un fingerprint stale fallen
sin escrituras parciales.

### TDD-TC-199 — terminalidad y autorización

Verifica que rechazo, expiración y actor no autorizado sean terminales o fallen cerrados.

### TDD-TC-200 — migración protegida

Verifica roundtrip vacío de la migración 0055 y downgrade bloqueado cuando existe historia.

### TDD-TC-201 — semántica del administrador

Verifica UserRound, diálogo Admin, deep link, comparación actual/propuesto y aceptación explícita.

### TDD-TC-202 — gates estáticos y de empaquetado

Verifica TypeScript estricto, build Admin, Ruff focal, trazabilidad y `git diff --check`.

### TDD-TC-203 — locking y migración PostgreSQL aislados

Con `AIA001_TEST_POSTGRES_URL` apuntando exclusivamente a una base local `aia001_*`, verifica que
dos aceptaciones concurrentes con la misma clave apliquen una sola vez, claves distintas produzcan
un único ganador y que 0055 pueda revertirse vacía pero bloquee downgrade con historia. CI crea
`aia001_ci` y nunca sustituye esta variable por `DATABASE_URL`.

### TDD-TC-204 — recorrido visual sintético Admin

Verifica en Chrome, a 1440x1000 y 390x844, que el icono accesible abra el asistente, una respuesta
READY_FOR_REVIEW navegue con deep link, la revisión muestre actual/propuesto y la aceptación envíe
una clave idempotente. Exige contenido visible, ausencia de overlay, `pageerror` y errores de consola.

### TDD-TC-205 — observabilidad redactada

Verifica eventos de creación y revisión con resultado, IDs técnicos, decisión, estado y código de
error; el prompt y la clave idempotente no pueden aparecer en logs.

PostgreSQL aislado se ejecuta sólo con `AIA001_TEST_POSTGRES_URL`; nunca se sustituye por
`DATABASE_URL`. La red real del proveedor no forma parte de las pruebas: el adaptador usa opener
inyectado y fixtures sintéticos. El canary productivo requiere autorización separada.
