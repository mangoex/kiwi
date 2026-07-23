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
RESTAURANTOS_DATABASE_URL=postgresql+psycopg://restaurantos:TU_PASSWORD@kiwi-postgres:5432/restaurantos
RESTAURANTOS_REDIS_URL=redis://kiwi-redis:6379/0
SECRET_KEY=CAMBIAR_POR_UN_SECRETO_LARGO
LOG_LEVEL=info
```

Si Easypanel entrega nombres internos distintos, reemplazar `kiwi-postgres` y `kiwi-redis` por los hosts reales.

## Health checks

Abrir:

```text
/health/live
/health/ready
/health/version
/docs
```

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

El contenedor web no ejecuta migraciones automaticamente al arrancar. Esto evita que
un error temporal de Postgres, una URL mal configurada o una migracion parcial tumbe
el proceso web y genere `502 Bad Gateway`. Primero debe levantar la API; despues se
ejecuta Alembic desde la consola del servicio API o como job operativo separado.

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

## Criterio de listo

1. El deploy de la API termina sin errores.
2. `/health/live` responde `ok`.
3. `/health/ready` muestra `postgres: ok` y `redis: ok`.
4. `alembic upgrade head` termina sin errores.
