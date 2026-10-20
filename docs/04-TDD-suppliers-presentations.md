# TDD - Proveedores y presentaciones de compra

## TDD-TS-040 Proveedores, contactos y presentaciones

Casos:

- crear proveedor central con código y RFC no duplicados;
- agregar múltiples contactos y banderas principales por función;
- configurar disponibilidad y condiciones por sucursal;
- crear presentación ligada a proveedor, artículo y unidad comercial;
- exigir rendimiento y contenido aprovechable positivos;
- calcular precio por unidad base con `Decimal` y redondeo documentado;
- registrar baseline corporativo e historial inmutable branch-scoped al capturar o recibir precio;
- resolver precio/costo efectivo con el mismo servicio para compras, diagnóstico y presentaciones;
- confirmar que compra/recepción en A no cambia precio, costo ni preferencia efectiva de B;
- no crear movimientos ni actualizar costo promedio al editar una presentación;
- rechazar unidad base distinta a la del artículo sin equivalencia autorizada;
- aplicar y revertir la migración conservando catálogos previos;
- restringir escritura a `catalog.manage` y lectura operativa a permisos autorizados.

## TDD-TC-033 Presentación de azúcar

Given azúcar tiene kilogramo como unidad base
When el administrador registra una bolsa de 10 kg a 280 pesos netos
Then `cost_per_base_unit` es 28
And existe una entrada baseline en historial de precios
And no existe un movimiento de inventario por esa captura
When una recepción en A confirma otro precio
Then el historial/proyección efectivos pertenecen a A
And B conserva su historial propio o el baseline corporativo.

## TDD-TC-406 Panel lateral completo de proveedor

Given el detalle de proveedor contiene datos del catálogo y un aviso de información financiera no disponible
When la suma de las secciones supera la altura disponible
Then el cuerpo del FastTab se encoge dentro del viewport y ofrece desplazamiento vertical propio
And el FastTab de CXP usa el ancho amplio en escritorio y ancho completo en móvil
And sólo el formulario editable queda deshabilitado en consulta
And las secciones conservan sus controles interactivos
And el crédito cero no se reemplaza por quince al consultar ni al guardar otro campo
And guardar un contacto conserva el límite de crédito interno sin redondearlo
And los estados activo, inactivo y suspendido conservan etiquetas distintas en listado y detalle
And no se asignan ciudades, facturas, saldos, semáforos, DPO o proyecciones de ejemplo
And un fallo de API se distingue de una colección vacía y permite reintentar
And los permisos de consulta no habilitan alta ni edición.

Evidencia automatizada dirigida: `tests/frontend/test_supplier_fast_tab_layout.mjs` y
`tests/browser/test_supplier_workspace.mjs` (fixtures sintéticos aislados, 390/1440 px,
consulta/edición, guardado sin cambiar crédito cero, precios con dos decimales, errores y recuperación).
La regresión de navegador está conectada al runtime aislado de Playwright del job frontend de CI;
`tests/architecture/test_ci_gates.py` verifica su inclusión obligatoria.

Alcance R2: presentación y fidelidad del catálogo; no modifica el cálculo ni la persistencia
de cuentas por pagar. Preguntas operativas: ¿falló la consulta o el catálogo está vacío?
La señal es el aviso de error con reintento, distinto del estado vacío. ¿El proveedor tiene saldo
cero o falta información financiera? La señal es el aviso explícito de información no disponible;
no se muestran importes, semáforos ni proyecciones sin fuente.
