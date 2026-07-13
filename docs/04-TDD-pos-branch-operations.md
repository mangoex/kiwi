# TDD - Módulos operativos de sucursal dentro del POS

## TDD-TS-052 Navegación y resúmenes operativos BA-003

Casos:

- `PosLayout` muestra Administración únicamente con `branch.admin.access`;
- `AdminHub` contiene exactamente las ocho opciones operativas acordadas;
- no existen tarjetas ni rutas para Sucursales, Usuarios, Roles o Personal;
- todas las tarjetas usan rutas locales bajo `/pos/administration` o `/pos/inventory`;
- Proveedores, Compras, Producción, Mermas, Traspasos y Conteos tienen una ruta protegida por su
  permiso granular;
- las páginas consumen los endpoints existentes con `active_branch.id` canónico;
- Proveedores es sólo lectura y no expone mutaciones de catálogo central;
- todas las vistas usan el contenedor visual común de la administración POS;
- ningún módulo usa `/admin`, `adminUrl` o `window.location` para navegar;
- BDD, TDD y matriz incluyen BDD-SC-136 a BDD-SC-143.

## TDD-TC-045 El centro administrativo no filtra autoridad ni mezcla shells

Given el código frontend de BA-003
When la prueba arquitectónica inspecciona rutas, tarjetas, permisos y contratos
Then comprueba ocho opciones operativas locales
And rechaza Sucursales, Usuarios, Roles y Personal en el centro
And comprueba guardas granulares y sucursal canónica
And rechaza enlaces al administrador corporativo.
