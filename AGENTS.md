# Instrucciones permanentes para Codex

## Misión

Construir y mantener RestaurantOS respetando el marco PRD + SDD + BDD + TDD. El código no es la fuente única de verdad. Las especificaciones y pruebas gobiernan el comportamiento.

## Orden obligatorio de trabajo

Ante cualquier historia, corrección o cambio:

1. Leer `README.md`.
2. Leer los documentos relevantes en `docs/`.
3. Identificar los requisitos afectados.
4. Identificar escenarios BDD existentes.
5. Identificar pruebas TDD existentes.
6. Proponer cambios documentales antes de modificar código.
7. Actualizar la matriz de trazabilidad.
8. Implementar el cambio más pequeño que satisfaga los criterios.
9. Ejecutar pruebas unitarias, de integración, contrato y end-to-end afectadas.
10. Reportar qué requisito, escenario y prueba quedaron modificados.

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
- Migraciones obligatorias.
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

Una tarea no está terminada si falta cualquiera de estos elementos:

- Requisito actualizado.
- Escenario BDD actualizado.
- Prueba automatizada.
- Migración, si aplica.
- Auditoría, si aplica.
- Métricas y logs.
- Manejo de errores.
- Documentación de operación.
- Matriz de trazabilidad actualizada.
