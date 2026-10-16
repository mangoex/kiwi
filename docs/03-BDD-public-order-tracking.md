# BDD-FEAT-149 Seguimiento público del pedido móvil

@BDD-SC-715
Scenario: Una solicitud pendiente no se presenta como aceptada
  Given una intención persistida PENDING_REVIEW
  When el cliente consulta el seguimiento
  Then ve Esperando confirmación sin etapas completadas
  And la lectura no crea pedidos, pagos, reservas ni eventos

@BDD-SC-716
Scenario: El seguimiento refleja cocina y entrega reales
  Given una intención aceptada vinculada a un pedido de la misma organización y sucursal
  When cambia el estado operativo mediante los comandos canónicos
  Then la misma referencia refleja confirmado, preparación, listo, salida y entrega
  And recolección no muestra una etapa En camino
  And CLOSED conserva una entrega o devolución registrada sin inventarla

@BDD-SC-717
Scenario: La consulta pública limita información y abuso
  Given una referencia desconocida, un folio operativo o un vínculo de otra sucursal
  When se consulta el seguimiento
  Then no se revela un pedido ajeno ni datos personales o motivos internos
  And las respuestas no se almacenan en caché
  And el límite de consultas rechaza el exceso y falla cerrado si no puede verificarse

@BDD-SC-718
Scenario: Recuperación local y varios pedidos por sucursal
  Given dos referencias persistidas de una sucursal en este navegador
  When se recarga el menú o se cierra la confirmación
  Then se recuperan sus tarjetas sin reenviar pedidos
  And cambiar de sucursal no muestra ni actualiza referencias de la anterior
  And esconder una tarjeta sólo elimina su referencia local

@BDD-SC-719
Scenario: La red y las respuestas tardías no inventan progreso
  Given una consulta lenta o una desconexión
  When el menú cambia de sucursal, se oculta o desmonta
  Then se cancelan las consultas y se descartan respuestas anteriores
  And no se solapan consultas ni se avanza por tiempo transcurrido
  And el error conserva el último estado y su última actualización
  And los estados terminales dejan de consultarse
