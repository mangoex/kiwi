# TDD - Administracion de usuarios y roles

## TDD-TS-025 Admin Users Roles

Casos:

- listar usuarios con roles asignados,
- listar roles existentes,
- crear rol con alcance valido,
- rechazar rol duplicado,
- crear usuario invitado con correo valido,
- rechazar usuario duplicado,
- asignar rol a usuario,
- no duplicar la misma asignacion,
- registrar auditoria en altas y asignaciones.

## TDD-TC-019 Alta de usuario con rol

Given existe la Sucursal Piloto
When se crea el rol Cajero
And se invita al usuario cajero@kiwi.local
And se asigna el rol Cajero al usuario
Then el usuario aparece con el rol asignado
And existen eventos de auditoria para rol, usuario y asignacion.
