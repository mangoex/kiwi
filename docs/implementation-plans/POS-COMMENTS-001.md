# POS-COMMENTS-001 — alcance de comentarios por producto

**Riesgo:** R2. Cambia comportamiento visible y relaciones de catálogo no críticas. No cambia dinero,
inventario, permisos, migraciones, offline, sucursales ni snapshots históricos.

## Objetivo y criterios de terminado

El Administrador puede conocer y ajustar exactamente qué productos activos reciben cada comentario,
tanto durante el alta masiva como desde el catálogo vigente. La historia termina cuando:

- el árbol permite selección completa, parcial e individual con nombre y SKU;
- preview y resumen representan exactamente los productos elegidos;
- cada comentario despliega sus productos y permite reemplazar el conjunto después de confirmar el
  impacto;
- el alta masiva conserva su semántica aditiva y nunca desvincula por omisión;
- errores, permisos, auditoría e historia permanecen fail-closed;
- BDD-SC-586..589 y TDD-TC-303..306 están verdes con QA visual y de teclado.

## Dependencias e invariantes

- Reutilizar `GET /catalog/products`, `GET /categories`, `GET /catalog/order-comments` y
  `PUT /catalog/order-comments/{id}/products`; no crear endpoint paralelo.
- `selectedProductIds` gobierna la selección; categorías y estados mixtos son proyecciones.
- Sólo productos `active` de la organización vigente y al menos uno por comentario.
- `POST /catalog/order-comments/bulk` agrega/reactiva; el PUT individual reemplaza exactamente.
- `catalog.manage` continúa siendo el único permiso de escritura; no aceptar `branch_id`.
- Conservar `order_comment.products_replaced`, relaciones archivadas y snapshots históricos.
- No agregar dependencias npm ni cambiar modelos, Alembic, gateway, POS o KDS.

## Hallazgo de la fase RED

El endpoint vigente materializa correctamente `products`, pero `_order_comment_payload` consume el
resultado SQL antes de construir `product_ids`, por lo que esa segunda proyección llega vacía. La
implementación debe convertir las relaciones a una lista una sola vez y derivar ambos campos de la
misma colección; no requiere cambiar contrato, esquema ni migración.

## Actividades

1. **RED y dependencias:** agregar prueba pura/semántica del árbol individual; ampliar la prueba API
   para lectura de nombres/SKU, reemplazo exacto, auditoría y rechazo vacío.
2. **Estado de selección:** extraer helpers puros para estado de subcategoría, toggles deduplicados e
   impacto; hacer de los productos la fuente de verdad e invalidar previews al cambiarla.
3. **Árbol de alta:** añadir expansión de subcategoría, búsqueda nombre/SKU, casillas individuales,
   estado mixto y acciones seleccionar/quitar todos con resumen exacto.
4. **Catálogo vigente:** convertir tarjetas en disclosure accesible, mostrar productos agrupados y
   abrir editor individual con conjunto inicial, diferencias agregadas/retiradas y confirmación.
5. **Persistencia:** enviar PUT con el conjunto completo, conservar borrador en error, refrescar
   comentarios/productos en éxito y separar claramente el copy aditivo del reemplazo.
6. **Verificación:** ejecutar focales API/frontend, arquitectura, typecheck/build Admin, recorrido de
   navegador en escritorio/ancho reducido, consola, trazabilidad y `git diff --check`.

## Pruebas previstas

- `tests/frontend/test_admin_order_comment_product_scope.mjs`: helpers y cableado semántico.
- `apps/api/tests/test_global_catalog_comments_extras.py`: exactitud, lectura, auditoría, rechazo y
  semántica aditiva.
- `tests/architecture/test_pos_ingredient_variations_frontend.py`: separación del catálogo vigente
  frente a ingredientes y superficies heredadas.
- Navegador: selección parcial, filtro, preview invalidado, editor exacto, error conservado, teclado,
  foco y responsive.

## Gates omitidos por alcance

No se programa suite PostgreSQL, migración, SQLite/gateway, POS/KDS, canary ni auditoría Sol mientras
la implementación permanezca en este alcance R2 sin SQL, persistencia nueva ni frontera externa. Si
el diff rompe esas condiciones, se reclasifica antes de continuar.

## Estado de implementación local

Implementado el 2026-10-04 sin endpoint, esquema, permiso ni dependencia nuevos. La fase RED detectó
la inconsistencia entre `products` y `product_ids`; la corrección materializa una sola colección y
ambas proyecciones quedaron cubiertas por la prueba API. La UI usa productos como fuente de verdad,
expone selección parcial, filtro, detalle agrupado y reemplazo exacto con impacto previo.

Evidencia local verde: 6 pruebas API focales, prueba semántica de la historia, 15 pruebas de
arquitectura/trazabilidad, Ruff, typecheck y build del Admin. El QA de navegador con datos ficticios
confirmó estado mixto, filtro sin pérdida de selección, detalle agrupado, impacto del editor y reflujo
de una columna a 640 px sin desbordamiento horizontal. CI, despliegue y comportamiento productivo
permanecen pendientes y se verifican por separado.
