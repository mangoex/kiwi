# CORP-PUR-001 — orden corporativa y recepción distribuida

**Riesgo:** R3. **Autoridad:** PRD-FR-274, SDD §60, BDD-FEAT-135, TDD-TS-140.
**Autorizado:** especificación, implementación y pruebas locales. Migración/deploy/configuración/datos
productivos conservan autorización separada.

## Secuencia

1. RED API para autorización organizacional, asignación exacta, no efectos antes de recibir,
   recepción parcial/completa, idempotencia y aislamiento.
2. Migración aditiva 0082, modelos y permisos corporativos.
3. Servicio Python transaccional con estado, snapshots, locks, ledger, costo e historial local.
4. Rutas versionadas y UI con dos acciones separadas.
5. Gates focales SQLite/frontend, migración, PostgreSQL de concurrencia cuando exista URL aislada,
   trazabilidad y auditoría Sol independiente.

## Afirmaciones R3 y refutación

| Afirmación | Evidencia buscada | Intento de refutación | Riesgo residual |
|---|---|---|---|
| Aprobar no mueve dinero ni existencias | conteos antes/después | fallo inyectado y búsqueda de inserts | código externo o trigger no cubierto |
| Una recepción no excede ni duplica saldo | lock, versión, unique/idempotencia | replay SQLite y carrera PostgreSQL obligatoria en CI | PostgreSQL local no disponible; CI aún no ejecutado |
| Cada efecto queda en su destino | branch+warehouse en ledger/costo/historial | IDs cruzados y otra razón social | datos legacy inconsistentes |
| La historia no se borra | estados y FK de movimientos | cancelar tras recepción | compensación futura aún no expuesta |
| El costo parcial concilia con la partida | costo acumulado y remanente final | tres recepciones de un costo no divisible | promedio unitario conserva redondeo de seis decimales |
| La conversión parcial no crea inventario | cantidad base acumulada y remanente final | dos recepciones de una conversión fraccionaria | precisión contractual de seis decimales |
| Una parcial mínima no deja saldo imposible | guardia antes de efectos y versión intacta | conversión 0.000001, parcial rechazada y total posterior | clientes deben mostrar el código estable |
| El historial local no filtra lineage ajeno | proyección global+branch autorizada | recepción en B consultada por actor local A | filas legacy sin sucursal siguen siendo globales |
| La consulta histórica no crece sin cota | lista resumida, limit/offset y detalle bajo demanda | límite inválido y página vacía | offset acotado no sustituye un cursor para volúmenes extremos |

## Operación y rollback

Las señales deben responder: órdenes detenidas por estado; rechazos por destino/cantidad; replays o
carreras; y conciliación asignado/recibido/pendiente. El log estructurado conserva sólo
operación/resultado/código estable/ID de orden; auditoría conserva estado, versión, destino,
cantidades e IDs de movimientos, sin notas, precios o claves. Rollback deshabilita comandos nuevos y conserva
lectura/historia; no hace downgrade con datos.

Riesgo residual operativo: los recibos idempotentes conservan el resultado completo necesario para
reproducir exactamente la respuesta original. Muchas recepciones parciales amplifican ese JSON;
antes de volumen sostenido se requiere política de retención o proyección compacta compatible con
replay, sin borrar auditoría ni historia transaccional.
