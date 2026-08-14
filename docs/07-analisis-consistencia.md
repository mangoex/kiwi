# Analisis de consistencia PRD + SDD + BDD + TDD

## Objetivo

Este documento registra la primera revision de consistencia del harness RestaurantOS antes de escribir logica de negocio completa.

## Hallazgos principales

| ID | Tipo | Severidad | Hallazgo | Impacto | Accion propuesta |
|---|---|---:|---|---|---|
| CONS-001 | Omision | Alta | La matriz de trazabilidad solo cubria una parte de los requisitos funcionales y no incluia requisitos no funcionales. | Dificulta saber que historias y pruebas gobiernan cada cambio. | Expandir `docs/05-matriz-trazabilidad.md` para cubrir requisitos, BDD y TDD por modulo. |
| CONS-002 | Omision | Alta | Fase 0 no tenia criterios tecnicos suficientemente verificables. | El bootstrap podria avanzar sin gates reproducibles. | Definir entregables, smoke tests, health checks, CI y pruebas de arquitectura. |
| CONS-003 | Riesgo | Alta | Offline de hasta dos horas esta definido como objetivo, pero falta contrato minimo nube-gateway. | Riesgo de duplicidad, perdida de pedidos o reconciliacion ambigua. | Crear contrato versionado para comandos, eventos, idempotencia y checkpoints. |
| CONS-004 | Riesgo | Alta | Impresion Windows tiene requisitos fuertes, pero falta decision de empaquetado e instalacion del agente. | Riesgo operacional en sucursales por variabilidad de impresoras. | Agregar ADR de agente Windows, spool persistente y matriz certificada. |
| CONS-005 | Omision | Media | No hay modelo inicial de errores de negocio. | Los controladores podrian filtrar errores tecnicos o mezclar reglas. | Definir taxonomia de errores en SDD y contratos compartidos. |
| CONS-006 | Omision | Media | Faltan versiones exactas de lenguaje, frameworks y herramientas. | CI/CD y onboarding quedan poco reproducibles. | Fijar stack base en `docs/09-fase-0-y-vertical-slice.md`. |
| CONS-007 | Riesgo | Media | Geocodificacion y optimizacion de rutas estan en PRD, pero proveedor esta abierto. | Riesgo de acoplamiento temprano o dependencia costosa. | Mantener puerto `RouteOptimizationProvider` y no implementar proveedor en fase 0. |
| CONS-008 | Riesgo | Media | CONTPAQi se declara configurable, pero la variante real esta abierta. | Riesgo de diseno de exportacion demasiado especifico. | Mantener modelo canonico y ADR de adaptadores, postergar layout real. |
| CONS-009 | Omision | Media | Seguridad menciona RBAC, pero no define aun autenticacion corporativa. | Riesgo de decisiones prematuras de identidad. | Mantener `OPEN-005` y agregar ADR propuesta para auth inicial local con adaptador. |
| CONS-010 | Contradiccion leve | Baja | La estructura objetivo menciona servicios separados, pero SDD favorece monolito modular inicial. | Puede impulsar un big bang de microservicios. | Interpretar `services/` como limites logicos y pruebas de dominio, no despliegues independientes en fase 0. |
| CONS-011 | Contradiccion resuelta | Alta | PRD/SDD vigente concede apertura/cierre de caja a Cajero; la jerarquía nueva ubica manejar caja en Cajero jefe. | Un cambio de semilla puede quitar o conceder autoridad de caja sin transición. | `OPEN-011/012` resueltos 2026-08-10: perfiles nuevos por permisos/alcance; compatibilidad legacy explícita y sin revocación silenciosa en PCO-001. |
| CONS-012 | Contradiccion resuelta | Crítica | El Administrador corporativo vigente recibe todo; la nueva jerarquía reserva acceso total y todas las sucursales a Dueño. | Riesgo de escalación o pérdida masiva de acceso en producción. | ADR-023 aprobada: mapeo individual, reversible y auditable; no conversión automática ni asignación de Dueño en migración. |
| CONS-013 | Contradiccion resuelta | Crítica | `PRD-FR-204` conserva de sólo lectura pedidos pagados o con producción iniciada, mientras el video menciona reabrir cuenta. | Podría alterar pagos, producción, inventario y corte históricos. | `OPEN-013A/B` resueltos: Cajero jefe+ solicita y Dueño decide en PCO-005A sin mutar historia; `APPROVED -> APPLIED` sigue cerrado hasta que PCO-005B gobierne cada compensación. |
| CONS-014 | Contradicción con solución aprobada | Alta | UI actual cierra turno con `counted_cash_cents=0` y backend combina cierre con corte. | Genera diferencias ficticias y borra separación operativa/financiera. | PCO-004/ADR-026 especifica cierre idempotente `OPERATIVELY_CLOSED`, snapshot y actor sin contado ni corte; alias legacy rechaza el contado. Sigue abierto hasta evidencia GREEN y productiva. |
| CONS-015 | Omisión en cierre incremental resuelta por PCO-003 | Alta | `PRD-FR-052` existe; PCO-002 implementó el catálogo efectivo y PCO-003 fue autorizado el 2026-08-11 para el comando POS genérico de depósito/retiro. | Sin el ledger desplegado, caja todavía no refleja movimientos manuales. | PCO-003 exige RED de fórmula/idempotencia/compensación, preserva historia legacy y mantiene offline fuera de alcance. |
| CONS-016 | Ambigüedad resuelta | Media | “Reporta merma” puede significar registrar o sólo consulta analítica y “corte por usuario” no define periodo/caja/tolerancia. | Permisos y contabilidad potencialmente demasiado amplios. | `OPEN-014` resuelto: Cajero jefe gestiona merma, Supervisor consulta/reporta; Líder+ finaliza corte, Dueño compensa reapertura y tolerancia inicial cero. |
| CONS-017 | Contradicción resuelta | Alta | `orders.amend` está concedido a Cajero, `dashboard.read` mezcla dashboard con reporte y `catalog.manage` puede mutar recetas corporativas; la jerarquía nueva los separa. | Una migración puede retirar acceso operativo o ampliar receta/reportes sin decisión. | Compatibilidad explícita por fase: `orders.amend` legacy permanece hasta mapeo; reportes/recetas son permisos separados; `OPEN-016` resuelto para alcance de recetas. |
| CONS-018 | Ambigüedad resuelta | Alta | Gastos puede sumar compra y retiro cash enlazados, y no está definida zona/día operativo ni el alcance de recetas de Supervisor. | Reportes/cortes no reproducibles o modificación de receta global. | `OPEN-016/017` resueltos: receta por sucursal/versionada; gasto por documento canónico, impuestos separados y día local 00:00–23:59. |
| CONS-019 | Riesgo residual controlado | Alta | Un administrador legacy puede crear roles organizacionales y conceder permisos explícitos, pero no existe un flujo PCO-001 para crear `organization_all_permissions`. | Sin guard, un permiso de alcance podría confundirse con Dueño. | PCO-001 separa permiso ordinario de grant dinámico, protege estructuralmente el rol con grant y prueba la denegación; la política general de administración de roles queda fuera del incremento. |
| CONS-020 | Contradicción resuelta con operación controlada | Crítica | La semilla deja cero Dueños pero la autoridad Dueño exige un actor Dueño para asignación normal. | Sin bootstrap explícito el sistema no puede iniciar; uno automático podría escalar o crear cuentas. | Bootstrap interno, no HTTP ni migración, con dos correos confirmados como input, organización/actor/procedencia explícitos, validación completa antes de escribir, replay idempotente y auditoría. PostgreSQL aislado quedó validado; la ejecución productiva sigue pendiente y requiere autorización separada. |
| CONS-021 | Riesgo residual controlado | Alta | La tabla de mapping existía como reserva sin workflow, snapshot ni idempotencia. | Podría perder especialidades o volver imposible revertir una transición. | PCO-001 añade dry-run sin PII, estados PENDING/MAPPED/REVERSED, aplicación aditiva, snapshot y reversión auditada; no ejecuta migración de usuarios reales ni convierte Administrador legacy automáticamente. |
| CONS-022 | Riesgo con solución aprobada | Crítica | Un cobro diferido puede confirmar contra `orders.cash_shift_id` después de que ese turno cierre, alterando el resumen congelado. | El cierre deja de ser inmutable o el pago queda atribuido a una caja/turno incorrectos. | PCO-004/ADR-026 exige `register_id`, resuelve el turno OPEN de cobro y serializa pago y cierre bajo el guard compartido; la carrera pierde sin escritura. |
| CONS-023 | Riesgo con solución aprobada | Alta | Familia, impuesto, descuento y cortesía no tienen snapshot histórico completo en el modelo vigente. | El monitor podría consultar catálogo vivo o inventar importes. | PCO-004/ADR-026 agrega snapshots por línea/pago, marca backfill/incompletos y devuelve monto conocido más conteo desconocido; Python no infiere IVA ni cortesía. |

## Requisitos afectados

- `PRD-FR-005`, `PRD-FR-006`, `PRD-FR-007`: bootstrap de identidad, dispositivos y auditoria.
- `PRD-FR-020`, `PRD-FR-030`, `PRD-FR-180` a `PRD-FR-188`: primer contrato POS-gateway-nube.
- `PRD-FR-046` a `PRD-FR-048`: impresion como capacidad local auditable.
- `PRD-FR-140` a `PRD-FR-147`: integraciones por adaptadores.
- `PRD-NFR-001` a `PRD-NFR-015`: gates tecnicos de fase 0.

## Escenarios BDD impactados

- `BDD-SC-001`: crear pedido offline.
- `BDD-SC-002`: sincronizar pedido creado offline.
- `BDD-SC-003`: idempotencia de pedido externo.
- `BDD-SC-018`: reintento de impresion fallida.
- `BDD-SC-021`: permisos por sucursal.

## Suites TDD impactadas

- `TDD-TS-003`: maquina de estado de pedido.
- `TDD-TS-004`: sync engine.
- `TDD-TS-009`: integraciones.
- `TDD-TS-011`: impresion.
- `TDD-TS-012`: seguridad.

## Criterio de salida de fase 0

Fase 0 se considera lista cuando el repo pueda demostrar:

1. CI ejecuta lint, pruebas documentales y health checks.
2. API central expone `/health` versionado sin tocar reglas de negocio.
3. Gateway expone contrato minimo de salud y cola local.
4. Contratos JSON Schema existen para health, comandos y eventos base.
5. Docker Compose levanta PostgreSQL, Redis, API y worker.
6. Easypanel tiene plantilla inicial sin secretos embebidos.
7. La matriz de trazabilidad enlaza requisito, diseno, BDD y TDD.
