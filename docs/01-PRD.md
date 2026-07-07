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

## 4. Alcance funcional

### 4.1 Organización y configuración

- `PRD-FR-001`: El sistema debe administrar una organización con varias razones sociales.
- `PRD-FR-002`: Cada sucursal debe pertenecer a una sola razón social.
- `PRD-FR-003`: Cada sucursal debe tener un solo almacén formal.
- `PRD-FR-004`: Debe permitir ubicaciones internas dentro del almacén.
- `PRD-FR-005`: Debe administrar usuarios, roles y permisos por organización y sucursal.
- `PRD-FR-006`: Debe registrar dispositivos, cajas, KDS e impresoras.
- `PRD-FR-007`: Debe conservar auditoría de acciones administrativas y operativas.
- `PRD-FR-008`: Debe soportar configuración heredada desde corporativo con excepciones por sucursal.

### 4.2 Catálogo y menú

- `PRD-FR-010`: Debe administrar categorías, productos, variantes, modificadores, extras y combos.
- `PRD-FR-011`: Un producto debe poder dividir componentes entre varias estaciones.
- `PRD-FR-012`: El menú debe ser común entre canales, salvo disponibilidad por sucursal.
- `PRD-FR-013`: Debe manejar horarios de venta y disponibilidad.
- `PRD-FR-014`: Debe permitir marcar productos agotados por sucursal.
- `PRD-FR-015`: Debe versionar precios y conservar el precio aplicado en cada pedido.
- `PRD-FR-016`: Debe mantener equivalencias entre productos internos y productos de canales externos.

### 4.3 Pedidos

- `PRD-FR-020`: Debe crear pedidos de mostrador, para recoger y a domicilio.
- `PRD-FR-021`: Debe aceptar pedidos desde POS, WhatsApp, chatbot y marketplaces.
- `PRD-FR-022`: Todo pedido externo debe ser idempotente.
- `PRD-FR-023`: Debe conservar el payload original de pedidos externos.
- `PRD-FR-024`: Debe registrar cliente, dirección, zona, costo, promesa y canal.
- `PRD-FR-025`: Debe calcular totales, descuentos, impuestos informativos y formas de pago.
- `PRD-FR-026`: Debe impedir que una modificación de catálogo altere pedidos históricos.
- `PRD-FR-027`: Debe registrar eventos y transiciones de estado del pedido.
- `PRD-FR-028`: Debe permitir cancelaciones con reglas según estado productivo y de pago.
- `PRD-FR-029`: Debe soportar notas por pedido, producto y estación.
- `PRD-FR-030`: Debe generar un folio único sin depender de conectividad continua.

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
- `PRD-FR-051`: Debe registrar fondo inicial.
- `PRD-FR-052`: Debe registrar ingresos, retiros, gastos y depósitos.
- `PRD-FR-053`: Debe registrar efectivo, tarjeta y transferencia.
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
- `PRD-FR-068`: Debe soportar conteos y ajustes autorizados.
- `PRD-FR-069`: Debe soportar traspasos entre sucursales.
- `PRD-FR-070`: Debe ofrecer kardex y existencia teórica.

### 4.7 Recetas, subrecetas y producción por lotes

- `PRD-FR-080`: Debe soportar recetas multinivel.
- `PRD-FR-081`: Debe impedir ciclos.
- `PRD-FR-082`: Debe versionar recetas.
- `PRD-FR-083`: Debe registrar rendimiento esperado y real.
- `PRD-FR-084`: Debe registrar merma planeada y real.
- `PRD-FR-085`: Debe producir insumos elaborados por lote.
- `PRD-FR-086`: Debe conservar trazabilidad de lotes consumidos.
- `PRD-FR-087`: Debe calcular costo real del lote.
- `PRD-FR-088`: Debe calcular costo teórico por producto y porción.
- `PRD-FR-089`: Debe usar costo promedio ponderado para inventario.
- `PRD-FR-090`: Debe usar costo estándar para análisis y presupuesto.

### 4.8 Compras y cuentas por pagar

- `PRD-FR-100`: Debe registrar recepciones sin requerir orden de compra.
- `PRD-FR-101`: Debe registrar proveedor, presentación, cantidad, costo, lote y caducidad.
- `PRD-FR-102`: Debe importar XML de CFDI.
- `PRD-FR-103`: Debe impedir XML duplicados.
- `PRD-FR-104`: Debe mapear conceptos de proveedor a productos internos.
- `PRD-FR-105`: Debe generar cuenta por pagar para compras a crédito.
- `PRD-FR-106`: Debe registrar vencimientos, pagos, saldos y devoluciones.
- `PRD-FR-107`: Debe conservar XML y evidencia de importación.

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

## 5. Requisitos no funcionales

- `PRD-NFR-001 Disponibilidad`: Operación local durante falla de internet.
- `PRD-NFR-002 Consistencia`: No perder ni duplicar comandos.
- `PRD-NFR-003 Rendimiento`: Una sucursal debe soportar 100 pedidos por hora con margen mínimo de 5x.
- `PRD-NFR-004 Latencia local`: Acciones POS críticas menores a 300 ms en red local en condiciones normales.
- `PRD-NFR-005 Latencia nube`: Respuestas API interactivas menores a 800 ms p95, excluyendo proveedores externos.
- `PRD-NFR-006 Seguridad`: Autenticación, autorización por rol y sucursal, cifrado en tránsito y secretos fuera del repositorio.
- `PRD-NFR-007 Auditoría`: Registro inmutable de acciones sensibles.
- `PRD-NFR-008 Recuperación`: Respaldos automáticos y procedimientos de restauración probados.
- `PRD-NFR-009 Observabilidad`: Logs estructurados, métricas, trazas y alertas.
- `PRD-NFR-010 Mantenibilidad`: Arquitectura modular y adaptadores.
- `PRD-NFR-011 Portabilidad`: Despliegue por contenedores en Easypanel.
- `PRD-NFR-012 Precisión`: Dinero y cantidades con aritmética decimal exacta.
- `PRD-NFR-013 Evolución`: Preparación para multiempresa futura sin exponer autoservicio.
- `PRD-NFR-014 Privacidad`: Minimización y protección de datos personales.
- `PRD-NFR-015 Compatibilidad`: Navegadores modernos y Windows en gateways.

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
