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

`/health/ready` responde:

- `ok` cuando Postgres y Redis estan configurados y accesibles.
- `degraded` cuando falta una variable o una dependencia no responde.

## Migraciones

La fase 0 incluye Alembic sin tablas de negocio todavia.

Para validar que la API puede conectarse a Postgres desde el contenedor, ejecutar en la consola del servicio API:

```bash
cd /app/apps/api
alembic upgrade head
```

Esto crea la tabla tecnica de Alembic y deja la base preparada para migraciones posteriores.

## Criterio de listo

1. El deploy de la API termina sin errores.
2. `/health/live` responde `ok`.
3. `/health/ready` muestra `postgres: ok` y `redis: ok`.
4. `alembic upgrade head` termina sin errores.

