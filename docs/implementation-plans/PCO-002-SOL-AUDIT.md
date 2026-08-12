# PCO-002 — auditoría de Sol a la implementación de Terra

**Fecha:** 2026-08-11
**Alcance:** catálogo corporativo versionado de conceptos de caja y lectura efectiva.
**Estado:** implementación y auditoría local aceptadas, incluido PostgreSQL 16.14 aislado;
publicación y despliegue no autorizados.

## 1. Autoridad y separación de responsabilidades

- Sol definió PRD, SDD, BDD, TDD, ADR, matriz y el handoff detallado de `PCO-002`.
- Terra medium implementó y probó en la tarea separada
  `019ff392-11e3-79c1-a6a6-cf3525a63ab9`.
- Sol auditó el resultado y devolvió cuatro iteraciones de corrección a Terra.
- No hubo commit, push, PR, merge, despliegue ni uso de la `DATABASE_URL` original.
- Los archivos no rastreados ajenos del usuario permanecieron fuera del alcance.

## 2. Frontera verificada

`PCO-002` incorpora únicamente:

- identidad inmutable y única por organización para conceptos de caja;
- versiones append-only con vigencia UTC;
- archivo sin eliminación de historia;
- idempotencia persistida por organización, actor, comando, objetivo y payload;
- lectura administrativa completa y lectura efectiva por tipo, fecha y sucursal autorizada;
- contratos JSON Schema Draft 2020-12;
- administración web protegida por `cash.concept.manage`;
- auditoría, logs mínimos y migración reversible cuando no existe historia.

Se verificó que no se agregó `POST /api/v1/cash/movements` ni se adelantaron ledger,
efectivo esperado, compensaciones, outbox, cierres, cortes, reaperturas o reportes de `PCO-003+`.

## 3. Hallazgos e iteraciones

1. **Idempotencia y replay:** Terra corrigió actor ausente del hash y replay de versión después de
   archivar.
2. **Contratos y UI:** se separaron payloads de alta/versión, se preservaron mensajes de éxito y se
   agregó validación JSON Schema real, pruebas de permisos y navegación.
3. **Concurrencia y tiempo:** dos sesiones SQLite contienden de forma determinista; el conflicto se
   normaliza y no deja historia parcial. Los timestamps recuperados de SQLite se serializan como UTC.
4. **QA productiva:** el navegador reveló que `crypto.randomUUID` se pasaba sin ligar, por lo que el
   alta fallaba antes del HTTP aunque las pruebas previas estuvieran verdes. Terra lo corrigió con
   una fábrica ligada y añadió la regresión correspondiente.

## 4. Evidencia automatizada de Sol

| Gate | Resultado |
|---|---|
| PCO-002 dominio, API, contratos, concurrencia, migración SQLite y arquitectura | `12 passed` |
| API y arquitectura completas | `247 passed in 495.22s` |
| Ruff dirigido a todos los archivos PCO-002 | `All checks passed!` |
| JSON Schema | Draft 2020-12 y RFC 3339 ejecutados; no omitidos |
| Frontend de conceptos | prueba Node 24 verde |
| Admin TypeScript | sin diagnósticos con Node `v24.14.0` |
| Admin Vite build | `1590 modules transformed`, build verde |
| Integridad de diff | `git diff --check` limpio |
| Migración SQLite | `0035 -> 0036 -> 0035 -> 0036` verde y downgrade con historia bloqueado |

La suite completa se ejecutó después de las correcciones de backend. La última iteración modificó
únicamente frontend y fue revalidada con prueba frontend, typecheck, build y flujo productivo local.

## 5. QA productiva local

Se levantó temporalmente el build Admin contra una SQLite desechable migrada a `0036`. Se usó una
credencial y asignación Dueño exclusivas de esa base temporal; ambos artefactos fueron eliminados al
terminar.

Resultados:

- navegación “Conceptos de caja” visible para Dueño;
- estado vacío y formulario visibles;
- alta `POST /api/v1/cash/concepts` HTTP 200;
- mensaje `Concepto publicado.` conservado después de recargar datos;
- código deshabilitado al publicar nueva versión;
- versión `PUT /api/v1/cash/concepts/{id}/versions` HTTP 200;
- historia incrementada de 1 a 2 sin borrar versión anterior;
- archivo confirmado con HTTP 200, estado `Archivado` e historia de dos versiones;
- viewport 1440×900: `document.scrollWidth == clientWidth`, componente contenido;
- viewport 768×900: `document.scrollWidth == clientWidth` y
  `main.scrollWidth == main.clientWidth`;
- servidor, navegador, enlaces, build y SQLite temporales retirados al terminar.

## 6. Gate PostgreSQL aislado aceptado

Con autorización explícita se descargó Postgres.app 2.9.5 y se ejecutó PostgreSQL 16.14 desde
`/private/tmp`, escuchando únicamente en localhost. No se instaló un servicio del sistema, no se
leyó ni modificó la `DATABASE_URL` original y no se usó Easypanel.

Evidencia de Sol:

- `alembic current -v` confirmó `PostgresqlImpl` y DDL transaccional;
- `0035 -> 0036 -> 0035 -> 0036` pasó sobre una base vacía;
- la huella SHA-256 determinista de las columnas legacy `cash_movements` fue idéntica antes y
  después de `0036`:
  `25647d3f31d518b33e13e6c99f66b0ca82576a62aeb5dd060dd7b5e57ac42f87`;
- con historia ficticia, el downgrade falló con
  `Safe downgrade blocked: cash concept history exists`, conservó la revisión `0036` y la fila;
- Terra añadió una suite opt-in que sólo acepta localhost y bases `pco002_*`, sin leer
  `DATABASE_URL`;
- Terra obtuvo `3 passed in 9.74s` en su base separada;
- Sol reconstruyó otra base desde cero y obtuvo `3 passed in 10.18s`;
- Sol ejecutó el conjunto dirigido SQLite/PostgreSQL/arquitectura: `15 passed in 33.81s`;
- Ruff dirigido y `git diff --check` quedaron verdes.

El gate técnico local de `PCO-002` queda aceptado y su matriz puede cambiar a `Implementado`. Commit,
publicación, migración en un ambiente compartido, despliegue y verificación de runtime continúan como
autorizaciones independientes y no forman parte de esta aceptación.

## 7. Siguiente incremento funcional

Una vez aceptado `PCO-002`, el siguiente paquete es `PCO-003`: ledger append-only de depósitos y
retiros, concepto efectivo obligatorio, referencia/evidencia, compensaciones y cálculo determinista
de efectivo esperado en Python. `PCO-003` no está implementado por este paquete.
