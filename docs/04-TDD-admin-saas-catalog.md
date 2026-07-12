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

## TDD-TS-035 Admin SaaS Command Center

Casos:

- renderizar un centro de mando visual en Inicio,
- mostrar checklist de preparacion para Catalogos, Inventario, Usuarios y Sistema,
- calcular estados textuales con datos cargados desde APIs,
- exponer saltos a los modulos Admin sin salir de la consola,
- mantener contrastes y etiquetas visibles sin depender solo de color.

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

## TDD-TC-027 Centro de mando SaaS

Given existe la consola Admin
When se renderiza `/admin`
Then el HTML contiene `saas-command-center`, `readiness-steps` y `ops-pulse`
And el JavaScript embebido actualiza los pasos con conteos de catalogo, inventario, usuarios y sincronizacion.

## TDD-TS-047 Consistencia de catálogos y centro Admin en POS

Casos:

- listar en una sucursal un producto central sin fila de disponibilidad local;
- ocultarlo únicamente cuando la disponibilidad local sea explícitamente falsa;
- listar en Admin productos sin precio vigente sin ofrecerlos en POS;
- combinar en POS el catálogo real de insumos con existencias reales de la sucursal y cero sin movimientos;
- resolver la sucursal asignada para usuarios restringidos;
- inicializar una sucursal válida para administradores y compartirla entre Admin y POS;
- usar el contexto canónico en compras, proveedores, producción, mermas, traspasos, conteos y modificadores;
- mostrar el centro administrativo en POS con `admin.manage` o superadministrador;
- ocultar el enlace y bloquear la ruta para una cuenta sin administración.

## TDD-TC-040 Herencia y acceso administrativo

Given existe un producto activo con precio vigente y una segunda sucursal sin excepción local
When se consulta `/catalog/products` para esa sucursal
Then el producto aparece disponible
When se registra una excepción local con `is_available=false`
Then el producto deja de aparecer en esa sucursal.

Given un administrador autenticado abre POS
Then existe el acceso `Administración`
And dirige a los módulos Admin existentes.
