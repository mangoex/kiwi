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

