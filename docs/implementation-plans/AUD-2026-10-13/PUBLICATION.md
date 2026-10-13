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

## Correcciones detectadas por CI durante la publicación

El selector E2E de conciliación identifica el desplegable por su opción de sucursales, sin asumir
su posición en la página; el recorrido real Admin/POS pasó localmente. La semilla offline ahora
selecciona todas las columnas explícitas: preserva la versión de autorización y vuelve a hidratar
el bundle exacto. Diez pruebas catálogo/gateway, E2E POS pago/KDS, Ruff y mypy verdes localmente.
Auditoría independiente: conservación 7→9 al renovar y rechazo de versión ausente/columna adicional
sin instalación parcial. Afirmación: no hay fallback de autoridad; resultado refutado con esos casos.
Riesgo residual: la fuente debe tener la migración de versión aplicada; no se habilita una fuente
anterior por tolerancia. La firma/reinicio se comprueban en la prueba de runtime existente.

Los tests funcionales PostgreSQL usan head. Sólo sus casos de reversibilidad aíslan la revisión
0055/0065/0071/0073 que verifican; el caso de combos inicia en 0082 porque la ejecución actual
requiere el esquema de modificadores compartidos posterior a 0066. Conservan los rechazos de historia y no evitan la revisión
0085 en producción. El gate estructural exige head 0086. La prueba 0077 comprueba lectura legacy
con V2 apagado y rechazo de migración incompleta al encenderlo. Crossorg conserva rechazo opaco
y cero asignación. No se cambiaron guardas, skips ni silenciamientos para obtener verde.

PostgreSQL focal: 13 verdes y un timeout local de Alembic. La primera repetición de combos en
0066 rechazó un esquema sin modificadores compartidos; con baseline 0082 pasó en 25.09 s y
conservó el rechazo exacto de historia 0066. Cada intento mantiene su XML separado.
SQLite 0077: la ejecución interrumpida se conserva y su repetición pasó
en 21.36 s. Arquitectura/perfiles: 25 verdes independientes; mypy completo de backend y Ruff verdes.
Estas evidencias no reemplazan el resultado de CI sobre el SHA final.

Preguntas operativas del ajuste offline: ¿se instaló el bundle esperado? Comprobar readiness e
identidad del bundle en el estado local. ¿Por qué se rechazó la instalación? Conservar el código
`offline_bundle_catalog_invalid` y la revisión del esquema, sin registrar payloads ni credenciales.

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
