# Publicación de incrementos revisados AUD-2026-10-13

Autorización del usuario: commit, merge y push para que él haga el redeploy. Riesgo R3.
Esta publicación entrega los incrementos implementados; no declara terminado el plan de 31 tareas.
`execution.json` conserva el estado por tarea, decisiones D02/D03/D04 y pendientes fiscales,
de sucursales, cuentas por pagar y compensaciones. No se modifica producción desde esta tarea.

## Alcance

Compras corporativas: reparto exacto de cantidad/costo, snapshots por destino, validación de
catálogo y recuperación de la intención por cuenta. Sucursales: autoridad vigente, contexto
durable y recuperación del cliente, guardas focales de caja/KDS/impresión/sync. Facturación:
capacidades propias, elegibilidad de pago completo/no cancelado, descarga autenticada,
configuración cifrada/versionada por razón social y transporte acotado con rechazo de truncación.
Las auditorías independientes y pruebas dirigidas están registradas en los TDD de cada alcance.

F03 (comando fiscal durable, recuperación e impuestos exactos) y F04 (ciclo completo de estados)
siguen pendientes. La configuración explícita no acredita CSD, SAT ni uso productivo del proveedor.

## Evidencia local de publicación

- Ruff de `apps/api tests`: verde. Mypy de los 76 archivos de backend: verde. Se corrigieron cinco
  anotaciones faltantes en Agent Tools, sin cambiar decisiones de negocio; sus 15 pruebas verdes.
- Typecheck frontend: verde. Builds Admin/POS: verdes; conservan advertencias de tamaño de bundle.
- Arquitectura/dependencias/trazabilidad: 28 pruebas verdes. Política/ratchet: 14 pruebas verdes.
- Scanner y ratchet de diff: verdes; fixtures sintéticos registrados por ruta, procedencia y hash
  exactos. Sin cambiar el scanner ni añadir exclusiones de pruebas.
- Transporte fiscal/descarga: 51 pruebas verdes; los intentos mixtos anteriores se conservan en TDD.
- La suite semántica frontend y CI se reportan por su resultado real en el cierre Git. No se
  presentan como aprobados sólo por estos gates locales. Las suites PG dirigidas previas y sus
  repeticiones constan en TDD; no se sustituye el gate PG obligatorio de CI por SQLite.

## Preparación del redeploy por el usuario

El esquema pasa de `0082` a `0086_fiscal_emitters` mediante cuatro revisiones aditivas. Los
Dockerfiles ejecutan uvicorn, no Alembic. Respaldar PostgreSQL y aplicar la cadena de migraciones
con el código publicado antes de habilitar las nuevas rutas (`python -m alembic -c alembic.ini
upgrade head` desde `apps/api`, usando la conexión del entorno correspondiente). Los downgrades
que eliminarían historia/configuraciones/contextos se bloquean; no forzar su eliminación.

La configuración fiscal nueva necesita un keyring explícito:
`RESTAURANTOS_FISCAL_ENCRYPTION_KEYS` (mapa de key-id a clave base64 de 32 bytes) y
`RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID`. Retener las claves antiguas para leer versiones
históricas. Nunca usar la clave de sesión como sustituto ni incluir secretos en Git. Configurar
razón social/ambiente/credencial en la nueva pantalla; legacy no habilita un emisor nuevo.

Comprobar salud y recuperación de sesión/contexto de una sucursal; compras con entradas vacías y
replay; lector fiscal y configuración por razón social. Registrar el SHA desplegado. Canary,
migración, configuración y comportamiento productivos requieren su autorización operativa;
el push de Git por sí solo no prueba el redeploy.
