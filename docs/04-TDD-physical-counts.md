# TDD - Conteo físico y conciliación

## TDD-TS-046 Sesiones de conteo

Casos:

- rechazar segunda sesión activa en la misma sucursal;
- abrir sesión con todos los artículos activos o un subconjunto explícito;
- congelar cantidad teórica, costo promedio y valor sin crear movimientos;
- ocultar fotografía y diferencias mientras el estado sea `counting`;
- capturar Decimal no negativo en unidad base con actor y fecha;
- permitir corrección de captura antes de enviar;
- rechazar envío mientras exista una línea sin captura;
- calcular diferencia física menos fotografía al enviar;
- impedir edición después de `submitted`;
- limitar captura a `inventory.count.capture`, revisión a `inventory.count.review` y aprobación,
  cierre o cancelación a `inventory.count.approve`, conservando compatibilidad heredada acotada;
- impedir que la proyección de captura revele teórico, costos, valores o diferencias antes o después
  del envío cuando el actor carece de permiso de revisión;
- abrir por grupos, congelar los grupos seleccionados y resolver sólo sus artículos activos;
- capturar atómicamente un lote de líneas;
- capturar una línea mediante unidad base y presentaciones, usando `Decimal` en backend;
- conservar cantidad original, rendimiento y conversión congelados por entrada;
- rechazar presentaciones ajenas al artículo o inactivas y cantidades negativas;
- al aprobar, calcular ajuste contra ledger vigente y no contra la fotografía;
- crear `COUNT_ADJUSTMENT` positivo o negativo con costo promedio vigente;
- no crear movimiento para diferencia vigente cero;
- actualizar cantidad del estado de costo sin cambiar costo promedio;
- repetir aprobación con la misma clave sin duplicar;
- rechazar otra clave después de aprobar;
- rechazar aperturas activas concurrentes mediante restricción de base de datos;
- serializar captura contra envío y dos aprobaciones concurrentes mediante lock y compare-and-set;
- bloquear movimientos/estados de costo durante aprobación PostgreSQL frente a otros escritores;
- adquirir el conjunto completo de advisory locks por artículo, sin duplicados y en orden estable,
  antes de que cualquier writer lea o escriba inventario para recalcular saldo;
- cerrar con compare-and-set e idempotencia de estado, sin duplicar auditoría;
- autorizar lectura por captura o revisión sin registrar rechazos falsos durante la alternativa válida;
- cerrar únicamente una sesión aprobada;
- cancelar únicamente una sesión en captura y sin movimientos;
- aplicar y revertir migración conservando el kardex previo.

## TDD-TS-131 Conteo dual Administrador y POS

Casos:

- Cajero y Cajero jefe reciben captura sin autoridad de revisión ni aprobación;
- Supervisor, Administrador y Dueño reciben captura, revisión y aprobación;
- un rol personalizado que ya tenía `inventory.count` conserva compatibilidad;
- la ruta POS de captura no requiere `branch.admin.access`;
- POS muestra avance, búsqueda, renglones pendientes y captura por presentación;
- Admin configura grupos, consulta desglose, diferencias y totales valorizados;
- el recorrido Cajero captura/envía y Administrador revisa/aprueba/cierra conserva auditoría;
- caída de red no se presenta como guardado exitoso;
- migración SQLite y PostgreSQL crea y revierte el esquema cuando no existe historia; con conteos
  capturados, el downgrade se bloquea y conserva la evidencia hasta una migración compensatoria.

## TDD-TC-039 Movimiento intermedio preservado

Given la fotografía contiene 10 kg y el conteo físico registra 8 kg
And después de abrir se confirma una salida legítima de 1 kg
When se aprueba el conteo
Then la diferencia de fotografía es -2 kg
And el ledger vigente antes del ajuste contiene 9 kg
And COUNT_ADJUSTMENT es -1 kg
And la existencia final es 8 kg.

## TDD-TC-302 Captura por presentación y separación de autoridad

Given un Cajero sólo tiene inventory.count.capture
And una presentación rinde 450 gramos
When captura dos presentaciones y 125 gramos y envía el conteo
Then el total autoritativo es 1025 gramos
And la respuesta del Cajero no contiene teórico, costos ni diferencias
When un Administrador consulta la misma sesión
Then recibe la conciliación completa y puede aprobarla idempotentemente.
