# TDD - POS, caja y KDS inicial

## TDD-TS-017 Cash Minimal

Casos:

- abrir turno de caja,
- impedir doble turno abierto,
- consultar turno abierto,
- cerrar turno abierto,
- rechazar cierre cuando no existe turno abierto.

## TDD-TS-018 Local Orders Minimal

Casos:

- crear pedido con turno abierto,
- rechazar pedido sin turno abierto,
- calcular total desde precio vigente,
- generar folio local,
- registrar evento `ORDER_ACCEPTED`.

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

