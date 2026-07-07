# TDD - Bootstrap de datos base

## TDD-TS-014 Bootstrap Data

Casos:

- migracion crea tablas de organizacion, sucursal, almacen, usuarios, roles y auditoria,
- seed inicial crea una organizacion,
- seed inicial crea una sucursal ligada a una razon social,
- seed inicial crea un almacen ligado a la sucursal,
- API lista organizaciones,
- API lista sucursales con razon social y almacen,
- API reporta conteos de bootstrap.

## TDD-TC-009 Estado de bootstrap

Given la base contiene seed inicial  
When se consulta `/api/v1/platform/bootstrap-status`  
Then responde `ok`  
And reporta una organizacion, una sucursal, un almacen, un usuario, un rol y un evento de auditoria.

