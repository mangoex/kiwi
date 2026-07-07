# Contexto del producto

## Nombre de trabajo

RestaurantOS.

## Organización inicial

- Una cadena mexicana.
- Siete sucursales.
- Quince cajas.
- Varias razones sociales.
- Cada sucursal pertenece a una sola razón social.
- Cada sucursal tiene un solo almacén.
- Cada sucursal tiene cocina propia.
- No existe cocina central.

## Modelo operativo

- Restaurantes de comida rápida.
- Sin mesas.
- Pedidos en mostrador.
- Pedidos para recoger.
- Pedidos a domicilio.
- Repartidores propios.
- Pedidos desde POS, WhatsApp, chatbot, Rappi, Uber Eats y DiDi.
- Pago al recoger o recibir.
- Formas de pago iniciales: efectivo, tarjeta registrada manualmente y transferencia.
- Varias cajas simultáneas por sucursal.
- Operación offline de hasta dos horas.
- Varias cajas pueden estar desconectadas simultáneamente.
- Cada sucursal dispone de una computadora Windows que puede operar como gateway local.
- Impresoras térmicas de marcas y modelos variables.
- KDS e impresión automática.
- Estaciones: cocina, bebidas, empaque y entrega.

## Inventarios y costos

- Un almacén formal por sucursal.
- Ubicaciones internas opcionales.
- Costo promedio ponderado para inventarios.
- Costo estándar para presupuestos y análisis.
- Recetas y subrecetas multinivel.
- Insumos elaborados por lote, como aderezos.
- Lotes y caducidades.
- Rendimiento planeado y real.
- Mermas autorizadas.
- Traspasos entre sucursales.
- Reserva al aceptar el pedido.
- Consumo al confirmar producción.

## Compras

- No se requieren órdenes de compra en la primera versión.
- Recepciones directas.
- Compras de contado y crédito.
- Cuentas por pagar.
- Presentaciones de proveedor.
- Importación de XML de CFDI.
- Equivalencias entre conceptos de proveedor y productos internos.

## Entrega

- Zonas, cobertura, costos, mínimos y tiempos.
- Optimización simultánea de pedidos y repartidores.
- Un repartidor puede llevar varios pedidos.
- Inicialmente no habrá aplicación móvil ni geolocalización en tiempo real del repartidor.
- La operación de estados será registrada por el despachador.

## Facturación

- No se emitirán CFDI directamente.
- Se exportará información hacia una variante de CONTPAQi aún no definida.
- Se requieren facturas individuales y globales.
- El formato de exportación debe ser configurable mediante adaptadores.

## Infraestructura

- Aplicación y base central desplegadas en Easypanel.
- VPS en Hostinger.
- Servicios en contenedores.
- PostgreSQL como base central.
- SQLite local en cada sucursal.
- Redis para cache, locks, colas y coordinación.
- Gateway local en Windows.
- Respaldo de conectividad 4G/5G recomendado para mantener canales externos.

## Supuestos

- El sistema se construirá inicialmente para una sola organización.
- El modelo incluirá `organization_id` para permitir evolución futura.
- Las integraciones existentes con marketplaces deberán auditarse antes de codificar adaptadores.
- La variante exacta de CONTPAQi se determinará durante implementación.
- La compatibilidad de impresoras se resolverá con una matriz certificada.
