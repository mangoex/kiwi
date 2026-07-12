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
- limitar comandos a `inventory.count` y al alcance de sucursal;
- al aprobar, calcular ajuste contra ledger vigente y no contra la fotografía;
- crear `COUNT_ADJUSTMENT` positivo o negativo con costo promedio vigente;
- no crear movimiento para diferencia vigente cero;
- actualizar cantidad del estado de costo sin cambiar costo promedio;
- repetir aprobación con la misma clave sin duplicar;
- rechazar otra clave después de aprobar;
- cerrar únicamente una sesión aprobada;
- cancelar únicamente una sesión en captura y sin movimientos;
- aplicar y revertir migración conservando el kardex previo.

## TDD-TC-039 Movimiento intermedio preservado

Given la fotografía contiene 10 kg y el conteo físico registra 8 kg
And después de abrir se confirma una salida legítima de 1 kg
When se aprueba el conteo
Then la diferencia de fotografía es -2 kg
And el ledger vigente antes del ajuste contiene 9 kg
And COUNT_ADJUSTMENT es -1 kg
And la existencia final es 8 kg.
