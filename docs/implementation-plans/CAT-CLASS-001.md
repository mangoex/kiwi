# CAT-CLASS-001 — Clasificación comercial independiente

Estado: implementación local R3 tras autorización «proceed»; base `d7b466b`, 2026-09-24.
Incluye código, migraciones ensayadas en bases desechables, pruebas y auditoría independiente.
No incluye ejecución productiva, commit/push ni despliegue. Los cambios locales previos se preservan.

## Objetivo y alcance

Hacer explícita Clasificación → Grupo → Subgrupo opcional → Producto, independiente de estación.
Fuentes canónicas: PRD-FR-246/247; SDD §49; BDD-FEAT-114 (531–537); TDD-TS-118 (271–276).
La captura aportada confirma un selector de clasificación en el grupo; no demuestra todas las
reglas de Soft Restaurant. No se presume equivalencia completa ni migración automática de sus datos.

La planificación original fue R0; el incremento implementado es R3 por persistencia, alcance corporativo,
concurrencia y catálogo offline. No modifica reglas de precio, inventario, pedidos o preparación.
PRD/SDD/BDD/TDD/matriz se activan por nueva regla, modelo, aceptación y cobertura. SDD §49 registra
la decisión técnica; no hace falta un ADR duplicado ni dependencia nueva.

## Evidencia de partida

- `models.py:product_categories` carece de clasificación; `create_category` recibe nombre/orden.
- `categoryOptionFlow.ts:productsForCatalogMenuGroup` deriva Alimentos/Bebidas de `station`.
- `ProductsList.tsx` presenta `station` como Área de impresión.
- `platform_data.py` proyecta productos, categorías y elegibilidad; debe mantener autoridad Python.
- `offline_order_catalog.py` usa v2 y acepta v1; incluye categorías, pero no las tablas de subgrupos
  en `_CATALOG_TABLES`. La paridad offline no puede darse por probada.
- CI contiene PostgreSQL y suites generales; las pruebas propuestas de clasificación aún no existen.
- Inventario inicial de escritores: `operations.py` (`_get_or_create_category`, `create_category`,
  `update_category`), `legacy_import.py`, `real_catalog_loader.py`, `recipe_catalog_seed.py`.
  Deben revisarse también escrituras genéricas y migraciones al ejecutar P0; este inventario no
  declara cobertura exhaustiva. Seeds/importadores no pueden crear grupos sin clasificar después
  de activar ni saltarse autoridad/auditoría bajo pretexto de ser herramientas internas.
- Hay cambios locales previos en operations.py y tres archivos mobile, además de output/ y
  .playwright-cli/. Preservarlos; la implementación futura requiere aislar su alcance.

## Tareas, dependencia y aceptación

| Tarea | Responsable previsto | Depende de | Entrega y criterio de salida |
|---|---|---|---|
| P0 Inventario y decisiones | Dominio + responsable del catálogo | — | Ratificar códigos iniciales; inventariar todos los escritores/lectores, reportes, gateway y capacidades reales. Mapping aún sin aplicar. No decisiones comerciales por inferencia. |
| P1 RED dirigido | Backend + frontend | P0 | Casos 271–276 reproducen diferencias/amenazas reales con fixtures sintéticos; registrar fallos esperados. |
| P2 Expansión | Backend | P1 | Migración nueva aditiva, NULL explícito, versión y CHECK; upgrade PG/SQLite, downgrade condicionado y fingerprints sin cambios ajenos. |
| P3 Comando corporativo | Backend | P2 | API, writers heredados e importadores comparten autorización, CAS, idempotencia y auditoría; 272/273 verdes. |
| P4 Lecturas y UI | Frontend + backend | P3 | Alta de grupo normal/contextual, clasificación heredada, preview y POS usan contrato; área operativa independiente, caso 271 y QA visual verdes. |
| P5 Offline y generaciones | Gateway + backend | P3 | Capabilities, firma, bundle v3, compatibilidad y subgrupos scoped, instalación atómica; caso 275 verde. |
| P6 Mapping y rollout ensayado | Operación + backend | P4/P5 | Dry-run revisable, comandos reanudables, cobertura, gate de activación, comparación vendible y reversión probados en staging; 274/276 verdes. |
| P7 Gates y auditoría de implementación | CI + auditor Sol independiente | P6 | Tests focales, tipos, lint, builds, CI y auditoría sobre diff final, sin hallazgos bloqueantes ni skips en gates exigidos. |
| P8 Autorización productiva | Usuario + operación | P7 | Paquete concreto con mapping, backup/restore ensayado, clientes compatibles, secuencia y compensación. Autorización separada para migración/configuración/despliegue/datos. |
| P9 Canary y cierre operativo | Operación | P8 | Una organización piloto explícitamente seleccionada y sus sucursales compatibles; recorrido acotado y observable; confirmar generaciones y huellas, detener/revertir ante umbral SDD §49.4. |

P4 y P5 pueden avanzar en paralelo una vez fijado el contrato P3. No hay estimación de horas sin
inventario P0. P0–P5 implementados; P6 ensayado en entorno local sintético (staging real pendiente); P7 con
evidencia local y auditoría abajo, CI remoto pendiente; P8/P9 productivos no ejecutados ni autorizados.

## Criterios de terminado del incremento

Cada escenario tiene prueba ejecutada y salida registrada; ninguna afirmación se apoya sólo en
compilación. Cobertura completa de grupos activos y todas las sucursales habilitadas con acuse;
clasificación independiente de estación; permisos negativos y concurrencia probados; online/offline
coherentes; cero cambio de dinero, routing, snapshots o disponibilidad; reversión ensayada sin borrar
historia. Auditoría independiente y CI aplicable verdes; canary sólo con autorización productiva.
Si una sucursal sigue desconectada, no presentar el cambio de modo como adoptado en esa sucursal.

## Antecedente: auditoría del paquete documental previo

La auditoría de planificación revisa coherencia, seguridad, operación, cobertura y tareas; no
certifica implementación. El auditor independiente trabaja con contexto fresco y documenta aquí
hallazgos concretos. Cada afirmación R3 debe relacionar evidencia propuesta, refutación, resultado y
riesgo residual. Este apartado conserva el resultado previo a la implementación. La auditoría P7 del diff de
runtime y la evidencia ejecutada se registran al cierre de este documento.

| Afirmación del diseño | Evidencia disponible / requerida | Intento de refutación | Resultado actual | Riesgo residual |
|---|---|---|---|---|
| Clasificar no cambia preparación ni dinero | Separación SDD §49; requiere TC-271/276 | Alimento en barra y reclasificación de pedido aceptado | Diseñado; no probado | Un consumidor puede seguir infiriendo por estación o ampliar clasificación a routing |
| No hay acceso ajeno ni doble escritura | Contrato SDD §49.1; requiere TC-272/273 | Rol sucursal, IDOR, replay revocado, carrera y fallo entre escrituras | Diseñado; no probado | Escritor heredado sin inventariar |
| Migración conserva operación e historia | Expansión/rollback §49.3; requiere TC-274/276 | Grupo mixto/vacío y venta posterior a migración | Diseñado; no probado | Mapping comercial incorrecto o restore destructivo |
| Offline no pierde catálogo ni subgrupos | Gap allowlist identificado; requiere TC-275 | Lector viejo, firma inválida, corte de instalación y nodo sin acuse | Diseñado; no probado | Capacidades/refresh actuales aún requieren implementación y prueba real |

### Revisión independiente Sol — 2026-09-24

Auditor con contexto fresco `/root/audit_classification_plan`, lectura del paquete y contraste con
API, proyección y gateway actuales. Detectó tres P1 de diseño, corregidos durante esta revisión:

1. Bundle antiguo firmado podía sustituir uno nuevo: §49.3 ahora exige generación monotónica,
   replay exacto, marcador atómico y reversión sólo como generación superior; BDD-536/TC-275.
2. Ampliar DTO de GET categorías sin branch podía exponer configuración: §49.1 exige autoridad
   corporativa en esa lectura y distingue DTO operativo con branch; BDD-533/TC-272.
3. Acuse de capacidad confundido con adopción: §49.3 define preparación/adopción y acuses exactos
   de instalación explícita; desconexión y carreras no permiten declarar activación completa;
   BDD-536/TC-275. Reversión sigue el mismo protocolo de acuses.

Estas correcciones son contratos de diseño, no seguridad demostrada en runtime. El auditor
revisó las correcciones y pidió aclarar también el paso 6 de §49.3: se corrigió para separar el
gate de preparación del de instalación explícita. Dictamen documental: sin otros hallazgos
bloqueantes tras esa aclaración. La planificación no elimina el inventario P0 ni ratifica los
valores comerciales por el cliente.

Evidencia local documental: `python -m pytest tests/architecture/test_traceability.py -q`: 8 passed.
`git diff --check`: sin errores de whitespace (avisos de conversión LF/CRLF de Git únicamente).
En ese cierre documental todavía no se habían ejecutado pruebas de runtime ni migraciones.
La implementación autorizada posteriormente y sus verificaciones se detallan a continuación.
Los cambios locales preexistentes se preservaron en ambas etapas.


## Implementación y procedimiento de entrega

La autorización «proceed» confirma Alimentos (`food`), Bebidas (`drinks`) y Otros (`other`) como
opciones iniciales; no autoriza inferir el mapping del catálogo real. Nuevos grupos usan selector
obligatorio; los existentes permanecen NULL/Pendiente hasta decisión explícita. Estación queda
independiente, heredando sólo clasificación desde grupo. Se corrigió únicamente el layout <=767px
que bloqueaba los controles afectados: navegación Admin y sidebar/carrito POS pasan a flujo normal;
escritorio conserva su distribución. Evidencia antes/después en `output/playwright/catalog-classification/`.

Contratos operativos añadidos:

- `GET /api/v1/catalog/classification-rollout`: inventario administrativo autorizado con nombres,
  IDs, clasificación, versión, estado, fingerprint y acuses por sucursal.
- `POST` a la misma ruta: `action` (`prepare`, `publish`, `revert`), `expected_version` y
  `Idempotency-Key`; `prepare` exige `online_readiness` por ID de sucursal con valor `cat-class/v1`.
  Este registro es una **atestación del operador corporativo** después de verificar/reabrir todos
  los POS online compatibles, no detección automática de pestañas viejas. El servidor no puede
  descubrir clientes que no se comunican; comprobar versiones forma parte del gate de despliegue.
- Bootstrap/renew aceptan `catalog_schema: ord-off-catalog/v3`; sin negociación el emisor conserva
  v2 antes de cualquier v3 emitido. Un downgrade de capacidad posterior se rechaza.
- `POST /api/v1/offline-orders/catalog-ack`: dispositivo autenticado de la sucursal, lease vigente,
  generación/hash/modo/epoch exactos de su último bundle. Un acuse de generación anterior o de otro
  dispositivo nunca completa adopción. Se audita instalación nueva; replay exacto no duplica evento.
- `catalog_generation`/`catalog_hash` identifican instalación confirmada; legacy sin acuse usa
  0/cadena vacía. `catalog_projection_hash` identifica topología online actual y evita mezclar dos
  GET; el POS comprueba también pertenencia exacta grupo/subgrupo y ofrece Reintentar ante conflicto.

Secuencia futura productiva (requiere P8, no ejecutada):

1. Revisar diff final y CI; identificar organización/sucursales piloto, ventanas, baseline de
   consultas/latencia, backup y restauración ensayada. No usar el PostgreSQL temporal de QA como
   fuente productiva. Migrar 0070 y 0071 aditivamente en el entorno autorizado, aún modo legacy.
2. Desplegar lectores/Admin/gateways compatibles, reabrir POS y comprobar cada sucursal. Exportar
   el array `groups` del GET administrativo; revisar y rellenar `classification_code` por grupo.
3. `python scripts/classification_mapping.py mapping.json` produce dry-run sin red. Revisar IDs,
   nombres y versiones. Sólo con autorización de datos usar `--url <origen> --apply` y token en
   `RESTAURANTOS_API_TOKEN`. Usa HTTP canónico, CAS y claves deterministas; ante error se detiene.
   Reejecutar el mismo archivo recupera resultados confirmados; corregir conflictos sólo tras
   volver a revisar el grupo. HTTPS obligatorio salvo localhost; no redirige credenciales.
4. Preparar/renovar bundles v3 legacy. Arrancar el gateway para instalar ambas bases; ejecutar
   `python -m edge_gateway acknowledge-catalog --config <config-local>` sólo después de instalación.
   El comando compara bundle firmado con ambos markers persistidos antes de enviar ACK. La descarga
   `prepare-orders` por sí sola nunca acredita instalación. Repetir ACK recupera fallos de transporte.
5. Enviar `prepare` con versión vigente y atestación online. `publish` exige cobertura/fingerprint
   sin cambios y gateways con ACK/capacidad/lease válidos. Alta/baja de sucursal y escritores de
   catálogo comparten bloqueo de organización. Cambiar topología obliga a preparar de nuevo.
6. En `adopting`, `renew-orders` obtiene generación explícita superior; tras instalar ejecutar
   `acknowledge-catalog`. Sucursal sin acuse conserva modo confirmado; la organización sólo llega a
   `explicit` con todas confirmadas. No hay conmutación simultánea ficticia para nodos desconectados.
7. Canary acotado: recorrer clasificación/grupo/subgrupo/producto y venta de prueba compensable,
   comparar destinos KDS/impresión, totales, snapshot/inventario y catálogo disponible contra baseline.
   Con cualquier umbral SDD §49.4 detener y enviar `revert` con versión/clave nuevas.
8. Reversión emite generaciones superiores legacy; renovar e instalar, enviar ACK por sucursal y
   confirmar estado. No borrar columnas/auditoría ni restaurar backup sobre ventas posteriores.
   Downgrade físico sólo en base sin historia; PostgreSQL y SQLite lo rechazan si hay comandos.

### Evidencia de implementación (local)

- SQLite/backend: comando corporativo, rollback, replays, versiones, entradas hostiles, escritores
  heredados, fixtures de importación y contrato HTTP ejecutados; detalle de recuentos al cierre.
- PostgreSQL 17.11 local desechable: cuatro pruebas reales de concurrencia y una de migración
  0069→0070→0071/roundtrip/historia, todas verdes sin skips. Instalación portable sólo en 127.0.0.1.
- Offline: 11 casos nuevos y cuatro variantes refresh/restart con firma, generación y snapshots;
  gateway v2/v3 conserva pedidos, movimientos y outbox existentes. Mypy y ruff focales verdes.
- Integración HTTP real: emisor firmado→hidratación SQLite→ACK autenticado→adopción→proyección POS;
  2 pruebas junto con el contrato de categorías verdes. No sustituye el canary productivo.
- Browser: eventos reales en 1440 y 390 px, alta normal/contextual, CAS 409, replay de 503, clasificación
  heredada, comida en barra bajo Alimentos, búsqueda/favoritos, snapshot incoherente y reintento.
- Trazabilidad 8/8 y gates de cadena Alembic/contratos 14/14. `git diff --check` al cierre.
- CI configurado para nueva base/suite PostgreSQL y cadena semántica frontend. No se consultó una
  ejecución remota de este diff sin publicar: CI no se presenta como verde.

### Afirmaciones R3 y refutación de implementación

| Afirmación | Evidencia e intento de refutación | Resultado local | Riesgo residual |
|---|---|---|---|
| Clasificación independiente sin alterar estación | Helpers POS con alimento en barra y grupos mixtos; HTTP comando; refresh v3 conserva snapshots/ledger | Verde focal | Canary KDS/impresión real y adopción de datos no ejecutados |
| Scope, CAS e idempotencia | Roles corporativo/sucursal/ajeno/revocado, payloads hostiles, fallo entre escritura/auditoría; carreras PG misma/distinta clave y writer legacy | Verde focal | Operación con catálogo real y CI remoto conservan sus gates |
| Activación no adelanta adopción | Falta ACK, ACK hash incorrecto/dispositivo ajeno, reversión con nueva generación; carrera PG alta sucursal vs publish | Verde focal | Atestación online manual; desconectados se reportan pendientes |
| Offline conserva último estado verificable | Firma inválida, replay antiguo firmado, instalación interrumpida/reinicio, refresh con orden abierta | Verde focal | Proceso canary/restauración en infraestructura real pendiente |
| Migración no inventa datos ni borra historia | PG/SQLite preservan filas, NULL, CHECK, downgrade vacío y rechazo tras comandos | Verde focal | Backup/restauración productiva requieren autorización y ensayo propio |

### Cierre de auditoría runtime y regresión final

Auditor independiente Sol `/root/classification_runtime_audit`, contexto fresco: **sin hallazgos
bloqueantes pendientes** tras revalidar bloqueo de topología, coherencia entre GET, identidad de
bundle separado de proyección, mapping con nombres y compatibilidad legacy sin acuse. Auditoría
asesora, no sustituto de los gates ejecutados. El posible retiro físico de filas heredadas del
bundle se registró como riesgo no alcanzable por el comando canónico de desactivación; éste conserva
las filas con estado inactivo. No se afirmó que una ruta feliz pruebe todos los escenarios.

Regresión consolidada final: **55 passed, sin skips** en las seis suites CAT-CLASS (comando,
rollout, HTTP, offline, migración y PostgreSQL), contratos, trazabilidad y direcciones/sucursales.
Incluye cinco casos PostgreSQL reales. Además **pnpm test:frontend-semantic completo verde**, builds
y typechecks Admin/POS verdes, browser desktop/móvil verde. Ruff de módulos afectados y mypy focal
verdes; se añadió pandas-stubs sólo a dependencias de desarrollo para reproducir el gate del loader.
Advertencias existentes: Starlette/httpx en tests, chunks frontend >500kB y Transform Types de Node;
no se suprimieron. Git diff-check sin errores.

Medición local `output/cat-class-benchmark.json`: con 1000 productos vendibles sintéticos y 10
muestras calientes, ambas proyecciones
conservaron 1000 productos. Comparativa bajo carga concurrente de QA: baseline mediana 294.90 ms y 3
consultas; CAT-CLASS 441.00 ms y 14 consultas. Es costo adicional constante de consultas y lineal en
catálogo, no una certificación de latencia productiva. Antes de release medir con catálogo real y
acordar presupuesto; no declarar SLO aprobado. No se introdujo caché que pueda ocultar cambios de
clasificación para mejorar artificialmente la medición.

CI remoto, despliegue, mapping real y canary permanecen pendientes. No hubo commit/push ni
operaciones productivas. Los cambios ajenos de mobile y public_key de sucursales se conservaron.

Ensayo de backup/restauración local: `output/cat-class-backup-check.json`, resultado aprobado.
Alembic real hasta 0071, pg_dump custom del schema sintético propio y pg_restore con
`--exit-on-error`: 139 tablas y 50 filas con conteos y SHA-256 idénticos antes/después. Incluye
categorías, comandos y auditoría. El schema del ensayo se eliminó; no se tocaron datos productivos.
