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

Para validar que la API puede conectarse a Postgres desde el contenedor, ejecutar en la consola del servicio API:

```bash
cd /app/apps/api
alembic upgrade head
```

Si ya habias ejecutado este comando antes, vuelve a correrlo. La migracion nueva aplicara solo lo pendiente.

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

## Criterio de listo

1. El deploy de la API termina sin errores.
2. `/health/live` responde `ok`.
3. `/health/ready` muestra `postgres: ok` y `redis: ok`.
4. `alembic upgrade head` termina sin errores.
