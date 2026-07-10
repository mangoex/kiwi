# TDD - POS, caja y KDS inicial

## TDD-TS-017 Cash Minimal

Casos:

- abrir turno de caja,
- impedir doble turno abierto,
- consultar turno abierto,
- cerrar turno abierto,
- rechazar cierre cuando no existe turno abierto,
- rechazar apertura o cierre sin token,
- rechazar apertura o cierre sin permiso,
- rechazar apertura o cierre fuera del alcance de sucursal,
- abrir turno con sucursal explicita asignada a la cuenta POS,
- auditar apertura y cierre con el actor real.

## TDD-TS-018 Local Orders Minimal

Casos:

- crear pedido con turno abierto,
- crear pedido enviando sucursal y caja del POS,
- rechazar pedido sin turno abierto,
- rechazar pedido sin permiso `orders.create`,
- calcular total desde precio vigente,
- generar folio local,
- registrar evento `ORDER_ACCEPTED`,
- registrar auditoria con actor real.

## TDD-TS-020 Payments Minimal

Casos:

- confirmar pago con permiso `payments.confirm`,
- rechazar pago sin token,
- rechazar pago sin permiso,
- rechazar pago con monto distinto al `total_cents` del backend,
- cerrar pedido pagado,
- actualizar resumen de caja y dashboard Admin.

## TDD-TS-019 KDS Minimal

Casos:

- generar tarea KDS por producto,
- listar tareas KDS,
- mover tarea de `PENDING` a `IN_PROGRESS`,
- mover tarea de `IN_PROGRESS` a `COMPLETED`,
- rechazar transicion invalida.

## TDD-TC-012 Venta minima hasta KDS

Given existe turno abierto  
And existe catalogo minimo  
When se crea un pedido desde POS  
Then el pedido queda aceptado  
And existe una tarea KDS pendiente asociada.

## TDD-TC-030 Cajero autorizado de punta a punta

Given existe un Cajero activo asignado a Sucursal Piloto
And tiene permisos POS, caja, pedidos y pagos
When inicia sesion, abre caja, crea pedido y cobra usando el total del backend
Then el pedido queda cerrado
And el pago queda confirmado
And el dashboard Admin muestra la transaccion y la actividad de caja.

## TDD-TC-031 Cuenta POS asignada a sucursal

Given un administrador crea una cuenta Cajero con una sucursal asignada
When la cuenta inicia sesion
Then el perfil autenticado expone la sucursal asignada
And puede abrir caja solo en esa sucursal
And puede crear y cobrar una orden usando esa sucursal y caja
And el usuario puede actualizar su propio perfil sin permiso `admin.manage`
And el dashboard Admin conserva la actividad de caja y los movimientos por sucursal.
