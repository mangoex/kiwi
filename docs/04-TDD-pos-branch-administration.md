# TDD - Frontend de administración operativa por sucursal en el POS

## TDD-TS-051 Frontend de administración por sucursal

Casos:

- la sesión canónica se obtiene de `GET /api/v1/auth/session` y no de `localStorage`,
- `hasPermission("branch.admin.access")` determina la visibilidad del menú Administración,
- un Cajero sin `branch.admin.access` no ve el menú y recibe acceso denegado al escribir la ruta,
- las rutas `/pos/administration`, `/pos/administration/products`, `/pos/administration/staff` y `/pos/administration/branch` existen dentro de `PosLayout`,
- `AdminHub` no contiene enlaces `/admin`, `adminUrl`, ni `window.location`,
- las tarjetas diferidas tienen `aria-disabled="true"` y no son navegables,
- la página de productos consume `/branch-administration/catalog/products` y permite `available`, `unavailable` e `inherit`,
- la página de personal consume `/branch-administration/staff` y es sólo lectura,
- la página de sucursal activa consume `/branch-administration/context`,
- la configuración usa `active_branch` para `scope branch` sin selector,
- `PointOfSale` usa `fetchApi` para modificadores enviando `Authorization: Bearer`.

## TDD-TC-044 El frontend de administración respeta permisos y no abandona el POS

Given una sesión canónica con permisos validados por backend
When la prueba arquitectónica inspecciona el código frontend
Then comprueba que la autoridad se toma de `/auth/session`
And comprueba que no hay enlaces a `/admin` en `AdminHub`
And comprueba que las tarjetas habilitadas usan `Link` dentro de `PosLayout`
Y comprueba que las tarjetas diferidas no son navegables.
