# TDD - Platform Shell

## TDD-TS-013 Platform Shell

Casos:

- raiz publica responde HTML,
- accesos Admin, POS y KDS responden HTML,
- la consola enlaza health checks y documentacion API,
- la consola conserva estado de fase 0 sin ejecutar logica de negocio.

## TDD-TC-008 Consola inicial visible

Given la API esta desplegada  
When el usuario abre `/`  
Then recibe HTML de la consola inicial  
And existen accesos a `/admin`, `/pos`, `/kds`, `/docs` y `/health/ready`.

