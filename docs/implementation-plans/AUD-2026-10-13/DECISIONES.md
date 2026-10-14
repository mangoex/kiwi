# Decisiones autorizadas durante la implementación

Fecha: 2026-10-13. Fuente: respuestas explícitas de Miguel González.

- D02: sólo son elegibles para facturación pedidos con pago completo; los cancelados se excluyen. La autorización, emisor, moneda y conjunto íntegro siguen siendo validaciones obligatorias.
- D04: la obligación de cuenta por pagar nace al confirmar una recepción a crédito. La recepción física y la aplicación de pagos son procesos separados; el XML se concilia con la obligación, no la duplica.
- D03: si hubo consumo, la corrección requiere revisión autorizada y un ajuste compensatorio explícito. El recibo y los movimientos originales se conservan. No se autoriza editar saldos ni inventario histórico.

Estas decisiones sustituyen las alternativas abiertas correspondientes del plan; no equivalen a autorización de despliegue ni de migración productiva. Las especificaciones de cada módulo incorporarán el detalle verificable antes de sus efectos.

## Delegación de diseño recibida el 14 de octubre de 2026

Fuente: respuestas explícitas de Miguel González durante la publicación del PR74.

- D05: «Estos datos tomalos considerando las mejores prácticas y como lo hace Softrestaurant.»
  Se autoriza definir ventana/horizonte/seguridad y el tratamiento de días sin operación,
  compras pendientes, empaques y mínimos a partir de fuentes verificables. La definición debe
  separar lo documentado por Soft Restaurant de los parámetros elegidos para RestaurantOS.
- D06: «Tómalo de las mejores prácticas y como lo hace Softrestaurant.» Se autoriza definir
  costeo/impuestos/flete/descuentos/tolerancias/correcciones con ese criterio. La recuperabilidad
  fiscal depende de la razón social y de los requisitos aplicables; no se inventará una tasa ni
  se tratará todo impuesto como recuperable por defecto.

Ya no se espera otra respuesta del usuario para iniciar ese diseño. La delegación no fija por sí
sola parámetros numéricos, clasificación tributaria de cada razón social ni tolerancias de XML.
El siguiente incremento debe documentar las decisiones concretas y su evidencia en los artefactos
activados antes de implementar efectos. Estas políticas aún no están implementadas en PR74.

Bases oficiales verificadas para continuar: [temario de inventarios de Soft Restaurant](https://apply.softrestaurant.com.mx/images/calendario/files/Temario_Inventarios__Soft_Restaurant.pdf),
que incluye mínimos/máximos y órdenes de compra; [IAS 2 de IFRS](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/), sobre costos de compra,
conversión y fórmulas de inventario; [Ley del IVA en SAT](https://wwwmat.sat.gob.mx/ordenamiento/37585/ley-del-impuesto-al-valor-agregado).
Los valores concretos de demanda y las reglas fiscales de la entidad deben contrastarse con el
contenido aplicable: estas referencias no acreditan una fórmula propietaria de Soft Restaurant.
