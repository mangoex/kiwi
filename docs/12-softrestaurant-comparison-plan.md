# Comparación con Soft Restaurant y plan de adaptación
Fecha: 2026-09-30. Base local: main, 5e09788afbcdf81826a3cadeac68880794bf52c8.

## Alcance y autoridad
Análisis solicitado de compras, productos, productos compuestos, insumos y presentaciones.
El análisis inicial fue R0. La instrucción posterior activa el paquete de especificación
SR-WORKSPACE-001 descrito al final y su cadena PRD/SDD/BDD/TDD/matriz. No autoriza despliegue,
migraciones ni cambios de datos. Las futuras intervenciones de runtime en compras, costeo,
inventario, permisos o consumo de recetas son R3.

Se leyeron las transcripciones automáticas de los cuatro videos y fotogramas seleccionados.
Las transcripciones pueden contener errores; los nombres, importes y unidades no se importan al
dominio. Los videos muestran versiones/configuraciones concretas de Soft Restaurant, no certifican
todas sus capacidades actuales. Se inspeccionó código y especificaciones locales; no se ejecutaron
pruebas funcionales en el análisis inicial; la evidencia posterior se distingue al final.
No se verificó la aplicación desplegada.

## Fuentes externas y observaciones
- [Compras](https://www.youtube.com/watch?v=KMBw7VCoOyw):
  00:27–01:28 cabecera con proveedor, fecha y referencia; 01:30–02:49 búsqueda y partida por
  presentación; 02:53–03:20 almacén; 03:26–04:16 costo y restricción de modificación.
  Se observa una tabla de partidas, pero el tutorial sólo explica una partida y no demuestra
  la confirmación completa de una nota con varios artículos.
- [Productos compuestos, RSB Systems](https://www.youtube.com/watch?v=j-RvWlreaN8):
  06:43–12:47 grupos ordenados con incluidos, máximo y captura obligatoria; 12:50–17:15 opciones
  y recargos; 17:34–19:57 resultado POS; 20:24–23:21 visibilidad por terminal/horario;
  23:37–25:51 copia de configuración.
- [Productos compuestos y modificadores 2025](https://www.youtube.com/watch?v=Ju4jkxlP8zs):
  00:35–02:40 productos base y opciones; 03:08–05:44 configuración desde la ficha del producto;
  05:47–06:46 ocultación de un grupo en el menú.
- [Insumos y presentaciones](https://www.youtube.com/watch?v=4BAsUl1MbI4):
  00:01–01:24 insumo y unidad; 01:37–04:59 varias presentaciones asociadas al mismo insumo;
  05:50–07:40 producto de venta con receta; 07:48–09:51 selección de mezclador.
  El ejemplo emplea equivalencias aproximadas: no constituye una política de conversión aprobada.

Dos enlaces tratan específicamente productos compuestos. La comparación de productos simples
proviene de las altas de producto incluidas en esos tutoriales y del cuarto video.

## Diferencias verificadas
| Área | Referencia observada | RestaurantOS actual | Acción recomendada |
| --- | --- | --- | --- |
| Compras corporativas | Cabecera y tabla de partidas en una ventana | PurchasesList.tsx captura una sola presentación y envía lines con un elemento | Editor de nota completa con varias partidas |
| Compras de sucursal | Captura documental con partidas | BranchAdminPurchases ya permite agregar/quitar filas y enviar varias líneas | Compartir editor y contrato con Admin; evitar dos flujos divergentes |
| Modelo de compra | Presentación y cantidad comercial | Backend y JSON Schema ya aceptan lines[]; Python calcula importes, conversión y costo | Reutilizar motor; verificar recorrido completo con varias líneas |
| Presentaciones | Insumo base con múltiples empaques/proveedor | Modelo tiene contenidos, unidades, rendimiento y proveedor; UI expone un subconjunto | Mostrar equivalencia comercial/base y navegación contextual |
| Ficha de producto | Lista lateral y secciones de configuración | ProductsList ya ofrece lista/detalle y pestañas de receta, combo y compuesto | Ajustes de búsqueda, densidad y continuidad; conservar avances existentes |
| Compuesto seleccionable | Preguntas ordenadas, incluidos, máximos, opciones y extras | ModifierManager y PRD-FR-245 contemplan estas reglas | Afinar editor y vista previa; distinguir comentarios de componentes consumibles |
| Combo fijo | No es el caso principal de esos tutoriales | Existe composición fija independiente y versionada | Mantener distinción visible entre siempre incluido y seleccionable |
| Copia de configuración | Copia a otro producto | Hay clonación heredada de grupos ordinarios; componentes tienen restricciones | Diseñar copia completa sobre el comando versionado; no eludir restricciones |
| Visibilidad | Tutorial muestra control por terminal y horario | Hay estados/alcance y catálogo POS; no se acreditó equivalencia por terminal/horario | Diferir hasta definir necesidad; es cambio de contrato, no ajuste visual |
| Costos en captura | Presentación muestra precio y rendimiento | Backend usa Decimal; algunas previsualizaciones frontend hacen aritmética JS | DTO de previsualización calculado en Python |
| Información de costos | Pantallas del tutorial muestran distintos costos | Texto de PresentationsList puede confundir equivalencia de precio con costo de receta | Etiquetas inequívocas: precio de compra, costo por unidad base y promedio contable |

## Hallazgos que condicionan el plan
### Compras
1. Admin corporativo: apps/admin-web/src/features/purchasing/PurchasesList.tsx:24 y :39.
   El formulario tiene una sola presentación. No es una limitación del modelo transaccional.
2. Sucursal: apps/pos-web/src/features/admin/BranchAdminOperations.tsx:303.
   Ya existen array de líneas, agregar/quitar fila y envío conjunto.
3. Backend: apps/api/restaurant_os/operations.py:19771 y :19937.
   Crear valida las partidas y persiste documento/líneas; confirmar calcula recepciones/promedio,
   retiro si procede y auditoría. Se requiere verificar atomicidad y concurrencia con pruebas,
   no inferirlas sólo por lectura.
4. apps/api/restaurant_os/models.py:1514 contiene identidad única por sucursal/proveedor/tipo/folio.
   Esto no equivale a recuperar idempotentemente la respuesta perdida de una creación.
   Crear recibe un dict HTTP y no consume una clave de creación en la función inspeccionada;
   confirmar sí tiene clave idempotente.
5. El test test_branch_supplier_presentation_and_multiline_purchase, en
   apps/api/tests/test_branch_purchases_and_courtesies.py, enviaba UNA línea en el baseline inicial.
   Su nombre no acreditaba una compra de varias partidas. En el paso posterior se amplió el test
   a tres partidas y dos presentaciones; ver TC-280 y evidencia al final.
6. El destino actual de confirmación es el almacén resuelto para la sucursal.
   Elegir almacén por partida, como en la referencia, sería una ampliación de dominio.
7. Las rutas inspeccionadas permiten crear, confirmar y cancelar; no se encontró allí un
   comando para editar borradores persistidos. Editar filas antes de guardar sí es posible.
8. XML, cuentas por pagar y lotes/caducidad tienen requisitos en PRD-FR-101..107 y estados
   Disenado en la matriz. La captura manual de una nota no acredita esas capacidades.
   Invoicing de ventas no debe confundirse con recepción/importación de compras.

### Relaciones y presentación de costos
1. operations.py:19476, create_purchase_presentation, puede sustituir un proveedor inexistente
   por otro consultado; con varios resultados scalar_one_or_none puede fallar.
   Es evidencia estática, sin reproducción en este análisis. El proveedor seleccionado debe
   conservarse o rechazarse; cualquier regla de proveedor general requiere especificación explícita.
2. PresentationsList.tsx:165 calcula precio/rendimiento con parseFloat.
   BranchAdminOperations.tsx:342 calcula totales de la nota en JS.
   ItemsList.tsx:474 calcula costo con impuesto y merma en JS.
   El backend sigue recalculando al guardar; no se afirma que estos previews alteren el ledger.
   Deben reemplazarse por resultados Python para cumplir la autoridad determinista solicitada.
3. PresentationsList.tsx:381 afirma que el costo se usará automáticamente en recetas.
   PRD-FR-094 distingue precio informativo de costo promedio actualizado por recepción.
   Debe aclararse la fuente y finalidad de cada costo.
4. Algunas lecturas usan queryKey sin branchId en Admin. Antes de compartir el editor se debe
   probar cambio de sucursal y aislamiento del cache/formulario. No se certifica filtración real.
5. La ficha y creación rápida de presentación asignan defaults numéricos/proveedor.
   Vacío o cero no debe convertirse silenciosamente en rendimiento 1 o impuesto 16 %.
   Las conversiones autorizadas deben distinguir masa, volumen y piezas; ninguna relación entre
   dimensiones puede inferirse sólo del nombre del artículo.

## Dependencias que se conservan
Proveedor y condiciones de sucursal -> presentación comercial -> insumo y unidad base.
Presentación + cantidad + precio + descuento + impuesto -> borrador de compra.
Confirmación -> movimientos de recepción + costo promedio + retiro único si procede + auditoría.
Producto de venta -> receta efectiva/versionada -> insumos/subrecetas.
Producto compuesto -> grupo -> opción/componente -> receta efectiva -> snapshot de pedido.
Combo fijo -> productos componentes y cantidades -> composición versionada.

Una presentación nueva no crea existencias. Un precio de catálogo no cambia el promedio contable.
Una receta nueva no reescribe pedidos ni costos históricos. Comentarios de preparación no consumen
inventario por convertirse visualmente en una opción. Componentes reales sí requieren su contrato
de consumo. Las restricciones vigentes incluyen no autorreferencia, componentes activos de la misma
organización/estación con receta efectiva y exclusión de anidamientos no permitidos.

## Plan por paquetes
| Orden | Paquete | Resultado | Riesgo y dependencias |
| --- | --- | --- | --- |
| 1 | Guardas de relación y costos | Proveedor inequívoco; defaults veraces; conceptos de costo claros | R3 si cambia validación/persistencia; base de altas seguras |
| 2 | Compra completa en ambas interfaces | Una cabecera, varias partidas, búsqueda, detalle y totales Python | R3, dinero/caja/inventario; motor y relaciones existentes |
| 3 | Ficha de insumo y presentación | Alta contextual sin perder la nota; unidad comercial/base y rendimiento visibles | R1 si sólo navegación; R3 si cambia alta/conversión |
| 4 | Ficha de producto y compuesto | Mejor configuración, previsualización y eventual copia versionada | R1 visual; R3 si cambia precio/consumo/configuración |
| 5 | Recepción documental ampliada | Crédito real, XML/OCR, lotes, caducidad o almacenes adicionales según alcance aprobado | R3; especificaciones y posible migración independiente |

No se necesita introducir agentes para completar los paquetes 1–4. Una futura IA podría preparar
el mismo borrador y detectar faltantes, sometiéndose al mismo contrato y revisión.

### Paquete 2: compra completa
Cabecera única: sucursal, proveedor, tipo, folio, fecha documental y modalidad de pago disponible.
Tabla: insumo/presentación, cantidad comercial, equivalencia base, precio antes de descuento,
descuento monetario por línea, impuesto monetario por línea e importe.
Resumen: subtotal, descuentos, impuestos y total devueltos por Python, con documento completo
visible antes de confirmar. Búsqueda por nombre/código; códigos de barras sólo si su contrato está
habilitado. Agregar, quitar y corregir filas localmente antes de guardar.

Componentes compartidos entre apps con alcance y permisos explícitos; no compartir estado sensible
entre sucursales. Nueva operación de preview sin persistencia, validación tipada en frontera, Decimal
y política de redondeo canónica. No crear documentos temporales para obtener un preview.

Cambiar proveedor exige revisar/limpiar partidas incompatibles y no perderlas silenciosamente.
Guardar crea un único borrador; confirmar sigue siendo operación independiente.
Detalle persistido debe mostrar todas las partidas y equivalencias congeladas.
Recuperar un guardado con respuesta perdida antes de volver a crear: elegir y documentar identidad
de creación/idempotencia. No afirmar que la confirmación idempotente cubre la creación.

Editar borrador persistido, aprobar diferencias de precio, descuentos globales, fletes y crédito
son ampliaciones separadas. No incluirlos implícitamente en una tabla nueva.
No introducir un permiso nuevo para precios sin definir actor, límite, aprobación y auditoría.
Que un pago no use caja no demuestra que exista una cuenta por pagar.

### Paquete 3: presentaciones
Desde el insumo, mostrar proveedor, empaque, contenido/unidad, rendimiento base, precio informativo,
equivalencia calculada por Python y estado. Desde una compra, poder abrir la ficha o un alta autorizada
y volver a la misma nota. Cancelar un alta deja el borrador intacto.
El guardado de catálogo debe quedar explícitamente separado del guardado/confirmación de recepción.

### Paquete 4: productos compuestos
Mantener las pestañas ya construidas. Editor de grupos con orden, mínimo obligatorio, máximo,
selecciones incluidas y recargos, expresados en lenguaje del operador.
Vista previa con precio y consumo desde backend; conservar separación entre comentario, ingrediente
adicional, componente de producto y combo fijo.
La copia completa debe validar destino, versiones y dependencias bajo el comando canónico.
No usar la clonación heredada para saltar la prohibición de componentes.
No adoptar automáticamente máximo=0 como infinito, como describe el tutorial.
La configuración por terminal/horario o componentes de estaciones distintas requiere alcance propio.

## Criterios de aceptación propuestos
Los criterios siguientes proceden del análisis inicial. La sección SR-WORKSPACE-001 los concreta
en 18 escenarios BDD con IDs, suites TDD y matriz; su implementación permanece pendiente.
1. Crear una nota de al menos tres partidas en Admin y sucursal produce un documento y conserva
   todas las líneas, proveedor, fecha y folio.
2. Una partida inválida entre partidas válidas rechaza toda la operación correspondiente sin efectos
   parciales en documento, recepción, caja o costo.
3. Cambiar proveedor/sucursal obliga a resolver incompatibilidades y nunca conserva una asociación
   silenciosa con otro proveedor/almacén.
4. Preview Python coincide con el documento persistido bajo el mismo contexto; si cambian datos
   relevantes, se revalida y muestra la diferencia antes de ejecutar.
5. Repetir confirmación tras perder HTTP produce una sola recepción por partida y un solo retiro
   para todo el documento; probar también recuperación de creación.
6. Dos presentaciones distintas del mismo insumo dentro de una nota convierten y acumulan correctamente
   cantidad/valor; no sobrescriben el cálculo de la primera línea.
7. Proveedor inexistente/inactivo o no autorizado produce error estable, sin sustitución.
8. Costo promedio cambia al recibir, no al editar precio de presentación ni al guardar borrador.
9. Cancelación conserva los originales y compensa los efectos conforme al contrato vigente.
10. Cambiar sucursal no muestra ni permite reutilizar datos o borradores de otra sucursal.
11. Opciones incluidas/extras respetan mínimo/máximo, precio Python y receta congelada; editar catálogo
    después de aceptar un pedido no modifica su snapshot.
12. Lectores sin permisos no pueden crear presentaciones, alterar precios ni confirmar compras.

## Artefactos activados y verificación futura
- PRD: sólo nuevas capacidades, actores, permisos o reglas. Referencias existentes:
  PRD-FR-061/062, 080..094, 100..111, 207, 242..245 y 248.
- SDD/ADR: contrato del preview, creación recuperable, relaciones, estado/concurrencia o decisiones
  nuevas. Mantener las fórmulas canónicas y la separación compra/receta/ledger.
- BDD: nota de varias partidas, altas contextuales, proveedor inválido, revisión de precio y
  comportamiento de copia sólo según el alcance que cambie.
- TDD: tests dirigidos de frontera, Decimal, multilínea real, misma materia prima en varias líneas,
  aislamiento, atomicidad, replay, compensación y carreras. Suites existentes TDD-TS-041 y 117.
- Matriz: añadir enlaces/evidencia que efectivamente cambien; no elevar estados por lectura.
- Backend: pytest focal, Ruff y mypy; frontend: pruebas semánticas afectadas y typecheck.
  Build antes de release. PostgreSQL por persistencia/bloqueo/concurrencia; SQLite/gateway sólo
  cuando compatibilidad offline/dual se vea afectada. El alta actual de compras es online.
- Recorrido E2E crítico de nota -> confirmación -> kardex/costo/caja -> cancelación.
  QA visual en ambas interfaces y breakpoints afectados.
- Auditoría independiente R3 antes de release; revisar origen -> operación sensible, guardas
  hermanas y correspondencia entre validación y escritura. CI sólo acredita lo que ejecuta.
- Migración/reversibilidad sólo si cambian esquema/estado/constraints. La tabla multilínea existente
  no exige por sí sola una migración, pero no se garantiza ausencia de migraciones en todo el plan.
- Canary acotado de R3 bajo autorización productiva separada, con observación y compensación.
  No afirmar despliegue por commit/push.

Preguntas operativas para esos paquetes:
1. ¿Qué nota se creó/confirmó y cuáles partidas produjeron movimientos?
2. ¿Una respuesta perdida produjo replay o una operación nueva?
3. ¿Qué guardia rechazó el documento y hubo algún efecto parcial?
4. ¿Cuál es el resultado de compensar una nota confirmada?
Auditoría/identificadores y métricas de resultado deben responder esas preguntas sin incluir documentos
completos, información personal ni claves de idempotencia en logs.

## Decisiones del diseño inicial (SR-A00)
- Política de modificar precio en recepción: autoridad actual o permiso/aprobación diferenciados.
- Si se requieren crédito real, descuentos globales, flete, lotes/caducidad, XML/OCR o varios almacenes,
  definirlos antes de ampliar el contrato.
- Si se permite editar borrador persistido y cómo se detectan versiones concurrentes.
- Prioridad de implementar la copia completa especificada en §51.6; no bloquea compras.
- Si existe necesidad real de visibilidad por terminal/horario; no asumirla por el video.

## Índice de evidencia local
- [Compras Admin](../apps/admin-web/src/features/purchasing/PurchasesList.tsx)
- [Compras sucursal](../apps/pos-web/src/features/admin/BranchAdminOperations.tsx)
- [Operaciones canónicas](../apps/api/restaurant_os/operations.py)
- [Modelo persistido](../apps/api/restaurant_os/models.py)
- [Contrato de compra](../packages/contracts/schemas/purchase-command.schema.json)
- [Presentaciones](../apps/admin-web/src/features/purchasing/PresentationsList.tsx)
- [Insumos](../apps/admin-web/src/features/inventory/ItemsList.tsx)
- [Productos](../apps/admin-web/src/features/catalog/ProductsList.tsx)
- [Compuesto](../apps/admin-web/src/features/catalog/ModifierManager.tsx)
- [Combo fijo](../apps/admin-web/src/features/catalog/ComboCompositionModal.tsx)
- [BDD compras](03-BDD-direct-purchases-costing.md)
- [BDD presentaciones](03-BDD-suppliers-presentations.md)
- [BDD receta/compuesto](03-BDD-recipes-production-modifiers.md)
- [TDD compras](04-TDD-direct-purchases-costing.md)
- [TDD compuesto](04-TDD-recipes-production-modifiers.md)
- [Matriz](05-matriz-trazabilidad.md)
- [Test de compra multilínea ampliado](../apps/api/tests/test_branch_purchases_and_courtesies.py)

## Cierre del análisis inicial
Entregable documental, sin cambios de runtime ni nuevos requisitos aprobados. Evidencia: lectura del
checkout, especificaciones, transcripciones y fotogramas. Los hallazgos de riesgo son observaciones
estáticas que requieren reproducción/pruebas en su paquete. Pruebas funcionales, CI, despliegue,
migraciones y comportamiento productivo no se verificaron en este análisis.

## Paquete autorizado de especificación — SR-WORKSPACE-001 (SR-A00 histórico)

La instrucción posterior del usuario activa PRD, SDD/ADR, BDD, TDD y matriz. Este paso entrega diseño,
criterios, actividades y pruebas de caracterización del motor existente. No implementa aún el editor,
previews, recuperación de creación, guardas nuevas ni copia completa. Esos cambios futuros son R3;
esta entrega conserva runtime y no realiza despliegue ni migración.

### Autoridades y trazabilidad

| Contrato | Autoridad de diseño | Criterios | Verificación |
| --- | --- | --- | --- |
| Nota completa en Admin/sucursal | PRD-FR-249; SDD §51.1/51.2/51.4 | BDD-FEAT-116; seis escenarios | TDD-TS-123; TC-280..283 |
| Cálculos exclusivamente Python | PRD-FR-250; SDD §51.3; sustituye permiso de preview JS en §50.2 | BDD-FEAT-117; cuatro escenarios | TDD-TS-123; TC-284/285 |
| Presentaciones/alta contextual | PRD-FR-251; SDD §51.1/51.5 | BDD-FEAT-118; cuatro escenarios | TDD-TS-124; TC-286/287 |
| Compuestos y copia completa | PRD-FR-252; SDD §51.6 | BDD-FEAT-119; cuatro escenarios | TDD-TS-124; TC-288/289 |

En SR-A00, ADR-037 era propuesta y FR249..252 permanecían `Disenado`. La autorización posterior
acepta la ADR y activa runtime; la evidencia de ejecución se registra al final de este plan.

Artefactos canónicos: [PRD](01-PRD.md), [SDD](02-SDD.md), [ADR](08-adrs-propuestas.md),
[BDD del paquete](03-BDD-softrestaurant-workspace.md), [TDD del paquete](04-TDD-softrestaurant-workspace.md)
y [matriz](05-matriz-trazabilidad.md).

### Actividades, dependencias y salida verificable

| ID | Actividad concreta | Depende de | Resultado/gate |
| --- | --- | --- | --- |
| SR-A00 | Especificar paquete, fórmulas, criterios y matriz; caracterizar recepción multilínea actual | Análisis y dominio vigente | Este paso; trazabilidad y pytest focal |
| SR-A01 | Reproducir proveedor inválido/ausente con varios proveedores, unidades inválidas y ceros/defaults; corregir guardas en writers y lectores hermanos | SR-A00 | RED dirigido por razón esperada -> GREEN; TC-286; permisos y ausencia de efectos |
| SR-A02 | Extraer funciones puras compartidas; DTOs estrictos, límites y previews Python de compra/presentación/insumo/receta; resolver discrepancias de campos sin cambiar fórmulas | SR-A01 y contratos actuales | TC-284/285; paridad/pureza; pytest, Ruff, mypy; contrato de cadenas decimales |
| SR-A03 | Diseñar evidencia durable de creación, namespace/retención/compatibilidad; implementar replay autorizado y resolver fecha HTTP/schema | SR-A00; patrón §48 | TC-282; PostgreSQL real con dos writers; migración aditiva si necesaria y reversibilidad |
| SR-A04 | Montar editor común en Admin/sucursal, lista de partidas, revisión de proveedor/precio, detalle y cache por alcance | SR-A01/02/03 | TC-280/281/283; pruebas semánticas ambas apps, typecheck, E2E crítico y QA visual |
| SR-A05 | Mejorar ficha insumo/presentaciones y alta contextual; labels de costo/fuente; retorno a captura | SR-A01/02/04 | TC-286/287; catálogo sin recepción; permisos sin escalación; QA afectado |
| SR-A06 | Afinar editor compuesto y vista previa de selección; comando de copia completa con versiones de origen/destino y dependencias | Dominio compuesto vigente; SR-A00/02 para previews | TC-288/289; PostgreSQL con writers hermanos; snapshots y replay; no clonación legacy |
| SR-A07 | Cerrar paquete implementado con auditoría R3 fresca, CI de gates efectivos y evidencia local/producción separada | Paquete elegido completo y sus dependencias | Sin claims no probados; build antes de release; canary autorizado, observable y compensable |

SR-A06 puede entregarse después de compras, sin hacer que la copia bloquee la mejora documental.
SR-A04 sí depende de las tres guardas de seguridad/cálculo/recuperación. No se libera una tabla nueva
con creación incierta o totales de otra autoridad. Cada cambio de comportamiento obtiene su RED
antes de implementar; este paso de documentación/caracterización no fabrica un RED funcional.

Actividades posteriores independientes: edición versionada de borradores persistidos, control nuevo
de cambios de precio, crédito/cuentas por pagar, XML/OCR, flete/distribución, lotes/caducidad,
varios almacenes y horarios/terminales. Requieren especificación y alcance propios; no son bloqueos
para la captura manual dentro del contrato vigente.

### Precisión comprobada y límite de evidencia

La prueba de borde encontró que `_money`, `_quantity` y `_cost` en el motor actual cuantizan a
**seis decimales**. Una propuesta inicial de centavos por fila habría cambiado la fórmula; se
corrigió la especificación y el test antes de tocar runtime. Ejemplo real: 0.5 * 0.29 conserva
0.145000; documento 562.015000; sólo retiro convierte ese total a 56202 centavos con HALF_UP.
El promedio usa costo recibido sin impuesto y saldo físico. No se modificó `_money` global.

La sección histórica SDD §41 sobre reportes describe redondeo al centavo como equivalente al comando;
esta comparación no permite certificar esa paridad para importes fraccionarios. Queda como
investigación dirigida del contrato de reportes antes de afirmar conciliación exacta; no se corrige
historia financiera ni se adopta una nueva política de redondeo en este paquete.

La caracterización actual, con fixture de administrador autorizado, valida tres partidas/dos presentaciones del mismo insumo, totales exactos,
última presentación inválida sin escritura parcial, stock recibido, replay de confirmación y
cancelación con tres referencias compensatorias. No verifica todavía creación idempotente,
proveedores sustituidos, previews puros, UI compartida o concurrencia PostgreSQL. El test de efectivo
existente valida caja requerida, retiro único y depósito compensatorio para una compra.

### Cierre histórico de SR-A00 — 2026-09-30

| Verificación ejecutada | Resultado | Alcance |
| --- | --- | --- |
| `python -m pytest tests/architecture/test_traceability.py -q` | 9 passed | IDs únicos, relaciones y estados documentales; no certifica runtime |
| `python -m pytest apps/api/tests/test_branch_purchases_and_courtesies.py -q` | 2 passed | Compra real de tres filas y caso existente de efectivo; SQLite aislado |
| `python -m ruff check apps/api/tests/test_branch_purchases_and_courtesies.py` | All checks passed | Test modificado |
| Integridad documental focal | 7 documentos, 19 enlaces locales válidos | Fences balanceados y whitespace |
| `git diff --check` | Sin errores | Diffs versionados; nuevos documentos incluidos en integridad focal |
| Auditoría independiente R3 con contexto fresco | Sin hallazgos accionables; 11 tests focales repetidos verdes, Ruff y diff verdes | Diseño y caracterización; sin cambios de runtime |

La advertencia Starlette/TestClient sobre `httpx` ya existía en el baseline; no se alteran dependencias
para silenciarla. No se ejecutaron CI remoto, mypy de runtime, typecheck/build/QA de frontend,
PostgreSQL, migraciones, E2E o canary: no cambió código de producción ni frontend. Esos gates se
activan por el diff real de cada actividad futura y no se presentan como aprobados en este cierre.

Afirmaciones revisadas en el mismo ciclo R3:

| Afirmación | Evidencia | Intento de refutación | Resultado | Riesgo residual |
| --- | --- | --- | --- | --- |
| Compra multilínea conserva importes Decimal del motor | TC-280 y helpers canónicos | Tercera partida fraccionaria, mismo insumo en dos presentaciones | Totales exactos y recepción de 30 unidades base | Promedio con existencia/costo previo y PostgreSQL real pendientes del paquete |
| Una última presentación inválida no deja escritura parcial | Snapshot de documentos, líneas, movimientos, estados de costo y caja | Dos filas válidas seguidas de ID inexistente | Error estable; cinco conjuntos sin cambios | Inyección de fallo durante confirmación y carreras aún pendientes |
| Replay confirmado no duplica efectos; cancelar preserva originales | Snapshots antes/después del replay y referencias de reversión | Reenviar misma clave; cancelar las tres recepciones | Efectos sin cambios; tres compensaciones y saldo físico restaurado | Creación recuperable y caso de efectivo multilínea requieren tests propios |
| Diseño futuro no se anuncia como implementado | Matriz Disenado, encabezados BDD/TDD/SDD y lista de actividades | Buscar una elevación de estado por baseline verde | Sin hallazgos en revisión independiente | Funciones nuevas no operativas hasta implementar y verificar |

El paso solicitado de especificaciones, criterios, plan, actividades y pruebas queda completado.
Al cerrar SR-A00 la implementación permanecía pendiente, sin commit, push, release ni
modificación productiva. La ejecución posterior se documenta a continuación.

## Ejecución autorizada — 2026-09-30

La instrucción “proceed” activa SR-A01..07 para implementación y verificación locales.
Se preserva el paquete documental anterior; los estados se elevan sólo con evidencia efectiva.
Producción, datos y configuración siguen bajo autorización separada.

### Resultado implementado

SR-A01..06 quedan implementados y verificados localmente. SR-A07 cierra la auditoría y evidencia
local del paquete; CI remoto, publicación y liberación productiva permanecen pendientes.

- Admin y sucursal comparten editor de nota completa con hasta 200 partidas, proveedor explícito,
  fecha documental, precios/descuentos/impuestos y revisión del detalle persistido antes de confirmar.
- Compra, presentación, ficha de insumo, receta y selección de compuesto solicitan previews Python.
  Dinero, cantidades, conversiones, merma y costos conservan `Decimal` y la fórmula canónica. La UI
  descarta resultados obsoletos y presenta costo pendiente cuando falta una fuente válida.
- Presentaciones validan proveedor, alcance, unidad base y comercial y contenido/rendimiento.
  El flujo nuevo exige IDs explícitos; el writer legacy conserva sólo compatibilidad documentada por
  identidad conocida. El alta contextual crea catálogo autorizado sin recepción ni modificación del
  promedio, y vuelve a la nota conservando sus filas.
- Creación con clave tiene recibo durable y transacción única de documento/partidas/auditoría/recibo.
  El editor congela intención ante resultado incierto y recupera con la misma clave/carga. El fingerprint
  del preview se valida bajo bloqueo de presentaciones antes de crear. Confirmación conserva su comando
  independiente; cancelación conserva originales y agrega compensaciones.
- Copia completa de compuesto usa versiones de origen/destino, IDs propios, locks compatibles con los
  writers existentes y la validación canónica. Una respuesta recuperada se reconcilia con la versión
  actual del destino. La copia corporativa no certifica elegibilidad de componentes en cada sucursal:
  preview/pedido siguen exigiendo receta efectiva en su contexto.
- Las fronteras nuevas responden a fallos SQL con 503 estable y log de tipo sin parámetros sensibles.
  Se mantiene el límite de cuerpo antes de decodificar JSON, aun con Content-Length falso o por chunks.

Migración aditiva `0072_purchase_create_commands`: probada únicamente contra SQLite/PostgreSQL
aislados; el downgrade se bloquea si eliminaría recibos históricos. No se aplicó a producción.
El contrato HTTP online tiene schema propio y DTO compartido; el envelope offline/gateway permanece
bajo su contrato separado. No se incorporaron dependencias críticas nuevas.

### Evidencia efectiva del cierre local

| Gate ejecutado | Resultado | Alcance y límite |
| --- | --- | --- |
| API workspace/copia/migración, compras existentes, contrato HTTP y trazabilidad | **69 passed** | SQLite aislado; siete fallos SQL inyectados, pureza, permisos, tipos, fecha, promedio previo, replay y rollback; incluye 9 pruebas documentales |
| Regresiones focales de `test_platform_api.py` | **10 passed, 77 deselected** | Lecturas autorizadas, presentaciones, compra/caja/promedio, stock negativo, recetas/snapshots y writers de modificadores |
| `test_purchase_workspace_postgres.py` | **7 passed en dos ejecuciones (5 + 2)** | PostgreSQL 16.15 real y aislado: claves iguales/distintas, identidad keyed/legacy, copia/writers, cambio de origen, catálogo/preview bajo lock y migración/reversibilidad |
| Ruff de backend, migración y pruebas afectadas | **All checks passed** | Sin nuevas exclusiones ni silenciamientos |
| mypy de los nueve módulos runtime afectados | **Sin errores** | API, operaciones, composición, previews, comandos, reglas de presentación, costos y middleware |
| `pnpm test:frontend-semantic` | **Verde** | Agregado del repositorio; tras los últimos cambios se repitieron los contratos focales de workspace, receta, compras POS y ficha de insumo |
| Builds Admin y POS | **Verdes** | Incluyen `tsc --noEmit`; advertencia de chunks >500 kB persiste, sin alterar umbrales |
| E2E de nota contra API real | **Admin y POS verdes** | Tres partidas; proveedor incompatible; alta contextual/cancelación; respuesta preview atrasada; abandono rechazado; respuesta de creación perdida y replay; detalle, recepción, retiro único 56202 y compensación |
| QA del editor de compra | **390 y 1440 px verdes** | Capturas de ambas apps y comprobación de ancho del editor; no equivale a matriz universal de pantallas |
| Browser de receta y compuesto | **Verdes** | Receta en 390/768/1440; compuesto en 1440. Estos recorridos usan mocks canónicos; no acreditan E2E real de copia completa |
| Política SEC001 | **Sin hallazgos** | Scanner de archivos versionados y 27 archivos nuevos; 6 regresiones del scanner verdes. Se renovaron sólo hashes exactos de dos fixtures sintéticos ya autorizados tras sus cambios |
| Integridad documental focal y `git diff --check` | **Verdes** | Enlaces locales y fences de artefactos del paquete; whitespace de diffs |
| Auditoría independiente Sol R3 | **Cerrada en el mismo ciclo** | Hallazgos de alcance, recuperación, vigencia, contrato y exposición SQL corregidos y reproducidos; no certifica producción |

El promedio comprobado con existencia previa es 13.471125 para 40 unidades; el documento conserva
562.015000 y sólo el retiro convierte a 56202 centavos. Crear catálogo contextual no modifica el
saldo/costo. No se modificaron pagos, movimientos, recetas o pedidos históricos directamente.

### Afirmaciones R3 y contraejemplos

| Afirmación | Evidencia | Intento de refutación | Resultado | Riesgo residual |
| --- | --- | --- | --- | --- |
| Creación recuperable es atómica y autorizada | Recibo durable y commit único; SQLite/PG y E2E real | Dos creadores con misma/diferente clave; carrera legacy; fallo al insertar recibo; permiso revocado | Un documento ganador o rechazo estable; rollback y replay sin efectos repetidos | Clientes sin clave conservan contrato legacy, sin recuperación durable |
| La nota nueva usa el contexto numérico revisado | Fingerprint y lock de presentaciones antes de comparar/escribir | Cambiar rendimiento antes de guardar y competir con writer de catálogo PG; replay tras cambiar catálogo | 409 sin escritura o cantidades revisadas; replay devuelve resultado original | Clientes legacy sin header revalidan/recalculan pero no acreditan el preview revisado |
| Copia conserva aislamiento, dependencias y versión | Writer canónico, locks y recibo/auditoría en una transacción | Writers de destino/origen PG; última dependencia inválida; fallo de auditoría; destino avanzado después del replay | Sin mezcla parcial ni versión instalada obsoleta; IDs propios | Elegibilidad por sucursal sigue en preview/pedido; copia completa no tiene E2E real de navegador |
| El editor conserva captura e intención incierta | Reducer/guardas y E2E Admin/POS | Proveedor distinto, cerrar modal, rechazar navegación, timeout tras commit, preview tardío | Partidas conservadas; retry exacto; ausencia de creación duplicada | Captura no persistida no se restaura tras cierre forzado del navegador; beforeunload avisa |
| Fronteras nuevas no filtran parámetros SQL | Siete inyecciones SQL, HTTP y caplog | Error con marcador sensible en previews, creación y copia | 503 constante y log sólo de tipo; marcador ausente | Wrappers de rutas legacy fuera del paquete mantienen exposición SQL preexistente; requiere remediación separada |

### Límites y siguiente paso de publicación

CI incorpora PostgreSQL aislado, regresión semántica y recorrido de compra real Admin/POS. Su YAML
configurado **no equivale a CI remoto ejecutado**. No se corrió una suite completa local: el cambio
se acotó mediante gates focales, carreras PG y E2E crítico; la suite completa configurada corresponde
a CI. No se certificaron gateway offline, matriz universal de roles ni comportamiento productivo.

No se hizo commit, merge, push, despliegue, migración/configuración productiva ni canary. Antes de
liberar: publicar el paquete, obtener CI de los gates configurados y autorizar separadamente migración
0072/despliegue/canary acotado con observación de recibos, ledger y compensaciones. El downgrade con
historia bloqueado exige recuperación hacia adelante; no borrar recibos para forzarlo.

Riesgos heredados registrados: posible diferencia de redondeo en reportes SDD §41, errores SQL de
wrappers legacy fuera de estas fronteras y tamaño de bundles. El paquete no certifica paridad contable
de todos los reportes ni seguridad universal. Crédito real, XML/OCR, fletes, lotes, múltiples almacenes
y edición versionada de borradores persistidos siguen fuera del alcance aprobado.
