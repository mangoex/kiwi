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

### 4.3 Pedidos

- `PRD-FR-020`: Debe crear pedidos de mostrador, para recoger y a domicilio.
  - Los pedidos creados desde POS requieren permiso `orders.create`, una sucursal autorizada y un turno de caja abierto.
  - Un pedido a domicilio exige cliente seleccionado y un domicilio activo perteneciente a ese cliente.
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
  y el método realmente recibido. Los pedidos `dine-in` conservan el cobro inmediato del POS.
- `PRD-FR-209`: El Punto de Venta debe concentrar su navegación lateral en la operación de caja:
  no presenta Panel Principal ni Inventario. Inventario permanece disponible dentro de
  Administración de sucursal. Cuando las categorías de productos excedan el espacio de la franja
  superior, el último control debe indicar **Siguiente** y, desde la segunda página, el primer
  control debe indicar **Regresar**, manteniendo visible la categoría activa de cada página.
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

## 5. Requisitos no funcionales

- `PRD-NFR-001 Disponibilidad`: Operación local durante falla de internet.
- `PRD-NFR-002 Consistencia`: No perder ni duplicar comandos.
- `PRD-NFR-003 Rendimiento`: Una sucursal debe soportar 100 pedidos por hora con margen mínimo de 5x.
- `PRD-NFR-004 Latencia local`: Acciones POS críticas menores a 300 ms en red local en condiciones normales.
- `PRD-NFR-005 Latencia nube`: Respuestas API interactivas menores a 800 ms p95, excluyendo proveedores externos.
- `PRD-NFR-006 Seguridad`: Autenticación, autorización por rol y sucursal, cifrado en tránsito y secretos fuera del repositorio.
  - Ninguna acción sensible debe usar un administrador semilla por omisión cuando falte token o actor.
- `PRD-NFR-007 Auditoría`: Registro inmutable de acciones sensibles.
- `PRD-NFR-008 Recuperación`: Respaldos automáticos y procedimientos de restauración probados.
- `PRD-NFR-009 Observabilidad`: Logs estructurados, métricas, trazas y alertas.
- `PRD-NFR-010 Mantenibilidad`: Arquitectura modular y adaptadores. Los identificadores PRD,
  BDD y TDD deben tener una sola definición formal; cada escenario BDD debe tener un identificador
  propio, y la matriz debe conservar tipos de referencia correctos sin aceptar un caso TDD en la
  columna BDD ni un escenario BDD en la columna TDD.
- `PRD-NFR-011 Portabilidad`: Despliegue por contenedores en Easypanel.
- `PRD-NFR-012 Precisión`: Dinero y cantidades con aritmética decimal exacta.
- `PRD-NFR-013 Evolución`: Preparación para multiempresa futura sin exponer autoservicio.
- `PRD-NFR-014 Privacidad`: Minimización y protección de datos personales.
- `PRD-NFR-015 Compatibilidad`: Navegadores modernos y Windows en gateways.
- `PRD-NFR-016 Calidad`: Todo cambio en Admin, POS, KDS o paquetes TypeScript compartidos debe superar en integración continua una instalación reproducible con lockfile, typecheck estricto y builds de producción. Una falla debe bloquear la integración.
- `PRD-NFR-017 Migraciones`: La cadena de migraciones debe admitir identificadores de revisión versionados sin truncamiento, conservar una sola línea de descendencia y poder avanzar o revertirse de manera reproducible en PostgreSQL y SQLite.
- `PRD-NFR-018 Localización operativa`: Toda cadena visible para cajeros y supervisores dentro del POS debe presentarse en español de México. Los códigos internos del dominio permanecen estables, pero nunca se muestran como etiquetas sin traducción.
- `PRD-NFR-019 Autorización reforzada`: Una acción de cortesía solicitada desde una sesión de Cajero
  debe exigir reautenticación de un Supervisor autorizado para la misma sucursal. La contraseña no
  se persiste ni aparece en logs; la autorización emitida es de un solo uso, expira y queda limitada
  a la acción, sucursal y pedido indicados.

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
- Pago en línea.
- Aplicación móvil del cliente.
- Aplicación móvil del repartidor.
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
