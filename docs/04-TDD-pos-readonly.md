# TDD - POS solo lectura

## TDD-TS-016 POS Readonly Catalog

Casos:

- `/pos` responde HTML,
- `/pos` incluye contenedor de catalogo,
- `/pos` consulta `/api/v1/catalog/products`,
- la vista indica que aun es solo lectura.

## TDD-TC-011 POS carga catalogo

Given la API esta desplegada  
When el usuario abre `/pos`  
Then recibe una vista HTML de POS  
And la vista carga el catalogo versionado desde `/api/v1/catalog/products`.

