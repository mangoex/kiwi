# Pantallas de referencia de Soft Restaurant

Revisión visual del 2026-09-18 sobre el repositorio en `d59c166`. Las 27 fotografías
documentan un recorrido administrativo de Soft Restaurant; constituyen evidencia de contexto,
no especificaciones ejecutables ni certificación de RestaurantOS.

- [Historias de usuario y contraste PRD → SDD → BDD → TDD](HISTORIAS.md).
- [Manifiesto de nombres originales, fechas EXIF y SHA-256](manifest.csv).
- [Contexto del producto](../docs/00-contexto-producto.md).
- [Matriz canónica de trazabilidad](../docs/05-matriz-trazabilidad.md).

## Criterio de orden

La numeración `001..027` sigue `DateTimeOriginal` del EXIF: 2026-09-08, de 14:10:29
a 14:35:20, tal como lo registra la cámara, sin atribuirle una zona horaria.
Esta secuencia coincide con los nombres IMG originales. Las fechas de modificación del
18 de septiembre corresponden a los archivos recibidos y no se usaron como fecha de captura.
No se recibió `IMG_3736.jpeg`; no se supone su contenido ni se deja un hueco en la numeración.

El nombre sigue `NNN_modulo-accion-o-contenido.jpeg`, sin acentos para facilitar enlaces.
Las imágenes conservan sus bytes, resolución y EXIF; sólo cambia el nombre. Para deshacer
el renombrado, `manifest.csv` relaciona `name` con `original` y permite verificar
`sha256` antes de restaurar nombres, sin sobrescribir archivos existentes.

## Lectura por flujo

| Grupo | Capturas | Historias |
|---|---|---|
| Acceso y navegación administrativa | 001, 002, 022 | SR-HU-01, SR-HU-02 |
| Insumos, clasificación y unidades | 003–006; unidad de venta en 016 | SR-HU-03, SR-HU-04 |
| Presentaciones y proveedores | 007–010 | SR-HU-05, SR-HU-06 |
| Productos, categorías, tamaños y estación | 011–016, 024 | SR-HU-07, SR-HU-08, SR-HU-09 |
| Receta, componentes, costeo y almacén | 017–019, 027 | SR-HU-10, SR-HU-11, SR-HU-12 |
| Comentarios de preparación y paquetes | 020, 025 | SR-HU-13, SR-HU-14 |
| Grupos y opciones de modificadores | 021 | SR-HU-15 |
| Orden del menú y de impresión | 023 | SR-HU-16 |
| Aplicación masiva de recetas | 026 | SR-HU-17 |
| Controles visibles sin recorrido completo | 003, 004, 007, 008 | SR-HU-18, SR-HU-19 |

## Inventario visual

Cada enlace abre la fotografía original renombrada. Las descripciones se basan en revisión visual;
un botón visible no prueba que se haya ejecutado la operación.

| Orden | Fotografía | Original | Hora EXIF | Contenido observado | Historias |
|---|---|---|---|---|---|
| 001 | [Inicio de sesi�n](001_acceso-inicio-de-sesion.jpeg) | `IMG_3730.jpeg` | 14:10:29 | Selecci�n de usuario, contrase�a y teclado. | SR-HU-01 |
| 002 | [Men� administrativo](002_inicio-menu-administrativo.jpeg) | `IMG_3731.jpeg` | 14:11:13 | Accesos a cat�logos, compras, almac�n y punto de venta. | SR-HU-02 |
| 003 | [Cat�logo de insumos](003_insumos-catalogo-y-costos.jpeg) | `IMG_3732.jpeg` | 14:12:13 | Listado con clave, descripci�n, costo y unidad; ficha y acceso a recetas relacionadas. | SR-HU-03, SR-HU-18, SR-HU-19 |
| 004 | [Alta de insumo](004_insumos-alta-y-propiedades.jpeg) | `IMG_3733.jpeg` | 14:12:50 | Grupo, clave, descripci�n, unidad, impuestos, inventariable y merma. | SR-HU-03, SR-HU-19 |
| 005 | [Grupos de insumos](005_insumos-grupos-y-clasificacion.jpeg) | `IMG_3734.jpeg` | 14:13:13 | Cat�logo de grupos con clasificaci�n y referencias a tipo de pedido y cuenta contable. | SR-HU-03 |
| 006 | [Unidad base del insumo](006_insumos-seleccion-unidad-base.jpeg) | `IMG_3735.jpeg` | 14:13:28 | Selector de unidades dentro de la ficha de insumo. | SR-HU-04 |
| 007 | [Alta de presentaci�n de compra](007_compras-alta-presentacion-insumo.jpeg) | `IMG_3737.jpeg` | 14:17:29 | Presentaci�n vinculada a insumo base, proveedor, rendimiento y costo. | SR-HU-05, SR-HU-18 |
| 008 | [Detalle de presentaci�n y rendimiento](008_compras-presentacion-proveedor-y-rendimiento.jpeg) | `IMG_3738.jpeg` | 14:18:07 | Ejemplo de frasco de 450 g equivalente a 0.4500 kg; proveedor y costos. | SR-HU-05, SR-HU-18 |
| 009 | [B�squeda del insumo base](009_compras-busqueda-insumo-base.jpeg) | `IMG_3739.jpeg` | 14:18:48 | Di�logo de b�squeda para vincular una presentaci�n a un insumo. | SR-HU-05 |
| 010 | [Cat�logo y alta de proveedores](010_proveedores-alta-datos-y-credito.jpeg) | `IMG_3740.jpeg` | 14:19:30 | Nombre, raz�n social, RFC, contactos, cr�dito, tipo, estado y cuenta contable. | SR-HU-06 |
| 011 | [Cat�logo de productos](011_productos-catalogo-y-ficha-general.jpeg) | `IMG_3741.jpeg` | 14:22:19 | Lista de productos y ficha con precio, impuesto, unidad, servicio y estado. | SR-HU-07 |
| 012 | [Detalle de producto y �rea de impresi�n](012_productos-precio-servicios-y-area-impresion.jpeg) | `IMG_3742.jpeg` | 14:22:37 | Producto seleccionado con grupo, subgrupo, precio, unidad y �rea Bebidas. | SR-HU-07, SR-HU-09 |
| 013 | [Selecci�n de grupo de producto](013_productos-seleccion-grupo.jpeg) | `IMG_3743.jpeg` | 14:22:46 | Categor�as comerciales como aguas, baguettes, bebidas y combos. | SR-HU-08 |
| 014 | [Selecci�n de subgrupo de producto](014_productos-seleccion-subgrupo.jpeg) | `IMG_3744.jpeg` | 14:22:50 | Subgrupos de tama�o: agua chica y agua grande. | SR-HU-08 |
| 015 | [Alta de subgrupo](015_productos-alta-subgrupo.jpeg) | `IMG_3745.jpeg` | 14:23:24 | Subgrupo relacionado con un grupo; lista de tama�os y extras. | SR-HU-08 |
| 016 | [Selecci�n de unidad de venta](016_productos-seleccion-unidad-venta.jpeg) | `IMG_3746.jpeg` | 14:23:44 | Selector de unidad dentro de la ficha comercial. | SR-HU-04, SR-HU-07 |
| 017 | [Editor de receta y almac�n de consumo](017_recetas-componentes-costeo-y-almacen.jpeg) | `IMG_3747.jpeg` | 14:24:50 | Componentes, cantidades, merma, costo, utilidad y relaci�n estaci�n-almac�n. | SR-HU-10, SR-HU-11, SR-HU-12 |
| 018 | [Selecci�n de ingrediente para receta](018_recetas-seleccion-de-ingredientes.jpeg) | `IMG_3748.jpeg` | 14:25:07 | Resultados de b�squeda de insumos de fresa para agregar a la receta. | SR-HU-10 |
| 019 | [Detalle de receta con costos](019_recetas-cantidades-costos-y-almacenes.jpeg) | `IMG_3749.jpeg` | 14:25:22 | Componentes capturados, cantidades, unidad, total y almacenes por estaci�n. | SR-HU-10, SR-HU-11, SR-HU-12 |
| 020 | [Comentarios y componentes de paquete](020_productos-comentarios-y-componentes-paquete.jpeg) | `IMG_3750.jpeg` | 14:26:16 | Dos secciones distintas: indicaciones de preparaci�n y productos de un paquete; ambas vac�as. | SR-HU-13, SR-HU-14 |
| 021 | [Producto compuesto y modificadores](021_modificadores-grupos-opciones-y-limites.jpeg) | `IMG_3751.jpeg` | 14:26:46 | Grupo de edulcorante con opciones, m�ximo, secuencia y multiplicaci�n por cantidad. | SR-HU-15 |
| 022 | [Men� de cat�logos e insumos](022_navegacion-menu-catalogos-e-insumos.jpeg) | `IMG_3752.jpeg` | 14:30:31 | Rutas a unidades, clasificaci�n, grupos, presentaciones e insumos elaborados. | SR-HU-02 |
| 023 | [Prioridad de grupos](023_productos-prioridad-visual-y-de-impresion.jpeg) | `IMG_3753.jpeg` | 14:31:11 | Orden de visualizaci�n separado del orden de impresi�n de notas y facturas. | SR-HU-16 |
| 024 | [Consulta de subgrupos, tama�os y extras](024_productos-subgrupos-tamanos-y-extras.jpeg) | `IMG_3754.jpeg` | 14:32:14 | Subgrupos de jugos, licuados, extras y servicio a domicilio. | SR-HU-08 |
| 025 | [Asignaci�n o eliminaci�n masiva de comentarios](025_comentarios-asignacion-masiva-por-grupo.jpeg) | `IMG_3755.jpeg` | 14:32:49 | Selecci�n de grupo y acci�n sobre comentarios; no se ve un resultado ejecutado. | SR-HU-13 |
| 026 | [Captura masiva de recetas](026_recetas-captura-masiva-por-productos.jpeg) | `IMG_3756.jpeg` | 14:34:50 | Receta con un insumo y selecci�n de productos destino; modo Reemplazar visible. | SR-HU-17 |
| 027 | [Cat�logo y alta de almacenes](027_almacenes-catalogo-y-asignacion-empresa.jpeg) | `IMG_3757.jpeg` | 14:35:20 | Clave, descripci�n, tipo y empresa; aparece un almac�n general. | SR-HU-12 |

## Alcance de la evidencia

Las fotos muestran formularios, listas y controles. No muestran respuestas del backend,
registros de auditoría, persistencia después de guardar, reglas de concurrencia ni pruebas.
Las pantallas 020 y 025 no contienen un ejemplo completo de comentarios aplicado; 026 muestra
selección de destino, pero no el resultado de reemplazar recetas.

No hay capturas detalladas de cobro, cortes, compras confirmadas, conteo físico, traspasos, KDS,
reparto ni operación offline. Sus accesos en el menú no se convierten en historias demostradas
por estas fotografías. Mesas, meseros y reservaciones visibles en el menú quedan sujetos a
las exclusiones de la versión 1 del PRD.

El contexto útil es la separación entre **insumo base → presentación de compra → receta →
producto vendible**, junto con proveedores, unidades y almacén. La distribución de ventanas,
los colores, los códigos y los importes del sistema de referencia no son contratos de RestaurantOS.
