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

## TDD-TS-034 RBAC Sensitive Actions

Casos:

- resolver actor por header interno `X-Actor-User-Id`,
- usar administrador semilla como actor por defecto,
- permitir al administrador corporativo cualquier accion sensible,
- rechazar ajuste de inventario si el actor no tiene `inventory.adjust`,
- rechazar alta de sucursal o producto si el actor no tiene `catalog.manage`,
- registrar auditoria `authorization.denied` con permiso requerido,
- conservar compatibilidad de la UI actual cuando no envia actor explicito.

## TDD-TS-036 Superadmin Login

Casos:

- migracion agrega credenciales hasheadas para el superadmin,
- login valida correo, contraseña y usuario activo,
- login devuelve token firmado y datos del usuario,
- Admin muestra login cuando no existe sesion local,
- Admin envia token y actor en acciones sensibles,
- alta de usuario con contraseña temporal crea usuario activo y credencial hasheada.

## TDD-TC-019 Alta de usuario con rol

Given existe la Sucursal Piloto
When se crea el rol Cajero
And se invita al usuario cajero@kiwi.local
And se asigna el rol Cajero al usuario
Then el usuario aparece con el rol asignado
And existen eventos de auditoria para rol, usuario y asignacion.

## TDD-TC-026 Cajero sin ajuste de inventario

Given existe un usuario con rol `Cajero`
And el rol no tiene permiso `inventory.adjust`
When el usuario intenta crear un movimiento de inventario
Then la API responde `403`
And registra `authorization.denied`.

Given el administrador corporativo ejecuta la misma accion
When registra un movimiento de inventario valido
Then la API responde `200`.

## TDD-TC-028 Login superadmin

Given existe el superadmin `mangoex@gmail.com`
When inicia sesion con contraseña valida
Then la API responde `200`
And devuelve token firmado.

Given el superadmin crea un administrador con contraseña temporal
When el nuevo administrador inicia sesion
Then la API responde `200`.
