# TDD - Liquidación de efectivo por repartidor

## TDD-TS-148 Selección y liquidación agrupada R3

Pruebas de dominio, API y persistencia:

- el listado de cuentas acepta `driver_id` sólo con `service_type=delivery`, conserva el cursor
  ligado al filtro y expone repartidor, intención de pago y elegibilidad sin PII adicional;
- el catálogo de liquidación incluye repartidores activos de la sucursal y repartidores inactivos o
  trasladados que todavía tienen cobros elegibles por asignación histórica en la sucursal autorizada;
- el comando exige `payments.confirm`, sucursal/contexto vigentes, caja con turno `OPEN`, una lista
  de 1 a 100 IDs UUID únicos y `Idempotency-Key` de 12 a 160 caracteres;
- todos los pedidos se bloquean en orden estable y se revalidan como `delivery`, asignados al mismo
  repartidor/sucursal, intención `cash`, no cancelados/cerrados y sin pago confirmado;
- la suma se calcula en Python desde `orders.total_cents`; no se acepta importe del navegador;
- una transacción crea cabecera, renglones, pagos, snapshots, eventos y auditoría, sin trabajos de
  impresión nuevos ni cambios de estado operativo;
- un fallo inyectado, pago competidor o turno cerrado revierte todo el lote;
- replay devuelve el snapshot persistido y una huella diferente bajo la misma clave falla;
- el downgrade de `0096_driver_cash_settlements` funciona vacío y se bloquea ante historia.
- en PostgreSQL, el downgrade bloquea las tres tablas antes de comprobar que estén vacías para
  impedir una inserción concurrente entre la guarda y el `DROP`.

El gate PostgreSQL usa exclusivamente `DRIVER_CASH_TEST_POSTGRES_URL`, exige host local y una base
aislada con prefijo `driver_cash_`; migra a `head` y enfrenta dos liquidaciones competidoras para
probar que sólo una confirma pagos y evidencia. CI debe ejecutarlo sin omisiones.

Pruebas frontend:

- `A domicilio` muestra Repartidor y otro servicio limpia repartidor/selección;
- la consulta envía `service_type=delivery&driver_id=...`;
- las casillas aparecen sólo para filas elegibles, con selección individual y total visible;
- el resumen muestra cantidad y total, exige caja configurada y confirma con una clave estable;
- éxito limpia selección y recarga cuentas; error conserva selección y clave para reintentar;
- el flujo agrupado se oculta cuando opera contra gateway local, que no implementa este comando.

## TDD-TC-410 Filtro y elegibilidad

Given pedidos heterogéneos de dos repartidores
When se filtra A domicilio por un repartidor
Then sólo sus pedidos se listan y únicamente los cash pendientes válidos son seleccionables.

## TDD-TC-411 Atomicidad, suma y turno de cobro

Given dos pedidos elegibles y un turno OPEN
When se confirma la liquidación
Then los dos pagos y su evidencia se confirman en el mismo turno por la suma exacta
And cualquier fallo intermedio deja cero efectos.

## TDD-TC-412 Idempotencia y concurrencia

Given dos solicitudes equivalentes o competidoras
When comparten clave o pedidos
Then una sola intención puede ganar y el replay equivalente reproduce evidencia sin duplicarla.

## TDD-TC-413 Alcance y errores cerrados

Given un actor sin permiso, otra sucursal, otro repartidor, método no cash o turno cerrado
When intenta liquidar
Then recibe un código estable sin efectos ni exposición transversal.

## TDD-TC-414 Interfaz de selección agrupada

Given el filtro A domicilio y un repartidor elegido
When el Cajero marca uno, varios o todos los renglones elegibles
Then ve cantidad y suma exacta antes de confirmar y los no elegibles permanecen bloqueados.

## TDD-TC-415 Deuda histórica tras traslado

Given un repartidor con pedidos cash pendientes en una sucursal
When su catálogo cambia a otra sucursal o pasa a inactivo
Then la sucursal de la asignación original todavía puede listar y liquidar esos pedidos
And la sucursal nueva no recibe ni puede liquidar esa deuda.
