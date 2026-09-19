# Historias derivadas de las pantallas de Soft Restaurant

Análisis documental R0 del 2026-09-18; base Git `d59c166`. Evidencia: las 27 fotografías
revisadas en el [índice visual](README.md) y su [manifiesto](manifest.csv).
Proceso: [AGENTS.md](../AGENTS.md) y
[restaurantos-development](../.agents/skills/restaurantos_dev/SKILL.md).

## Cómo interpretar la confirmación

**Seguimiento de implementación:** el análisis inicial R0 se conserva a continuación como
registro de descubrimiento. La solicitud posterior activó el paquete R3
[ADMIN-RETRO-001](../docs/implementation-plans/ADMIN-RETRO-001.md). SR-HU-16 a 19 ya tienen
contrato en PRD-FR-238 a 241; SR-HU-14 se concreta como combo fijo de precio propio bajo
PRD-FR-242. Esos contratos están en implementación y no equivalen a evidencia de entrega.
La apariencia administrativa se gobierna por PRD-FR-237.

Para SR-HU-03 se reutilizan categoría descriptiva del insumo, tipo canónico y unidad base;
no se incorpora la jerarquía contable heredada. Para SR-HU-08 se reutilizan categoría del
producto y grupos/valores de opciones para tamaños; no se convierte automáticamente cada
subgrupo fotografiado en otro producto. La comprobación de estos recorridos forma parte del
paquete, y no implica importar los datos personales o comerciales visibles en las fotografías.

En el análisis inicial se identificaron **19 historias**: 12 con respaldo documental, 3 parciales y
4 candidatas. Los IDs `SR-HU-*` identifican este análisis, no crean requisitos PRD ni
escenarios BDD/TDD nuevos. Los actores se derivan del marco de RestaurantOS; las fotografías
por sí solas no demuestran sus permisos.

- **Confirmada en el marco**: la intención funcional ya tiene respaldo PRD, SDD y BDD/TDD.
  No afirma que la implementación actual esté completa, probada hoy o desplegada.
- **Parcial**: existe el concepto en el marco, pero alguna capacidad de la pantalla no tiene
  un contrato específico identificado. Se indica exactamente el límite.
- **Candidata**: observación o inferencia útil para descubrimiento; no es alcance aceptado.
  Los criterios sugeridos requieren definición antes de incorporarlos a PRD → SDD → BDD → TDD.

No se copian automáticamente las reglas de Soft Restaurant. Las referencias de la tabla final
son relaciones de contexto con especificaciones existentes, sin promover sus estados de evidencia.

## Historias y criterios

### SR-HU-01 — Iniciar sesión con acceso autorizado

**Pantalla 001 · Confirmada en el marco.** Como usuario del sistema, quiero autenticarme para
acceder a las funciones permitidas a mi cuenta y sucursal.

Se observan selección de usuario, contraseña y teclado. El criterio canónico es que una sesión
válida identifique al actor y aplique sus permisos; el acceso sensible sin permiso se rechaza.
La lista pública de nombres y el teclado de la foto no se adoptan como requisitos de UX.
No se transcriben los nombres de empleados a fixtures ni a datos del proyecto.

### SR-HU-02 — Encontrar los módulos administrativos

**Pantallas 002 y 022 · Confirmada en el marco.** Como administrador autorizado, quiero abrir
los módulos de catálogos, inventario y configuración desde una navegación reconocible para
realizar el trabajo sin perder el contexto operativo.

Se observan menú principal, accesos rápidos y submenú de insumos. El criterio existente es
navegar por módulos y conservar el contexto canónico de sucursal; el acceso corporativo y el
de sucursal están separados por permisos. Un acceso visible a «Insumos elaborados» sólo prueba
la ruta ofrecida por el sistema de referencia, no una demostración de producción por lotes.

### SR-HU-03 — Mantener el catálogo de insumos y su clasificación

**Pantallas 003–005 · Parcial.** Como responsable autorizado del catálogo, quiero identificar
los insumos por clave, nombre y unidad y organizarlos para encontrarlos y usarlos en compras y recetas.

Se observan listado, ficha de alta, grupos y clasificación; también inventariable, merma,
impuestos y campos de costo. Está respaldado el catálogo central y su unidad base, separado
del saldo derivado de movimientos. La fórmula de merma de receta se rige por el PRD, no por
la apariencia de un campo heredado. No se identificó un contrato completo para replicar
«grupo de insumo → clasificación → tipo de pedido → cuenta contable» ni cambios masivos al grupo.
Queda pendiente definir si esa jerarquía es necesaria en RestaurantOS y con qué alcance.

### SR-HU-04 — Distinguir unidad base, de compra y de venta

**Pantallas 006 y 016; apoyo 007–008 · Confirmada en el marco.** Como administrador de catálogo,
quiero expresar insumos, presentaciones y productos con unidades compatibles para evitar
errores al comprar, preparar y vender.

Se ven selectores separados en insumo y producto. El criterio existente exige cantidades y
conversiones exactas y rechaza unidades incompatibles sin equivalencia autorizada. «Frasco» o
«bolsa» no son conversiones universales: el rendimiento pertenece a cada presentación.
La coincidencia de nombres de unidad en dos listas no demuestra equivalencia entre ellas.

### SR-HU-05 — Relacionar una presentación de compra con su insumo y proveedor

**Pantallas 007–009 · Confirmada en el marco.** Como responsable de compras autorizado,
quiero registrar presentaciones de proveedor y su contenido aprovechable para conocer cuánto
insumo base recibiré y comparar su precio por unidad.

Se observan proveedor, insumo base, búsqueda, rendimiento, estado y costos. El ejemplo visible
de frasco de 450 g con rendimiento 0.4500 kg confirma la relación conceptual; sus importes no
se importan como precios vigentes. Criterios existentes: rendimiento positivo y compatible,
precio informativo por unidad base e historial de precios. Editar una presentación no genera
existencia ni cambia el costo promedio contable; eso requiere recepción confirmada.

### SR-HU-06 — Administrar proveedores y condiciones comerciales

**Pantalla 010 · Confirmada en el marco.** Como administrador autorizado, quiero conservar la
identidad y contactos de proveedores y sus condiciones para gestionar el abastecimiento.

Se observan nombre, razón social, RFC, dirección, teléfono, correo, crédito y estado.
RestaurantOS ya contempla contactos separados por función y condiciones por sucursal.
Criterios: evitar duplicados de identidad, auditar altas y no propagar silenciosamente una
condición particular a otras sucursales. El campo de cuenta contable y la clasificación de
proveedor de la foto no implican incorporar contabilidad general ni copiar ese formulario.

### SR-HU-07 — Crear y consultar un producto vendible

**Pantallas 011, 012 y 016 · Confirmada en el marco.** Como administrador de catálogo,
quiero definir producto, categoría, estación y precio para ofrecerlo de manera consistente.

Se observan catálogo, SKU, descripción, precio, impuesto, unidad, suspensión y servicios.
Criterios existentes: precio vigente versionado, disponibilidad efectiva por sucursal,
auditoría y conservación del precio histórico del pedido. Un producto sin precio puede verse
en administración, pero no venderse. No se infiere una política tributaria de los valores de
la foto ni se adopta «precio abierto», comisión de mesero o «no facturable».
El menú común entre canales de RestaurantOS prevalece sobre las casillas de servicio heredadas.

### SR-HU-08 — Organizar productos por categorías y opciones de tamaño

**Pantallas 013–015 y 024 · Parcial.** Como administrador de catálogo, quiero organizar
productos y sus tamaños para que el operador encuentre la presentación correcta.

Se observan grupos, subgrupos y ejemplos de tamaño, extras y domicilio. El PRD contempla
categorías y variantes; el catálogo progresivo de POS ya distingue grupos operativos,
subcategorías y opciones. No se confirma que «subgrupo» heredado deba convertirse siempre en
una variante, ni que «servicio a domicilio» sea un producto o categoría del modelo nuevo.
Antes de importar se debe resolver la equivalencia por concepto, evitando duplicar productos
o mezclar un adicional inventariable con una simple clasificación.

### SR-HU-09 — Enviar cada producto a su estación y salida de impresión

**Pantalla 012; apoyo 011 · Confirmada en el marco.** Como responsable de operación,
quiero asociar el producto a su estación para que la preparación y la comanda lleguen al destino correcto.

Se observa «Área de impresión: Bebidas». RestaurantOS modela estaciones, tareas y trabajos
de impresión. Criterios existentes: separar tareas según estación y enrutar la impresión
configurada, con trazabilidad de trabajos y reimpresiones. La foto no prueba impresora física,
entrega de comanda ni disponibilidad del servicio de impresión.

### SR-HU-10 — Definir la receta de un producto con componentes exactos

**Pantallas 017–019 · Confirmada en el marco.** Como responsable autorizado de recetas,
quiero seleccionar insumos y cantidades para estandarizar la preparación y su consumo.

Se observan editor, búsqueda de ingredientes y receta capturada. Criterios existentes:
versionar receta, expresar cantidades exactas, aplicar merma estándar según fórmula canónica
y conservar el snapshot usado por cada pedido. Activar una versión posterior no reescribe
pedidos anteriores. Los botones de copiar o generar desde paquete son indicios de funciones
del referente, no prueba de un contrato equivalente ya definido en RestaurantOS.

### SR-HU-11 — Consultar el costo teórico de una receta

**Pantallas 017 y 019 · Confirmada en el marco.** Como responsable de costos,
quiero consultar el desglose de ingredientes y merma para evaluar el costo por producto y porción.

Se observan totales, selector «Último costo», costo y utilidad. El criterio de RestaurantOS es
registrar cálculo por sucursal, versión y fecha, distinguir costo promedio de inventario y
costo estándar de análisis, y conservar los históricos. La foto no determina qué base usa
«utilidad» ni valida una fórmula. No se equipara último precio de proveedor, costo promedio,
costo estándar y precio de venta; cambiar la vista del cálculo no debe reinterpretar históricos.

### SR-HU-12 — Identificar el almacén operativo de la sucursal

**Pantallas 019 y 027; apoyo 017 · Confirmada en el marco.** Como administrador autorizado,
quiero identificar el almacén de cada sucursal para ubicar sus movimientos y consumos.

Se observan catálogo de almacenes, empresa y relación estación-almacén. El modelo confirmado
de RestaurantOS mantiene un almacén formal por sucursal, ligado a su estructura organizacional.
Criterios: alcance autorizado, integridad de organización y rechazo de inactivación del almacén
de una sucursal activa. La reserva ocurre al aceptar y el consumo al confirmar producción.
La etiqueta heredada «descarga por venta» no cambia ese momento ni habilita varios almacenes
operativos por sucursal.

### SR-HU-13 — Administrar comentarios de preparación y asignarlos a productos

**Pantallas 020 y 025 · Confirmada en el marco.** Como administrador corporativo,
quiero reutilizar indicaciones de preparación y asignarlas a conjuntos de productos para
evitar capturas repetidas y transmitir instrucciones consistentes a cocina.

Se observan comentarios por producto y asignación/eliminación masiva por grupo, sin resultado
ejecutado. El contrato actual ya contempla catálogo corporativo, selección por subcategorías,
preview de alcance y asignación masiva sin retirar relaciones no incluidas. Los comentarios
se congelan en pedido, KDS y comanda sin cambiar precio, receta, reserva, consumo ni costo.
No se confirma una eliminación masiva equivalente a la del referente; requiere definir
semántica de retiro y conservación histórica si se quiere incorporar.

### SR-HU-14 — Definir los productos que componen un paquete o combo

**Pantalla 020 · Parcial.** Como administrador de catálogo, quiero agrupar productos en un
paquete para que el operador capture una oferta compuesta de forma consistente.

Se observa una tabla vacía de componentes, cantidad y acciones de agregar/eliminar. El PRD
incluye combos, pero la captura no demuestra una configuración guardada, precio, elecciones,
consumo ni distribución por estación. No se identificó un escenario dedicado suficiente para
confirmar toda esta historia. Quedan por definir precio del conjunto, componentes fijos u
opcionales, sustituciones, desglose de comanda e impacto en inventario. La restricción textual
del referente entre «paquete» y «producto compuesto» no se adopta como regla de RestaurantOS.

### SR-HU-15 — Configurar grupos de modificadores y límites de elección

**Pantalla 021 · Confirmada en el marco.** Como administrador de catálogo,
quiero configurar opciones, orden, obligatoriedad y límites para guiar la personalización del producto.

Se observa un grupo de edulcorante, opciones, máximo, incluidos en precio y multiplicación
por cantidad. Los criterios vigentes validan cardinalidad antes de aceptar, calculan
adicionales en backend y congelan precio, texto y consumo. El nombre de una opción no basta
para inferir su efecto: «Sin azúcar» puede ser comentario sin impacto inventariable bajo
PRD-FR-199; una modificación real exige efecto de dominio explícito bajo PRD-FR-096.
La captura no autoriza un motor recursivo de productos compuestos ni la convención «0 = ilimitado».

### SR-HU-16 — Ordenar grupos en pantalla e impresión de forma independiente

**Pantalla 023 · Candidata.** Como administrador de catálogo, quiero elegir el orden de
los grupos visibles y el de impresión para adaptar la lectura a la operación.

La evidencia es directa: dos listas separadas y una opción para activar prioridad de impresión.
No se identificó contrato específico para esas dos prioridades en las especificaciones revisadas.
El orden fijo de grupos del POS vigente no equivale a permitir configuración arbitraria.
Borrador de aceptación: cambiar una prioridad conservaría la otra y mostraría el orden resultante.
Falta decidir alcance corporativo/sucursal, superficies afectadas, permisos y comportamiento
al desactivar la prioridad. PRD-FR-209 debe revisarse antes de adoptar un orden configurable.

### SR-HU-17 — Aplicar una receta a varios productos

**Pantalla 026 · Candidata.** Como responsable autorizado de recetas, quiero preparar un
cambio común y seleccionar sus productos destino para reducir el trabajo repetitivo.

Se observa «Captura masiva de recetas», modo «Reemplazar», ingredientes y casillas de productos.
No se ve confirmación ni su resultado. Versionar recetas individuales no demuestra cobertura de
una operación masiva. Borrador de aceptación: presentar destinos y diferencias, y conservar
versiones históricas. Falta decidir reemplazo frente a adición, atomicidad, conflictos concurrentes,
alcance de sucursal, reintentos y recuperación. Su implementación sería R3 por afectar recetas,
inventario y costos; este análisis no habilita reemplazos destructivos.

### SR-HU-18 — Configurar umbrales de existencias

**Pantallas 003, 007 y 008 · Candidata.** Como responsable de abastecimiento,
quiero configurar mínimos y máximos y consultar alertas para identificar necesidades de reposición.

Se ven controles de stock mínimo/máximo y alerta, sin demostrar que una alerta se haya emitido.
No se identificó un contrato específico de umbrales en PRD/SDD/BDD/TDD revisados.
Borrador de aceptación: evaluar un umbral explícito contra la existencia calculada, sin editarla.
Falta definir unidad, ámbito, disponible frente a teórico, tratamiento de reservas, canal y
frecuencia de alerta. El checkbox «usar báscula» tampoco demuestra una integración de hardware.

### SR-HU-19 — Consultar en qué recetas se utiliza un insumo

**Pantallas 003 y 004 · Candidata.** Como responsable de catálogo y costos,
quiero encontrar las recetas que utilizan un insumo para evaluar el alcance de un cambio.

Se observa el botón «Recetas de productos con este insumo», pero no la pantalla de resultados.
La existencia de componentes de receta no demuestra una consulta inversa especificada.
Borrador de aceptación: dado un insumo, listar usos y permitir abrir la receta correspondiente.
Falta decidir versiones activas frente a históricas, dependencias indirectas de elaborados,
alcance de sucursal y permisos de lectura de costos. No se infieren datos ni cambios automáticos.

## Correspondencia con el marco vigente

Las referencias BDD/TDD describen cobertura **documentada**, no resultados de ejecución de hoy.
En historias parciales sólo respaldan el subconjunto indicado. En candidatas son antecedentes;
no se les asignan IDs canónicos ni estado de implementación.

| Historia | PRD vigente | Diseño | BDD existente | TDD existente / límite |
|---|---|---|---|---|
| SR-HU-01 | PRD-FR-005; PRD-NFR-006 | [SDD] §5.1, ADR-015 | [BDD-ACC] BDD-SC-059, BDD-SC-060 | [TDD-ACC] TDD-TS-036, TDD-TC-028, TDD-TC-029 |
| SR-HU-02 | PRD-FR-018, PRD-FR-019 | [SDD] §24 | [BDD-CAT] BDD-SC-046, BDD-SC-112, BDD-SC-113 | [TDD-CAT] TDD-TS-026, TDD-TS-047, TDD-TC-040 |
| SR-HU-03 | PRD-FR-017, PRD-FR-060, PRD-FR-061 | [SDD] §5.7 | [BDD-INV] BDD-SC-049, BDD-SC-050 | [TDD-INV] TDD-TS-028; no confirma jerarquía completa de grupos |
| SR-HU-04 | PRD-FR-061, PRD-FR-062, PRD-FR-093 | [SDD] §5.7, §5.10 | [BDD-PROV] BDD-SC-077, BDD-SC-078 | [TDD-PROV] TDD-TS-040, TDD-TC-033 |
| SR-HU-05 | PRD-FR-093, PRD-FR-094 | [SDD] §5.10 | [BDD-PROV] BDD-SC-077, BDD-SC-078 | [TDD-PROV] TDD-TS-040, TDD-TC-033 |
| SR-HU-06 | PRD-FR-091, PRD-FR-092 | [SDD] §5.10 | [BDD-PROV] BDD-SC-075, BDD-SC-076 | [TDD-PROV] TDD-TS-040 |
| SR-HU-07 | PRD-FR-010, PRD-FR-012, PRD-FR-014, PRD-FR-015, PRD-FR-017 | [SDD] §5.3 | [BDD-CAT] BDD-SC-048, BDD-SC-110, BDD-SC-111 | [TDD-CAT] TDD-TS-027, TDD-TS-047, TDD-TC-020 |
| SR-HU-08 | PRD-FR-010, PRD-FR-199, PRD-FR-209, PRD-FR-229 | [SDD] §34.1, §34.5, §42 | [BDD-CAT] BDD-SC-048; [BDD-OPS] BDD-SC-203 | [TDD-CAT] TDD-TS-027; [TDD-OPS] TDD-TS-063; no confirma equivalencia universal del subgrupo heredado |
| SR-HU-09 | PRD-FR-011, PRD-FR-040, PRD-FR-041, PRD-FR-046, PRD-FR-047 | [SDD] §5.5, §11 | [BDD-KDS] BDD-SC-031; [BDD-PRINT] BDD-SC-035 | [TDD-KDS] TDD-TS-019; [TDD-PRINT] TDD-TS-022 |
| SR-HU-10 | PRD-FR-080, PRD-FR-082, PRD-FR-084 | [SDD] §5.8 | [BDD-INV] BDD-SC-051; [BDD-REC] BDD-SC-084, BDD-SC-085 | [TDD-INV] TDD-TS-029; [TDD-REC] TDD-TS-042 |
| SR-HU-11 | PRD-FR-084, PRD-FR-088, PRD-FR-089, PRD-FR-090 | [SDD] §5.8, §9 | [BDD-REC] BDD-SC-084, BDD-SC-085 | [TDD-REC] TDD-TS-042; no certifica fórmula de utilidad del referente |
| SR-HU-12 | PRD-FR-002, PRD-FR-003, PRD-FR-063, PRD-FR-064 | [SDD] §5.2, §8.2 | [BDD-CAT] BDD-SC-047, BDD-SC-453; [BDD-INV] BDD-SC-052, BDD-SC-053 | [TDD-CAT] TDD-TC-214; [TDD-INV] TDD-TS-030 |
| SR-HU-13 | PRD-FR-199, PRD-FR-201 | [SDD] §34.1 | [BDD-OPS] BDD-SC-203, BDD-SC-204, BDD-SC-205, BDD-SC-206 | [TDD-OPS] TDD-TS-063, TDD-TC-058; sin confirmar eliminación masiva |
| SR-HU-14 | PRD-FR-010, alcance general de combos | [SDD] §5.3, §6 | No se identificó escenario dedicado suficiente | Pendiente de contrato y cobertura específica para paquetes |
| SR-HU-15 | PRD-FR-095, PRD-FR-096, PRD-FR-097, PRD-FR-098, PRD-FR-099 | [SDD] §5.8 | [BDD-REC] BDD-SC-089, BDD-SC-090, BDD-SC-093, BDD-SC-094 | [TDD-REC] TDD-TS-043, TDD-TC-036 |
| SR-HU-16 | Antecedente PRD-FR-209; configuración dual sin requisito específico identificado | [SDD] §34.5 y §11, sólo antecedentes | Pendiente | Pendiente |
| SR-HU-17 | Antecedente PRD-FR-082; operación masiva sin requisito específico identificado | [SDD] §5.8, sólo antecedente | Pendiente para operación masiva | Pendiente para operación masiva |
| SR-HU-18 | Antecedente PRD-FR-070; umbrales sin requisito específico identificado | [SDD] §5.7, sólo antecedente | Pendiente para umbrales | Pendiente para umbrales |
| SR-HU-19 | Antecedente PRD-FR-080; consulta inversa sin requisito específico identificado | [SDD] §5.8, sólo antecedente | Pendiente para consulta inversa | Pendiente para consulta inversa |

Todas las referencias PRD se resuelven en el [PRD canónico][PRD]; su estado de entrega permanece
en la [matriz canónica](../docs/05-matriz-trazabilidad.md). Una coincidencia de concepto no es
paridad funcional completa entre ambos productos.

## Decisiones de contexto que deben conservarse

1. Insumo base, presentación de compra, producto de venta y receta son conceptos distintos.
   Crear una presentación no es comprar; cambiar una cotización no actualiza el promedio contable.
2. El referente usa grupos de catálogo para tamaños, extras y servicios. La migración debe decidir
   equivalencias explícitas; no trasladar esa clasificación literalmente al dominio.
3. Comentarios, modificadores y adicionales requieren efectos distintos y explícitos. No se
   deduce consumo a partir del texto de una instrucción.
4. «Reemplazar receta» y «Eliminar» no autorizan borrar historia. RestaurantOS conserva versiones,
   snapshots y correcciones trazables conforme a su contrato.
5. Un almacén por sucursal, reserva al aceptar y consumo al preparar prevalecen sobre el diseño
   de estaciones/almacenes del referente.
6. Los campos de precio abierto, comisión, cuenta contable, promociones, imagen y monedero
   aparecen como controles o pestañas, sin recorridos completos. No se confirman historias
   detalladas de esas funciones sólo por sus etiquetas. Mesas, meseros, reservaciones y
   contabilidad general siguen fuera del alcance V1 definido en el PRD.

## Aplicación proporcional y límites de verificación

Este cambio organiza evidencia y crea correspondencias de análisis. Se activa la referencia
de contexto y el enlace complementario de la matriz. PRD, SDD, BDD y TDD mantienen sus contratos;
las candidatas no se promueven a historias aceptadas. No hay implementación ni cambio de permisos,
precios, recetas, persistencia o comportamiento del producto.

La integridad se comprueba con conteo de imágenes, secuencia de nombres, hashes antes/después,
enlaces locales y resolución de IDs referenciados. El gate de trazabilidad verifica las
relaciones canónicas existentes. No se ejecutan suites funcionales, build, migraciones,
canary ni despliegue para este R0; tampoco se certifica funcionamiento actual de los módulos.

Resultado local de esta revisión:

- 27/27 imágenes verificadas contra SHA-256 y tamaño del original; numeración continua y
  correspondencia completa con las 19 historias.
- 57 enlaces locales comprobados en el índice, este análisis y los dos documentos enlazantes;
  93 identificadores canónicos referenciados encontrados en las especificaciones vigentes.
- Los cuatro archivos de código previamente modificados conservan sus hashes.
- `git diff --check`: sin errores de whitespace; los documentos nuevos también se comprobaron
  directamente porque Git no incluye archivos sin seguimiento en ese comando.
- `python -m pytest tests/architecture/test_traceability.py -q`: **6 passed, 2 failed**.
  Los dos fallos se reprodujeron al ejecutar el mismo gate sobre los documentos y la prueba
  extraídos directamente de `HEAD` (`d59c166`) en un directorio temporal separado.
  Se detectan `BDD-SC-115` duplicado entre Admin SaaS y frontend CI, y `TDD-TS-048` duplicado
  entre sus respectivos documentos TDD. Son fallos previos; este cambio no los corrige ni
  declara verde el gate de trazabilidad. No se revisó CI remoto.

[PRD]: ../docs/01-PRD.md
[SDD]: ../docs/02-SDD.md
[BDD-ACC]: ../docs/03-BDD-admin-users-roles.md
[TDD-ACC]: ../docs/04-TDD-admin-users-roles.md
[BDD-CAT]: ../docs/03-BDD-admin-saas-catalog.md
[TDD-CAT]: ../docs/04-TDD-admin-saas-catalog.md
[BDD-INV]: ../docs/03-BDD-inventory-saas.md
[TDD-INV]: ../docs/04-TDD-inventory-saas.md
[BDD-PROV]: ../docs/03-BDD-suppliers-presentations.md
[TDD-PROV]: ../docs/04-TDD-suppliers-presentations.md
[BDD-REC]: ../docs/03-BDD-recipes-production-modifiers.md
[TDD-REC]: ../docs/04-TDD-recipes-production-modifiers.md
[BDD-OPS]: ../docs/03-BDD-pos-order-operations-wave.md
[TDD-OPS]: ../docs/04-TDD-pos-order-operations-wave.md
[BDD-KDS]: ../docs/03-BDD-pos-cash-order-kds.md
[TDD-KDS]: ../docs/04-TDD-pos-cash-order-kds.md
[BDD-PRINT]: ../docs/03-BDD-payment-cut-print.md
[TDD-PRINT]: ../docs/04-TDD-payment-cut-print.md
