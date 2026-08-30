<!-- SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-easypanel-runbook-v1 -->
# Operacion en Easypanel

## Objetivo

Dejar la API de RestaurantOS conectada a PostgreSQL y Redis en Easypanel sin introducir logica de negocio completa.

## Servicios esperados

| Servicio | Tipo | Nombre sugerido | Puerto interno |
|---|---|---|---|
| API | App desde GitHub | `paperclip-kiwirestaurante` | `8000` |
| PostgreSQL | Database | `kiwi-postgres` | `5432` |
| Redis | Database/cache | `kiwi-redis` | `6379` |

## Variables de entorno de la API

La API acepta variables normales o prefijadas. En Easypanel se recomienda usar:

```env
RESTAURANTOS_ENVIRONMENT=production
RESTAURANTOS_SERVICE_NAME=restaurant-os-api
RESTAURANTOS_GIT_COMMIT=SHA_COMPLETO_DEL_COMMIT_PUBLICADO
RESTAURANTOS_DATABASE_URL=postgresql+psycopg://restaurantos:TU_PASSWORD@kiwi-postgres:5432/restaurantos
RESTAURANTOS_REDIS_URL=redis://kiwi-redis:6379/0
SECRET_KEY=CAMBIAR_POR_UN_SECRETO_LARGO
LOG_LEVEL=info
```

Si Easypanel entrega nombres internos distintos, reemplazar `kiwi-postgres` y `kiwi-redis` por los hosts reales.

### Pedido asistido con OpenRouter (POS-AI-002)

Esta integración no requiere migración. En el servicio **API** de Easypanel, abre **Environment** y
agrega estas variables; la clave es un secreto de servidor y está prohibido configurarla en el
frontend, en `VITE_*`, en Git o en una captura de pantalla:

```env
RESTAURANTOS_ASSISTED_ORDER_ENABLED=true
RESTAURANTOS_OPENROUTER_API_KEY=sk-or-v1-REEMPLAZAR
RESTAURANTOS_OPENROUTER_MODEL=google/gemini-3.1-flash-lite
RESTAURANTOS_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
RESTAURANTOS_OPENROUTER_TIMEOUT_SECONDS=10
RESTAURANTOS_OPENROUTER_HTTP_REFERER=https://TU-DOMINIO-PUBLICO
RESTAURANTOS_OPENROUTER_APP_TITLE=Kiwi RestaurantOS POS
```

`HTTP_REFERER` es identificación opcional de la aplicación, no una credencial. Guarda las variables y
haz redeploy únicamente cuando el release haya sido aprobado. La API falla cerrada si la función está
apagada o falta la clave. Para deshabilitarla sin retirar código, cambia
`RESTAURANTOS_ASSISTED_ORDER_ENABLED=false` y redeploy; el POS manual sigue funcionando.

Verificación posterior, usando una sesión real de Cajero y sin copiar PII a logs:

1. Abre `/pos`, confirma que junto a la sucursal aparece sólo el icono de persona.
2. Envía una frase sintética y confirma que el diálogo identifica un producto.
3. Omite una opción obligatoria y confirma que pregunta usando sólo opciones del catálogo.
4. Selecciona las respuestas y confirma que **Agregar al pedido** se habilita, sin crear todavía una orden.
5. Revisa logs: deben mostrar resultado/modelo/sucursal, nunca frase, nombre, teléfono ni payload.
6. Prueba reversión apagando la bandera; el endpoint debe responder no configurado y la venta manual debe continuar.

La clave puede validarse de forma administrativa en OpenRouter, pero no debe imprimirse en la consola.
Configura límites de crédito y alertas en la cuenta de OpenRouter antes de habilitar producción.

El dictado no requiere variable en Easypanel. El POS muestra **Dictar** automáticamente cuando el
navegador implementa `SpeechRecognition`; al pulsarlo, el navegador solicita permiso de micrófono.
El audio no se envía a OpenRouter desde RestaurantOS, aunque el fabricante del navegador puede usar
sus propios servicios de reconocimiento. Si no existe esa API o se deniega permiso, permanece la
captura escrita.

## Health checks

Abrir:

```text
/health/live
/health/ready
/health/version
/docs
```

`RESTAURANTOS_GIT_COMMIT` es metadato operativo, no autoridad para elegir código. EasyPanel debe
seguir configurado contra el branch aprobado y su historial de build debe mostrar el mismo commit.
Antes de cada redeploy actualizar esta variable al SHA completo que se va a publicar; después,
`/health/version` debe coincidir exactamente. Un SHA anterior no implica que el contenedor haya
fallado, pero deja el release sin trazabilidad suficiente y bloquea el criterio de listo. No cambiar
`DATABASE_URL` ni sustituir `kiwi-postgres` para corregir metadatos de versión.

## Métricas operativas PCO-004

La API emite logs estructurados con los campos `metric`, `result`, `branch_id`,
`error_code` y, cuando aplica, `value`. No incluyen claves de idempotencia,
payloads ni datos personales. Alertar por resultados `error` o `conflict` de:

- `cash_shift_open_total`;
- `cash_shift_operational_close_total`;
- `cash_shift_guard_conflict_total`;
- `sales_monitor_request_total`;
- `sales_monitor_incomplete_operations` (su `value` es el número de operaciones incompletas).

Un `result=replay` confirma que la operación fue respondida idempotentemente; no
es un cierre u apertura nueva. Antes de reintentar un `conflict`, revisar el
turno y la autorización de sucursal con el identificador de sucursal del log.

## Acceso a la plataforma

Abrir la URL publica del servicio API:

```text
/
/admin
/pos
/kds
```

En `/admin` se pueden crear roles, crear usuarios con contraseña temporal y
asignar roles. Si un usuario se crea sin contraseña queda en estado `invited`;
si se crea con contraseña temporal queda `active` y puede iniciar sesion.

La consola Admin ya incluye login inicial. La cuenta superadmin semilla es
`mangoex@gmail.com`; su contraseña se guarda como hash, no como texto plano.
Desde esa cuenta se pueden crear administradores operativos con contraseña
temporal y despues asignarles el rol `Administrador corporativo` o un rol de
sucursal.

`/health/ready` responde:

- `ok` cuando Postgres y Redis estan configurados y accesibles.
- `degraded` cuando falta una variable o una dependencia no responde.

## Migraciones

La fase 0.2 incluye Alembic con tablas base de organizacion, sucursal, almacen, roles, usuarios y auditoria.

### PCO-005B — correcciones compensatorias

Este procedimiento aplica sólo al release que contiene `0040_order_corrections`.

1. Genera un respaldo recuperable de PostgreSQL antes del redeploy.
2. Redeploy de la imagen aprobada y, desde la consola del servicio API, confirma el punto de partida:

```bash
cd /app/apps/api
alembic current -v
```

Debe mostrar `0039_order_reopen_requests` antes de la migración PCO-005B.

3. Aplica únicamente la cadena real de migraciones y confirma la head:

```bash
alembic upgrade head
alembic current -v
```

El resultado esperado es `0040_order_corrections (head)`. El procedimiento productivo usa la
`RESTAURANTOS_DATABASE_URL` ya configurada por la app; está prohibido usar `alembic stamp` o
sustituirla por `DATABASE_URL` o por URLs de prueba.

4. Confirma `/health/ready` con PostgreSQL y Redis en `ok`. Haz un smoke no destructivo: abre cuentas
   y la cola, confirma que cargan sin `UndefinedTable` y que la UI muestra PCO-005B. No apliques una
   corrección sin una solicitud `APPROVED` autorizada.
5. Sólo considera rollback si no existe historia de correcciones, líneas o ajustes PCO-005B. Respeta
   las guardas de downgrade de Alembic; si ya existe historia, no fuerces rollback y escala el caso.

El contenedor web no ejecuta migraciones automaticamente al arrancar. Esto evita que
un error temporal de Postgres, una URL mal configurada o una migracion parcial tumbe
el proceso web y genere `502 Bad Gateway`. Primero debe levantar la API; despues se
ejecuta Alembic desde la consola del servicio API o como job operativo separado.

### PCO-006 — corte por usuario (0041)

La migración `0041_user_cash_cuts` requiere una ventana de mantenimiento: no se debe
aceptar tráfico ni escrituras de API o worker durante el cambio. Antes de intervenir,
genera un snapshot recuperable y prepara la imagen nueva, pero no la pongas a servir.

1. Detén tráfico, API y worker; confirma que no quedan escrituras en curso.
2. Desde la imagen compatible nueva, ejecuta `alembic upgrade 0041_user_cash_cuts` contra la
   `RESTAURANTOS_DATABASE_URL` productiva ya configurada.
3. Confirma `alembic current -v`, inicia API/worker de la imagen nueva y verifica
   `/health/ready` antes de reabrir tráfico.
4. Si falla antes de crear historia PCO-006, restaura el snapshot o aplica el downgrade guardado;
   si existe historia PCO-006, no fuerces downgrade ni modifiques filas históricas: escala el caso.

Para validar que la API puede conectarse a Postgres desde el contenedor, ejecutar en la consola del servicio API:

```bash
cd /app/apps/api
alembic upgrade head
```

Si ya habias ejecutado este comando antes, vuelve a correrlo. La migracion nueva aplicara solo lo pendiente.

Para `POS-CAT-002/003`, la revision esperada despues del despliegue es
`0028_global_order_comments_extras`. Si la pantalla **Comentarios del pedido** muestra
`No fue posible cargar comentarios`, comprobar primero `alembic current -v` y ejecutar el upgrade
anterior; no usar `alembic stamp`.

Esto crea la tabla tecnica de Alembic, las tablas base y el seed inicial:

- organizacion `Kiwi Restaurante`,
- razon social placeholder,
- `Sucursal Piloto`,
- almacen formal de la sucursal,
- usuario administrador invitado,
- rol de administrador corporativo,
- evento de auditoria del bootstrap,
- catalogo minimo con categorias, productos, precios vigentes y disponibilidad por sucursal.

Las migraciones posteriores agregan:

- turno de caja minimo,
- pedidos locales aceptados desde POS,
- lineas de pedido,
- eventos de pedido,
- tareas KDS por estacion,
- pagos confirmados e inmutables,
- corte final de caja con ventas, efectivo esperado, efectivo contado y diferencia,
- trabajos de impresion simulada para ticket y comanda,
- comandos de sincronizacion idempotentes,
- eventos de sincronizacion con checkpoint por sucursal.
- credenciales hasheadas para el superadmin inicial.

Despues de cada push con migraciones nuevas, repetir:

```bash
cd /app/apps/api
alembic upgrade head
```

### Correccion de capacidad de identificadores de revision (DB-001)

Sintoma exacto: al ejecutar `alembic upgrade head` sobre una base detenida en `0013_pos_cash_rbac_permissions`, PostgreSQL rechaza la transaccion antes de registrar `0014_legacy_caja_role_permissions` con:

```text
StringDataRightTruncation: value too long for type character varying(32)
UPDATE alembic_version SET version_num='0014_legacy_caja_role_permissions'
```

Causa: `alembic_version.version_num` es `VARCHAR(32)` y los identificadores de revision 0014 a 0018 miden entre 33 y 37 caracteres. La transaccion se revierte y la base permanece en `0013_pos_cash_rbac_permissions`.

Esta prohibido usar `alembic stamp` para forzar el avance. La cadena debe avanzar con la migracion puente real.

Procedimiento de despliegue en Easypanel:

1. Antes de operar, genera un respaldo de la base (snapshot de PostgreSQL en Easypanel o `pg_dump`).
2. Verifica la revision actual:

```bash
cd /app/apps/api
alembic current -v
```

Debe mostrar `0013_pos_cash_rbac_permissions`.

3. Avanza la cadena completa, incluyendo la migracion puente que amplía `version_num`:

```bash
alembic upgrade head
```

4. `0023_physical_counts` es el punto de control posterior a DB-001. En una versión que ya contiene
   BA-001, el resultado final esperado es `0024_branch_admin_scope`.
5. Verificacion posterior: ejecuta `alembic current -v` y confirma que la base terminó en la head
   incluida en la imagen desplegada. Abre `/health/ready` y confirma `postgres: ok`.

La migracion puente es `0013a_expand_version_num`, que amplía `alembic_version.version_num` a `VARCHAR(128)` en PostgreSQL. En SQLite la operacion es un no-op porque SQLite no impone el limite de longitud. La cadena de revisiones permanece lineal y reversible.

Para validar el flujo de fase 1 despues de migrar:

1. Abrir `/pos`.
2. Abrir caja con fondo inicial.
3. Crear pedido desde un producto del catalogo.
4. Cobrar el pedido por el total exacto.
5. Revisar los trabajos de impresion simulada.
6. Reintentar ticket o comanda para marcarlo como impreso.
7. Registrar efectivo contado y cerrar caja.
8. Enviar un comando a `/api/v1/sync/commands` y confirmar que devuelve checkpoint.
9. Abrir `/api/v1/sync/events` para confirmar descarga de eventos pendientes.
10. Abrir `/api/v1/sync/status` para revisar ultimo checkpoint y conteos.

### Administración operativa por sucursal (BA-001)

Antes de desplegar BA-001, genera respaldo de PostgreSQL. Después del redeploy:

```bash
cd /app/apps/api
alembic current -v
alembic upgrade head
alembic current -v
```

El resultado esperado es una única head `0024_branch_admin_scope`. No uses `alembic stamp`.

Verificación mínima:

1. `/health/ready` mantiene PostgreSQL y Redis en `ok`.
2. Un Supervisor de sucursal vuelve a iniciar sesión para recibir los permisos migrados.
3. `GET /api/v1/auth/session` devuelve `scope.level=branch`, su `assigned_branch_id` y
   `branch.admin.access`.
4. El mismo Supervisor recibe 403 si solicita el contexto de otra sucursal.
5. Un Cajero recibe 403 en `/api/v1/branch-administration/context`.
6. Cambiar disponibilidad y luego usar `inherit` conserva el producto central y elimina sólo la
   excepción local.

Rollback técnico, únicamente si la aplicación aún no depende de los permisos nuevos:

```bash
cd /app/apps/api
alembic downgrade 0023_physical_counts
```

El downgrade no elimina roles, usuarios ni operación histórica. Después de un rollback de código y
migración, valida nuevamente `/health/ready`.

### Centro administrativo POS de sucursal (BA-003)

BA-003 no agrega migraciones. Depende de que BA-001 ya haya dejado PostgreSQL en
`0024_branch_admin_scope`; si producción sigue en `0023_physical_counts`, el cliente no debe
inventar permisos y la opción Administración permanecerá oculta.

Verificación posterior al redeploy:

1. Ejecuta `alembic current -v` en el servicio API y confirma `0024_branch_admin_scope`.
2. Cierra la sesión de la Supervisora y vuelve a iniciarla para refrescar la sesión canónica.
3. Confirma que el menú POS muestre Administración y abra `/pos/administration` sin cambiar a
   `/admin`.
4. Confirma las ocho tarjetas: Productos y recetas, Insumos, Proveedores, Compras, Producción,
   Mermas, Traspasos y Conteos físicos.
5. Confirma que no existan tarjetas de Sucursales, Usuarios, Roles ni Personal.
6. Abre cada resumen y verifica que el encabezado muestre la sucursal asignada a la Supervisora.
7. Inicia sesión con un Cajero y confirma que Administración no aparezca y que una URL directa sea
   rechazada.

Los seis resúmenes nuevos son de consulta en BA-003. Las mutaciones sensibles continúan en sus
flujos existentes y conservan permisos, idempotencia y auditoría del backend.

### Importación privada de catálogos de Constitución (DATA-001)

Los cinco Excel son datos operativos privados. No deben agregarse a Git, copiarse a la imagen ni
pegarse en la consola. El adaptador `tools/import_legacy_branch_catalogs.py` los lee localmente y
envía contratos JSON por HTTPS, con un máximo de 500 filas por petición.

1. Respalda PostgreSQL y despliega la versión que incluye DATA-001.
2. En la consola API ejecuta:

```bash
cd /app/apps/api
alembic upgrade head
alembic current -v
```

Debe mostrar una única head `0025_legacy_branch_catalog_import` y `/health/ready` debe continuar en
`ok`.

3. En el equipo que conserva los Excel valida sin transmitir datos:

```bash
cd /ruta/privada/Kiwi
python3 tools/import_legacy_branch_catalogs.py .
```

4. Define sólo el correo en el entorno y ejecuta la carga; la contraseña se solicita sin eco y no
queda en el historial:

```bash
export RESTAURANTOS_IMPORT_EMAIL='correo-del-administrador'
python3 tools/import_legacy_branch_catalogs.py . \
  --apply \
  --api-url 'https://dominio-del-servicio'
unset RESTAURANTOS_IMPORT_EMAIL
```

También puede definirse temporalmente `RESTAURANTOS_IMPORT_TOKEN` en vez de contraseña. Nunca se
debe compartir el token en chat, commit o captura. El cargador resuelve Constitución por nombre o
código; si hay ambigüedad, se usa `--branch-id` con el id obtenido del administrador.

5. En `/admin/imports`, selecciona Constitución y verifica conteos. Completa la estación de cada
producto en `/admin/products` y actívalo sólo después de revisar categoría, precio y flujo de
producción. Vincula proveedores y recetas en sus módulos; no fuerces presentaciones ni recetas desde
la bandeja.

Verificación de aislamiento:

- el administrador corporativo ve el lote y todos sus registros;
- la Supervisora de Constitución ve productos, insumos y clientes centrales más los de su sucursal;
- un Supervisor de otra sucursal no ve los registros exclusivos de Constitución;
- el POS no muestra productos `needs_review`;
- no se crean movimientos ni costos promedio como consecuencia de los costos heredados.

Reintentar el mismo comando es seguro: manifiesto y claves de fila son idempotentes. No borres ni
edites directamente registros operativos para repetir la carga. Para revertir antes de usar la nueva
estructura, restaura el respaldo; el downgrade técnico a `0024_branch_admin_scope` elimina tablas de
importación y columnas de alcance, por lo que requiere respaldo y ventana de mantenimiento.

### Depuración y catálogo corporativo compartido (DATA-003)

DATA-003 depura la carga heredada sin borrar físicamente productos, categorías o insumos que puedan
estar referenciados por pedidos, recetas o movimientos. Los registros inválidos quedan archivados y
la migración conserva sus valores previos en `catalog_cleanup_records`.

1. Genera un snapshot de PostgreSQL o un `pg_dump` verificable.
2. Despliega la imagen que contiene la revisión `0027_catalog_cleanup`.
3. En la consola del servicio API ejecuta:

```bash
cd /app/apps/api
alembic current -v
alembic upgrade head
alembic current -v
```

La revisión final debe ser `0027_catalog_cleanup (head)`. No uses `alembic stamp`.

4. Confirma `/health/ready` con PostgreSQL y Redis en `ok`.
5. Con sesión de administrador consulta `GET /api/v1/catalog/cleanup-status`. Debe responder
   `status: completed`, `revision: 0027_catalog_cleanup` y únicamente conteos.
6. Verifica en administración:

- productos retenidos con SKU numérico sin comilla inicial, nombre en mayúsculas y estado activo;
- categorías visibles únicamente en mayúsculas;
- insumos visibles únicamente con SKU numérico;
- bebidas en `drinks`, comida en `kitchen` y empaques en `packing`;
- el mismo catálogo de productos, categorías e insumos en dos sucursales;
- existencias, almacenes, clientes y movimientos todavía aislados por sucursal;
- productos sin precio positivo visibles para revisión administrativa, pero ausentes del cobro POS.

La migración no inventa precios, recetas, proveedores ni existencias. Tampoco modifica pedidos,
pagos, costos o movimientos históricos.

Rollback técnico, sólo durante una ventana de mantenimiento y antes de depender de identidades
nuevas creadas después del despliegue:

```bash
cd /app/apps/api
alembic downgrade 0026_ingredient_variations
```

El downgrade restaura SKU, categoría, estación, estado, alcance y excepciones locales respaldadas.
Después del rollback valida `/health/ready` y los conteos históricos; si la aplicación ya operó con
el catálogo normalizado, restaura el snapshot en lugar de mezclar historia nueva con identidades
anteriores.

### Pedidos pendientes de pago y enmiendas POS (POS-PAY-003)

La revisión `0029_order_amendments_deferred` agrega la intención de pago, la versión del pedido y
el historial inmutable de enmiendas. Antes del redeploy genera un snapshot verificable de
PostgreSQL. Después de desplegar, ejecuta:

```bash
cd /app/apps/api
alembic current -v
alembic upgrade head
alembic current -v
```

La revisión final debe ser `0029_order_amendments_deferred (head)`. No uses `alembic stamp`.
Confirma que `/health/ready` continúe con PostgreSQL y Redis en `ok`; después crea un pedido para
llevar, verifica que aparezca pendiente en **Pedidos**, edítalo antes de iniciar producción y
confirma el pago con el medio realmente recibido.

El downgrade sólo es seguro antes de registrar intenciones de pago, versiones modificadas o
enmiendas. Si la sucursal ya operó este flujo, restaura el snapshot en una ventana de mantenimiento
en vez de eliminar su historial.

### Catálogo administrativo de repartidores (PRD-FR-210)

La revisión `0030_driver_catalog` agrega el catálogo corporativo de repartidores asignados a
sucursal. Antes del redeploy genera un snapshot verificable de PostgreSQL. Después de desplegar:

```bash
cd /app/apps/api
alembic current -v
alembic upgrade head
alembic current -v
```

La revisión final debe ser `0030_driver_catalog (head)`. Confirma `/health/ready`, abre
**Repartidores** en Administración, registra un repartidor de prueba y verifica que la sucursal
asignada aparezca en el listado.

El downgrade a `0029_order_amendments_deferred` se bloquea cuando existe cualquier repartidor,
porque eliminar la tabla destruiría datos personales y futuras referencias operativas. Si ya hay
registros, revierte usando el snapshot dentro de una ventana de mantenimiento.

### Asignación de repartidores a pedidos a domicilio (PRD-FR-211)

La revisión `0031_delivery_assignments` agrega el registro inmutable que vincula pedido, cliente,
repartidor, sucursal, domicilio capturado, importe y cantidades al momento de la asignación. Antes
del redeploy genera un snapshot verificable de PostgreSQL. Después de desplegar:

```bash
cd /app/apps/api
alembic current -v
alembic upgrade head
alembic current -v
```

La revisión final debe ser `0031_delivery_assignments (head)`. Confirma `/health/ready`; en el POS
crea un pedido **A domicilio**, abre **Cobrar pedido**, asigna un repartidor activo de la sucursal y
guarda el pedido. En Administración abre **Repartidores** y verifica que **Historial de entregas**
muestre el folio, cliente, importe, líneas y unidades del pedido.

El downgrade a `0030_driver_catalog` se bloquea cuando existe cualquier asignación. No elimines ni
edites directamente estos registros: una reasignación futura debe conservar la asignación original
y registrar una compensación auditable. Si ya hay entregas, revierte con el snapshot en una ventana
de mantenimiento.

### Checador y recuperación del rol superadministrador (PRD-FR-212)

La revisión `0032_attendance_clock` agrega los códigos laborales y las checadas. La revisión
correctiva `0033_restore_superadmin_role` restaura idempotentemente el rol `Administrador
corporativo` de la cuenta superadministradora canónica si una edición propia fallida ejecutada con
una versión anterior lo eliminó. No cambia contraseña, código de empleado ni otros usuarios.

Después del redeploy ejecuta desde la consola del servicio API:

```bash
cd /app/apps/api
alembic current -v
alembic upgrade head
alembic current -v
```

La revisión final debe ser `0033_restore_superadmin_role (head)`. No uses `alembic stamp`. Cierra
la sesión del navegador, vuelve a iniciar sesión y confirma que `GET /api/v1/auth/session`, Usuarios
y Repartidores dejan de responder 403. La migración conserva el rol reparado al hacer downgrade,
porque retirarlo volvería a bloquear la administración; sólo elimina su evento técnico de reparación.

### PCO-004: cierre operativo y monitor de ventas

La revisión `0038_cash_shift_closures_sales_monitor` crea cierres operativos separados del corte,
congela familia y ventas históricas y amplía el índice de turno activo para incluir `OPEN` y
`CLOSING`. Antes del redeploy genera un snapshot verificable de PostgreSQL. No uses `alembic stamp`
ni edites pagos, turnos, líneas o snapshots directamente para superar un preflight.

Primero verifica que la imagen desplegada contiene una sola head y que producción continúa en
`0037_cash_movement_ledger`:

```bash
cd /app/apps/api
alembic heads
alembic current -v
```

`alembic heads` debe mostrar únicamente `0038_cash_shift_closures_sales_monitor (head)`. Ejecuta el
upgrade como job operativo o desde la consola API:

```bash
alembic upgrade 0038_cash_shift_closures_sales_monitor
alembic current -v
```

La migración falla cerrada antes de crear historia ambigua si detecta turnos `OPEN|CLOSING`
duplicados para una caja, familia vacía o una relación organización-pedido-producto-categoría
incoherente. Para pagos `CONFIRMED`, el único alias histórico de servicio permitido es el valor exacto
`takeaway`: genera snapshot `takeout` sin actualizar `orders.order_type`. No normalices ni edites el
pedido para superar el preflight; cualquier otro tipo desconocido se investiga y corrige mediante un
procedimiento auditado antes de repetir el mismo upgrade.

Verificación posterior sin consultar importes ni datos personales:

1. `alembic current -v` muestra `0038_cash_shift_closures_sales_monitor (head)`.
2. `/health/ready` mantiene PostgreSQL y Redis en `ok`.
3. Una cuenta sin `reports.sales.read` recibe 403 en `/api/v1/reports/sales-monitor`.
4. Administrador sólo consulta su sucursal y Dueño puede seleccionar una sucursal autorizada.
5. El monitor identifica por separado indicadores conocidos y operaciones incompletas; no presenta
   impuesto, descuento ni cortesía desconocidos como cero.

El canary productivo requiere autorización operativa explícita. Usa una caja exclusiva de QA, por
ejemplo `QA-PCO004`, y nunca cierres una caja o turno comercial para probar el despliegue:

1. Abre `QA-PCO004` con una clave `Idempotency-Key` nueva y fondo cero.
2. Repite exactamente la apertura con la misma clave y confirma el mismo turno.
3. Si la política permite una venta canary, crea y cobra un pedido de prueba identificado usando la
   misma caja QA; en caso contrario valida un turno vacío.
4. Cierra **por ID** con `POST /api/v1/cash/shifts/{id}/close-operationally`, otra clave estable y
   cuerpo `{}`. No envíes contado, esperado ni diferencia.
5. Repite el cierre con la misma clave y confirma la misma identidad de cierre y el mismo snapshot.
6. Comprueba que la respuesta indique `OPERATIVELY_CLOSED`, que no exista un corte nuevo y que el POS
   muestre “el corte final queda pendiente”.
7. Consulta el monitor en el intervalo UTC del canary y verifica el drill-down sin PII.

El rollback preferido es volver a la versión anterior de la aplicación y **conservar** la base en
`0038`; las rutas antiguas de contado deben permanecer desactivadas. Un downgrade de esquema sólo
es admisible antes de cualquier cierre, comando, snapshot o familia `captured`, con la aplicación
detenida y el snapshot de PostgreSQL disponible:

```bash
cd /app/apps/api
alembic downgrade 0037_cash_movement_ledger
alembic current -v
```

El downgrade elimina únicamente snapshots legacy regenerables y restaura el índice activo previo.
Si responde `Safe downgrade blocked: PCO-004 captured history exists`, no lo fuerces, no uses
`stamp` y no elimines filas: conserva `0038` y revierte sólo la aplicación. Si la recuperación exige
volver físicamente a `0037`, restaura el snapshot completo dentro de una ventana autorizada y valida
la pérdida de toda operación posterior antes de ejecutarla.

### Evidencia productiva PCO-004 — 2026-08-12/13

- Snapshot previo restaurable: `pre-pco004-2026-08-12` en `kiwi-postgres`.
- El primer preflight se detuvo en `0037` por dos `order_type=takeaway`; no creó DDL ni se editaron
  filas. La compatibilidad histórica gobernada se publicó mediante PR #25.
- El redeploy del merge `9aa9eb7` terminó `Success` y la revisión productiva quedó en
  `0038_cash_shift_closures_sales_monitor (head)`.
- Health posterior: API, PostgreSQL y Redis en `ok`.
- Canary vacío `QA-PCO004`: replay estable de apertura y cierre, estado
  `OPERATIVELY_CLOSED`, monitor y drill-down 200, un cierre operativo, cero cortes finales y cero
  turnos QA activos. No se registró venta canary.

### PCO-006: corte final por usuario

La revisión `0041_user_cash_cuts` agrega el cajero canónico nullable a turnos legacy y cinco tablas
append-only para corte, operaciones, comandos, reapertura y compensación. Antes del redeploy crea un
snapshot PostgreSQL restaurable y registra su identidad. No uses `DATABASE_URL` como URL de pruebas,
no ejecutes `stamp` y no edites turnos, pagos, movimientos o asociaciones para superar un error.

Durante la misma ventana, con tráfico, API y worker detenidos, usa la imagen nueva preparada sin
ponerla todavía a servir. Valida una sola head y la revisión actual, y ejecuta la migración desde
esa imagen:

```bash
cd /app/apps/api
alembic heads
alembic current -v
alembic upgrade 0041_user_cash_cuts
alembic current -v
```

La salida final debe mostrar `0041_user_cash_cuts (head)`. Sólo entonces inicia API y worker con la
imagen nueva, confirma `/health/ready`, reabre tráfico, inicia sesión de nuevo y verifica que Líder o
superior vea **Cortes por usuario**; sólo Dueño debe ver solicitud, decisión y compensación de
reapertura.

El canary crea historia financiera permanente y requiere autorización separada. Debe usar una caja
QA, un turno cerrado controlado y contado conocido: crear borrador, capturar contado, finalizar,
repetir cada comando con la misma `Idempotency-Key`, consultar lista/detalle y comprobar que otra
sucursal o un perfil inferior recibe denegación. No solicites reapertura salvo que el canary aprobado
incluya explícitamente probar la compensación append-only.

El rollback preferido es volver a la aplicación anterior y conservar `0041`. El downgrade a `0040`
sólo funciona si las cinco tablas están vacías y ningún turno tiene `cashier_user_id`; el backfill
inequívoco puede hacer que se bloquee aun antes del primer corte. Si aparece el bloqueo de historia,
no lo fuerces ni borres filas. Para regresar físicamente a `0040`, detén la aplicación y restaura el
snapshot completo dentro de una ventana autorizada.

### MOB-ORD-001 y PCO-008: promoción manual hasta 0053

Las revisiones `0051_public_order_intents`, `0052_pos_handoff_and_idempotency` y
`0053_cash_offline_sync` forman una ventana R3. Antes del redeploy crea un snapshot restaurable.
El proceso web no reconoce `RESTAURANTOS_AUTO_MIGRATE`; la ausencia de
`RESTAURANTOS_PUBLIC_ORDER_INTENTS_ENABLED` mantiene las escrituras públicas apagadas.

Detén tráfico y ejecuta desde la imagen aprobada:

```bash
cd /app/apps/api
alembic heads
alembic current -v
alembic upgrade 0053_cash_offline_sync
alembic current -v
```

La revisión final debe ser `0053_cash_offline_sync`. Sólo entonces inicia API y worker, confirma
`/health/ready` y verifica que `/health/version` reporte el SHA completo del build. No acoples
`alembic upgrade head` al arranque o reinicio del proceso web. Si el comando Alembic separado termina
distinto de cero, detén la promoción: no inicies/reinicies API ni worker.

El rollback preferido es volver a la aplicación anterior y conservar el esquema. No fuerces
downgrades si ya existen handoffs, comandos idempotentes, intents públicos, checkpoints o
sincronizaciones; usa el snapshot únicamente dentro de una ventana que acepte perder toda operación
posterior al respaldo.

### Guard 0058 para la semilla heredada de La Primavera

`0058_verify_0049_la_primavera_seed` es una promoción R3 forward-only. Antes de intentar producción,
restaura un snapshot reciente en una PostgreSQL aislada `seed0058_*` y ejecuta allí la imagen aprobada.
No uses `DATABASE_URL` como URL de prueba, no edites 0049 y no uses `alembic stamp`.

Si la copia aislada avanza, 0058 sólo agrega `migration.0049_seed_state_verified` a auditoría con el
snapshot de la única asignación Cajero; no cambia `user_roles`. Si falla con `manual role
reconciliation`, la revisión debe permanecer en 0057 y la promoción se detiene. Inspecciona de forma
read-only la cuenta y su topología, sin copiar el resultado a logs o tickets públicos:

```sql
SELECT u.id, u.created_at, u.updated_at, r.id AS role_id, r.name, ur.branch_id
FROM users u
LEFT JOIN user_roles ur ON ur.user_id = u.id
LEFT JOIN roles r ON r.id = ur.role_id
WHERE LOWER(u.email) = 'caja01laprimavera@kiwi.com';

SELECT b.id, b.name, b.code, b.created_at, b.updated_at,
       w.id AS warehouse_id, w.name AS warehouse_name, w.created_at AS warehouse_created_at
FROM branches b
LEFT JOIN warehouses w ON w.branch_id = b.id
WHERE b.organization_id = '018f6f73-2d0a-74f0-8f1c-000000000001'
  AND LOWER(b.name) LIKE '%primavera%';
```

Compara contra un respaldo anterior a 0049 y somete la asignación correcta a decisión del dueño de
los datos. Si se aprueba reparar, crea una migración o comando compensatorio aparte con snapshot
esperado, actor, alcance y auditoría; no ejecutes `DELETE FROM user_roles` ni SQL ad hoc. Hasta contar
con esa evidencia/decisión, no migres producción ni inicies la imagen que depende de 0058. El
downgrade de 0058 está bloqueado: volver el código conserva la revisión y su auditoría; restaurar un
snapshot completo requiere su propia ventana y autorización.

## Criterio de listo

### Semilla gobernada no productiva

La migración del catálogo Kiwi y sus siete sucursales sólo se ejecuta fuera de producción, desde la
imagen/version del repositorio que contiene el preset. No usa `DATABASE_URL`, no crea DDL y no
incluye ventas, caja, turnos, pedidos ni pagos. Primero inspecciona el resultado con dry-run y sólo
después aplica en una base no productiva migrada y explícitamente indicada:

```bash
cd /app/apps/api
python -m restaurant_os.internal_seed --preset kiwi-v1 --actor OPERADOR_EXPLICITO \
  --confirm-environment development --sqlite-url sqlite:////ruta/no-productiva/kiwi.db
python -m restaurant_os.internal_seed --preset kiwi-v1 --apply --actor OPERADOR_EXPLICITO \
  --confirm-environment development --sqlite-url sqlite:////ruta/no-productiva/kiwi.db
```

El replay del mismo preset debe devolver `replayed: true`. Para cualquier otro manifest se usa su
ruta explícita como argumento posicional; nunca se autoriza este comando para datos productivos.

1. El deploy de la API termina sin errores.
2. `/health/live` responde `ok`.
3. `/health/ready` muestra `postgres: ok` y `redis: ok`.
4. `alembic upgrade head` termina sin errores.
5. `/health/version` reporta exactamente el SHA completo del build registrado por EasyPanel.
