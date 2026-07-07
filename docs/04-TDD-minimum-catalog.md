# TDD - Catalogo minimo

## TDD-TS-015 Minimum Catalog

Casos:

- migracion crea categorias,
- migracion crea productos,
- migracion crea precios versionados,
- migracion crea disponibilidad por sucursal,
- API lista productos con categoria,
- API lista productos con precio vigente,
- API lista productos con disponibilidad de sucursal.

## TDD-TC-010 Productos semilla del catalogo

Given la base contiene seed de catalogo  
When se consulta `/api/v1/catalog/products`  
Then responde productos activos  
And cada producto incluye sku, categoria, estacion, precio vigente y disponibilidad.

