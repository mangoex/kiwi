# TDD - Revisión accionable de importaciones

## TDD-TS-054 Resumen, filtro y guía de conciliación

Casos:

- la lista corporativa de lotes devuelve conteos por tipo y estado;
- el endpoint de registros filtra por `entity_type` y conserva paginación acotada;
- un tipo no soportado produce un error de negocio explícito;
- la UI presenta tarjetas independientes para presentación, producto y receta;
- cada fila usa `normalized_payload` para mostrar nombre y SKU sin exponer el payload crudo;
- cada tipo explica el dato faltante y enlaza al catálogo canónico;
- el enlace de producto incluye su SKU como búsqueda y el catálogo respeta ese parámetro;
- ninguna acción de la bandeja activa productos, inventa proveedores o crea recetas vacías.

## TDD-TC-047 Navegación de una cola mixta

Given un lote con 159 presentaciones, 317 productos y 317 recetas en `needs_review`
When el administrador abre cada tarjeta y cambia de página
Then cada consulta contiene un solo `entity_type`, limit y offset
And las filas muestran identidad y pasos diferentes según su causa
And el editor de Productos puede abrir filtrado por la clave elegida.
