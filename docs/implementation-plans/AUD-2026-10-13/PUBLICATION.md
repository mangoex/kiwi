# Publicación de incrementos revisados AUD-2026-10-13

Autorización del usuario: commit, merge y push para que él haga el redeploy. Riesgo R3.
Esta publicación entrega los incrementos implementados; no declara terminado el plan de 31 tareas.
`execution.json` conserva el estado por tarea, decisiones D02/D03/D04 y pendientes fiscales,
de sucursales, cuentas por pagar y compensaciones. No se modifica producción desde esta tarea.

## Alcance del primer paquete (PR 68)

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

El siguiente gate Python de CI pasó 1761 pruebas, con ocho skips y una falla del downgrade offline:
la fixture recreaba permisos y se detenía en 0085 antes de llegar a la guarda 0067. El replay ahora
conserva una variante `head` y otra `0077`; ambas comprueban snapshot, concurrencia y revocación.
La histórica exige mensaje 0067, inbox conservado y revisión 0077 tras rollback. El primer intento
desde 0082 pasó los dos casos actuales, pero encontró la frontera autocommit del índice 0079;
su XML de 1 falla/2 verdes se conserva. La variante definitiva 0077 pasó en 26.01 s. Ruff,
trazabilidad (9 verdes) y revisión independiente focal sin bloqueantes; no cambios a migraciones,
guardas ni skips. CI debe confirmar el último SHA antes de integrar.

Frontend CI aprobó en `57313f1`: semántica, builds y E2E Admin/POS, conciliación, gastos, gateway,
catálogo, sucursales, fiscal, asistente y shells offline. La barra superior ya no se contrae en
móvil; el recorrido completo y la inspección visual local verificaron acceso al asistente.

Preguntas operativas del ajuste offline: ¿se instaló el bundle esperado? Comprobar readiness e
identidad del bundle en el estado local. ¿Por qué se rechazó la instalación? Conservar el código
`offline_bundle_catalog_invalid` y la revisión del esquema, sin registrar payloads ni credenciales.

## Preparación del redeploy del primer paquete

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

## Segundo paquete: PR 69

La PR 69 integra el código revisado hasta `6acab5b`: preparación fiscal privada durable,
JSON decimal exacto, reconciliación del neto pagado, lectura fiscal histórica autorizada,
auditoría y rollback del replay de workspace, y registro compartido de concesiones offline.
Es un incremento del plan; `execution.json` conserva las tareas parciales y pendientes.

Las auditorías independientes de estos alcances están cerradas sin bloqueantes abiertos.
CI sobre `6acab5b` (run `38496167613`) terminó con 1892 pruebas verdes, ocho skips y dos fallos;
el gate Python falló:
la prueba de downgrade fiscal esperaba alcanzar 0087 desde head, pero 0088 protegió primero
su evidencia offline. Se conservan las carreras en head y se añade un caso aislado 0087 que
exige su rechazo exacto y conservación de las cuatro tablas fiscales. No se cambian migraciones,
guardas ni skips; el verificador obliga a ejecutar el caso nuevo. El SHA posterior necesita
confirmación de CI antes del merge. Esta guía distingue la evidencia anterior de ese resultado.

Corrección local: seis pruebas PG verdes (239.09 s) y repetición final de los dos casos head
con conservación ampliada de seis tablas (97.13 s). Arquitectura/trazabilidad/verificador:
32 verdes; scanner, Ruff y diff-check verdes. Revisión independiente focal sin hallazgos;
se conserva el resultado rojo original de CI. No cambia runtime de la versión revisada.

CI `559ede8` (run `38499379049`) aprobó 1895 pruebas, con ocho skips/siete warnings,
el gate de los once módulos PostgreSQL y mypy81. El run falló por E501 de una línea de
101 caracteres en `models.py` y por timeout de foco del modal de catálogo en frontend.
La línea se dividió con AST idéntico y Ruff completo/mypy81 locales verdes. La prueba
de navegador existente pasó localmente en escritorio/móvil sin cambiar UI ni su aserción.
Se conserva el fallo original; el SHA siguiente requiere CI final antes del merge.

### Esquema del segundo paquete

El head del segundo paquete es `0088_offline_authorization`. Si ya se aplicó el primer paquete
hasta 0086, faltan las revisiones aditivas `0087_fiscal_commands` y
`0088_offline_authorization`; si la base sigue en 0082, Alembic recorre toda la cadena.
Los contenedores no ejecutan estas migraciones al iniciar. Respaldar PostgreSQL y aplicar
`python -m alembic -c alembic.ini upgrade head` desde `apps/api`, con el código y la conexión
del entorno correspondiente. Verificar `alembic current` antes de servir rutas del nuevo esquema.
No forzar downgrades: 0087 bloquea eliminación de intención fiscal existente y 0088 bloquea
eliminación de evidencia de autoridad offline.

### Límites operativos para el redeploy

0088 deja las organizaciones existentes en `unprepared`, sin inventar fechas de cutover,
versiones de concesiones históricas ni readiness. Con V2, una transición de sucursal sin
preflight válido devuelve `branch_offline_preflight_required`; una concesión incompatible
vigente devuelve `branch_switch_offline_grant`. La revocación sólo en central no elimina
el bloqueo del TTL del token desconectado. No cambiar manualmente el estado a
`clean_install`: ese estado en las pruebas corresponde a una organización sintética recién
creada. El mecanismo de adopción controlada, la versión firmada y el registro de comandos
inciertos siguen pendientes; esta publicación no habilita movilidad de organizaciones existentes.

La preparación fiscal conserva `dispatch_ready=false`, sin ruta pública, worker ni envío al
PAC. No acredita el cierre de F03/F04, impuestos/conceptos ni recuperación de emisión externa.
La configuración cifrada continúa requiriendo el keyring explícito del primer paquete.
Comprobar salud, recuperación de sesión y lectura fiscal permitida; no emitir CFDI para
validar este incremento privado. Conservar el SHA desplegado y los códigos de rechazo.
El redeploy, las migraciones y la configuración productivos quedan a cargo del usuario.
