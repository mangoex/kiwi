# CRM-MOBILE-001 — Plan, tareas y evidencia

R3. Alcance: API, migración, menú móvil y editor CRM. Autoridad: PRD-FR-281/282,
SDD §69, BDD-SC-740..744, TDD-TS-153. Trabajo local previo en operación Easypanel,
allowlist de política y tmp/ preservado. Sin autorización para producción.

1. [x] Inspección y contrato; especificaciones y criterios en la cadena canónica.
2. [x] RED dirigido de cumpleaños, OTP, perfil, delivery, vínculo e idempotencia.
3. [x] Migración aditiva y servicio de identidad con proveedor aislado.
4. [x] CRM cumpleaños; registro, perfil y checkout móvil.
5. [x] Gates focales backend/frontend, migración PG/SQLite, contrato y QA visual.
6. [x] Auditoría Sol independiente y corrección de hallazgos; cierre con límites reales.

## Evidencia

Verificación local inicial 2026-10-20, previa a publicación Git. No incluyó CI remoto,
despliegue, configuración, migración ni SMS productivos. La edición previa del runbook y su hash se conservaron; sólo se
actualizó además el hash existente de CI por las dos bases/variables agregadas, sin nuevas exclusiones.

| Gate | Evidencia local |
| --- | --- |
| RED | Las rutas de acceso/perfil fallaban 404 frente al contrato esperado, antes de implementarlas. |
| API/regresión | 59 passed, 115 deselected en test_mobile_customer_profile + public_order_intents + public_order_tracking + platform_api + traceability con filtro mobile/public_order/customer/traceability. |
| Contratos añadidos | 15 casos de perfil, 2 del adaptador HTTP sin SMS; últimos 3 negativos de alcance/límite ejecutados aparte. |
| Migración | 2 passed: SQLite y PostgreSQL17; cliente, intención aceptada y pedido históricos sobreviven ida/vuelta. Reversión con cumpleaños nuevo bloqueada. |
| Concurrencia PG | 3 passed: login simultáneo, perfil/domicilio repetido y cambios de teléfono solapados. |
| Frontend | 14 contratos móviles existentes, 5 semánticos nuevos y visibilidad digital pasan. |
| Tipos/build | pnpm typecheck del monorepo; builds mobile-web/admin-web; mypy de 11 módulos backend afectados, sin errores. Build admin conserva aviso de chunk mayor a 500 KiB. |
| Integridad | Ruff focal verde; diff --check; política completa y focal de archivos nuevos verdes; 23 pruebas de trazabilidad/política/quality ratchet y 12 de cadena/capacidad Alembic verdes. |
| Navegador | Chromium real contra API sintética local, 320/390/1280 px; CRM1366 px. Alta sin año, enriquecimiento al elegir envío, retorno al carrito, reintento y guardado repetido. Sin excepciones de página. |
| Revisión R3 | Auditoría Sol independiente, contexto fresco; cero hallazgos pendientes tras refutar los contraejemplos de abajo. |

No se suman conteos superpuestos. Evidencia visual reproducible en
`output/playwright/crm-mobile-journey/` (ignorado por Git). Aviso local preexistente:
StarletteDeprecationWarning por httpx/TestClient, sin fallos de aserción.

### Afirmaciones R3 y refutación

| Afirmación | Evidencia e intento de refutación | Resultado | Riesgo residual |
| --- | --- | --- | --- |
| Sólo la identidad verificada edita su perfil | Código inválido/vencido/reusado, cookie revocada, otra organización, ID de domicilio ajeno, body con customer_id; error SQL con marcador sensible | Denegado sin datos ajenos; 503 privado; login nuevo funciona con cookie vieja | OTP real depende del proveedor configurado y posesión actual del teléfono |
| Reintentar no duplica identidad, dirección ni intención | Dos logins y perfiles concurrentes PG; teléfono cambiado mientras otro check espera; mismo creation_key; mismo body/key tras cambiar nombre y otro cliente intenta la clave | Un ganador estable, una primary activa, misma dirección e intención; cliente ajeno recibe conflicto | Bloqueo por organización es conservador; capacidad productiva no medida |
| El CRM mantiene historia | Editar perfil tras aceptar pedido; migrar/downgradear con cliente, pedido e intención anteriores y relaciones existentes | Snapshot original y total/vínculos preservados en SQLite/PG; downgrade con datos nuevos bloqueado | Backup/canary y retención de sesiones/desafíos vencidos requieren operación autorizada |

### Reproducción

```powershell
.venv/Scripts/python.exe -m pytest apps/api/tests/test_mobile_customer_profile.py apps/api/tests/test_phone_verification.py tests/architecture/test_traceability.py -q
# Definir MOBILE_CUSTOMER_TEST_POSTGRES_URL y MOBILE_CUSTOMER_RUNTIME_POSTGRES_URL
# sólo para bases locales aisladas crm_mobile_* antes de ejecutar:
.venv/Scripts/python.exe -m pytest apps/api/tests/test_mobile_customer_migration.py apps/api/tests/test_mobile_customer_postgres.py -q
pnpm test:mobile-customer-profile
pnpm typecheck
pnpm --filter @restaurantos/mobile-web build
pnpm --filter @restaurantos/admin-web build
# Elegir carpeta nueva; fixture siempre en loopback y con verificador falso:
.venv/Scripts/python.exe tests/e2e/mobile_customer_fixture.py --directory output/playwright/crm-mobile-ui-new --port 8158
# En otra consola: apuntar MOBILE_PROFILE_MANIFEST a esa carpeta y
# MOBILE_PROFILE_PLAYWRIGHT_IMPORT al paquete Playwright disponible, si no está en node_modules.
node tests/browser/test_mobile_customer_profile.mjs
```

La suite aplicable completa está configurada en CI. Las suites PostgreSQL nuevas son obligatorias
en verify_postgres_evidence.py; los skips no dan verde. No se ejecutó una suite local completa:
el riesgo se acotó con contratos, PostgreSQL, historial, navegador y regresiones dirigidas.

### Activación pendiente (autorización productiva separada)

1. Preparar backup y verificar credenciales/proveedor en entorno de prueba; no crear cuentas ni contratar servicios durante este paquete.
2. Configurar RESTAURANTOS_TWILIO_ACCOUNT_SID, RESTAURANTOS_TWILIO_AUTH_TOKEN y RESTAURANTOS_TWILIO_VERIFY_SERVICE_SID; secretos fuera de Git. Redis requerido en producción.
3. Aplicar migración0098 con acceso móvil aún desactivado; desplegar lector/escritor compatibles.
4. Habilitar RESTAURANTOS_PUBLIC_ORDER_INTENTS_ENABLED y RESTAURANTOS_MOBILE_CUSTOMER_ACCESS_ENABLED al publicar la web móvil compatible. El frontend nuevo exige el acceso: coordinar flag/proveedor/release para evitar bloqueo del menú.
5. Canary acotado: un alta OTP, sesión reutilizada, delivery con correo/domicilio, aceptación con customer_id y verificación CRM; observar códigos de límite/proveedor/auditoría sin PII. Compensar sólo solicitudes sintéticas bajo autorización, sin editar historia financiera.

Configuración real del proveedor y canary no ejecutados.
Rollback: desactivar acceso móvil y volver al lector anterior antes de downgrade;
la migración bloquea eliminación si existen datos nuevos. Conservar backup antes de migrar.
Los tests históricos de downgrade conservan sus aserciones y actualizan únicamente la revisión
head esperada a 0098; sus suites PostgreSQL completas quedan bajo el CI configurado.


### Publicación Git autorizada

El usuario autorizó commit, merge y push después del cierre local. Rama de implementación:
`codex/mobile-customer-profile`, destino `main`, con CI de PR antes de integrar. El runbook
Easypanel previo, su hash y tmp/ quedan fuera del commit. Esta autorización no activa
SMS, migraciones ni despliegue productivo. El SHA y resultado de publicación se informan en el cierre.
