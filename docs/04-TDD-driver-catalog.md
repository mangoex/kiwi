# TDD - Catálogo administrativo de repartidores

## TDD-TS-071 Repartidores propios

Pruebas de migración y dominio:

- `0030_driver_catalog` crea `drivers` con organización, sucursal, datos solicitados, estado y
  timestamps;
- el downgrade funciona si no existen registros y se bloquea cuando eliminaría repartidores;
- alta y edición exigen `admin.manage`;
- todos los campos solicitados son obligatorios después de recortar espacios;
- la sucursal debe existir, estar activa y pertenecer a la organización;
- listar incluye `branch_name`;
- desactivar cambia estado sin borrar;
- auditoría de alta, edición y desactivación no contiene teléfono, domicilio, licencia ni placas.

Pruebas frontend:

- el menú administrativo contiene Repartidores y la ruta `/drivers`;
- la tabla presenta nombre, sucursal, licencia, placas, teléfono, domicilio, contacto y estado;
- el formulario carga sucursales y permite crear o editar todos los campos;
- los estados de carga, vacío, error y guardado son visibles;
- Desactivar pide confirmación y actualiza el catálogo.

## TDD-TC-067 Alta, edición y desactivación auditada

Given un Administrador corporativo y una sucursal activa
When crea un repartidor, cambia su teléfono y después lo desactiva
Then las lecturas muestran cada estado vigente y el nombre de la sucursal
And un actor sin admin.manage recibe acceso denegado
And los eventos conservan acciones y campos modificados sin datos personales
And el registro permanece en la tabla con estado inactivo.
