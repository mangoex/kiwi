# TDD-TS-146 Historias del piloto POS/Admin

## TDD-TC-402 Diagnóstico y autoridad de sucursal

API/perfil distingue rollout desactivado de permiso ausente; navegador muestra
  selector sólo según alcance autorizado, bloqueo explicado y selección canónica. Cajero permanece
  fijo. Sin cambio de flags, permisos, contratos offline ni escrituras históricas.
## TDD-TC-403 Alcance corporativo del catálogo

Navegador en hub Inventario e Insumos verifica ausencia del selector operativo;
  almacenes/umbrales conservan sus controles. Probar escritorio y móvil.
## TDD-TC-404 Pedidos de ambos orígenes

`test_pilot_order_feed.py` reproduce mezcla de POS/web, límite, páginas completas,
  filtros, folio, empates y alcance. Verificar SQL en SQLite y PostgreSQL aislado; HTTP y navegador
  prueban enlace del pedido confirmado y rechazo explícito. Conservar regresiones de reapertura.
## TDD-TC-405 Selector superior de productos

Semántica y navegador verifican selector superior accesible, filtros, ancho del
  detalle, selección con teclado, confirmación/cancelación de descarte y altas sin guardar;
  seis pestañas, receta, combo y acciones conservadas. Typecheck y build antes de publicar.

Pruebas focales antes de implementación; CI completa aplicable una vez por candidato y auditoría
R3 independiente del diff. Evidencia y límites en `implementation-plans/PILOT-UX-2026-10-15.md`.
