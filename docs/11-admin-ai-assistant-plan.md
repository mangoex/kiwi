# AIA-001 — plan, tareas y handoff del asistente Admin

Riesgo `R3`. Autorizado: especificación, implementación y pruebas locales. Excluido: commit, push,
merge, proveedor/red real, credenciales, despliegue, migración y datos productivos.

## Contrato de entrega

- Icono `UserRound` en la barra superior de Admin sin alterar avatar.
- Conocimiento canónico citado y Q&A fail-closed.
- Propuesta persistida de una acción allowlist, nunca escritura directa del modelo.
- Revisión sobre la pantalla de configuración con actual vs propuesto, fuentes y warnings.
- Aceptación humana, permiso de dominio, fingerprint, expiración, idempotencia y auditoría.
- Soporte vertical para producto, insumo, grupo/opción de modificador y receta versionada.

## Tareas

1. `AIA-001-DOC`: PRD-FR-230, PRD-NFR-030, SDD §43/ADR-034, BDD, TDD y matriz.
2. `AIA-001-PERSIST`: migración 0055, lifecycle y downgrade con historia bloqueado.
3. `AIA-001-PROVIDER`: contexto mínimo, esquema estricto, adaptador inyectable y fallo cerrado.
4. `AIA-001-VALIDATE`: evidencia humana, referencias, fuentes, snapshot y fingerprint.
5. `AIA-001-APPLY`: revisión/rechazo/aplicación por servicio canónico e idempotencia.
6. `AIA-001-UI`: trigger de persona, diálogo, deep link y revisión actual/propuesto.
7. `AIA-001-TEST`: RED/GREEN backend, migración, semántica frontend, TypeScript y trazabilidad.
8. `AIA-001-AUDIT`: revisión independiente requisito por requisito y reporte de gates omitidos.

## AIA-002A — endurecimiento previo a staging

1. Eliminar IDs BDD duplicados y volver verde el gate completo de trazabilidad.
2. Añadir PostgreSQL aislado de CI para migración, `FOR UPDATE` e idempotencia concurrente.
3. Ejecutar el recorrido sintético real en navegador para escritorio y móvil, con capturas.
4. Añadir observabilidad redactada de propuesta y decisión, sin prompt ni idempotency key.
5. Verificar con Node compatible, pruebas focales, typecheck, build y `git diff --check`.
6. Entregar runbook de staging default-off con canary, abortos y rollback; ejecutarlo requiere una
   autorización separada para credencial, configuración, migración y despliegue.

## Secuencia segura

Cada propuesta contiene una acción. Para un producto completo el asistente encadena, sin aplicar:
insumo(s) -> producto -> grupo -> opción(es) -> receta. El usuario revisa y acepta cada paso; una
dependencia todavía inexistente se formula como pregunta o propuesta posterior, nunca como ID
inventado. Un fallo no deja otro módulo parcialmente escrito por la misma aceptación.
