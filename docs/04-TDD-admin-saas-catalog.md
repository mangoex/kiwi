# TDD - Admin SaaS y catalogos operativos

## TDD-TS-026 Admin SaaS UI

Casos:

- Admin muestra navegacion agrupada por modulos,
- Admin muestra indicadores operativos,
- Admin carga catalogos, usuarios y sincronizacion desde API,
- Admin conserva formularios con labels visibles y mensajes de estado.
- Admin expone accesos operativos a POS, KDS, Catalogos, Inventario y Usuarios.

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

## TDD-TS-033 Admin UIX Workbench

Casos:

- renderizar cabecera operativa con estado SaaS y acciones POS/KDS,
- renderizar tarjetas de acceso para Catalogos, Inventario, Usuarios y Sistema,
- mostrar tablas de sucursales, productos, existencias, recetas y kardex con encabezados,
- mostrar estados con texto visible ademas de color,
- conservar labels visibles en formularios,
- mantener sintaxis valida del JavaScript embebido.

## TDD-TC-020 Alta minima de catalogo

Given existe la organizacion Kiwi Restaurante
When se crea una sucursal con codigo `NORTE`
And se crea un producto con SKU `KIWI-WRAP`
Then la sucursal aparece en Admin con almacen
And el producto aparece en Catalogos con precio vigente y disponibilidad.

## TDD-TC-025 Admin workbench visual

Given existe la consola Admin
When se renderiza `/admin`
Then el HTML contiene accesos `Abrir POS`, `Abrir KDS`, `Catalogos`, `Inventario` y `Usuarios`
And contiene `catalog-workbench`, `inventory-workbench`, `recipes-table` y `inventory-kardex-table`
And el JavaScript embebido valida sintaxis.
