# ADMIN-SESSION-001 — sesión y menú de administración

Fecha: 2026-10-01. Riesgo R3 por identidad, caché e intención de comandos; cambio de menú R1.

Los logs aportados muestran 401 en sucursales, catálogo y categorías. El cliente borraba el token
sin notificar al router y QueryClient reintentaba esas lecturas. La sesión dura 12 horas según el
backend; los logs no distinguen vencimiento de invalidación de firma. No se cambió TTL, firma,
permisos, credenciales, persistencia ni configuración productiva.

## Contrato y resultado

PRD-FR-005/237 y PRD-NFR-027; SDD §23.1/46.1; BDD-SC-560..565; TDD-TS-125/TC-290..292.
El 401 vigente solicita login una vez, conserva 403/login fallido y no borra una autenticación
nueva por una respuesta tardía (incluido token de valor idéntico). Cada nueva sesión obtiene otro
QueryClient. Agentes sustituye Panel Principal y queda después de Administración, seguido de POS;
conserva el destino actual y no agrega capacidades de agentes.

Antes de desmontar, la sesión interrumpida pone compras/copias activas en cuarentena sólo en RAM,
aisladas por actor/contexto. Reautenticar el mismo actor permite recuperar clave/carga/fingerprint
o versiones originales; no permite completar una operación sin reautorización del servidor.

## Evidencia local

- RED de transporte: 401 anterior borraba token nuevo. RED navegador: Productos permanecía abierto
  sin volver a login tras 401. Ambos GREEN tras corrección.
- `pnpm test:frontend-semantic`: agregado verde, incluida nueva regresión de sesión con transporte
  y QueryClient/MutationCache reales y snapshots de compra/copia. No se desactivaron casos.
- Builds Admin/POS verdes; typecheck KDS verde. Advertencia de chunks >500 kB heredada, sin silenciar.
- Browser sesión/menú verde a 390/1440. API SQLite sintética real: credencial inválida → login →
  catálogo 200 con producto del fixture. Sin modificar datos o credenciales productivos.
- E2E real compra Admin/POS: respuesta perdida, replay; Admin agrega 401/reautenticación SPA,
  recuperación de tres partidas y tres intentos con la misma clave/cuerpo/fingerprint; un documento,
  confirmación, retiro único y cancelación compensatoria.
- Auditoría independiente R3: sin bloqueantes. Ensayos adicionales en navegador: actor B no ve
  compra de A en la misma sucursal; volver a A recupera su intención; copia incierta conserva
  versiones y clave y vuelve a habilitar edición sólo tras replay y lectura actual del destino.
- Trazabilidad: 9 passed. Regresiones SEC001: 6 passed; scanner de archivos afectados limpio y
  `git diff --check` verde. Dos nuevos fixtures con credenciales exclusivamente sintéticas tienen
  excepciones exactas por ruta/hash/provenance; auditoría focal verificó su origen y ausencia de logs
  de credenciales. El hash de CI existente se renovó por agregar gates, sin ampliar su excepción.

## Afirmaciones R3

| Afirmación | Evidencia / intento de refutación | Resultado | Riesgo residual |
| --- | --- | --- | --- |
| 401 viejo no invalida login nuevo | Token distinto e idéntico, generación vieja, dos 401 concurrentes y login fallido | Transporte verde, una notificación por invalidación | Generación del realm actual; sincronización automática entre pestañas no certificada |
| Cache nuevo queda aislado | Completar mutación anterior después de limpiar/sustituir cliente | Producto anterior queda sólo en cliente original | Un comando autorizado puede completar legítimamente en servidor |
| Reautenticación conserva comandos inciertos sin mezclar actores | Pérdida de respuesta, 401, B misma sucursal, luego A; copia con versiones originales | Recuperación exacta; B recibe captura vacía | Sólo RAM: recarga completa o cierre forzado pierde el snapshot |
| Contexto anterior no sobrescribe perfil/sucursal nuevos | Respuesta de sucursal/perfil retrasada tras desmonte y login distinto | Abort/guardas impiden escritura tardía | No se afirma cancelación de un commit del servidor |

## Separación de publicación y producción

CI incorpora las regresiones de sesión y los recorridos de compra/reautenticación; configuración
no equivale a CI remoto ejecutado. No se ejecutó suite backend completa ni PostgreSQL: el diff no
cambia dominio, SQL, migraciones ni persistencia transaccional. No cambia gateway/offline.
La corrección requiere servir el build nuevo y reautenticar la sesión rechazada. Esta evidencia
no certifica despliegue, canary ni comportamiento productivo; publicación Git se informa por separado.
