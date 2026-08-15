# Instrucciones permanentes para Codex

## Misión

Construir y mantener RestaurantOS respetando el marco PRD + SDD + BDD + TDD. El código no es la fuente única de verdad. Las especificaciones y pruebas gobiernan el comportamiento.

## Autoridad y proporcionalidad

`AGENTS.md` es la fuente canónica del proceso de trabajo. `README.md` lo resume y
`.agents/skills/restaurantos_dev/SKILL.md` lo operacionaliza. Las reglas de negocio continúan bajo
la autoridad de PRD, SDD, BDD, TDD, ADR y matriz de trazabilidad.

- `GOV-DEV-001 Proporcionalidad`: el rigor se calibra por riesgo y alcance. El marco no obliga a
  producir cambios artificiales en todos los documentos.
- `GOV-DOC-001 Documentación activada`: se actualiza sólo el artefacto cuya autoridad cambió.
- `GOV-TEST-001 Verificación dirigida`: primero se ejecutan las pruebas afectadas; la suite completa
  aplicable se ejecuta una vez en CI. Una suite completa local sólo se justifica si CI no cubre el
  gate, está ausente/inconcluso, el R3 es transversal o existe solicitud explícita.
- `GOV-REL-001 Separación productiva`: una autorización de paquete puede cubrir edición, pruebas,
  commit, merge y push; despliegue, migración, configuración o datos productivos conservan una
  autorización explícita separada.

## Clasificación de riesgo

Clasificar el cambio antes de editar. Ante duda razonable, usar el nivel superior.

- `R0`: documentación, comentarios o evidencia sin cambio de contrato ni runtime.
- `R1`: refactor interno o UI de bajo impacto, sin cambiar permisos, persistencia ni estados.
- `R2`: comportamiento observable, API o regla de dominio sin afectar activos críticos.
- `R3`: dinero, pagos, caja, inventario, producción, permisos, datos sensibles, offline,
  concurrencia, migraciones, integraciones externas o cambios difíciles de revertir.

## Flujo de trabajo proporcional

1. Leer `README.md`, el estado Git y sólo los documentos relevantes al alcance.
2. Identificar contrato, invariantes y riesgo `R0..R3`; preservar trabajo local ajeno.
3. Determinar qué artefactos se activan mediante `GOV-DOC-001`.
4. Actualizar los artefactos aplicables en orden PRD → SDD/ADR → BDD → TDD → matriz.
5. Para comportamiento nuevo o corrección, crear o identificar una prueba dirigida que falle por la
   razón esperada; no fabricar una fase RED para cambios `R0` ni para refactors cubiertos.
6. Implementar el cambio más pequeño que satisfaga el contrato.
7. Ejecutar los gates activados por `GOV-TEST-001` y el nivel de riesgo.
8. Reportar evidencia exacta, gates omitidos y riesgo residual sin repetir información ya canónica.
9. Publicar y desplegar sólo dentro de la autorización aplicable según `GOV-REL-001`.

## Disparadores documentales

- PRD: sólo cuando cambia alcance, valor, actor, permiso o regla funcional/no funcional.
- SDD o ADR: sólo cuando cambia arquitectura, modelo de datos, estado, fórmula, integración o
  decisión técnica significativa.
- BDD: sólo cuando cambia un comportamiento observable o criterio de aceptación.
- TDD: sólo cuando cambia la estrategia/cobertura de verificación o se agrega una regresión.
- Matriz: sólo cuando cambian relaciones, IDs, cobertura o estado de evidencia.
- Plan o handoff: sólo si hay delegación, múltiples componentes o secuencia no obvia; debe ser breve
  y puede convivir en un único paquete de trabajo.
- Reporte de implementación: sólo para cierres, releases, canaries o evidencia que no esté registrada
  en CI. No debe copiar nuevamente la especificación.

No se crean ni editan artefactos para declarar “sin cambios”. Un cambio que no activa PRD, SDD, BDD,
TDD o matriz debe registrarlo en el reporte final, no introducir diffs ceremoniales.

## Verificación proporcional

- Siempre: pruebas directamente afectadas cuando existan y `git diff --check`.
- Backend modificado: lint/typecheck y pruebas Python focales del módulo o contrato afectado.
- Frontend modificado: typecheck y prueba semántica afectada; build cuando cambia empaquetado,
  rutas, dependencias o antes de release.
- PostgreSQL: sólo ante migración, persistencia, bloqueo, concurrencia, SQL o diferencia de dialecto.
- SQLite/gateway: sólo ante offline, sincronización, gateway o compatibilidad dual afectada.
- Contrato/E2E: cuando cruza componentes o representa un recorrido crítico real.
- QA visual: sólo si cambia UI; usar estados y breakpoints afectados, no una matriz universal.
- Suite completa local: sólo para R3 transversal que no pueda acotarse con pruebas focales, CI
  ausente/inconcluso, investigación de regresión o petición explícita. CI es autoritativo únicamente
  para las suites que realmente ejecuta; un gate no configurado debe correrse de forma focal.
- Canary productivo: sólo para R3, migraciones/datos, integraciones o cuando una prueba local no puede
  representar el riesgo. Debe ser acotado, observable y compensable.

Un handoff a Terra y una auditoría de Sol forman un único ciclo de cambio. La auditoría independiente
es obligatoria para R3 o cuando el usuario la solicite; para R0..R2 basta revisión focal y CI verde.

## Prohibiciones

- No inventar reglas de negocio.
- No cambiar estados, fórmulas, permisos o flujos sin actualizar especificaciones.
- No eliminar auditoría para simplificar.
- No editar saldos, existencias, pagos o movimientos históricos directamente.
- No introducir dependencias críticas sin una ADR.
- No acoplar el dominio a CONTPAQi, Google Maps, Rappi, Uber Eats, DiDi o WhatsApp.
- No implementar un proveedor externo sin adaptador.
- No usar MongoDB como fuente transaccional principal.
- No tratar el modo offline como simple caché.
- No permitir actualizaciones destructivas sin migración y reversibilidad.
- No hacer un “big bang” de todos los módulos.

## Principios de dominio

- PostgreSQL es la fuente central de verdad.
- SQLite es la fuente operativa temporal de la sucursal durante desconexión.
- Inventario se deriva de movimientos, no de campos editables sin trazabilidad.
- Pagos y movimientos de caja son inmutables; se corrigen con compensaciones.
- Recetas y subrecetas son versionadas.
- Pedidos usan eventos y transiciones explícitas.
- Cada sucursal pertenece a una razón social y tiene un almacén.
- Cada sucursal produce localmente.
- El consumo de inventario se reserva al aceptar el pedido y se confirma al preparar.
- Cancelaciones posteriores a producción generan merma o recuperación autorizada.
- Integraciones externas deben ser idempotentes.
- El sistema debe conservar payloads externos originales.
- Todo proceso sensible debe producir auditoría.

## Reglas de desarrollo

- Monorepo.
- TypeScript estricto en frontend.
- Python tipado en backend.
- APIs versionadas.
- Todo cambio de esquema se realiza mediante migraciones.
- Validación en frontera y en dominio.
- Estados modelados como máquinas de estado.
- Errores de negocio explícitos.
- Idempotency keys en comandos externos y sincronización.
- Outbox e inbox para sincronización.
- Tests deterministas.
- Datos de prueba reproducibles.
- Timestamps en UTC; presentación en zona local.
- Dinero en enteros de la unidad mínima o decimal exacto, nunca `float`.
- Cantidades y conversiones con `Decimal`.
- No mezclar lógica de dominio con controladores HTTP.

## Estructura objetivo del monorepo

```text
apps/
  admin-web/
  pos-web/
  kds-web/
  edge-gateway/
  api/
  worker/
packages/
  ui/
  contracts/
  domain-types/
  test-fixtures/
services/
  order-service/
  inventory-service/
  costing-service/
  production-service/
  cash-service/
  delivery-service/
  integration-service/
  export-service/
infra/
  easypanel/
  docker/
  migrations/
docs/
tests/
  contract/
  integration/
  e2e/
```

## Criterio de terminado

Una tarea está terminada cuando el comportamiento solicitado y sus invariantes aplicables están
satisfechos, la evidencia activada por riesgo está verde y se informan límites reales. El criterio no
es una lista universal de artefactos.

- Documentación y matriz: actualizadas únicamente cuando sus disparadores se activaron.
- Pruebas: automatizadas y dirigidas al cambio cuando hay runtime/comportamiento; integridad
  documental focal para R0; suite completa conforme a `GOV-TEST-001`.
- Manejo de errores: obligatorio para las fronteras afectadas.
- Migración, reversibilidad, auditoría, métricas, logs y runbook: obligatorios sólo cuando el cambio
  los requiere; en R3 deben quedar explícitos o justificarse como no aplicables.
- Evidencia: distinguir local, CI, Git, despliegue, migración y comportamiento productivo.
- Alcance: trabajo ajeno preservado y riesgos/gates omitidos declarados sin presentarlos como aprobados.
