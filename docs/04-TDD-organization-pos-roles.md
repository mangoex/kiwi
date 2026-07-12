# TDD - Estructura organizacional y roles POS

## TDD-TS-038 Unidad de negocio y perfiles operativos

Casos:

- la migracion crea `business_units` y asigna la sucursal existente a una unidad semilla;
- una unidad exige organizacion, razon social, codigo unico y tipo valido;
- una sucursal nueva exige una unidad compatible con su razon social;
- crear unidad y sucursal registra auditoria con actor;
- Administrador recibe todos los permisos nuevos;
- Cajero no recibe compras, retiros, merma, traspasos, conteos ni auditoria;
- Supervisor recibe permisos operativos sensibles con alcance de sucursal;
- Receptor solo recibe lectura de inventario y recepcion de traspasos;
- Auditor recibe consultas y no recibe permisos de mutacion;
- downgrade elimina asignaciones semilla, permisos y unidad sin perder sucursales previas.

## TDD-TC-030 Jerarquia organizacional

Given existe una razon social Kiwi
When el administrador crea la unidad `KIWI-NORTE`
And crea una sucursal dentro de ella
Then la API devuelve la unidad en la sucursal
And existe un evento de auditoria para cada alta.

## TDD-TC-031 Perfiles POS separados

Given se aplicaron las migraciones desde cero
When se consultan los permisos semilla
Then Supervisor puede gestionar compras, mermas, traspasos enviados y conteos
And Receptor solo puede recibir traspasos
And Auditor solo tiene permisos de lectura
And Cajero conserva exclusivamente su perfil POS y caja.
