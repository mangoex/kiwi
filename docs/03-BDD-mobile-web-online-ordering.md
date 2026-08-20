# BDD: Pedidos en Línea y Autoservicio Web Móvil

## BDD-FEAT-090: Captura de Pedidos Públicos en Línea

@BDD-SC-353
Scenario: Captura de pedido público con precios autorizados de catálogo
  Given un cliente accede a la web de autoservicio para una sucursal activa
  When selecciona productos del catálogo y envía la orden con datos de entrega
  Then el pedido se crea con los precios vigentes de catálogo sin fallbacks artificiales

@BDD-SC-354
Scenario: Rechazo de producto sin precio activo configurado
  Given un producto del catálogo que carece de precio activo en la sucursal
  When se intenta registrar en un pedido en línea
  Then el backend rechaza la orden con error explícito de precio faltante

@BDD-SC-355
Scenario: Asociación a turno activo de caja o turno virtual
  Given una sucursal con turno de caja abierto o sin turno físico presencial
  When entra un pedido público en línea
  Then el pedido se asocia únicamente a un turno abierto o crea un turno online abierto
