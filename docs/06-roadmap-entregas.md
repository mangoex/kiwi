# Roadmap de entregas

## Principio

Construir vertical slices utilizables. No desarrollar todos los módulos horizontalmente antes de probar operación real.

## Fase 0 — Harness y plataforma

Entregables:

- monorepo,
- CI/CD,
- entornos,
- autenticación,
- organización,
- sucursales,
- dispositivos,
- logging,
- auditoría,
- migraciones,
- contratos,
- feature flags.

Gate:

- despliegue en staging,
- migración reproducible,
- observabilidad,
- smoke tests.

## Fase 1 — Venta local, cocina y caja

Vertical slice:

1. abrir caja,
2. crear pedido,
3. enviar a cocina,
4. imprimir,
5. completar,
6. cobrar,
7. cerrar caja.

Incluye:

- catálogo mínimo,
- POS,
- KDS,
- estaciones,
- impresión,
- pagos,
- corte,
- gateway local,
- operación offline básica.

Gate:

- piloto en una sucursal,
- prueba de dos horas offline,
- cero pedidos perdidos,
- reimpresión auditada.

## Fase 2 — Inventario, recetas y producción

Incluye:

- unidades,
- conversiones,
- recetas,
- subrecetas,
- lotes,
- caducidad,
- reserva,
- consumo,
- merma,
- producción por lote,
- costo promedio,
- costo estándar,
- kardex,
- conteos,
- traspasos.

Gate:

- costeo reproducible,
- conciliación de consumo,
- trazabilidad de lote.

## Fase 3 — Compras y cuentas por pagar

Incluye:

- proveedores,
- recepciones,
- XML,
- equivalencias,
- crédito,
- vencimientos,
- pagos,
- devoluciones.

Gate:

- XML duplicado bloqueado,
- recepción genera inventario,
- crédito genera saldo.

## Fase 4 — Domicilio y rutas

Incluye:

- clientes,
- direcciones,
- zonas,
- costos,
- tiempos,
- repartidores,
- optimización,
- despacho manual,
- liquidación.

Gate:

- rutas sugeridas,
- fallback manual,
- cobros conciliados.

## Fase 5 — Canales externos

Incluye:

- WhatsApp,
- chatbot,
- marketplaces,
- mapeos,
- webhooks,
- idempotencia,
- health,
- reintentos,
- DLQ.

Gate:

- pedidos externos sin recaptura,
- duplicados bloqueados,
- incidencias visibles.

## Fase 6 — Exportación fiscal

Incluye:

- modelo canónico,
- factura individual,
- global,
- adaptador configurable,
- lotes,
- conciliación,
- reexportación.

Gate:

- importación validada en la versión real de CONTPAQi.

## Fase 7 — Despliegue a siete sucursales

Incluye:

- instalación de gateways,
- matriz de impresoras,
- capacitación,
- migración de catálogos,
- monitoreo,
- soporte,
- rollback.

## Backlog posterior

- app del repartidor,
- tracking,
- pago en línea,
- promociones avanzadas,
- fidelización,
- pronóstico,
- multiempresa autoservicio,
- CFDI directo.
