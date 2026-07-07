# Edge Gateway

Gateway minimo de fase 1 para operar comandos locales antes de sincronizar con
la nube central.

Responsabilidades actuales:

- inicializar SQLite en modo WAL,
- persistir comandos locales en outbox,
- conservar `idempotency_key` unica,
- listar comandos pendientes,
- marcar comandos confirmados con checkpoint.

Responsabilidades futuras:

- API local,
- inbox de eventos remotos,
- WebSocket local,
- spool de impresion,
- health checks,
- reconciliacion completa con nube.

Validacion:

```bash
python -m pytest tests/edge_gateway
```
