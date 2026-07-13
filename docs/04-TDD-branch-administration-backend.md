# TDD - Backend de administración por sucursal

## TDD-TS-050 Administración operativa por sucursal

Casos:

- la migración 0024 crea los permisos `branch.admin.access`, `branch.staff.read` y `catalog.branch.manage` de forma idempotente,
- la migración asigna los tres permisos al Administrador corporativo y al Supervisor de sucursal,
- la migración verifica `production.manage` en el Supervisor,
- Cajero y Caja legacy no reciben los tres permisos,
- la migración es reversible (downgrade retira asignaciones y permisos),
- `GET /api/v1/auth/session` con token válido devuelve perfil, roles, permisos, alcance y active_branch,
- token ausente, inválido, expirado o usuario inactivo recibe 401 o 403,
- `GET /branch-administration/context` requiere `branch.admin.access` y devuelve sucursal, unidad de negocio, razón social y almacén,
- `GET /branch-administration/staff` requiere `branch.staff.read` y devuelve sólo usuarios de la sucursal sin credenciales,
- `GET /branch-administration/catalog/products` requiere `branch.admin.access` y muestra disponibilidad efectiva, sellable y herencia,
- `PUT /branch-administration/catalog/products/{id}/availability` requiere `catalog.branch.manage`, actualiza sólo branch_product_availability, registra auditoría y admite inherit,
- un Supervisor no puede forzar branch_id de otra sucursal,
- inventario y kardex usan el branch_id autorizado y no devuelven movimientos de otra sucursal,
- un Cajero es rechazado con 403 al acceder a branch-administration,
- las lecturas sensibles sin actor reciben 401 y una sesión autenticada sin permiso recibe 403,
- un Supervisor no puede crear, modificar ni borrar productos, insumos, proveedores, recetas, unidades de negocio, sucursales, usuarios, roles ni permisos,
- no hay fuga por branch_id en compras, producción, mermas, traspasos ni conteos,
- `unit_type` acepta `restaurant`, `bakery`, `production` y `other`, y rechaza valores desconocidos.

## TDD-TC-043 El backend de administración por sucursal aísla datos y respeta permisos

Given una organización con al menos dos sucursales y un Supervisor asignado a una de ellas
When la prueba automatizada ejercita los endpoints de branch-administration y los endpoints centrales
Then el Supervisor sólo opera su sucursal asignada
And el Cajero recibe 403 en branch-administration
And el Supervisor no puede forzar otra sucursal
And la disponibilidad se hereda salvo excepción local explícita
And la auditoría registra valor anterior y nuevo
And `unit_type` distingue restaurant, bakery, production y other.
