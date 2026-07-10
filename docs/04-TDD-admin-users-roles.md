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
- resolver actor por token `Authorization: Bearer`,
- rechazar acciones sensibles cuando no hay actor autenticado,
- permitir al administrador corporativo cualquier accion sensible,
- rechazar ajuste de inventario si el actor no tiene `inventory.adjust`,
- rechazar alta de sucursal o producto si el actor no tiene `catalog.manage`,
- rechazar apertura/cierre de caja si el actor no tiene permisos de caja,
- rechazar pedidos POS si el actor no tiene `orders.create`,
- rechazar pagos si el actor no tiene `payments.confirm`,
- rechazar dashboard si el actor no tiene `dashboard.read`,
- rechazar acciones de sucursal cuando el actor no tiene alcance sobre esa sucursal,
- registrar auditoria `authorization.denied` con permiso requerido,
- conservar compatibilidad solo para lecturas publicas o endpoints no sensibles.

## TDD-TS-036 Superadmin Login

Casos:

- migracion agrega credenciales hasheadas para el superadmin,
- login valida correo, contraseña y usuario activo,
- login devuelve token firmado y datos del usuario,
- Admin muestra login cuando no existe sesion local,
- Admin muestra una bienvenida visual antes de autenticar,
- Admin oculta diagnostico tecnico superior salvo sesion superadmin,
- login devuelve roles, permisos y bandera superadmin para adaptar el panel,
- Admin y POS envian token en acciones sensibles,
- alta de usuario con contraseña temporal crea usuario activo y credencial hasheada.

## TDD-TS-037 POS RBAC y dashboard operativo

Casos:

- login de Cajero devuelve permisos POS y sucursal asignada,
- Cajero abre caja propia con `cash.shift.open`,
- Cajero no abre caja de otra sucursal,
- usuario sin permiso no abre caja,
- Cajero crea pedido con turno abierto y `orders.create`,
- Cajero no crea pedido sin turno abierto,
- Cajero confirma pago con `payments.confirm`,
- pago usa el `total_cents` calculado por backend,
- dashboard Admin refleja apertura, venta, pago y cierre,
- usuario sin `dashboard.read` no consulta dashboard.

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
And devuelve token firmado
And devuelve roles, permisos y bandera de superadmin.

Given el superadmin crea un administrador con contraseña temporal
When el nuevo administrador inicia sesion
Then la API responde `200`.

## TDD-TC-029 Admin visual por rol

Given se abre `/admin` sin sesion local
When se renderiza el shell
Then existe una pantalla de bienvenida con login
And el diagnostico tecnico superior queda marcado como exclusivo de superadmin.

Given existe una sesion valida
When Admin carga catalogos, inventario, usuarios y roles
Then el panel visual muestra productos destacados, resumen operativo y rol de sesion.
