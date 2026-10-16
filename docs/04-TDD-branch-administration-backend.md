# TDD - Backend de administración por sucursal

## TDD-TS-050 Administración operativa por sucursal

Casos:

- la migración 0024 crea los permisos `branch.admin.access`, `branch.staff.read` y `catalog.branch.manage` de forma idempotente,
- la migración asigna los tres permisos al Administrador corporativo y al Supervisor de sucursal,
- la migración verifica `production.manage` en el Supervisor,
- Cajero y Caja legacy no reciben los tres permisos,
- la migración es reversible (downgrade retira asignaciones y permisos),
- `GET /api/v1/auth/session` con token válido devuelve perfil, roles, permisos, alcance y active_branch,
- `GET /api/v1/auth/session?branch_id=...` no cambia contexto y responde
  `branch_selection_requires_command`; sólo `POST /api/v1/auth/branch-selections` transiciona,
- token ausente, inválido, expirado o usuario inactivo recibe 401 o 403,
- `GET /branch-administration/context` requiere `branch.admin.access` y devuelve sucursal, unidad de negocio, razón social y almacén,
- `GET /branch-administration/staff` requiere `branch.staff.read` y devuelve sólo usuarios de la sucursal sin credenciales,
- `GET /branch-administration/catalog/products` requiere `branch.admin.access` y muestra disponibilidad efectiva, sellable y herencia,
- `PUT /branch-administration/catalog/products/{id}/availability` requiere `catalog.branch.manage`, actualiza sólo branch_product_availability, registra auditoría y admite inherit,
- un Supervisor no puede forzar branch_id de una sucursal no autorizada,
- inventario y kardex usan el branch_id autorizado y no devuelven movimientos de otra sucursal,
- un Cajero es rechazado con 403 al acceder a branch-administration,
- las lecturas sensibles sin actor reciben 401 y una sesión autenticada sin permiso recibe 403,
- un Supervisor no puede crear, modificar ni borrar identidad/credenciales de usuarios, roles,
  permisos, productos, insumos, proveedores, recetas, unidades de negocio o sucursales; la única
  excepción es la reasignación acotada con `staff.branch.reassign` y el comando BRANCH-SCOPE-001,
- no hay fuga por branch_id en compras, producción, mermas, traspasos ni conteos,
- `unit_type` acepta `restaurant`, `bakery`, `production` y `other`, y rechaza valores desconocidos.

## TDD-TC-043 El backend de administración por sucursal aísla datos y respeta permisos

Given una organización con al menos dos sucursales y un Supervisor con alcance persistido
When la prueba automatizada ejercita los endpoints de branch-administration y los endpoints centrales
Then el Supervisor sólo opera la active_branch autorizada por la sesión
And el Cajero recibe 403 en branch-administration
And el Supervisor no puede forzar una sucursal fuera de allowed_branch_ids
And la disponibilidad se hereda salvo excepción local explícita
And la auditoría registra valor anterior y nuevo
And `unit_type` distingue restaurant, bakery, production y other.

## TDD-TS-147 Visibilidad del menú digital por sucursal

Casos:

- la migración `0095_branch_product_digital_visibility` crea una tabla separada con llave compuesta,
  default visible por ausencia y downgrade bloqueado cuando existen exclusiones;
- la consulta administrativa devuelve `show_in_digital_menu=true` para productos sin excepción;
- el comando booleano requiere `catalog.branch.manage`, respeta la sucursal autorizada, audita el
  cambio y sólo crea una excepción al ocultar;
- ocultar no cambia la disponibilidad ni la proyección POS, pero sí excluye el producto del catálogo
  público de esa sucursal y rechaza una captura pública que reutilice un ID obsoleto;
- volver a mostrar elimina la excepción y no modifica precio, receta, inventario ni historia;
- un error al cargar el catálogo público no activa productos estáticos que el backend no autorizó.
- el resumen corporativo agrega únicamente sucursales activas autorizadas y distingue `all`, `none`
  y `mixed`, respetando productos con alcance local;
- los comandos `all-active` requieren alcance organizacional, bloquean sucursales en orden estable,
  escriben y auditan en una transacción, y dejan intactas las sucursales futuras.

## TDD-TC-408 La visibilidad digital permanece separada de la venta POS

Given un producto activo, con precio positivo y disponibilidad efectiva en dos sucursales
When la prueba desmarca Mostrar en menú digital únicamente en la sucursal A
Then Administración refleja la excepción sólo en A
And el producto permanece en el catálogo POS de A
And no aparece ni puede capturarse en el canal público de A
And continúa visible en el canal público de B
When la prueba vuelve a marcarlo
Then la fila de excepción se elimina y el default visible vuelve a aplicar.

## TDD-TC-409 El alcance total es corporativo, explícito y atómico

Given un producto corporativo y dos sucursales activas con estados distintos
When el Dueño consulta el resumen de Todas las sucursales actuales
Then recibe conteos y estado mixto sin cambiar la sucursal activa de la sesión
When confirma disponibilidad o visibilidad para todas
Then ambas sucursales cambian dentro de un solo commit y cada efecto queda auditado
And repetir la lectura devuelve estado uniforme
When un Supervisor intenta la operación total o una escritura inyectada falla
Then recibe rechazo o rollback completo sin efectos parciales.
