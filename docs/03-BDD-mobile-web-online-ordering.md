# BDD: Pedidos en Línea y Autoservicio Web Móvil

## BDD-FEAT-092: Captura de Pedidos Públicos en Línea

@BDD-SC-377
Scenario: Captura de pedido público con precios autorizados de catálogo
  Given un cliente accede a la web de autoservicio para una sucursal activa
  When selecciona productos del catálogo y envía la orden con datos de entrega
  Then el pedido se crea con los precios vigentes de catálogo sin fallbacks artificiales

@BDD-SC-378
Scenario: Rechazo de producto sin precio activo configurado
  Given un producto del catálogo que carece de precio activo en la sucursal
  When se intenta registrar en un pedido en línea
  Then el backend rechaza la orden con error explícito de precio faltante

@BDD-SC-379
Scenario: Asociación a turno activo de caja o turno virtual
  Given una sucursal con turno de caja abierto o sin turno físico presencial
  When entra un pedido público en línea
  Then el pedido se asocia únicamente a un turno abierto o crea un turno online abierto

@BDD-SC-382
Scenario: Resolución de sucursal más cercana por GPS en la web móvil
  Given múltiples sucursales con coordenadas registradas
  When un cliente móvil autoriza ubicación GPS
  Then la app resuelve y asigna automáticamente la sucursal más cercana con indicador de distancia

@BDD-SC-383
Scenario: Captura de pedidos fuera de horario con caja cerrada
  Given una sucursal seleccionada que no tiene turno de caja abierto en ese momento
  When un cliente confirma un pedido desde la app móvil
  Then el pedido se registra exitosamente con turno virtual de la sucursal y queda encolado para atención al abrir caja

@BDD-SC-384
Scenario: Modalidades de consumo en barra, para llevar y envío
  Given un cliente armando su carrito de compra en la app web móvil
  When selecciona modalidad comer en local (en barra), para llevar o a domicilio
  Then la orden se etiqueta con el tipo de servicio correspondiente sin requerir asignación de mesa
```
