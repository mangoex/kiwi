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

## TDD-TC-434 Corrección central de proveedor y unidad comercial

R3; verificación dirigida en `apps/api/tests/test_purchase_workspace.py`,
`apps/api/tests/test_corporate_purchases.py` y `tests/browser/test_supplier_workspace.mjs`.
Secuencia: contrato y regresión RED, escritor/preview compartidos, edición accesible, pruebas
SQLite de referencias/permisos/atomicidad/snapshots, QA 390/1440 y auditoría independiente.
PostgreSQL verifica versión concurrente usando el fixture aislado corporativo existente.
Sin migraciones ni cambios productivos: catálogo actualizable, documentos e historial inmutables.
Se prueba rollback ante referencia ajena/inactiva, versión ausente/obsoleta y fallo de auditoría;
precio cero y precisión interna, discrepancia heredada y corrección explícita del contenido.

Preguntas operativas: ¿quién corrigió qué? Auditoría antes/después con actor y UTC.
¿Por qué no guardó? Errores estables de referencia/permisos/versión visibles en el formulario.
¿Cambió el costo al asignar proveedor? Preview conservado y regresión de magnitudes/historia.

Evidencia local del paquete (2026-10-20): RED inicial 5 casos por identidad inmutable/preview sin
contexto; después 98 pruebas de workspace, compras locales/corporativas y proveedores verdes,
3 de permisos, 3 de referencias organización/sucursal y 1 recepción corporativa posterior a
corrección. Trazabilidad documental: 9 pruebas; API mypy (95 archivos), Ruff, typecheck Admin,
build y QA de navegador 390/1440 verdes. El harness existente de proveedores, conectado a CI,
incluye asignación, precisión, corrección explícita, error recuperable y permiso de lectura.
Auditoría Sol independiente: sin hallazgos accionables en el diff revisado.

Afirmación: corregir el catálogo conserva operaciones históricas y pendientes. Evidencia: comparación
de tablas/snapshots y confirmación/recepción posterior. Refutación intentada: reasignar proveedor y
unidad antes de confirmar; la actualización de precio compara proveedor, unidad y conversión en el
mismo UPDATE. Resultado local: snapshots/costos originales conservados, catálogo corregido intacto.
Riesgo residual: gate PostgreSQL concurrente pendiente (caso añadido al fixture CI existente).

CI #394 verificó los tres casos PostgreSQL corporativos, incluido el nuevo ganador único, y
detectó dos regresiones SQLite/PostgreSQL de caja al confirmar snapshots legacy sin rendimiento.
La guarda corregida usa comparación SQL nula (sin coincidencia) para omitir sólo el repricing de
catálogo cuando falta esa evidencia. No inventa conversión ni bloquea la confirmación o su historia.
Regresión determinista adicional: `test_legacy_purchase_snapshot_confirms_without_guessing_catalog_conversion`;
también se mantienen los casos existentes de carrera cierre de caja/compra en ambos dialectos.

Afirmación: no hay escritura parcial ni sobrescritura de una edición desactualizada. Evidencia:
versión observada, bloqueo/UPDATE condicional y auditoría transaccional. Refutación: replay, versión
inválida, referencias ajenas/inactivas y fallo inyectado de auditoría; sin efectos parciales en SQLite.
Resultado: rechazo estable y rollback. PostgreSQL no se certifica con SQLite.

Afirmación: metadata no repricia datos heredados ni redondea campos intactos. Evidencia: normalizador
compartido, strings originales y cálculo Decimal. Refutación: costo heredado 202.333333 con contenido
1 y rendimiento 0.45; precisión de seis decimales y precio cero. Resultado: costo/precisión conservados
hasta corrección explícita; preview de edición coincide con guardado.

No se ejecutó suite completa local, CI ni canary productivo en este paquete. No se publicó ni
modificó producción; el gate PostgreSQL real sigue pendiente antes de release. No hay cambio de
esquema. Reversibilidad: nueva corrección auditada con valores anteriores, conservando toda historia.

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
