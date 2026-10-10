# TDD - Estructura organizacional y roles POS

## TDD-TS-038 Unidad de negocio y perfiles operativos

Casos:

- la migracion crea `business_units` y asigna la sucursal existente a una unidad semilla;
- una unidad exige organizacion, razon social, codigo unico y tipo valido;
- una sucursal nueva exige una unidad compatible con su razon social;
- crear unidad y sucursal registra auditoria con actor;
- Administrador recibe todos los permisos nuevos;
- Cajero recibe únicamente captura ciega de conteos y no recibe compras, retiros, merma,
  traspasos, revisión, aprobación ni auditoría;
- Supervisor recibe permisos operativos sensibles aplicados únicamente al active_branch autorizado;
- Receptor solo recibe lectura de inventario y recepcion de traspasos;
- Auditor recibe consultas y no recibe permisos de mutacion;
- downgrade elimina asignaciones semilla, permisos y unidad sin perder sucursales previas.

## TDD-TC-054 Jerarquia organizacional

Given existe una razon social Kiwi
When el administrador crea la unidad `KIWI-NORTE`
And crea una sucursal dentro de ella
Then la API devuelve la unidad en la sucursal
And existe un evento de auditoria para cada alta.

## TDD-TC-055 Perfiles POS separados

Given se aplicaron las migraciones desde cero
When se consultan los permisos semilla
Then Supervisor puede gestionar compras, mermas, traspasos enviados y conteos
And Receptor solo puede recibir traspasos
And Auditor solo tiene permisos de lectura
And Cajero conserva su perfil POS y caja más inventory.count.capture
And no recibe inventory.count.review ni inventory.count.approve.
