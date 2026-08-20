# SEC-001 — handoff Terra de contención de seguridad

**Estado:** autorizado el 2026-08-19 para implementación y pruebas aisladas por Terra; auditoría Sol
obligatoria. **Riesgo:** R3. **Decisión:** ADR-030 aprobada.

## Autoridad y objetivo

Leer README/AGENTS/skill y FR-221/222, NFR-006/026/027, SDD §39.1/39.3/39.4,
BDD-SC-355..360, TDD-TS-089/TC-141..145, CONS-024/025/027/031. Implementar sólo `SEC-001A`:
frontera default-deny, seed interno, estado real de impresión y policy gate de repositorio.

## Exclusiones

- No cambiar visibilidad GitHub, reescribir historia, rotar credenciales o eliminar clones/releases.
- No usar datos reales, `DATABASE_URL`, Easypanel, deploy o migración productiva.
- No ampliar comandos PCO-008 ni rediseñar RBAC humano.
- No implementar cortesía, proveedores, compras o pedido público.

## Secuencia RED → GREEN

1. Desde branch/worktree limpio fijado por Sol, inventariar rutas/router y archivos tracked por path;
   nunca imprimir contenido sensible.
2. Escribir TC-141..145 y guardar RED exacto. La prueba debe invocar rutas/servicios, no buscar texto.
3. Implementar guard común de actor/capacidad/scope y credenciales rotables de dispositivo; modelo y
   migración sólo si el esquema vigente no permite identidad segura.
4. Quitar routes seed y crear comando interno con manifest estricto, dry-run/apply/replay/audit.
5. Aplicar guard a KDS/sync/print; respuestas no enumeran recursos cross-scope.
6. Hacer que retry encole un intento. Sólo ack del agente transita a PRINTED; fallos son atómicos.
7. Añadir `.gitignore` y scanner determinista de paths/firmas con allowlist sintética. Retirar del
   árbol tracked sólo archivos expresamente identificados; no tocar historia.
8. Integrar gate en CI de PR y rama protegida. Reporte sólo path/clase.
9. Ejecutar GREEN focal, migraciones si aplican, Ruff, arquitectura y `git diff --check`.

## Gates

- API: anónimo/credencial inválida/revocada/capacidad/branch/org y replay.
- Impresión: `FAILED -> QUEUED -> CLAIMED -> PRINTED` sólo por ack; carreras y fallo inyectado.
- Repo: fixture temporal prohibido falla; fixture sintético permitido pasa; no filtra marcador.
- PostgreSQL sólo con `SEC001_TEST_POSTGRES_URL` y base `sec001_*`; si no hay migración, justificar
  por qué el gate no aplica. Nunca leer variable genérica.
- CI actual en PR, no workflow histórico.

## Entrega a Sol

Sin commit/push: archivos, diff stat, RED/GREEN exactos, rutas cubiertas, migración/rollback, logs,
gates omitidos, `git status --short` y `git diff --check`. Sol reejecuta TC-141/143/144/145. Una vez
auditado se solicita publicación. `SEC-001B` se planifica y autoriza aparte.
