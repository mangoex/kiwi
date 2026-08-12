# PCO-002 — paquete de implementación para Terra

**Preparó:** Sol
**Implementa y prueba:** Terra, esfuerzo medio
**Audita y acepta:** Sol
**Fecha:** 2026-08-11
**Estado:** especificación aprobada; implementación heredada parcial no auditada
**Rama existente:** `codex/pco-002-cash-concepts-movements`

## 1. Objetivo verificable

Completar exclusivamente el catálogo corporativo versionado de conceptos de caja y su lectura
efectiva por backend. Al terminar, Dueño puede crear una identidad con código inmutable, publicar
versiones y archivar sin borrar historia; un operador con `cash.concept.read` puede consultar por
tipo, fecha y sucursal únicamente la versión efectiva autorizada.

PCO-002 es precondición del ledger. No crea depósitos, retiros, compensaciones, esperado de caja,
outbox/inbox, cierre operativo, corte, reapertura ni reportes.

## 2. Autoridad y trazabilidad

| Elemento | Fuente canónica |
|---|---|
| Alcance de producto | `PRD-FR-216` en `docs/01-PRD.md` |
| Autorización | `PRD-FR-215`, `SDD-ADR-015`, matriz de permisos SDD §38.1 |
| Identidad/versiones/idempotencia | SDD §38.2.1 y `SDD-ADR-024` |
| Comportamiento | `BDD-SC-296`, `BDD-SC-301`; sólo precondición de catálogo de `BDD-SC-278` |
| Pruebas | subconjunto catálogo de `TDD-TS-078` y `TDD-TC-084` |
| Estado | fila `PRD-FR-216` de `docs/05-matriz-trazabilidad.md` |

`SDD-ADR-024` fue aprobado para este incremento por el Dueño de producto el 2026-08-11. No reemplaza
otro ADR y no autoriza incrementos posteriores ni acciones Git/productivas.

## 3. Alcance obligatorio

1. Modelo de identidad corporativa `cash_movement_concepts`:
   - UUID/string ID.
   - `organization_id` obligatorio.
   - `code` de hasta 64 caracteres, normalizado a mayúsculas, único por organización e inmutable.
   - estado `active|archived`.
   - actor de creación y timestamps UTC.
   - archivo lógico; jamás DELETE de historia.
2. Modelo append-only `cash_movement_concept_versions`:
   - ID, `concept_id`, versión entera positiva y única por concepto.
   - nombre visible.
   - `allowed_movement_type=deposit|withdrawal|both`.
   - `valid_from` con zona y persistencia UTC.
   - `requires_reference=true` y `requires_evidence=true`; PCO-002 no permite falsos.
   - actor y timestamp de publicación.
3. Modelo de comandos `cash_concept_commands`:
   - unicidad `(organization_id, idempotency_key)`.
   - comando `create|version|archive`, target, actor, hash SHA-256, resultado estable y timestamp.
   - el actor forma parte de la identidad canónica del comando.
   - replay exacto devuelve el resultado almacenado antes de validar estado mutable actual.
   - misma key con actor, comando, target o payload distinto devuelve `idempotency_conflict`.
4. Servicios Python autoritativos para crear, versionar, archivar, listar historia y resolver efectivos.
5. API versionada y contratos JSON Schema compartidos.
6. Pantalla Admin visible exclusivamente con `cash.concept.manage`.
7. Auditoría de éxito y denegación; logs estructurados sin secretos ni payload completo.
8. Migración `0036_cash_concepts`, reversible sólo vacía y compatible con SQLite/PostgreSQL.

## 4. Exclusiones fail-closed

- No agregar `POST /api/v1/cash/movements`.
- No modificar semántica ni columnas de la tabla legacy `cash_movements`.
- No calcular `expected_cash` ni fórmulas financieras.
- No crear compensaciones ni integrar compras cash.
- No escribir outbox/inbox ni simular éxito offline.
- No crear cierre operativo, cortes, reapertura o reportes.
- No sembrar conceptos de negocio inventados.
- No usar nombres de rol como autorización.
- No tocar PostgreSQL productivo, `DATABASE_URL` original ni datos reales.
- No commit, push, PR, merge o deploy.

## 5. Contratos HTTP v1

### 5.1 Crear concepto

`POST /api/v1/cash/concepts`
Permiso: `cash.concept.manage`
Header obligatorio: `Idempotency-Key`

```json
{
  "code": "RETIRO_OPERATIVO",
  "name": "Retiro operativo",
  "allowed_movement_type": "withdrawal",
  "requires_reference": true,
  "requires_evidence": true,
  "valid_from": "2026-08-11T18:00:00Z"
}
```

Respuesta: identidad con estado y arreglo `versions` que contiene versión 1. Backend genera IDs,
versión, actor y timestamps.

### 5.2 Publicar versión

`PUT /api/v1/cash/concepts/{concept_id}/versions`
Permiso: `cash.concept.manage`
Header obligatorio: `Idempotency-Key`

El body tiene los campos de presentación/vigencia del alta, pero no acepta cambiar `code`. La
respuesta contiene identidad e historia completa ordenada ascendentemente por versión.

### 5.3 Archivar

`POST /api/v1/cash/concepts/{concept_id}/archive`
Permiso: `cash.concept.manage`
Header obligatorio: `Idempotency-Key`; body vacío.

Archivar cambia únicamente estado/marca de la identidad. Replay idéntico devuelve la respuesta
original aunque el concepto ya esté archivado.

### 5.4 Historia administrativa

`GET /api/v1/cash/concepts`
Permiso: `cash.concept.manage`

Devuelve conceptos de la organización, activos y archivados, con todas sus versiones. Nunca incluye
comandos, hashes o datos de otros actores/organizaciones.

### 5.5 Lectura efectiva

`GET /api/v1/cash/concepts/effective?movement_type=withdrawal&effective_at=<UTC>&branch_id=<id>`
Permiso: `cash.concept.read` evaluado con alcance canónico de sucursal.

Sólo admite `deposit|withdrawal`; excluye archivados, versiones futuras y tipos incompatibles. Por
concepto devuelve la versión con número mayor entre las elegibles `valid_from <= effective_at`.

## 6. Errores estables

| Código | Condición | Escritura |
|---|---|---:|
| `actor_required` | falta autenticación | ninguna |
| `permission_denied` | permiso o alcance insuficiente | sólo auditoría de denegación |
| `idempotency_key_required` | mutación sin key | ninguna |
| `idempotency_conflict` | key reutilizada con identidad/payload distinto | ninguna |
| `cash_concept_invalid` | código/nombre/tipo/fecha/requisitos inválidos o versión sobre archivado | ninguna |
| `cash_concept_not_found` | identidad inexistente o ajena | ninguna |
| `cash_concept_code_conflict` | código ya reservado, incluso archivado | ninguna |
| `cash_concept_code_immutable` | versión intenta cambiar código | ninguna |
| `cash_concept_version_conflict` | carrera al asignar versión | ninguna parcial |

El API conserva la taxonomía HTTP existente: autenticación/autorización según adaptador vigente,
not-found 404 y conflicto de negocio 409. No filtrar errores SQL.

## 7. Esquemas compartidos

Crear al menos:

- `packages/contracts/schemas/cash-concept-command-v1.schema.json`
- `packages/contracts/schemas/cash-concept-response-v1.schema.json`
- `packages/contracts/schemas/effective-cash-concepts-v1.schema.json`

Usar `additionalProperties: false` donde corresponda, `format: date-time`, enums exactos y enteros
positivos para versión. Agregar pruebas de contrato que validen ejemplos válidos e inválidos. No
crear lógica financiera en TypeScript.

## 8. Admin Web

- Ruta `/admin/cash-concepts`, guard `cash.concept.manage` y elemento “Conceptos de caja” en sidebar.
- No confiar en el guard cliente: el backend vuelve a autorizar todo.
- Estados: carga, vacío, error recuperable, listado, creando, versionando, archivado y confirmación.
- Código deshabilitado al versionar; referencia/evidencia se muestran obligatorias y no editables.
- Idempotency key estable durante un reintento de la misma intención; una intención nueva usa nueva key.
- Historia visible y ordenada; archivado requiere confirmación y no ofrece reactivar en PCO-002.
- Accesibilidad: labels, foco visible, teclado, `role=status|alert`, contraste y contención responsive.
- POS no añade todavía formulario ni ruta de movimiento. La lectura efectiva queda preparada para
  PCO-003 y no se sustituye con texto libre.

## 9. Auditoría y observabilidad mínima

Eventos append-only:

- `cash_concept.created`
- `cash_concept.versioned`
- `cash_concept.archived`
- `authorization.denied` para rechazo de permisos/alcance

El payload de auditoría puede incluir código, versión, tipo y estado, pero no idempotency key, token,
hash completo ni body. Logs estructurados registran acción, resultado, actor ID, organization ID,
concept ID y correlation ID. Contadores mínimos, si la infraestructura actual los permite sin nueva
dependencia crítica: comandos por tipo/resultado y lecturas efectivas por tipo/resultado. Si no hay
infraestructura de métricas, Terra debe documentar el gap para PCO-009; no inventar un framework.

## 10. Migración y reversibilidad

- Mantener una sola head: `0036_cash_concepts` desciende de `0035_cumulative_profiles_rbac`.
- Crear únicamente las tres tablas e índices necesarios; no sembrar conceptos.
- `upgrade` debe preservar exactamente tablas/columnas legacy de caja.
- `downgrade 0035` se permite sólo si las tres tablas están vacías.
- Con cualquier identidad, versión o comando, bloquear con
  `Safe downgrade blocked: cash concept history exists`.
- Probar `0035 -> 0036 -> 0035 -> 0036` en SQLite y PostgreSQL aislado.
- PostgreSQL aislado significa contenedor/base desechable o ambiente de pruebas expresamente
  autorizado; jamás el `DATABASE_URL` productivo.

## 11. Matriz de pruebas RED → GREEN

### Documentación/arquitectura

1. IDs PRD/BDD/TDD únicos y trazados.
2. Estado de matriz permitido.
3. Head Alembic única `0036` y todas las assertions históricas actualizadas.
4. Presencia de contratos, rutas y ausencia de `POST /cash/movements`.

### Dominio Python

5. Alta válida genera versión 1.
6. Código normalizado/único e identidad archivada no libera el código.
7. Valores inválidos no escriben concepto, versión, comando ni éxito de auditoría.
8. Versión incrementa una vez y conserva versión anterior.
9. Intento de cambiar código falla.
10. Archivo conserva identidad/versiones.
11. Selección efectiva por fecha y tipos `deposit|withdrawal|both`.
12. Concepto archivado y versión futura quedan excluidos.
13. Cajero puede leer en sucursal asignada y no administrar.
14. Dueño administra por autoridad persistida, no etiqueta visible.
15. Sucursal u organización ajena falla cerrado.

### Idempotencia/concurrencia

16. Replay idéntico de create/version/archive devuelve resultado original sin filas nuevas.
17. Replay de version sigue estable después de archivar el concepto.
18. Misma key con actor, comando, target o payload distinto falla.
19. Carrera de versión produce una sola versión o conflicto estable, nunca dos números iguales.
20. Una denegación revierte escritura pendiente antes de auditar.

### API/contrato

21. Header obligatorio y errores estables.
22. JSON Schema acepta respuestas reales y rechaza campos/tipos extra.
23. Gestión lista historia; lectura efectiva no filtra historia ni comandos.
24. `POST /api/v1/cash/movements` continúa 404.

### Frontend

25. Dueño ve navegación y CRUD permitido de PCO-002.
26. Usuario sin permiso no ve navegación, guard redirige y API niega llamada directa.
27. Estados carga/vacío/error/datos y reintento sin duplicidad.
28. Build/typecheck con Node >=22.
29. QA visual desktop y ancho reducido con evidencia de contención del componente interno.

### Regresión

30. Suite completa API/arquitectura verde.
31. Suites PCO-001 verdes.
32. Ruff `--no-cache`, typecheck/build y `git diff --check` verdes.

## 12. Baseline heredado que Terra debe corregir

La rama contiene un intento parcial previo. No asumir que es correcto ni reescribir todo sin revisar.
Auditoría Sol previa al handoff:

- `238 passed, 5 failed` en API + arquitectura.
- Tres fallos son assertions de head `0035` que deben esperar `0036`.
- Un fallo: la ruta Admin existe pero falta navegación lateral.
- Un fallo: la matriz usaba un estado no canónico; Sol ya la corrigió a `Disenado`.
- Ruff detectó imports desordenados en API/test y una línea larga.
- Admin typecheck/build pasó bajo Node 20 con warning; debe repetirse con Node >=22.
- SQLite dirigido pasó; PostgreSQL `0036` no se ha ejecutado.
- Revisión manual: replay de version después de archive debe resolverse antes de validar estado mutable.
- Falta confirmar contrato JSON Schema, logs/métricas, pruebas frontend y QA visual.

Archivos heredados principales:

- `apps/api/alembic/versions/202608110100_0036_cash_concepts.py`
- `apps/api/restaurant_os/models.py`
- `apps/api/restaurant_os/operations.py`
- `apps/api/restaurant_os/api.py`
- `apps/api/tests/test_cash_concepts.py`
- `apps/api/tests/test_cash_concept_migration.py`
- `apps/admin-web/src/features/cash/CashConceptsManager.tsx`
- `apps/admin-web/src/App.tsx`
- `tests/architecture/test_pco002_cash_concepts.py`

## 13. Orden obligatorio para Terra

1. Confirmar cwd, rama y archivos locales del usuario; no borrar ni incluir no rastreados ajenos.
2. Leer `AGENTS.md`, `README.md`, PRD/SDD/BDD/TDD/matriz/ADR y este handoff.
3. Auditar diff heredado contra §§1–12; reportar cualquier contradicción antes de codificar.
4. Ejecutar baseline y conservar salida RED exacta.
5. Completar/corregir primero pruebas y contratos RED.
6. Implementar el cambio mínimo para GREEN sin PCO-003.
7. Ejecutar pruebas dirigidas, regresión completa, lint y builds.
8. Ejecutar round-trip SQLite y PostgreSQL aislado o declarar gate no ejecutado.
9. Ejecutar QA funcional/visual de Dueño y usuario sin permiso.
10. Actualizar TDD, matriz y este plan sólo con evidencia realmente ejecutada.
11. Entregar reporte exacto; no commit/push/deploy.

## 14. DoD para entrega a Sol

Terra puede declarar “listo para auditoría”, no “aceptado”, únicamente si entrega:

- lista de archivos modificados y exclusiones preservadas;
- requisitos/BDD/TDD afectados;
- evidencia RED inicial y GREEN final;
- conteos exactos de cada suite;
- migración SQLite y PostgreSQL con revisión antes/después;
- resultado Node >=22, typecheck/build y QA visual;
- auditorías/logs/errores verificados;
- `git diff --check` limpio;
- riesgos residuales y gates no ejecutados;
- confirmación de cero commit, push, deploy y acceso a producción.

Sol revisará código, diff, contratos, migraciones y repetirá los gates. Cualquier discrepancia devuelve
el paquete a Terra para iteración; sólo Sol, tras auditoría, puede recomendar publicación.
