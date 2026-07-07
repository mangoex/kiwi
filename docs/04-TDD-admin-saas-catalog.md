# TDD - Admin SaaS y catalogos operativos

## TDD-TS-026 Admin SaaS UI

Casos:

- Admin muestra navegacion agrupada por modulos,
- Admin muestra indicadores operativos,
- Admin carga catalogos, usuarios y sincronizacion desde API,
- Admin conserva formularios con labels visibles y mensajes de estado.

## TDD-TS-027 Catalog Management Minimal

Casos:

- listar sucursales con razon social y almacen,
- crear sucursal y almacen formal,
- rechazar codigo de sucursal duplicado,
- listar productos con precio y disponibilidad,
- crear producto activo con categoria,
- crear categoria si no existe,
- crear precio vigente,
- crear disponibilidad por sucursal,
- registrar auditoria de sucursal y producto.

## TDD-TC-020 Alta minima de catalogo

Given existe la organizacion Kiwi Restaurante
When se crea una sucursal con codigo `NORTE`
And se crea un producto con SKU `KIWI-WRAP`
Then la sucursal aparece en Admin con almacen
And el producto aparece en Catalogos con precio vigente y disponibilidad.
