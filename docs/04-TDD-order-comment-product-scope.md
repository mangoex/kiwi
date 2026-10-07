# TDD — alcance de comentarios por producto

## TDD-TS-132 Selección parcial y reemplazo exacto de productos

### TDD-TC-303 Estado jerárquico y preview exacto

Una prueba frontend determinista verifica funciones puras para:

- derivar `none`, `partial` y `all` desde los productos activos de una subcategoría;
- seleccionar o retirar una subcategoría completa sin perder selecciones de otras subcategorías;
- seleccionar o retirar un producto individual de forma deduplicada;
- calcular productos agregados, retirados y conservados para la confirmación;
- invalidar el preview cuando cambia el conjunto ordenado de `product_ids`.

La prueba semántica exige que `VariationNotes` despliegue productos con nombre y SKU, comunique
`aria-expanded` y estado mixto, ofrezca búsqueda y acciones masivas, y utilice el conjunto de
productos —no las categorías— como fuente de verdad.

### TDD-TC-304 Reemplazo exacto, auditoría e historia inmutable

Una prueba focal API crea un comentario relacionado con dos productos, consulta nombres/SKU,
reemplaza el alcance por un conjunto distinto mediante
`PUT /catalog/order-comments/{id}/products` y confirma:

- respuesta y lectura posterior contienen exactamente el conjunto deseado;
- la relación retirada deja de aparecer en ventas nuevas;
- `order_comment.products_replaced` conserva actor y conteos de productos/relaciones archivadas;
- pedidos y snapshots ya aceptados no son modificados.

### TDD-TC-305 Semántica aditiva separada del reemplazo

La prueba API conserva la regresión del alta masiva: reenviar un comentario existente con un
subconjunto agrega o reactiva destinos enviados y no archiva relaciones omitidas. La prueba frontend
exige copy visible que dirija las bajas al editor individual.

### TDD-TC-306 Errores, permisos y accesibilidad

Pruebas negativas verifican que conjunto vacío, producto inactivo/inexistente/de otra organización,
`branch_id` y actor sin `catalog.manage` fallen sin mutación parcial. El editor conserva el borrador,
muestra el error en `role=alert` y sólo se cierra tras una respuesta persistida. Una prueba de
navegador cubre teclado, foco de apertura/cierre, estado mixto anunciado, búsqueda por nombre/SKU y
reflujo sin desplazamiento horizontal en escritorio y ancho reducido.

### TDD-TC-307 Retiro rápido desde un chip

Una prueba frontend determinista verifica que el retiro produzca el conjunto ordenado restante y
rechace producto ausente o último destino. La prueba semántica exige un botón accesible dentro de cada
chip, el `PUT` vigente, error/éxito local a la tarjeta y CSS que revele la `X` con hover o foco y la
mantenga visible en dispositivos sin hover. El recorrido de navegador confirma que el chip no se
retira antes de la respuesta, desaparece tras éxito y la última `X` queda deshabilitada.

## Gates de implementación

1. RED focal: `node tests/frontend/test_admin_order_comment_product_scope.mjs` falla por ausencia de
   la función y el control de retiro rápido.
2. Dependencia backend: prueba focal de `test_global_catalog_comments_extras.py` confirma el contrato
   de reemplazo existente antes de cambiar UI.
3. GREEN: ambas pruebas focales, prueba arquitectónica de comentarios, typecheck Admin y build Admin.
4. Contrato cruzado: recorrido de navegador alta parcial → preview → aplicación y edición exacta de
   un comentario existente, sin errores de consola.
5. Cierre: `python -m pytest tests/architecture/test_traceability.py -q` y `git diff --check`.

PostgreSQL, migración, SQLite/gateway, POS/KDS y suite completa local no se activan mientras el diff
no cambie esquema, SQL, offline ni consumidores; CI ejecutará la suite completa que tenga configurada.
