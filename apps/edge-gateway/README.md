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
