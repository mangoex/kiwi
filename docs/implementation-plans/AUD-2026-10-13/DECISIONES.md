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
El diseño concreto siguiente se registra antes de implementar efectos. Estas políticas no están
implementadas en PR74 y la referencia matemática no reemplaza integración transaccional.

Bases oficiales verificadas para continuar: [temario de inventarios de Soft Restaurant](https://apply.softrestaurant.com.mx/images/calendario/files/Temario_Inventarios__Soft_Restaurant.pdf),
que incluye mínimos/máximos y órdenes de compra; [IAS 2 de IFRS](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/), sobre costos de compra,
conversión y fórmulas de inventario; [Ley del IVA en SAT](https://wwwmat.sat.gob.mx/ordenamiento/37585/ley-del-impuesto-al-valor-agregado).
Los valores concretos de demanda y las reglas fiscales de la entidad deben contrastarse con el
contenido aplicable: estas referencias no acreditan una fórmula propietaria de Soft Restaurant.

## Diseño delegado concretado — PROC-POLICY-001

Autoridad detallada: PRD-FR-275/111, SDD §63, BDD-SC-685..688, TDD-TS-143/TC-388..391.
Riesgo R3 por decisiones de inventario/dinero; este incremento sólo especifica y ejecuta referencia
sin efectos productivos. D01 y los pendientes transaccionales del plan conservan su estado.

- D05_v1: 28 días completos de historial; promedio por día de semana con dos observaciones mínimas;
  revisión siete días (1..90), lead time explícito 0..90 y horizonte total 1..180. Seguridad inicial
  20% configurable 0..100%. Son elecciones propias para iniciar calibración, no valores publicados
  por Soft Restaurant ni garantía estadística de nivel de servicio. Días cerrados se excluyen;
  desconocidos/censurados requieren revisión. El corte común de stock/consumo/reservas evita
  comprar demanda ya consumida. ETA intradía pasa conservadoramente al bucket siguiente.
- D05_v1 usa cobertura por demanda con mínimo como piso; máximo limita stock proyectado a ETA.
  No copia el algoritmo puro mínimo→máximo de Oracle. Pendientes aprobados por residual/ETA,
  rendimiento congelado, múltiplos y MOQ sólo ante déficit; exceso/caducidad/capacidad incompatible
  requiere revisión. No se confirma automáticamente una recomendación ni se inventa historial.
- D06_v1: perfil fiscal explícito/versionado por razón social, impuesto y uso; fracción recuperable
  0..1, unknown exige revisión. Precio neto, impuesto no recuperable y flete atribuible forman costo;
  obligación documental y acreditamiento efectivo se conservan separados. Descuentos no se duplican,
  reparto canónico exacto conserva residuo y correcciones usan compensaciones atribuidas D03/D04.
  Tolerancia de negocio XML-documento inicial cero a precisión de moneda; validación del esquema
  fiscal es otro gate, no una tolerancia comercial. Perfil legacy y movimientos previos no se
  reinterpretan al activar v1. No se determina aquí la clasificación fiscal real de una empresa.

Fuentes primarias consultadas el 14-10-2026 y límites de atribución:

- [Soft Restaurant: control de merma e inventarios](https://softrestaurant.com/blog-restaurantero/reduce-la-merma-de-tu-restaurante-6-maneras-de-lograrlo-con-soft-restaurant):
  documenta mínimos/máximos, compras basadas en stock y recetas. No publica en esa fuente la fórmula
  de pronóstico, ventana, seguridad o tratamiento fiscal exacto que se pueda reproducir.
- [Oracle: Min-Max Planning](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/famml/min-max-planning.html)
  y [Reorder-point planning](https://docs.oracle.com/cd/A60725_05/html/comnls/us/inv/roplan.htm):
  referencias de posición con compras pendientes, lotes/MOQ y plazo/seguridad configurable.
  No justifican un porcentaje universal ni convierten el algoritmo propio en réplica de Oracle.
- [IFRS: módulo 13 Inventories](https://www.ifrs.org/content/dam/ifrs/supporting-implementation/smes/module-13.pdf)
  y [IAS 2](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/): referencias
  de costo de adquisición, descuentos, impuestos no recuperables y costos atribuibles.
  No se afirma que toda razón social mexicana reporte bajo IFRS.
- [SAT: artículo 5 de la Ley del IVA](https://wwwmat.sat.gob.mx/articulo/46936/articulo-5):
  el acreditamiento requiere condiciones y puede depender de pago/uso y proporción; por eso no se
  presume recuperabilidad universal. La clasificación de IEPS u otros tributos requiere evidencia
  propia. No se extrapolan tolerancias de CFDI 3.3 a CFDI 4.0 ni se afirma validación SAT implementada.

No fue posible abrir el manual completo de Soft Restaurant 11 en el enlace consultado; no se usó
para atribuir fórmulas. La evidencia y límites de este incremento se registran en execution.json;
I03/I04, X01/X02, A01/A02 y C02 continúan pendientes según sus dependencias.
