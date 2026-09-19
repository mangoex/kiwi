# Edge Gateway

Gateway loopback PCO-008R para registrar movimientos de caja durante una
interrupcion temporal de la API central y reconciliarlos despues.

Responsabilidades actuales:

- inicializar SQLite en modo WAL,
- persistir exclusivamente `cash.movement.create.v1` en outbox,
- verificar grants Ed25519 con un llavero publico,
- exponer API local solo en loopback con CORS exacto,
- reconciliar con credencial tecnica `gateway.sync`,
- recuperar `SYNCING` tras reinicio y aplicar backoff acotado,
- exponer health live/ready y version sin filtrar secretos,
- escribir eventos de ciclo de vida y fallos redactados en `log_path`, con rotación acotada.

El runtime exige configuracion absoluta y separa config, SQLite, llavero publico,
credencial y log por ruta e identidad de archivo. Rechaza symlinks y hardlinks;
SQLite y log se revalidan en cada apertura. La credencial debe ser un archivo
regular dentro de `runtime_root`; en plataformas POSIX el root no puede conceder
permisos de grupo/otros y SQLite, credencial y log quedan privados (`0600`). Sólo
se permite un handler de log activo y shutdown libera los recursos aun si una
etapa intermedia falla. Si la composición no termina, también cierra el cliente
HTTP y el handler que ya hubiera creado. El origen CORS conserva la sintaxis
canónica, incluidos corchetes IPv6.

Ejecucion:

```bash
restaurantos-edge serve --config /ruta/absoluta/gateway.json --port 8765
```

La instalacion o provision real en sucursales permanece fuera de este paquete
local y requiere autorizacion de rollout separada.

Validacion:

```bash
python -m pytest tests/edge_gateway
```

## Incremento ORD-OFF-001 (en validación)

El modo de pedidos añade una dependencia interna `restaurant-os-api==0.0.0` para
ejecutar el mismo dominio Python que la nube. Ambos wheels se construyen desde
el mismo checkout y se instalan juntos; no se descarga un paquete homónimo de
un índice público para sustituir el dominio del proyecto.

La configuración existente conserva su comportamiento cash. El bloque opcional
`orders` contiene cuatro rutas absolutas, distintas y dentro de `runtime_root`:

```json
{
  "orders": {
    "database": "/ruta/runtime/orders.db",
    "catalog_database": "/ruta/runtime/order-catalog.db",
    "bundle": "/ruta/runtime/order-bundle.json",
    "signing_key": "/ruta/runtime/order-device-key.pem"
  }
}
```

Este fragmento complementa los campos obligatorios existentes; no constituye una
configuración completa. El bundle debe proceder de bootstrap central, estar
firmado por una clave del llavero y coincidir con organización/sucursal/dispositivo.
La clave privada Ed25519 debe corresponder a la clave registrada para la concesión
de autoridad del gateway. Nunca se entrega al navegador.

La instalación inicial conserva un marcador de hash dentro de la transacción de
hidratación. Un reinicio con el mismo bundle conserva pedidos/outbox. Otro hash
se rechaza para impedir sobrescrituras accidentales; un catálogo distinto se
instala mediante `renew-orders`, con todos los comandos confirmados y un registro
durable que permite retomar una publicación interrumpida. No se debe borrar
SQLite para resolver un rechazo.

Para una instalación inicial, con las rutas de `orders` ya configuradas y la
clave privada Ed25519 existente, el gateway solicita el lease y bundle firmados
por HTTPS con su credencial técnica:

```bash
restaurantos-edge prepare-orders --config /ruta/absoluta/gateway.json
```

El comando verifica firma y alcance antes de publicar el archivo de bundle de
forma atómica. Es deliberadamente sólo de primera instalación: no reemplaza un
bundle existente ni una base que ya contiene pedidos. No se debe borrar SQLite
para eludir ese límite.

La devolución de autoridad, renovación y recuperación usan acciones explícitas:

```bash
restaurantos-edge orders-status --config /ruta/absoluta/gateway.json
restaurantos-edge handoff-orders --config /ruta/absoluta/gateway.json
restaurantos-edge renew-orders --config /ruta/absoluta/gateway.json
restaurantos-edge recover-orders --config /ruta/absoluta/gateway.json
```

`handoff-orders` congela primero las nuevas escrituras, y conserva ese estado si
quedan pedidos o movimientos de caja pendientes de conciliación. Sólo entrega
autoridad cuando el manifiesto firmado del epoch está íntegramente confirmado.
`renew-orders` mantiene el mismo epoch y preserva pedidos, pagos, movimientos y
snapshots existentes; se debe reiniciar el runtime para que una instancia ya
abierta deje de conservar su bundle anterior. `recover-orders` sólo opera tras
una devolución central confirmada y activa el epoch siguiente. El cierre de caja se
realiza en central después de la devolución confirmada; sigue bloqueado incluso
si vence el lease. El cierre local de caja y los proveedores externos quedan
fuera de este incremento.

POS y KDS usan `/api/v1/local/order-api`, con `Authorization: Offline <grant>`.
El estado de cada comando se consulta en `/api/v1/local/orders/commands/{id}`.
Las escrituras locales nunca se desvían a nube ante un timeout. El worker reenvía
el mismo sobre firmado, con espera creciente persistida de 5 a 300 segundos,
y sólo confirma un recibo que coincide con command_id y contiene checkpoint.

Para acceso LAN, el listener exige certificado y clave TLS explícitos:

```bash
restaurantos-edge serve --config /ruta/absoluta/gateway.json --host 192.168.1.10 --port 8765 --tls-certificate /ruta/cert.pem --tls-key /ruta/key.pem
```

El navegador debe confiar en ese certificado y el origen POS/KDS debe coincidir
con `pos_origin`. La provisión de certificados, dispositivos, claves y cambios
productivos sigue siendo una operación de despliegue separada.
