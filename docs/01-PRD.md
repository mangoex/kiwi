# PRD — Product Requirements Document

## 1. Propósito

Construir una plataforma web, offline-first, para controlar la operación comercial, productiva, logística, financiera e inventariable de una cadena mexicana de restaurantes de comida rápida.

El producto deberá sustituir procesos fragmentados y reducir la dependencia de software local monolítico, manteniendo continuidad operativa ante fallas de internet.

## 2. Objetivos de negocio

1. Unificar ventas, cocina, inventario, compras, reparto y exportaciones.
2. Mantener operación local durante hasta dos horas sin internet.
3. Centralizar información de siete sucursales y varias razones sociales.
4. Obtener costo teórico y real con recetas y subrecetas.
5. Integrar canales propios y marketplaces sin recaptura.
6. Mejorar tiempos de preparación y despacho.
7. Reducir errores de caja, mermas y diferencias de inventario.
8. Preparar información consistente para facturación individual y global.
9. Crear una base técnica que permita convertir el producto en SaaS posteriormente.

## 3. Usuarios y roles

### PRD-ROLE-001 Administrador corporativo
Configura organización, razones sociales, sucursales, catálogos, permisos, integraciones y reportes.

### PRD-ROLE-002 Gerente de sucursal
Supervisa operación, caja, inventario, mermas, producción y repartidores de una sucursal.

En la operación POS este perfil se mostrará como `Supervisor de sucursal`. Su autoridad se
resuelve mediante permisos y alcance de sucursal, no mediante el nombre del rol.

El Supervisor de sucursal opera un centro de administración operativa limitado a su sucursal
asignada mediante los permisos `branch.admin.access`, `branch.staff.read` y
`catalog.branch.manage`. No puede modificar catálogos centrales, usuarios, roles, sucursales
o unidades de negocio.

### PRD-ROLE-003 Cajero
Abre turno, captura pedidos, cobra, imprime y ejecuta cortes autorizados.

### PRD-ROLE-004 Operador de cocina
Consulta KDS, inicia preparación, marca componentes terminados y reporta incidencias.

### PRD-ROLE-005 Operador de bebidas
Atiende componentes asignados a bebidas.

### PRD-ROLE-006 Operador de empaque
Consolida componentes y libera pedidos a entrega.

### PRD-ROLE-007 Despachador
Asigna repartidores, aprueba rutas sugeridas y registra estados de entrega.

### PRD-ROLE-008 Repartidor
Actor operativo registrado, sin aplicación móvil en la versión 1.

### PRD-ROLE-009 Encargado de inventarios
Registra recepciones, lotes, conteos, traspasos, mermas y producción.

### PRD-ROLE-010 Cuentas por pagar
Gestiona documentos, vencimientos, pagos y saldos de proveedores.

### PRD-ROLE-011 Auditor
Consulta eventos, movimientos, cierres y modificaciones sin capacidad de alteración.

### PRD-ROLE-012 Receptor de traspaso
Confirma cantidades recibidas y registra diferencias en la sucursal destino, sin facultad para
crear ajustes generales de inventario.

## 4. Alcance funcional

### 4.1 Organización y configuración

- `PRD-FR-001`: El sistema debe administrar una organización con varias razones sociales.
- `PRD-FR-002`: Cada sucursal debe pertenecer a una sola razón social.
- `PRD-FR-003`: Cada sucursal debe tener un solo almacén formal.
- `PRD-FR-004`: Debe permitir ubicaciones internas dentro del almacén.
- `PRD-FR-005`: Debe administrar usuarios, roles y permisos por organización y sucursal.
  - El rol operativo de caja se denomina `Cajero`.
  - El acceso a Admin, POS y acciones sensibles debe resolverse por permisos, no por nombre visual del rol.
  - Las acciones de caja, pedidos POS, pagos y dashboard requieren actor autenticado.
  - Un usuario con alcance de sucursal solo puede operar o consultar la sucursal asignada.
  - Un Supervisor de sucursal accede a un centro de administración operativa con los permisos
    `branch.admin.access`, `branch.staff.read` y `catalog.branch.manage`, limitado a su
    sucursal; no equivale a administrador corporativo ni recibe `admin.manage` ni `catalog.manage`.
- `PRD-FR-006`: Debe registrar dispositivos, cajas, KDS e impresoras.
- `PRD-FR-007`: Debe conservar auditoría de acciones administrativas y operativas.
- `PRD-FR-008`: Debe soportar configuración heredada desde corporativo con excepciones por sucursal.
  - La herencia central se aplica salvo excepción explícita por sucursal; volver a "heredar"
    elimina la excepción local de forma segura y restablece el valor central.
- `PRD-FR-009`: La estructura organizacional debe modelar Grupo, Razón social, Unidad de negocio,
  Sucursal y Almacén. Una unidad de negocio debe distinguir restaurantes Kiwi de otras unidades;
  cada sucursal debe pertenecer a una unidad de negocio y conservar una sola razón social y un solo
  almacén operativo en esta etapa.
  - El tipo de unidad de negocio (`unit_type`) distingue `restaurant`, `bakery`, `production` y
    `other`, sin duplicar catálogos ni crear registros productivos automáticamente.

### 4.2 Catálogo y menú

- `PRD-FR-010`: Debe administrar categorías, productos, variantes, modificadores, extras y combos.
- `PRD-FR-011`: Un producto debe poder dividir componentes entre varias estaciones.
- `PRD-FR-012`: El menú debe ser común entre canales, salvo disponibilidad por sucursal.
- `PRD-FR-013`: Debe manejar horarios de venta y disponibilidad.
- `PRD-FR-014`: Debe permitir marcar productos agotados por sucursal.
- `PRD-FR-015`: Debe versionar precios y conservar el precio aplicado en cada pedido.
- `PRD-FR-016`: Debe mantener equivalencias entre productos internos y productos de canales externos.
- `PRD-FR-017`: Productos, categorías, insumos, sucursales y usuarios deben conservar una fuente
  central única y aparecer consistentemente en las superficies autorizadas. La ausencia de una
  excepción por sucursal hereda el estado central; sólo una excepción explícita puede ocultar un
  producto en esa sucursal. Un producto sin precio vigente debe seguir visible en administración,
  marcado como no vendible, y no puede ofrecerse ni cobrarse en POS.
  - La administración operativa por sucursal muestra la disponibilidad efectiva y distingue si
    proviene de herencia central o de una excepción local, sin permitir modificar el catálogo central.
- `PRD-FR-018`: El POS debe distinguir entre administración corporativa y administración operativa
  por sucursal, con acceso controlado por permisos granulares en lugar de un único permiso o
  comparación de nombres de rol.
  - La administración corporativa (`admin.manage` y `catalog.manage`) administra productos,
    insumos, sucursales, usuarios, roles, proveedores, recetas/producción, unidades de negocio y
    permisos a nivel central.
  - La administración operativa por sucursal (`branch.admin.access`, `branch.staff.read`,
    `catalog.branch.manage`) permite al Supervisor de sucursal consultar su sucursal, personal
    asignado y catálogos centrales, y modificar únicamente disponibilidad y excepciones de su
    sucursal, sin alterar catálogos centrales, usuarios, roles, sucursales o unidades de negocio.
  - Las cuentas operativas sin `branch.admin.access` ni `admin.manage` no deben ver el acceso al
    centro administrativo ni abrir su ruta directamente.
  - Ninguna cuenta puede entrar a la aplicación POS sin el permiso efectivo `pos.operate`, aunque
    tenga otros permisos administrativos u operativos.
  - El centro de administración de sucursal debe conservar el mismo shell, navegación, colores y
    contexto visual del POS. Para el Supervisor muestra Productos y recetas, Insumos, Proveedores,
    Compras, Producción, Mermas, Traspasos y Conteos físicos; no muestra Sucursales, Usuarios ni
    Roles, porque esos catálogos pertenecen exclusivamente a la administración corporativa.
  - Cada opción operativa se muestra y protege por su permiso granular. Un Cajero sin
    `branch.admin.access` no ve Administración ni puede abrir ninguna ruta administrativa.
- `PRD-FR-019`: Admin y POS deben compartir un contexto canónico de sucursal. Para usuarios con
  alcance restringido prevalece la sucursal asignada; para administradores se conserva una selección
    válida y, si falta, se elige una sucursal activa disponible. Cambiarla debe aplicarse a todos los
    módulos operativos dependientes de sucursal.
  - El contexto canónico se resuelve en backend; el cliente no es autoridad. Un Supervisor siempre
    queda fijado a su sucursal asignada; un administrador corporativo puede seleccionar una
    sucursal activa autorizada.
  - Al cargar una sesión de alcance sucursal, `active_branch.id` reemplaza cualquier sucursal local
    obsoleta. Una selección de alcance organización sólo se persiste y aplica después de que
    `GET /api/v1/auth/session?branch_id=...` la valida y la devuelve como `active_branch`.

- `PRD-FR-213`: Una categoría puede requerir un único selector previo de selección única (por
  ejemplo, **Tamaño**) antes de mostrar productos concretos en POS. Elegir su valor no agrega una
  línea al carrito; sólo limita el menú a productos concretos, activos, disponibles en la sucursal y
  con precio vigente positivo. La asignación producto–valor es explícita: no se deriva de nombres,
  presentaciones ni sufijos. Una categoría configurada falla cerrada en POS cuando un producto
  vendible carece de asignación válida, mientras Administración corporativa lo conserva visible como
  configuración incompleta. El pedido, KDS, comanda y precio conservan siempre el `product_id` y
  snapshot concretos; el valor elegido no es modificador ni precio. Cambiar de categoría u opción
  sólo limpia personalización transitoria, nunca el carrito. La búsqueda no evita el selector.

### 4.3 Pedidos

- `PRD-FR-020`: Debe crear pedidos de mostrador, para recoger y a domicilio.
  - Los pedidos creados desde POS requieren permiso `orders.create`, una sucursal autorizada y un turno de caja abierto.
  - Un pedido a domicilio exige cliente seleccionado y un domicilio activo perteneciente a ese cliente.
  - Crear un pedido desde POS exige `Idempotency-Key`. Repetir la misma intención devuelve el mismo
    pedido sin duplicar reservas, tareas, eventos ni auditoría; reutilizar la clave con otra intención
    falla sin escritura parcial.
- `PRD-FR-021`: Debe aceptar pedidos desde POS, WhatsApp, chatbot y marketplaces.
- `PRD-FR-022`: Todo pedido externo debe ser idempotente.
- `PRD-FR-023`: Debe conservar el payload original de pedidos externos.
- `PRD-FR-024`: Debe registrar cliente, dirección, zona, costo, promesa y canal.
  - El checkout del POS debe permitir agregar un domicilio estructurado sin cerrar la venta y seleccionarlo automáticamente.
- `PRD-FR-025`: Debe calcular totales, descuentos, impuestos informativos y formas de pago.
  - El backend es la fuente de verdad del total del pedido y POS debe cobrar el `total_cents` devuelto por la API.
- `PRD-FR-026`: Debe impedir que una modificación de catálogo altere pedidos históricos.
- `PRD-FR-027`: Debe registrar eventos y transiciones de estado del pedido.
- `PRD-FR-028`: Debe permitir cancelaciones con reglas según estado productivo y de pago.
- `PRD-FR-029`: Debe soportar notas por pedido, producto y estación.
- `PRD-FR-030`: Debe generar un folio único sin depender de conectividad continua.
- `PRD-FR-031`: Cada cliente debe tener un ID interno inmutable y puede registrar varios
  teléfonos. El teléfono normalizado es un criterio operativo de búsqueda, no una llave primaria,
  y una coincidencia no debe fusionar clientes automáticamente.
  - En el checkout del POS, el teléfono mexicano normalizado es el criterio primario y exacto de
    búsqueda. Nombre y correo permanecen disponibles en el directorio administrativo, pero no
    sustituyen la identificación telefónica durante el cobro.
  - Si varios clientes comparten el mismo teléfono, el POS debe mostrar todos sus nombres y nunca
    fusionarlos automáticamente.
- `PRD-FR-032`: Un cliente puede tener cualquier cantidad de direcciones de entrega, con alias,
  referencias, instrucciones, coordenadas, zona, preferencia y estado.
  - Un domicilio heredado de un sistema externo se muestra sólo como referencia pendiente de confirmación; nunca se convierte automáticamente en un domicilio operativo.
- `PRD-FR-033`: Los datos fiscales del cliente deben mantenerse separados de las direcciones de
  entrega para futura exportación o integración.
- `PRD-FR-034`: Al usar cliente o dirección en un pedido, se debe guardar un snapshot histórico;
  las modificaciones posteriores del directorio no alteran pedidos previos.
  - El POS debe conservar el cliente seleccionado aunque cambien o se limpien los resultados de búsqueda.
- `PRD-FR-035`: Repetir un pedido debe crear una orden nueva y validar precios, receta,
  disponibilidad, promociones y modificadores vigentes.

### 4.4 Producción y KDS

- `PRD-FR-040`: Debe generar tareas por estación.
- `PRD-FR-041`: Debe soportar cocina, bebidas, empaque y entrega.
- `PRD-FR-042`: Debe mostrar tiempos, prioridad, promesa y retrasos.
- `PRD-FR-043`: Un pedido solo podrá marcarse listo cuando todas las tareas obligatorias concluyan.
- `PRD-FR-044`: Debe permitir reimpresión y reapertura autorizadas.
- `PRD-FR-045`: Debe registrar incidencias, faltantes y agotados.
- `PRD-FR-046`: Debe imprimir automáticamente sin diálogo del navegador.
- `PRD-FR-047`: Debe dirigir cada impresión a una impresora configurada.
- `PRD-FR-048`: Debe registrar cada intento y resultado de impresión.

### 4.5 Caja y pagos

- `PRD-FR-050`: Debe manejar turnos por caja.
  - Abrir, consultar y cerrar turnos requiere permisos explicitos de caja y alcance sobre la sucursal.
- `PRD-FR-051`: Debe registrar fondo inicial.
- `PRD-FR-052`: Debe registrar ingresos, retiros, gastos y depósitos.
- `PRD-FR-053`: Debe registrar efectivo, tarjeta y transferencia.
  - El POS debe distinguir tarjeta de débito y tarjeta de crédito en la selección previa a confirmar
    el cobro y conservar esa distinción en el registro inmutable del pago.
  - Confirmar pagos requiere permiso `payments.confirm` y debe auditar al actor.
  - Confirmar un pago desde POS exige `Idempotency-Key`; repetir la misma intención devuelve el
    mismo pago y no duplica snapshots, eventos, impresiones ni auditoría. Reutilizar la clave con
    pedido, actor, caja, método o importe distintos falla con conflicto explícito.
- `PRD-FR-054`: Los pagos confirmados deben ser inmutables.
- `PRD-FR-055`: Debe permitir corte parcial.
- `PRD-FR-056`: Debe realizar arqueo y calcular diferencias.
- `PRD-FR-057`: Debe realizar corte final irreversible salvo reapertura autorizada.
- `PRD-FR-058`: Debe mantener evidencia y auditoría de reaperturas.
- `PRD-FR-059`: Debe conciliar cobros entregados por repartidores.

### 4.6 Inventarios

- `PRD-FR-060`: La existencia debe derivarse de un libro de movimientos.
- `PRD-FR-061`: Debe manejar unidades de compra, almacenamiento, producción y consumo.
- `PRD-FR-062`: Debe usar conversiones exactas y auditables.
- `PRD-FR-063`: Debe reservar inventario al aceptar un pedido.
- `PRD-FR-064`: Debe convertir la reserva en consumo al confirmar producción.
- `PRD-FR-065`: Debe liberar reservas canceladas antes de producción.
- `PRD-FR-066`: Cancelaciones posteriores deben generar merma o recuperación autorizada.
- `PRD-FR-067`: Debe manejar lotes y caducidades.
- `PRD-FR-068`: Debe soportar sesiones de conteo físico con fotografía teórica, captura ciega,
  envío a revisión, cálculo `físico - teórico`, autorización, movimientos `COUNT_ADJUSTMENT` y
  cierre. La diferencia de conteo no se clasifica automáticamente como merma. Si el libro cambia
  después de la fotografía, el ajuste autorizado se calcula contra la existencia vigente para no
  sobrescribir movimientos intermedios. Los ajustes confirmados son inmutables e idempotentes.
- `PRD-FR-069`: Debe soportar traspasos entre sucursales.
- `PRD-FR-070`: Debe ofrecer kardex y existencia teórica.
  - La pantalla de inventario del POS muestra existencia teórica derivada del ledger de la sucursal canónica, distinguiendo positivo, cero y negativo.
- `PRD-FR-071`: Una merma real debe registrarse separada de merma estándar, diferencia de conteo y
  cancelación producida, con sucursal, artículo, cantidad, unidad, motivo, etapa, fecha, notas y
  evidencia opcional.
- `PRD-FR-072`: Los motivos de merma deben ser configurables y conservar código, nombre, estado y
  clasificación para reportes; desactivar un motivo no altera registros históricos.
- `PRD-FR-073`: Capturar una merma crea un borrador sin afectar existencias. Confirmarla requiere
  `inventory.waste`, existencia suficiente e idempotency key, y crea una salida `WASTE_REAL` con el
  costo promedio vigente y los actores de captura y autorización.
- `PRD-FR-074`: Una merma confirmada es inmutable. Su corrección requiere motivo e idempotency key y
  crea `WASTE_REVERSAL` referenciado; nunca elimina ni sobrescribe el movimiento original.
- `PRD-FR-075`: La merma y su reversa deben actualizar el estado de costo por sucursal sin cambiar el
  costo promedio unitario, y aparecer en kardex, auditoría y conciliación con su documento de origen.
- `PRD-FR-076`: Un traspaso debe tener sucursal y almacén de origen y destino distintos, líneas en
  unidad base, actor, fechas y estados `draft`, `sent`, `received`, `received_with_difference` o
  `cancelled`; un borrador no afecta existencias.
- `PRD-FR-077`: Enviar requiere `inventory.transfer.send`, existencia suficiente e idempotency key;
  crea `TRANSFER_OUT` en origen y un saldo documentado en tránsito al costo promedio congelado.
- `PRD-FR-078`: Recibir requiere `inventory.transfer.receive` en destino e idempotency key; crea
  `TRANSFER_IN` únicamente por la cantidad confirmada y nunca convierte automáticamente el envío
  completo en entrada.
- `PRD-FR-079`: Una recepción menor debe registrar cantidad y costo de diferencia, motivo o daño y
  estado `received_with_difference`. El costo de origen se incorpora al promedio ponderado del
  destino y no se clasifica como compra; líneas y movimientos confirmados son inmutables.

### 4.7 Recetas, subrecetas y producción por lotes

- `PRD-FR-080`: Debe soportar recetas multinivel.
- `PRD-FR-081`: Debe impedir ciclos.
- `PRD-FR-082`: Debe versionar recetas de venta y de producción, con borrador, activación,
  retiro, vigencia y alcance central o por sucursal. Una operación conserva la versión aplicada.
- `PRD-FR-083`: Debe registrar rendimiento esperado y real.
- `PRD-FR-084`: Debe registrar merma planeada y real. La merma estándar se calcula como pérdida
  sobre cantidad bruta: `bruta = neta / (1 - merma)` y no genera una salida duplicada.
- `PRD-FR-085`: Debe producir insumos elaborados por lote: producción consume materias primas,
  genera existencia del elaborado y la venta posterior consume solamente el elaborado.
- `PRD-FR-086`: Debe conservar trazabilidad de lotes consumidos.
- `PRD-FR-087`: Debe calcular costo real del lote.
- `PRD-FR-088`: Debe calcular costo teórico por producto y porción con desglose por componente,
  costo antes de merma, costo de merma, costo total, sucursal y fecha del cálculo.
- `PRD-FR-089`: Debe usar costo promedio ponderado para inventario.
- `PRD-FR-090`: Debe usar costo estándar para análisis y presupuesto.
- `PRD-FR-091`: Debe administrar proveedores centralmente con identidad fiscal, condiciones
  comerciales, moneda, crédito, días y tiempos habituales de entrega.
- `PRD-FR-092`: Un proveedor debe admitir varios contactos clasificados para pedidos,
  facturación y cobranza, con alcance y disponibilidad por sucursal.
- `PRD-FR-093`: Un artículo inventariable debe admitir presentaciones de compra específicas por
  proveedor, con unidad comercial, contenido bruto, neto y aprovechable, rendimiento en unidad
  base, impuestos, código de barras y sucursales habilitadas.
- `PRD-FR-094`: Capturar o editar el precio de una presentación debe conservar historial y calcular
  su equivalencia por unidad base, pero no debe alterar el costo promedio contable ni el costo de
  recetas hasta confirmar la recepción de una compra.
- `PRD-FR-095`: Debe administrar grupos de modificadores por producto con obligatoriedad, mínimo,
  máximo, estación, orden y alcance central o por sucursal.
  - Debe permitir editar y retirar grupos y opciones ordinarios. El retiro es lógico para ventas
    futuras, conserva pedidos y snapshots históricos, y no puede dejar un grupo activo con menos
    opciones que su mínimo; la administración usa la vista central completa aunque una sucursal
    deshabilite opciones, y comentarios e ingredientes adicionales mantienen su catálogo canónico.
- `PRD-FR-096`: Una opción debe poder quitar, agregar, sustituir o cambiar cantidad de un componente,
  elegir una variante o conservar una instrucción libre, con precio adicional y texto para cocina.
- `PRD-FR-097`: Al aceptar el pedido debe validar las cardinalidades del grupo y congelar opciones,
  precio, texto y consumo final; cambios posteriores del catálogo no alteran la orden.
- `PRD-FR-098`: Reserva, preparación y liberación deben usar el consumo final modificado. Una
  instrucción libre nunca cambia inventario automáticamente.
- `PRD-FR-099`: El backend calcula el precio adicional de modificadores vigentes y lo multiplica por
  la cantidad de la línea; POS no puede enviar un importe confiable como fuente de verdad.

### 4.8 Compras y cuentas por pagar

- `PRD-FR-100`: Debe registrar recepciones sin requerir orden de compra.
- `PRD-FR-101`: Debe registrar proveedor, presentación, cantidad, costo, lote y caducidad.
- `PRD-FR-102`: Debe importar XML de CFDI.
- `PRD-FR-103`: Debe impedir XML duplicados.
- `PRD-FR-104`: Debe mapear conceptos de proveedor a productos internos.
- `PRD-FR-105`: Debe generar cuenta por pagar para compras a crédito.
- `PRD-FR-106`: Debe registrar vencimientos, pagos, saldos y devoluciones.
- `PRD-FR-107`: Debe conservar XML y evidencia de importación.
- `PRD-FR-108`: Una compra directa debe manejar borrador, confirmación y cancelación controlada;
  la confirmación genera entradas de inventario y, si se pagó desde caja, un retiro inmutable
  vinculado sin duplicar el egreso.
- `PRD-FR-109`: El costo promedio ponderado móvil debe actualizarse únicamente al confirmar una
  recepción, por sucursal, almacén y artículo. Editar cotizaciones o presentaciones no lo modifica.
- `PRD-FR-110`: Compras, retiros y movimientos de recepción deben aceptar claves de idempotencia,
  conservar actor/documento y corregirse mediante compensaciones referenciadas, nunca borrado.
- `PRD-FR-111`: En este incremento el costo neto inventariable excluye impuestos informativos y
  reduce descuentos de línea. Flete y gastos no se distribuyen hasta aprobar una política; una
  recepción con existencia física negativa se rechaza con decisión de costeo pendiente.

### 4.9 Reparto y rutas

- `PRD-FR-120`: Debe administrar zonas, cobertura, mínimos, costos y tiempos.
- `PRD-FR-121`: Debe geocodificar direcciones.
- `PRD-FR-122`: Debe calcular distancia y ETA.
- `PRD-FR-123`: Debe optimizar simultáneamente pedidos y repartidores.
- `PRD-FR-124`: Debe permitir varios pedidos por repartidor.
- `PRD-FR-125`: Debe considerar ventanas de entrega y tiempo de preparación.
- `PRD-FR-126`: Debe permitir modificar manualmente la recomendación.
- `PRD-FR-127`: Debe soportar despacho manual cuando el optimizador no esté disponible.
- `PRD-FR-128`: Debe registrar estados de entrega desde la estación de despacho.
- `PRD-FR-129`: Debe liquidar efectivo y diferencias por repartidor.

### 4.10 Integraciones

- `PRD-FR-140`: Debe exponer APIs versionadas para canales.
- `PRD-FR-141`: Debe recibir webhooks idempotentes.
- `PRD-FR-142`: Debe registrar salud y errores por integración.
- `PRD-FR-143`: Debe reintentar operaciones seguras.
- `PRD-FR-144`: Debe permitir pausar una sucursal en canales compatibles.
- `PRD-FR-145`: El chatbot debe consultar menú, disponibilidad, zona, costo y tiempo en el sistema.
- `PRD-FR-146`: El chatbot no debe inventar productos, precios o tiempos.
- `PRD-FR-147`: Cada proveedor externo debe implementarse mediante adaptador.
- `PRD-FR-232`: El panel de administración corporativo (`admin-web`) debe proveer un Hub de Integraciones desacoplado para configurar credenciales seguras, mapeo de sucursales, vinculación de productos y monitoreo de webhooks de marketplaces externos (Uber Eats, DiDi Food, Rappi).
- `PRD-FR-233`: La terminal POS (`pos-web`) debe proveer una vista dedicada de pedidos de marketplaces externos (Uber Eats) accesible desde su barra de navegación principal debajo de Pedidos, con actualización en tiempo real, alertas sonoras, gestión de estados (aceptar, en cocina, listo para repartidor, rechazar) y reimpresión de comandas.

### 4.11 Exportación y facturación

- `PRD-FR-160`: Debe preparar facturas individuales.
- `PRD-FR-161`: Debe preparar factura global.
- `PRD-FR-162`: Debe separar exportaciones por razón social.
- `PRD-FR-163`: Debe exportar documentos, conceptos, clientes, pagos y control.
- `PRD-FR-164`: Debe prevenir doble exportación.
- `PRD-FR-165`: Debe permitir reexportación autorizada.
- `PRD-FR-166`: Debe soportar adaptadores configurables para variantes de CONTPAQi.
- `PRD-FR-167`: Debe conservar historial y conciliación de lotes exportados.

### 4.12 Offline y continuidad

- `PRD-FR-180`: Cada sucursal debe operar mediante gateway local.
- `PRD-FR-181`: El gateway debe coordinar cajas, KDS e impresoras.
- `PRD-FR-182`: Debe soportar hasta dos horas sin internet.
- `PRD-FR-183`: Debe soportar varias cajas desconectadas simultáneamente.
- `PRD-FR-184`: Debe usar outbox, inbox e idempotencia.
- `PRD-FR-185`: Debe reconciliar operaciones al recuperar conexión.
- `PRD-FR-186`: Debe mostrar estado de sincronización.
- `PRD-FR-187`: Debe evitar pérdida o duplicación de pedidos.
- `PRD-FR-188`: Debe continuar impresión y KDS dentro de la red local.
- `PRD-FR-189`: La recepción de canales externos requiere conectividad principal o de respaldo.

### 4.13 Migración de catálogos heredados por sucursal

- `PRD-FR-190`: Debe importar catálogos heredados mediante lotes idempotentes, conservar el archivo y la fila de origen como evidencia lógica y registrar resultado, rechazo y destino por fila.
- `PRD-FR-191`: Productos, categorías e insumos conforman un catálogo corporativo compartido por
  todas las sucursales. La sucursal sólo limita existencias, disponibilidad y operación local. Los
  clientes importados conservan alcance de su sucursal de origen.
- `PRD-FR-192`: Un producto heredado sin estación operativa debe quedar en revisión y no debe
  venderse hasta que un administrador complete su configuración, salvo una migración aprobada que
  pueda asignarla de forma determinista por categoría y nombre sin inventar precio ni receta.
- `PRD-FR-193`: Una presentación heredada sin proveedor y una receta sin componentes o cantidades deben quedar en revisión; el sistema no debe inventar relaciones, rendimientos ni costos operativos.
- `PRD-FR-194`: El costo heredado de un insumo o presentación es sólo referencia de migración y no puede modificar existencia, costo promedio ni movimientos de inventario.
- `PRD-FR-195`: El directorio de clientes debe consultar por sucursal con búsqueda y paginación, sin cargar el padrón completo ni ejecutar consultas por cliente.
  - La búsqueda del checkout debe ser remota, paginada y exacta por teléfono mexicano válido;
    no consulta con un número incompleto y cancela solicitudes anteriores.
- `PRD-FR-196`: El administrador corporativo debe poder revisar y completar los registros
  importados; la bandeja debe agrupar los pendientes por tipo, identificar el registro por nombre y
  clave, explicar el dato faltante y dirigir a la acción canónica correspondiente. El Supervisor
  sólo puede administrar disponibilidad del catálogo compartido en su sucursal dentro de los
  permisos locales definidos.
- `PRD-FR-197`: La importación debe aceptar reintentos sin duplicar registros canónicos y debe producir auditoría por lote y por cambio sensible.

### 4.14 Identificación telefónica en checkout

- `PRD-FR-198`: Cuando un teléfono válido no tenga coincidencias en la sucursal, el POS debe
  permitir registrar un cliente con nombre y ese teléfono sin abandonar ni reiniciar la venta.
  El cliente creado queda seleccionado y, para entrega a domicilio, permite capturar y seleccionar
  inmediatamente un domicilio estructurado. Una clave heredada no puede convertirse en teléfono
  si la fuente no declara que lo sea.

### 4.15 Variaciones y cambios preestablecidos

- `PRD-FR-199`: Debe administrar un catálogo corporativo único de comentarios o indicaciones
  predefinidas —incluidos “Sin azúcar”, “Sin lechuga”, “Sin cebolla” y “Azúcar de dieta”— y
  relacionar cada comentario con uno o varios productos. El administrador corporativo puede pegar
  comentarios separados por coma, salto de línea o dos o más espacios, depurarlos antes de guardar
  y asignarlos masivamente marcando una o varias subcategorías dentro de categorías operativas
  desplegables. La selección incluye todos los productos activos que componen esas subcategorías y
  muestra su alcance antes de confirmar.
  Los comentarios no tienen disponibilidad ni excepción por sucursal. En POS se muestran como
  controles táctiles únicamente para los productos relacionados y se congelan en la línea, KDS y
  comanda. Un comentario nunca modifica precio, receta, inventario, reserva, consumo ni costo.
- `PRD-FR-200`: Debe administrar ingredientes adicionales corporativos a partir del catálogo de
  insumos, con cantidad exacta en unidad base, estación y precio de venta explícito. Un ingrediente
  adicional activo queda disponible para cualquier producto sin relación previa producto-insumo; en
  POS se agrega a una línea concreta elegida durante la venta. Su costo proviene del estado de costo
  de la sucursal, pero nunca determina automáticamente el precio cobrado. Al aceptar el pedido debe
  modificar snapshot, costo teórico, reserva y consumo, y congelar cantidad, precio y texto.
- `PRD-FR-201`: El sistema debe separar explícitamente los comentarios del pedido de los
  ingredientes adicionales en administración corporativa, administración de sucursal y POS. Las
  acciones históricas de retiro de POS-VAR-002 se conservan para auditoría, pero no se ofrecen ni
  aceptan en ventas nuevas.
- `PRD-FR-202`: Debe depurar el catálogo heredado con una migración reversible y auditable. Los
  insumos con SKU distinto de dígitos ASCII y las categorías cuyo nombre no esté completamente en
  mayúsculas se retiran del catálogo operativo. Un producto sólo se conserva cuando, después de
  quitar comillas iniciales de importación, su SKU contiene únicamente dígitos ASCII y su nombre
  está completamente en mayúsculas. Los productos conservados quedan activos, con SKU normalizado,
  alcance corporativo y estación `drinks`, `kitchen` o `packing` según reglas explícitas. Los
  registros retirados no se muestran en catálogos, pero sus identificadores se conservan archivados
  cuando existan referencias históricas. La migración no modifica movimientos, existencias, costos,
  pagos, pedidos ni snapshots históricos.
- `PRD-FR-203`: El catálogo POS debe mostrar una sola representación seleccionable de cada producto:
  las tarjetas dentro de la categoría activa; no debe duplicar los mismos productos en una banda
  superior. El carrito debe permitir reducir cantidad y retirar por completo una línea antes de
  crear el pedido, mediante controles táctiles accesibles y sin dejar cantidades en cero.
- `PRD-FR-204`: La sección **Pedidos** debe abrir el detalle de cualquier pedido de la sucursal. Un pedido sin
  pago confirmado puede modificarse únicamente mientras su estado sea `ACCEPTED` y todas sus tareas
  productivas estén pendientes. Agregar, sustituir o retirar líneas crea una enmienda versionada,
  compensa reservas, actualiza tareas pendientes y conserva eventos y snapshots anteriores. Un
  pedido pagado o con producción iniciada permanece disponible sólo para consulta. En escritorio,
  seleccionar una fila mantiene visible la lista y abre el detalle en una columna derecha estable,
  alineada con el patrón de cuenta del Punto de Venta; no debe interrumpir la revisión con un popup.
  **Editar pedido** debe conservar el identificador del pedido seleccionado en una ruta explícita y
  abrir el Punto de Venta en modo edición, nunca como una venta nueva. El carrito editable debe
  mostrar todas las líneas activas del pedido; si un producto ya no forma parte del catálogo visible,
  debe reconstruirlo con el snapshot histórico de la línea en vez de descartarlo.
  La navegación lateral debe mostrar junto a **Pedidos** un contador visible y accesible con el total
  exacto de pedidos `PENDING` (**Por aceptar**) de la sucursal activa. El contador se oculta cuando el
  total es cero, no incluye otros estados ni otras sucursales y se actualiza al recuperar foco,
  periódicamente durante la sesión y después de aceptar un pedido.
- `PRD-FR-205`: Antes del pago se puede reducir el importe cobrable mediante un ajuste de cortesía
  autorizado por un Supervisor de la misma sucursal. El subtotal calculado de líneas no se
  sobrescribe: cada cambio agrega un ajuste inmutable con importe anterior, nuevo importe, delta,
  solicitante, autorizador, justificación y fecha. El total no puede ser negativo y el pago debe
  coincidir con el total calculado por el backend después de los ajustes.
- `PRD-FR-206`: El Supervisor puede consultar el catálogo corporativo de proveedores y registrar un
  proveedor nuevo desde la administración de su sucursal. El alta es corporativa, evita duplicados
  por código o RFC, queda habilitada para la sucursal de origen y produce auditoría. El Cajero no
  puede crear proveedores ni modificar su identidad fiscal o condiciones de otras sucursales.
- `PRD-FR-207`: El Supervisor debe registrar compras directas de su sucursal seleccionando proveedor,
  una o varias presentaciones de insumos, cantidades, precios y método de pago. Efectivo es el valor
  predeterminado y, al confirmar con turno abierto, crea un retiro inmutable de caja vinculado. Los
  demás medios no afectan caja. La recepción, costo promedio, idempotencia, cancelación y
  compensaciones siguen las reglas de `PRD-FR-108` a `PRD-FR-111`.
- `PRD-FR-208`: Los pedidos `takeout` y `delivery` deben poder aceptarse con un método de pago
  previsto sin crear todavía un pago confirmado. En **Pedidos** se muestran como **Pendiente de
  pago**, pueden abrirse y, mientras cumplan las reglas de `PRD-FR-204`, editarse. Al entregar y
  verificar el cobro, un actor con `payments.confirm` registra el pago inmutable por el total vigente
  y el método realmente recibido. La confirmación exige la caja de cobro y se atribuye al turno
  `OPEN` de esa caja en el momento del pago, aunque el pedido se haya capturado en un turno anterior.
  Pago, movimientos de efectivo, compras cash y cierre operativo compiten bajo el mismo guard: si el
  pago gana, queda incluido en el resumen del turno; si el cierre gana, el pago falla sin escritura y
  debe reintentarse en un turno nuevo. Los pedidos `dine-in` conservan el cobro inmediato del POS.
- `PRD-FR-209`: El Punto de Venta debe concentrar su navegación lateral en la operación de caja:
  no presenta Panel Principal ni Inventario. Inventario permanece disponible dentro de
  Administración de sucursal. La navegación superior del catálogo presenta siempre cinco grupos:
  **Todo**, **Alimentos**, **Bebidas**, **Otros** y **Favoritos**. **Todo** contiene todas las
  categorías con productos activos y disponibles; **Alimentos**, **Bebidas** y **Otros** las agrupan
  por su estación operativa vigente. **Favoritos** es la excepción: muestra directamente los
  productos concretos que el Cajero marcó en ese navegador, guardados localmente por `product_id`,
  usuario y sucursal. Marcar una variante/tamaño no marca otras variantes; IDs obsoletos simplemente
  no producen tarjeta. Al cambiar a Todo, Alimentos, Bebidas u Otros, el cuadro intermedio sustituye
  sus opciones por las categorías correspondientes, conservando tarjetas grandes, claras, con iconos
  y sin paginación. Cada tarjeta de producto concreto permite marcar o retirar su favorito mediante
  un control accesible independiente; quitarlo desde Favoritos sólo retira esa tarjeta y no modifica
  carrito ni búsqueda.
- `PRD-FR-210`: Administración corporativa debe incluir un catálogo de repartidores propios. Cada
  registro conserva nombre, licencia, placas de la motocicleta, sucursal asignada, teléfono,
  domicilio y persona de contacto. El administrador puede consultar, crear, editar y desactivar
  registros; la desactivación no elimina historial y cada cambio produce auditoría sin duplicar
  teléfono ni domicilio dentro del evento.
- `PRD-FR-211`: El modal de cobro debe respetar el tipo de pedido seleccionado previamente y no
  volver a solicitarlo. Sólo para pedidos a domicilio puede asignarse un repartidor activo de la
  misma sucursal. Al crear el pedido, la asignación conserva un registro inmutable con repartidor,
  pedido, cliente, domicilio de entrega, total, número de líneas, cantidad de productos, moneda,
  actor y fecha; Administración permite consultar este historial por repartidor.
- `PRD-FR-212`: El POS debe ofrecer **Checador** entre **Pedidos** y **Administración**. Al abrirlo
  muestra la hora actual y solicita únicamente la clave del empleado. La clave se valida contra un
  identificador laboral de exactamente seis caracteres alfanuméricos, normalizado a mayúsculas y
  asignado de forma única a una sola persona en toda la organización, sin importar si pertenece al
  catálogo de Usuarios o al de Repartidores. Este código no sustituye el UUID técnico interno. Una
  clave inexistente, con formato inválido o perteneciente a un registro inactivo no genera checada.
  Cada checada conserva de forma inmutable persona, tipo de catálogo, sucursal,
  actor, hora UTC y día local de la sucursal. Se permiten como máximo dos checadas por persona y día
  local: con una sola, el reporte la muestra en azul; con dos, muestra la primera en verde como
  entrada y la segunda en rojo como salida. Dentro de Administración de sucursal, un actor con
  `branch.staff.read` puede consultar el reporte y filtrarlo por código de empleado, día o mes y
  sucursal, siempre dentro de su alcance autorizado. Todo Usuario o Repartidor nuevo requiere su
  código; los registros existentes sin código se conservan, pero no pueden usar el checador hasta
  que un administrador les asigne uno.
- `PRD-FR-214`: En la cuadrícula del POS, una tarjeta de producto concreto sin fotografía utilizable
  debe usar un fallback visual compacto y un nombre legible de hasta tres líneas. Una tarjeta con
  fotografía conserva su imagen, texto alternativo y tratamiento actual. El selector previo de una
  categoría (por ejemplo, Tamaño Chica/Grande) no es un producto concreto y conserva su apariencia
  y conducta. Este ajuste de presentación no cambia selección, precio, carrito, complementos ni
  ningún contrato de venta.
- `PRD-FR-229`: El catálogo POS debe guiar la captura en etapas progresivas: grupos fijos de menú,
  categorías, selector previo de categoría cuando aplique, productos concretos y compositor de
  modificadores. Al avanzar, la etapa anterior queda disponible como contexto compacto para cambiar
  o regresar, sin competir visualmente con la etapa actual. Elegir un grupo fijo reinicia el flujo
  transitorio; cambiar categoría u opción y confirmar una personalización preservan carrito y
  búsqueda conforme a sus contratos vigentes. Los modificadores se muestran por grupos como pestañas
  grandes y sólo las opciones de la pestaña activa se presentan a la vez. El POS comunica si cada
  grupo es Obligatorio u Opcional y sus límites existentes; sólo habilita Agregar al pedido cuando
  todos los mínimos ya se cumplen. Un producto sin modificadores se agrega directamente. Esta
  presentación no cambia catálogo, precios, reglas operativas, selección de modificadores, carrito,
  pedido ni contratos API.

### 4.17 POS-CASH-OPS-001 — operación de caja, cuentas y perfiles acumulativos

**Estado documental:** Decisiones de producto aprobadas el 2026-08-10. `PCO-001` completó la
transición de autorización, perfiles y alcance. `PCO-002` completó el catálogo corporativo
versionado de conceptos y su lectura efectiva. `PCO-003` implementó y activó el ledger de
depósitos/retiros, compensaciones y efectivo esperado. `PCO-004` implementó y activó el cierre
operativo separado del corte, los snapshots históricos y el monitor trazable. Corte por usuario,
reapertura, venta por insumos/reportes y operación offline conservan sus incrementos separados en el
plan (`PCO-005` a `PCO-008`).

La jerarquía de producto confirmada es acumulativa: **Cajero** vende y registra retiros;
**Cajero jefe** hereda Cajero y maneja caja, modifica pedidos, compras y mermas; **Líder** hereda
Cajero jefe y puede sacar corte por usuario y cancelar pedidos; **Supervisor** hereda Líder y
modifica recetas, consulta venta por insumos, inventario y reporta merma; **Administrador** hereda
Supervisor y consulta reportes de ventas y gastos; **Dueño** tiene acceso total en todas las
sucursales. La herencia describe capacidad de producto: la autorización efectiva se resuelve sólo
por permisos granulares persistidos y alcance, nunca por comparar nombres en la UI.

- `PRD-FR-215`: Debe asignar capacidades acumulativas a los seis perfiles nuevos mediante permisos
  persistidos y alcance. Dueño recibe explícitamente el conjunto completo de permisos persistidos
  vigente en su organización (incluidos permisos corporativos y especializados), además de alcance
  organización/todas las sucursales; no usa wildcard confiado desde cliente ni cruza organizaciones.
  Todos los demás operan exclusivamente sobre sucursales asignadas y fallan cerrado si no hay una
  asignación explícita, activa y válida; una asignación branch `NULL` heredada tampoco autoriza. No elimina los perfiles especializados
  vigentes de cocina, bebidas, empaque, despacho, reparto, inventarios, cuentas por pagar, auditoría
  ni recepción de traspaso. La transición de roles semilla debe ser reversible: el Administrador
  corporativo existente no se convierte silenciosamente en Dueño: el mapeo es individual, explícito,
  reversible y auditable; el rol legacy sigue compatible hasta mapearlo. La asignación o revocación
  de Dueño exige un actor que ya tenga la misma autoridad persistida en la organización. Si no hay
  Dueño, sólo el bootstrap inicial aprobado puede resolver la primera asignación; no se inventa ni
  ejecuta contra datos reales en PCO-001. Un rol con `organization_all_permissions` conserva alcance de organización:
  no se puede borrar, reducir por reemplazo de permisos ni cambiar a `branch`; su etiqueta puede
  cambiarse sólo por un actor con la misma autoridad y nunca define autorización. Crear un rol
  organizacional u otorgarle el permiso ordinario `access.organization.all_branches` no crea la
  concesión dinámica ni equivale a Dueño. El bootstrap inicial aprobado es una operación de
  mantenimiento sin endpoint HTTP, explícita y única: recibe organización, actor operacional y
  procedencia, y acepta únicamente los dos correos configurados como entrada
  `aniacuestas@gmail.com` y `mangoex@gmail.com`. Sólo puede asignar el rol con grant persistido a
  usuarios ya existentes y activos de esa organización; la precondición verificada por lectura indica
  que ambos conservan Administrador corporativo legacy, que el bootstrap preserva sin convertir ni
  borrar. No crea cuentas, contraseñas, organizaciones ni roles,
  y rechaza ausencia, duplicidad, mezcla de organización, asignación parcial o Dueño preexistente no
  aprobado. La ejecución es atómica y el rerun idéntico devuelve resultado estable/auditado sin nueva
  asignación. Un rechazo revierte primero toda escritura pendiente del llamador y persiste sólo su
  auditoría de denegación. La migración no ejecuta el bootstrap ni lee datos reales.
  El mapeo individual usa `PENDING -> MAPPED -> REVERSED`, con snapshot de roles sin PII,
  idempotency keys por etapa y auditoría. Aplicar agrega el perfil destino sin borrar especialidades;
  aplicar falla si el rol legacy ya no está asignado exactamente en la sucursal capturada en el
  snapshot. Revertir sólo retira la asignación exacta
  (perfil y sucursal) creada por el mapping; si fue retirada o reasignada, falla sin marcar
  `REVERSED`. Un actor inexistente, inactivo o de otra organización es denegado sin confirmar
  escrituras ajenas y genera auditoría en la organización objetivo; actor inexistente se registra
  como `NULL`. Todo dry-run, creación, aplicación o reversión de mapping exige primero que la
  organización exista y esté activa; de lo contrario responde
  `profile_transition_organization_invalid` sin mapping ni auditoría. El replay concurrente compara
  payload/procedencia completos antes de responder.
  Ninguna operación convierte automáticamente
  Administrador corporativo legacy en Dueño.
- `PRD-FR-216`: Debe registrar depósitos y retiros manuales de efectivo durante turno abierto, con
  tipo, concepto de catálogo versionado, referencia obligatoria y evidencia obligatoria para todo
  movimiento manual.
  Cada movimiento es append-only, idempotente, auditable y se corrige sólo mediante compensación;
  se incluye una vez y de manera determinista en el efectivo esperado. La inferencia actual define
  retiro como retiro manual de efectivo con turno abierto. El Dueño administra conceptos; el actor
  sólo puede seleccionar un concepto efectivo devuelto por backend; nunca puede
  inventar texto o código. Una compra en efectivo se clasifica una sola vez como retiro por su
  documento/razón y no puede duplicar el efectivo esperado.
  `PCO-002` cubre la precondición de catálogo: crear la identidad inmutable de un concepto,
  publicar nuevas versiones con vigencia, archivar sin borrar historia y consultar desde backend la
  versión efectiva por tipo y fecha. No habilita todavía `POST /cash/movements`, compensaciones ni
  efectivo esperado; esas operaciones pertenecen a `PCO-003`. PCO-003 exige que el cliente envíe
  sucursal/caja, tipo, concepto, importe positivo en centavos, referencia y una o más referencias de
  evidencia; el backend deriva actor, organización, turno `OPEN`, versión efectiva, snapshot y signo.
  Sólo Dueño puede compensar y la compensación es única, exacta, opuesta y enlazada al original. Las
  compras en efectivo y sus cancelaciones usan el mismo ledger sin requerir un concepto manual y sin
  crear un segundo término contable. El POS debe exponer al Dueño una acción de compensación sobre
  originales elegibles, pedir sólo motivo y evidencia, mostrar el vínculo original-compensación y
  refrescar ledger y efectivo esperado después de crear o compensar. Un actor sin
  `cash.movement.compensate` no ve ni puede invocar esa acción. PCO-003 no declara éxito offline ni
  cambia cierre/corte.
- `PRD-FR-217`: Debe permitir consultar cuentas/pedidos por turno, día, caja, sucursal y tipo de
  servicio, buscar folio o cliente y abrir un detalle histórico con snapshots de líneas, cantidades,
  productos y pago. La reapertura de una cuenta se limita inicialmente a solicitud, autorización y
  enmienda auditables. Un pedido pagado, cerrado o con producción iniciada permanece sólo lectura
  hasta solicitud de Cajero jefe o superior, autorización de Dueño y aplicación auditable/
  compensatoria conforme a invariantes; no se habilita reapertura implícita. `PCO-005A` entrega la
  consulta, solicitud y decisión sin mutar pedido, pago, inventario, producción, cierre o snapshots;
  incluso una solicitud aprobada conserva la aplicación cerrada con
  `order_reopen_policy_pending`. Conforme a `SDD-ADR-027`, `PCO-005B` habilita
  `APPROVED -> APPLIED` mediante una corrección enlazada y append-only: la cuenta, pago, snapshot,
  turno y corte originales no se reescriben. Dueño aplica la imagen exacta; Python deriva el delta
  financiero y productivo. Delta positivo crea cargo adicional, delta negativo reembolso y delta
  cero sólo conciliación. Producción `PENDING` puede liberar/reemplazar, `IN_PROGRESS` bloquea y una
  reducción `COMPLETED` exige `waste|recovery`; las adiciones crean reserva y tarea nuevas. Toda la
  aplicación es atómica, idempotente y auditable.
- `PRD-FR-218`: Debe permitir abrir, consultar y cerrar operativamente turnos, y separar ese cierre
  del corte final. Apertura y cierre son comandos idempotentes; el cierre transaccional conserva
  `OPEN -> CLOSING -> OPERATIVELY_CLOSED`, actor y resumen congelado, sin aceptar efectivo contado,
  esperado o diferencia y sin crear un corte. Debe proveer un monitor de ventas por periodo UTC,
  turno/caja, categorías o familias y tipo de servicio, con importes en centavos, impuestos,
  descuentos/cortesías, conteos y drill-down trazable hacia operaciones. El backend Python calcula
  los agregados desde pagos confirmados y snapshots históricos de líneas; cada indicador financiero
  distingue monto conocido y número de operaciones sin dato canónico, sin consultar el catálogo
  vigente, inferir IVA ni sustituir faltantes por cero. Filtros por estación, salida a
  pantalla/impresora/Excel y formato especial de folio/nota de consumo son candidatos visuales del
  video, no requisitos confirmados. La UI sólo convierte el día local cuando ya tiene una sucursal
  autorizada con zona horaria válida; el API recibe límites UTC con zona y rechaza periodos ingenuos.
  Las listas y drill-down usan límites de 1 a 100 y cursores opacos, estables y estrictamente
  validados. La migración histórica falla cerrada si no puede conservar una moneda ISO de tres letras
  coherente entre pago y pedido; nunca inventa una moneda para publicar una venta. Como excepción
  exclusiva de lectura histórica de `0038`, un pago confirmado cuyo pedido conserva el código legado
  exacto `takeaway` se proyecta como `takeout` en el snapshot sin modificar el pedido. Las rutas y
  comandos vigentes aceptan únicamente `dine-in|takeout|delivery`; cualquier otro valor histórico
  bloquea el preflight.
- `PRD-FR-219`: Debe realizar corte por usuario con autorización, alcance inequívoco por cajero,
  caja, turno y periodo, efectivo contado, efectivo esperado, diferencia/tolerancia configurada,
  reporte inmutable, historial y eventual reapertura sólo compensatoria. Debe impedir cortes
  concurrentes, duplicados o periodos solapados sobre una misma operación y nunca contar una
  operación dos veces. Una operación asociada a un corte `FINALIZED` nunca se reasigna a otro corte,
  aun si aquél recibe reapertura/compensación; ésta crea artefactos enlazados sin liberar la asociación.
  Periodo/día operativo se almacenan UTC y se presentan en zona local; la zona, tolerancia,
  autorizador es Líder o superior dentro de sucursal asignada; sólo Dueño reabre por compensación.
  La tolerancia inicial es cero centavos; una excepción futura por sucursal requiere autorización de
  Dueño.
- `PRD-FR-220`: Debe permitir a Supervisor y perfiles superiores consultar venta por insumos dentro
  de su alcance y a Administrador/Dueño reportes de ventas y gastos según su alcance. El backend
  Python deriva resultados con `Decimal` desde líneas, snapshots y versiones de receta aplicadas;
  una receta actual nunca recalcula una operación histórica. Gastos se derivan de documentos y
  movimientos con clasificación canónica por documento, sin sumar por separado una compra y su retiro
  enlazado; los impuestos se separan. El día operativo usa inicialmente la zona horaria de sucursal,
  de 00:00 a 23:59 local. React/TypeScript sólo presenta el resultado autoritativo.
- `PRD-FR-221`: Toda ruta operacional o de mantenimiento debe fallar cerrada. Sembrar catálogos o
  sucursales será una operación interna idempotente y auditada, no una ruta HTTP pública. KDS,
  sincronización y gestión de trabajos de impresión exigirán una identidad humana o de dispositivo,
  permiso/capacidad granular y alcance de organización/sucursal resueltos en backend. La ausencia de
  actor, credencial, alcance o política explícita devuelve denegación sin ejecutar efectos.
- `PRD-FR-222`: Imprimir y reimprimir debe crear un trabajo persistente, idempotente y auditable. Una
  solicitud aceptada sólo confirma que el trabajo quedó encolado; únicamente el acuse verificable del
  agente de impresión puede marcarlo `PRINTED`. Reintentar conserva el trabajo e historial originales,
  crea o reactiva un intento enlazado y nunca presenta éxito si la API no lo persistió. Los totales
  del POS, modificadores, extras y recetas se calculan en Python y React sólo presenta el DTO. Confirmar
  un pago no cierra el pedido: KDS conduce producción hasta `READY` y los comandos idempotentes de
  fulfillment, autorizados por sucursal, realizan entrega y cierre con auditoría.
- `PRD-FR-223`: El sitio web público móvil puede capturar pedidos sin autenticación de empleado, pero
  debe resolver la sucursal desde una clave pública opaca configurada en servidor, exigir
  `Idempotency-Key`, validar catálogo, disponibilidad, cantidades y precios en backend Python, y
  persistir exactamente una intención canónica. Nunca aceptará un UUID interno de sucursal como
  autoridad ni fabricará folio o éxito ante rechazo, timeout o indisponibilidad.
  Un actor autenticado con `orders.create` y alcance de sucursal puede rechazar de forma terminal
  una intención pendiente, con versión esperada, idempotencia, motivo y auditoría, sin crear pedido
  ni efectos operativos. `EXPIRED` permanece reservado: este alcance no define TTL ni expiración
  automática.
- `PRD-FR-224`: Una intención pública aceptada debe entrar al mismo dominio de pedidos, reservas,
  producción, eventos, auditoría y outbox que el resto de los canales. La captura pública no crea,
  elige ni reutiliza turnos de caja y no confirma pagos. Si la política operativa exige revisión, la
  intención queda `PENDING_REVIEW` hasta que un actor autorizado de la sucursal la acepte; sólo esa
  transición puede crear el pedido operativo y su reserva exactamente una vez.
- `PRD-FR-225`: Debe generar automáticamente el reporte de conciliación y corte diario de sucursal
  (corte Z extendido, desglose multicanal de cobros y partidas de egresos, cálculo de balance y
  sobrante/faltante) a partir de turnos y movimientos reales, calculando los límites UTC exactamente
  a partir de la zona horaria de la sucursal asignada (00:00:00 a 23:59:59 local) y requiriendo
  permiso de lectura de dashboard y alcance de sucursal.
- `PRD-FR-226`: Debe permitir a Administradores corporativos y Dueño consultar el consolidado multi-sucursal
  diario y mensual sin solapamiento entre días, persistir de forma inmutable en base de datos
  (`reconciliation_audit_logs`) el estado de auditoría gerencial con notas y revisor, y exportar el
  libro de cálculo en Excel (.xlsx) con el formato oficial de Kiwi protegido por RBAC.
- `PRD-FR-227`: Debe proveer una interfaz web responsiva de autoservicio para clientes móviles
  (`apps/mobile-web`) y endpoints públicos de consulta de catálogo y captura de pedidos en línea
  (`/api/v1/public/*`), asignando precios vigentes de catálogo sin fallbacks artificiales y registrando
  dirección de entrega o retiro. Conforme a ADR-031, la captura pública persiste una intención
  idempotente y no crea, selecciona ni reutiliza turnos de caja; sólo una aceptación autenticada puede
  crear el pedido operativo.
- `PRD-FR-228`: El Cajero con `orders.create` debe poder abrir **Captura asistida** desde el encabezado
  del POS, escribir o dictar una solicitud en español de México y obtener un borrador revisable que
  proponga cliente, teléfono, tipo de servicio y líneas del pedido usando exclusivamente el catálogo
  efectivo y la sucursal canónica. Aplicar el borrador sólo llena el carrito y los datos editables del
  checkout: nunca crea, cobra, acepta, reserva inventario ni presenta folio. Una coincidencia telefónica
  única puede seleccionar al cliente; cero o múltiples coincidencias requieren confirmación humana.
  Productos, comentarios o modificadores ambiguos/no disponibles permanecen sin resolver y no se
  sustituyen ni inventan. Si el producto exige tamaño, pan, aderezo u otro grupo obligatorio, la
  captura debe formular una pregunta concreta y ofrecer únicamente opciones efectivas de la sucursal;
  no puede aplicar la línea hasta satisfacer todas las cardinalidades. El cajero puede corregir o
  descartar todo antes de usar el checkout canónico. El acceso visual se presenta como un botón de
  icono de persona, con nombre accesible pero sin texto visible en el encabezado. El dictado puede
  continuar internamente hasta 3000 ms de silencio desde el último resultado, incluso si el navegador
  corta una sesión técnica; Detener, cerrar o un fallo permanente lo cancelan de inmediato. Reiniciar
  Dictar agrega texto sin duplicar resultados ni reemplazar una corrección manual.
- `PRD-FR-230`: El Administrador corporativo con `catalog.manage` debe poder abrir desde el
  encabezado de Admin un asistente de inteligencia artificial exclusivo del backoffice. El
  asistente consulta conocimiento canónico sobre organización, catálogo, pedidos, recetas,
  inventario, caja, permisos, auditoría y operación, y debe identificar las fuentes usadas sin
  presentarse como autoridad del dominio. Para configuración sólo puede preparar una propuesta
  revisable de una acción por vez: crear o actualizar producto, crear insumo, crear grupo u opción
  de modificador, o versionar receta usando productos, grupos, insumos y unidades existentes.
  En consultas de diagnóstico, **precio de venta**, **precio de compra** y **costo promedio** son
  conceptos distintos: el primero corresponde a la versión vigente del producto; el segundo, a una
  presentación activa del insumo y su historial de proveedor; el tercero, al estado contable por
  sucursal, almacén e insumo después de recepciones confirmadas. Una solicitud ambigua como
  “insumos sin precio” debe pedir al usuario que elija el concepto y no puede inferirlo, mezclar
  productos con insumos ni entregar como resultado identificadores internos sin etiqueta legible.
  La aclaración debe continuar dentro de una conversación visible y acotada: una respuesta breve
  como “de compra” se interpreta sólo contra la pregunta pendiente autenticada, sin exigir que el
  usuario reformule la solicitud completa. Para insumos ofrece únicamente precio de compra y costo
  promedio; no ofrece precio de venta de producto como una salida ejecutable. Cada turno conserva
  sucursal, actor y propuesta padre, revalida permisos contra la sucursal solicitada y nunca concede
  autoridad de escritura. Cada padre admite un solo seguimiento; las respuestas previas del usuario
  necesarias para una aclaración genérica viajan como contexto efímero acotado, no se persisten, y
  cerrar el modal termina esa sesión visible. Cada seguimiento usa una clave idempotente para poder
  recuperar el mismo hijo si la respuesta HTTP se pierde, sin volver a consumir el padre.
  Un diagnóstico explícito sólo se responde cuando la proyección canónica de ese concepto y alcance
  está habilitada; de lo contrario queda `DRAFT` con una explicación, sin propuesta aplicable. Las
  proyecciones habilitadas de precio de compra y costo promedio deben calcularse en Python, devolver
  sólo estado faltante, nombre, SKU, unidad y alcance, y nunca exponer al proveedor de IA importes,
  existencias, proveedores, movimientos o historial de compras. Consultar costo promedio exige
  `inventory.read` para la sucursal seleccionada. Ambos diagnósticos exigen una sucursal explícita y
  respetan `catalog_scope/source_branch_id`. Precio de compra revalida la autoridad canónica
  `purchases.read`, cuya compatibilidad vigente admite `catalog.manage`; costo promedio revalida el
  grant independiente `inventory.read` al crear, consultar o revisar la respuesta persistida.
  Valores materiales como nombre, SKU, precio, cantidades y cardinalidades deben proceder de la
  solicitud humana; datos faltantes se preguntan y nunca se inventan. Una propuesta lista dirige a
  la pantalla administrativa correspondiente, muestra estado actual, valor propuesto, advertencias
  y fuentes, y no modifica nada hasta que un usuario autorizado la acepte explícitamente. Aceptar
  vuelve a resolver identidad, permisos, alcance, expiración y fingerprint del catálogo, y delega
  al servicio canónico de la acción con idempotencia y auditoría. Rechazar o expirar no escribe
  configuración. El MVP excluye órdenes, pagos, caja, compras, movimientos físicos de inventario,
  producción operativa, usuarios, roles y cualquier borrado o archivado automático.

- `PRD-FR-231`: La ruta pública `/` debe presentar la portada institucional de Kiwi Natural en
  navegadores de escritorio y redirigir los accesos identificados como teléfono a `/menu/` antes de
  cargar el video u otros recursos pesados de la portada. La selección de presentación no concede
  autenticación ni cambia el comportamiento de `/admin/`, `/pos/`, `/kds/`, `/menu/`, `/api/` o los
  health checks. La respuesta de la raíz debe impedir mezcla de variantes por caché y la portada debe
  usar enlaces relativos para conservar el mismo destino bajo cualquiera de los dominios públicos.

## 5. Requisitos no funcionales

- `PRD-NFR-001 Disponibilidad`: Operación local durante falla de internet.
- `PRD-NFR-002 Consistencia`: No perder ni duplicar comandos.
- `PRD-NFR-003 Rendimiento`: Una sucursal debe soportar 100 pedidos por hora con margen mínimo de 5x.
- `PRD-NFR-004 Latencia local`: Acciones POS críticas menores a 300 ms en red local en condiciones normales.
- `PRD-NFR-005 Latencia nube`: Respuestas API interactivas menores a 800 ms p95, excluyendo proveedores externos.
- `PRD-NFR-006 Seguridad`: Autenticación, autorización por rol y sucursal, cifrado en tránsito y secretos fuera del repositorio.
  - Ninguna acción sensible debe usar un administrador semilla por omisión cuando falte token o actor.
  - Tokens de sesión y perfiles de usuario nunca viajan en query string ni fragmentos. El traspaso
    entre Admin y POS usa un código opaco de un solo uso, con expiración máxima de 60 segundos; el
    fragmento se elimina antes del canje y el backend vuelve a resolver usuario, permiso y alcance.
- `PRD-NFR-007 Auditoría`: Registro inmutable de acciones sensibles.
- `PRD-NFR-008 Recuperación`: Respaldos automáticos y procedimientos de restauración probados.
- `PRD-NFR-009 Observabilidad`: Logs estructurados, métricas, trazas y alertas.
- `PRD-NFR-010 Mantenibilidad`: Arquitectura modular y adaptadores. Los identificadores PRD,
  BDD y TDD deben tener una sola definición formal; cada escenario BDD debe tener un identificador
  propio, y la matriz debe conservar tipos de referencia correctos sin aceptar un caso TDD en la
  columna BDD ni un escenario BDD en la columna TDD. El gate de pull request debe analizar sólo el
  diff propuesto y bloquear nuevos silenciamientos de tipos/lint/cobertura o pruebas desactivadas,
  salvo una excepción local explícitamente justificada; la deuda histórica no modificada no falla el
  gate y los hallazgos no exponen el contenido de la línea.
- `PRD-NFR-011 Portabilidad`: Despliegue por contenedores en Easypanel.
- `PRD-NFR-012 Precisión`: Dinero y cantidades con aritmética decimal exacta.
- `PRD-NFR-013 Evolución`: Preparación para multiempresa futura sin exponer autoservicio.
- `PRD-NFR-014 Privacidad`: Minimización y protección de datos personales.
- `PRD-NFR-015 Compatibilidad`: Navegadores modernos y Windows en gateways.
- `PRD-NFR-016 Calidad`: Todo cambio en Admin, POS, KDS o paquetes TypeScript compartidos debe superar en integración continua una instalación reproducible con lockfile, typecheck estricto y builds de producción. Una falla debe bloquear la integración.
- `PRD-NFR-017 Migraciones`: La cadena de migraciones debe admitir identificadores de revisión versionados sin truncamiento, conservar una sola línea de descendencia y poder avanzar o revertirse de manera reproducible en PostgreSQL y SQLite.
- `PRD-NFR-018 Localización operativa`: Toda cadena visible para cajeros y supervisores dentro del POS debe presentarse en español de México. Los códigos internos del dominio permanecen estables, pero nunca se muestran como etiquetas sin traducción.
- `PRD-NFR-019 Autorización reforzada`: Una acción de cortesía solicitada desde una sesión de Cajero
  debe exigir reautenticación de un Supervisor autorizado para la misma sucursal mediante validación de
  PIN/código en backend. La contraseña no se persiste ni aparece en logs; la autorización emitida es de
  un solo uso, expira y queda limitada a la acción, sucursal y pedido indicados.
- `PRD-NFR-020 Autorización de caja`: Toda ruta y comando de POS-CASH-OPS debe requerir actor real,
  permiso granular, alcance canónico y, cuando proceda, autorización reforzada. La UI oculta opciones
  no autorizadas pero el backend falla cerrado y audita también el intento denegado.
- `PRD-NFR-021 Exactitud y no repudio`: Importes se conservan en centavos enteros y cantidades/cálculos
  derivados se ejecutan con `Decimal` en Python. Pagos, cortes, movimientos de caja, inventario y
  sus correcciones son append-only o compensatorios, conservando actor, correlación y UTC.
- `PRD-NFR-022 Continuidad`: Los comandos de caja definidos para offline deben llevar actor,
  idempotency key, outbox/inbox y reconciliación servidor; una denegación posterior no se presenta
  como éxito definitivo local.
- `PRD-NFR-023 Observabilidad`: Caja, corte, reapertura, reporte y autorización deben producir logs
  estructurados sin secretos ni PII innecesaria, métricas de éxito/denegación/conflicto y trazas por
  correlation id, sucursal y caja.
- `PRD-NFR-024 Migración segura`: El cambio de perfiles, permisos y modelos de caja debe migrar y
  revertir de forma reproducible en PostgreSQL y SQLite, sin alterar historia financiera, pagos,
  inventario, auditoría ni roles especializados existentes.
  PCO-001 valida la migración reversible de perfiles en SQLite y en PostgreSQL aislado de integración;
  los esquemas de caja posteriores permanecen sin implementar ni verificar.
- `PRD-NFR-025 Corrección compensatoria segura`: Aplicar una reapertura debe bloquear solicitud,
  pedido y turno afectado, revalidar versión, organización, alcance, moneda, snapshots y producción,
  y confirmar corrección, ajustes, eventos, auditoría y estado `APPLIED` en una sola transacción.
  Carreras o fallos dejan cero escritura parcial; replay idéntico devuelve la misma respuesta y una
  clave con plan distinto falla. Los importes se calculan en Python con centavos enteros, las
  cantidades con `Decimal`, y logs/DTO omiten evidencia, motivo libre, PII e idempotency keys.
- `PRD-NFR-026 Higiene de repositorio y secretos`: Bases de datos, respaldos, credenciales, hashes,
  sales y datos operativos no se versionan ni se publican como artefactos. CI bloquea contenido
  sensible y archivos prohibidos. Retirar un archivo del árbol actual no equivale a sanear su
  historia: cambio de visibilidad, rotación de credenciales y reescritura histórica son operaciones
  separadas, verificables y con autorización humana explícita.
- `PRD-NFR-027 Resultado autoritativo`: Ninguna UI declara éxito, limpia datos pendientes ni muestra
  un folio definitivo antes de recibir una respuesta autoritativa persistida. Ante timeout o resultado
  incierto conserva el estado local, la misma clave idempotente y una acción segura de consulta o
  reintento; TypeScript no sustituye una falla por un resultado simulado.
- `PRD-NFR-028 Protección de escritura pública`: Las escrituras públicas usan esquema estricto,
  límites de tamaño y cantidad, rate limiting por señales no sensibles, idempotencia, correlación y
  observabilidad redactada. Los datos personales se minimizan y nunca aparecen completos en logs,
  métricas, hashes de idempotencia o respuestas de error.
- `PRD-NFR-029 Privacidad y autoridad de captura asistida`: La interpretación semántica puede usar
  OpenRouter sólo desde un adaptador de backend explícitamente habilitado. Nombre y teléfono se
  extraen y redactan antes de la solicitud externa; la clave nunca llega al navegador y ni el texto
  original ni la PII se registran o persisten. El dictado se ofrece cuando el navegador implementa
  `SpeechRecognition` y sólo inicia después de la acción del Cajero y del permiso de micrófono; esa
  implementación puede procesar audio mediante servicios de su fabricante y no utiliza OpenRouter.
  Si falta capacidad o se deniega permiso, siempre existe captura manual. La resolución usa IDs del catálogo efectivo; precios, cardinalidades, disponibilidad y
  creación del pedido permanecen bajo las autoridades Python vigentes. El proveedor opera con salida
  JSON estructurada, timeout acotado y fallo cerrado; una respuesta inválida, ID desconocido o proveedor
  no configurado no modifica la venta y mantiene disponible la captura manual del POS.
- `PRD-NFR-030 Privacidad y autoridad del asistente Admin`: El proveedor de IA opera únicamente
  desde backend, detrás de un flag Admin separado y deshabilitado por defecto, con clave fuera del
  navegador, salida JSON Schema estricta, temperatura cero y timeout finito. Sólo recibe el prompt
  administrativo y un contexto allowlist mínimo de IDs/nombres/versiones del catálogo, unidades y
  reglas canónicas; nunca recibe clientes, teléfonos, pedidos, pagos, credenciales, personal,
  movimientos, auditoría completa ni datos productivos ajenos al alcance. Prompt y transcript no se
  persisten ni se registran. La salida del modelo se considera no confiable: el backend rechaza
  fuentes desconocidas, IDs inexistentes, campos sin evidencia humana, acciones fuera de allowlist,
  propuestas múltiples, cambios obsoletos o respuestas inválidas. Proveedor ausente o fallido sólo
  permite orientación local fail-closed y nunca produce una propuesta aplicable.

## 6. Métricas de éxito

- Más de 99.9% de pedidos sin duplicidad.
- Cero pérdida de pedidos durante una desconexión controlada.
- Menos de 1% de impresiones con error no recuperado.
- Reducción de recaptura de pedidos externos.
- Diferencia de inventario identificable por movimiento.
- Tiempo medio de resolución de conflicto de sincronización menor a 10 minutos.
- 100% de pagos y movimientos sensibles auditables.
- 100% de requisitos críticos con pruebas automatizadas.

## 7. Fuera de alcance de versión 1

- Mesas, reservaciones y meseros.
- CFDI emitido desde el sistema.
- Pago en línea pasarela bancaria.
- Aplicación móvil nativa en tiendas de apps (se entrega canal web móvil responsivo bajo PRD-FR-223).
- Aplicación móvil nativa del repartidor.
- Geolocalización en tiempo real del repartidor.
- Producción centralizada.
- Nómina.
- Contabilidad general.
- Inteligencia de demanda avanzada.
- Portal de proveedores.
- Alta multiempresa por autoservicio.

## 8. Decisiones abiertas

- `OPEN-001`: Producto y versión exacta de CONTPAQi.
- `OPEN-002`: Tipo de integración actual con cada marketplace.
- `OPEN-003`: Proveedor definitivo de geocodificación y optimización.
- `OPEN-004`: Matriz de impresoras certificadas.
- `OPEN-005`: Método de autenticación corporativa.
- `OPEN-006`: Política exacta de factura global.
- `OPEN-007`: Reglas fiscales y layouts definitivos.
- `OPEN-008`: Política de venta cuando inventario reservado queda negativo.
- `OPEN-009`: Política de reapertura de cierres y periodos.
- `OPEN-010`: Topología de respaldo 4G/5G por sucursal.

### Decisiones resueltas — trazabilidad POS-CASH-OPS

- `OPEN-011` — **RESUELTO 2026-08-10:** Administrador corporativo no se convierte automáticamente
  en Dueño; el mapeo individual es explícito, reversible y auditable, preservando el rol legacy.
- `OPEN-012` — **RESUELTO 2026-08-10:** salvo Dueño, cada perfil sólo opera sucursales asignadas;
  falta de asignación es fail-closed. Dueño se limita a su organización y todas sus sucursales.
- `OPEN-013A/013B` — **RESUELTO 2026-08-10:** Cajero jefe o superior solicita reapertura de pedido
  pagado/cerrado; Dueño autoriza y la aplicación es auditable/compensatoria. PCO-001 no implementa
  ese workflow.
- `OPEN-014` — **RESUELTO 2026-08-10:** Líder o superior finaliza corte por usuario dentro de su
  alcance; sólo Dueño reabre por compensación, sin liberar operaciones históricas; tolerancia inicial
  cero.
- `OPEN-015` — **RESUELTO 2026-08-10:** Dueño administra conceptos; referencia siempre obligatoria
  y evidencia obligatoria en movimientos manuales. PCO-001 sólo siembra permisos, no rutas.
- `OPEN-016` — **RESUELTO 2026-08-10:** Supervisor o superior versiona recetas únicamente para sus
  sucursales; Dueño administra recetas corporativas y nunca se reescribe historia.
- `OPEN-017` — **RESUELTO 2026-08-10:** gastos se clasifican por documento canónico sin duplicar
  compra/retiro, impuestos separados y día operativo 00:00–23:59 en zona de sucursal.

## 9. Criterio de aceptación del producto

La versión 1 podrá declararse operativa cuando una sucursal piloto pueda:

1. Vender y preparar pedidos.
2. Imprimir y operar KDS.
3. Trabajar sin internet.
4. Sincronizar sin duplicados.
5. Descontar inventario con receta versionada.
6. Registrar caja y corte.
7. Recibir compras y XML.
8. Preparar reparto y rutas.
9. Exportar un lote validado.
10. Producir auditoría completa.
