# TDD - Platform Shell

## TDD-TS-013 Platform Shell

Casos:

- raiz publica responde HTML,
- accesos Admin, POS y KDS responden HTML,
- la consola enlaza health checks y documentacion API,
- la consola conserva estado de fase 0 sin ejecutar logica de negocio,
- el `CMD` de los Dockerfiles inicia Uvicorn sin ejecutar Alembic como bloqueo previo.

## TDD-TC-008 Consola inicial visible

Given la API esta desplegada  
When el usuario abre `/`  
Then recibe HTML de la consola inicial  
And existen accesos a `/admin`, `/pos`, `/kds`, `/docs` y `/health/ready`.

## TDD-TC-030 Arranque de contenedor sin migracion bloqueante

Given existe el `Dockerfile` de produccion
When se inspecciona el comando `CMD`
Then inicia `uvicorn restaurant_os.main:app`
And no antepone `alembic upgrade head` al arranque del proceso web.
