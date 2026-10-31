# TDD-TS-163 Contrato, autoridad y operación del servidor MCP

Esta suite es diseño de verificación para MCP-001. Ningún caso se considera ejecutado hasta que
exista implementación y evidencia reproducible. Red real, secretos, despliegue, migración,
configuración y canary productivos requieren autorización separada.

## TDD-TC-481 Manifiesto, OpenAPI y runtime

Construye la tabla de operación REST, herramienta MCP, perfil, capacidades, branch, schema,
read/write e idempotencia. Exige correspondencia exacta entre manifiesto, OpenAPI y ambos adapters,
nombres únicos, schemas cerrados y ausencia de `call_api`, SQL, URL o ruta libre. Una nueva ruta
FastAPI no aparece automáticamente en MCP.

## TDD-TC-482 Transporte moderno y compatibilidad acotada

Con el SDK fijado, prueba Streamable HTTP stateless MCP `2026-07-28`, headers/método/nombre
concordantes, requests independientes y catálogo determinista. Rechaza versión, header o body
incompatibles. Si un cliente canary exige la era `initialize`, valida ambos recorridos sobre el mismo
endpoint y la misma autorización; no se habilita compatibilidad sólo por suposición.

## TDD-TC-483 OAuth resource server fail-closed

Con reloj y claves inyectados valida firma, issuer, resource/audience, expiración, scopes y
protected-resource metadata. Rechaza token humano, emisor confundido, audience genérica, algoritmo
no admitido, token vencido y autoridad indisponible antes de dominio. Comprueba que `/mcp` no emite
tokens y que producción no inicia habilitada con configuración incompleta.

## TDD-TC-484 Catálogo filtrado, caché y revocación

Prueba `tools/list` para todas las combinaciones relevantes de perfil/capacidad. El orden es estable,
la caché es privada y ligada a identidad/authorization_version, y no filtra herramientas entre
clientes. Después de revocar o cambiar política, una llamada con catálogo antiguo se reautoriza y
falla; no basta un TTL vigente.

## TDD-TC-485 Matriz de organización, perfil, capacidad y sucursal

Ejecuta cada herramienta con principal permitido y contra organización ajena, perfil distinto,
capacidad ausente, branch omitida/ambigua/fuera de allowlist e identidad pausada. Inyecta en prompt,
argumentos y `_meta` otro scope y demuestra que no altera `AgentPrincipal` ni provoca consulta
cross-scope.

## TDD-TC-486 Paridad de las dieciséis lecturas

Para fixtures sintéticos y el mismo principal/argumentos compara el resultado canónico REST y MCP de
contexto, catálogo, ventas, gastos, pagos, cortes, conciliación, insumos, stock, movimientos,
recetas, proveedores, presentaciones, historial, necesidades y operación. Incluye cursores, periodos,
decimales/centavos, campos omitidos, vacíos y errores estables. Ninguna lectura escribe dominio.

## TDD-TC-487 Escrituras mediadas y ausencia de efectos prematuros

Para las cuatro herramientas permitidas exige una propuesta `READY_FOR_REVIEW` o compra `DRAFT` con
actor agente correcto. Compara antes/después catálogo efectivo, receta activa, movimientos,
existencias, costo, cuentas por pagar, pagos, caja y permisos. Intenta nombres de herramientas para
aplicar, confirmar, recibir, pagar, cancelar, ajustar inventario o administrar usuarios y exige
ausencia contractual o denegación sin efectos.

## TDD-TC-488 Idempotencia, concurrencia y recuperación PostgreSQL

En PostgreSQL aislado ejecuta ganadores concurrentes con misma identidad/key/hash, conflicto con
hash distinto y misma key entre identidades. Inyecta fallo antes y después del commit. Exige una sola
entidad/comando/auditoría, cero efecto parcial y recuperación por `operation_status` o replay exacto
después de reautorizar. Revocación impide recuperar el resultado.

## TDD-TC-489 Migración e aislamiento multibot

Aplica y revierte la revisión en SQLite y PostgreSQL aislados. Verifica backfill estable, referencias
históricas, varias identidades del mismo perfil, unicidad por client_key, credenciales y versiones
independientes. Prueba revocación y llamadas simultáneas de dos bots. Downgrade con historia
incompatible debe bloquearse sin borrar datos.

## TDD-TC-490 Límites, redacción y observabilidad

Prueba cuerpo sobredimensionado, schema/profundidad, timeout, concurrencia, rate limit y fallo de
Redis/autoridad. Inspecciona respuesta, logs, métricas y trazas con canarios sintéticos para bearer,
secreto, PII, texto libre, importe detallado e idempotency key; ninguno aparece. Las dimensiones son
acotadas y permiten responder las cuatro preguntas operativas de SDD §72.4.

## TDD-TC-491 Drenado y rollback operativo

Crea operaciones pendientes y finalizadas, bloquea nuevas escrituras/emisión y permite sólo
recuperación propia reautorizada durante el drenado. Deshabilita `/mcp` y prueba que REST, historia y
auditoría permanecen. Un rollback no transforma timeout o pendiente en éxito ni elimina comandos.

## TDD-TC-492 E2E con cliente MCP real

Contra una instancia efímera, un cliente MCP real obtiene metadata, autentica, lista herramientas y
ejecuta lecturas conocidas. Otro perfil/sucursal/herramienta falla. El canary automatizado inicial
no enumera ni invoca escrituras. La prueba registra versión exacta de cliente y servidor sin guardar
tokens o payloads sensibles.

## TDD-TC-493 Trazabilidad, auditoría y gates de release

Ejecuta `tests/architecture/test_traceability.py`, contrato MCP focal, Ruff, mypy y
`git diff --check`. Cuando cambien persistencia o concurrencia agrega PostgreSQL/SQLite; cuando exista
runtime cruza REST/MCP y ejecuta auditoría Sol independiente con contexto fresco. CI corre la suite
completa aplicable. Browser/Admin sólo se activa si cambia la gestión visual. Publicación Git no
acredita deploy, migración, secretos, configuración, canary ni comportamiento productivo.

## TDD-TC-494 Mapeo WorkOS y reautorización fail-closed

Firma tokens sintéticos con claims equivalentes a AuthKit y prueba el tuple exacto
`(iss, client_id, sub)`: una coincidencia habilitada lista y llama herramientas; cambiar cualquiera
de los tres valores u omitir `client_id` falla antes de dominio. Verifica que otro `org_id` externo
no cambia organización ni alcance, que el runtime no consulta la API de WorkOS, no acepta el UUID
interno como `sub` por compatibilidad y no persiste access/refresh tokens.

## TDD-TC-495 Ciclo de vida y migración del vínculo OAuth

Prueba alta, reemplazo, revocación, conflicto de tuple, versión obsoleta, permisos humanos y auditoría
redactada. Cada mutación incrementa `authorization_version`, deshabilita la identidad y exige
reactivación explícita. Ejecuta upgrade/downgrade vacío en SQLite y PostgreSQL aislados; el downgrade
con cualquier vínculo se bloquea. Comprueba que una identidad sin secreto Agent Tools puede
habilitarse con un vínculo OAuth y que quitar ambos mecanismos impide habilitarla.

## Evidencia local parcial — 2026-10-30

`apps/api/tests/test_mcp_contract.py` ejecuta parcialmente TDD-TC-481/482/483/484/492: manifiesto de
dieciséis lecturas contra OpenAPI, flag default-off, configuración fail-closed, firma JWT/JWKS,
issuer/audience/scope/expiración, metadata RFC 9728, intercambio HTTP moderno, catálogo filtrado con
TTL cero, revocación en la siguiente solicitud, resistencia al envenenamiento del bucket con un
`sub` no firmado y un recorrido con el cliente oficial MCP 2.3.0. JWKS rechaza redirecciones,
credenciales embebidas e IP literales no globales en producción y corta el stream sobre 256 KiB. La
autoridad y datos son fixtures sintéticos; no se usaron credenciales ni red productiva.

TDD-TC-493 verifica además que cada importación HTTP directa del runtime MCP sea una dependencia
directa del proyecto y quede congelada en el lock de la API. Esta regresión cubre el incidente donde
`httpx` existía sólo en el extra de desarrollo: la imagen productiva inició sin el módulo y la API
respondió 502 hasta revertir el paquete. El release exige ahora tanto la prueba de dependencia/lock
como el build real de las imágenes Docker en CI; resolver imports en el entorno local no sustituye
ese gate.

TDD-TC-493 tiene evidencia local focal de Ruff, mypy, trazabilidad, locks y regresiones Agent Tools,
y evidencia CI completa 41178917384 sobre `18b7f055`, incluida la construcción de ambas imágenes
Docker desde locks congelados.
Esto no completa TDD-TS-163: siguen pendientes la paridad de las dieciséis lecturas, toda la matriz
de perfiles/capacidades/sucursales, schemas cerrados, allowlist/egress DNS para JWKS, límite por
identidad OAuth ya verificada, límites globales y redacción, y los casos de fases B/C.
La auditoría R3 independiente no encontró P0; el poisoning de bucket se corrigió, pero ratificó esos
bloqueantes de release. PostgreSQL, migraciones y browser no se activan para este scaffold sin
cambios de persistencia, concurrencia o UI.

## Evidencia local incremental — 2026-10-31

TDD-TC-494/495 inició con tres fallos RED esperados: endpoint de vínculo inexistente, tabla/modelo
ausente y revisión Alembic no localizada. Después de implementar el tuple OAuth persistido se
aprobaron 27 pruebas focales de Agent Tools, contrato MCP y migración; seis regresiones críticas se
repitieron tras la revisión AppSec y aprobaron. Las nueve pruebas de trazabilidad y las doce de
capacidad/linealidad Alembic aprobaron. Ruff focal, mypy focal y `git diff --check` aprobaron.

La verificación contra la documentación vigente de WorkOS agregó una regresión RED: `AnyHttpUrl`
normalizaba el issuer configurado con `/` final y rechazaba el `iss` canónico sin slash de AuthKit.
El verificador ahora compara el valor canónico sin slash; el JWT con variante slash queda rechazado.
La auditoría independiente detectó que protected-resource metadata todavía publicaba la variante
con slash; la regresión ahora exige que `authorization_servers` use el mismo issuer canónico.

El roundtrip SQLite, incluido downgrade vacío y bloqueo con historia, aprobó. El caso PostgreSQL
quedó implementado pero se omitió localmente porque `GROKBOT_TEST_POSTGRES_URL` no está disponible;
debe ejecutarse en CI o en una base aislada antes de integrar. No se ejecutaron CI, imágenes Docker,
migración real, configuración WorkOS/Easypanel, browser, deploy ni canary. La auditoría Sol
independiente R3 emitió PASS sin bloqueantes P0-P2 después de corregir la metadata del issuer, alinear
el tratamiento no autoritativo de `org_id` y acotar los identificadores del índice OAuth.
