# Decisiones autorizadas durante la implementación

Fecha: 2026-10-13. Fuente: respuestas explícitas de Miguel González.

- D02: sólo son elegibles para facturación pedidos con pago completo; los cancelados se excluyen. La autorización, emisor, moneda y conjunto íntegro siguen siendo validaciones obligatorias.
- D04: la obligación de cuenta por pagar nace al confirmar una recepción a crédito. La recepción física y la aplicación de pagos son procesos separados; el XML se concilia con la obligación, no la duplica.
- D03: si hubo consumo, la corrección requiere revisión autorizada y un ajuste compensatorio explícito. El recibo y los movimientos originales se conservan. No se autoriza editar saldos ni inventario histórico.

Estas decisiones sustituyen las alternativas abiertas correspondientes del plan; no equivalen a autorización de despliegue ni de migración productiva. Las especificaciones de cada módulo incorporarán el detalle verificable antes de sus efectos.
