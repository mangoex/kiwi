# Auditoria RBAC POS Caja Dashboard

Fecha: 2026-07-10

## Alcance

Auditoria del flujo en que usuarios administrativos y usuarios de caja operan POS:

- autenticacion y autorizacion por actor real,
- apertura, consulta y cierre de caja,
- creacion de pedidos POS,
- confirmacion de pagos,
- actualizacion del dashboard administrativo,
- trazabilidad PRD, SDD, BDD y TDD.

## Estado Actual Verificado

El sistema ya no debe operar acciones sensibles con un administrador implicito. Las acciones sensibles resuelven actor desde `Authorization: Bearer <token>` o `X-Actor-User-Id` para pruebas/herramientas internas. Si no hay actor, la API responde `actor_required`.

Permisos operativos definidos:

- `cash.shift.read`
- `cash.shift.open`
- `cash.shift.close`
- `orders.read`
- `orders.create`
- `payments.read`
- `payments.confirm`
- `dashboard.read`
- `pos.operate`

Asignacion esperada:

- `Administrador corporativo`: acceso administrativo y operativo completo.
- `Cajero`: operar POS, leer/abrir/cerrar caja, leer/crear pedidos y confirmar pagos solo dentro de su sucursal asignada.

## Hallazgos Cerrados

| Hallazgo | Riesgo | Resolucion |
| --- | --- | --- |
| Endpoints POS/caja aceptaban operaciones sin actor requerido. | Movimientos sin responsable real y control de acceso debil. | Actor obligatorio en caja, pedidos, pagos y dashboard. |
| UI dependia del nombre de rol `Caja`. | Ruptura al migrar a `Cajero` o a permisos granulares. | Admin/POS ahora validan permisos como `pos.operate`, `admin.manage` y `dashboard.read`. |
| Cajero podia carecer de permisos semilla para operar caja/POS. | Usuario de caja bloqueado o comportamiento inconsistente entre datos semilla y runtime. | Migracion `0013_pos_cash_rbac_permissions` agrega permisos y asignaciones. |
| Scope de sucursal no estaba centralizado para POS/caja/dashboard. | Un usuario de caja podria intentar operar otra sucursal. | `authorize_branch_scope` valida permiso y sucursal efectiva. |
| POS calculaba localmente un total con IVA y lo enviaba a pagos. | Mismatch entre POS y backend, pago rechazado o cobro incorrecto. | POS paga con `orderData.total_cents` devuelto por backend. |
| Dashboard administrativo podia ser consultado sin permiso especifico. | Exposicion de indicadores operativos. | Dashboard requiere `dashboard.read`; cajero sin ese permiso es rechazado. |
| Movimientos POS no estaban probados contra actualizacion del dashboard. | Regresion silenciosa entre venta POS y admin. | Test de punta a punta verifica pago y dashboard admin actualizado. |

## Evidencia De Pruebas

Comandos verificados:

- `python3 -m pytest apps/api/tests`: 32 passed.
- `RESTAURANTOS_DATABASE_URL=sqlite+pysqlite:////tmp/... python3 -m alembic -c alembic.ini upgrade head`: aplica hasta `0013_pos_cash_rbac_permissions`.
- `pnpm -r typecheck`: passed.
- `pnpm -r build`: Admin, POS y KDS compilan para produccion.
- `git diff --check`: sin errores.

Pruebas clave:

- `test_sensitive_pos_endpoints_require_authenticated_actor`
- `test_cashier_can_operate_pos_and_admin_dashboard_reflects_payment`
- `test_cashier_cannot_operate_outside_assigned_branch`
- `test_payment_cut_and_print_flow`
- `test_rbac_rejects_inventory_adjustment_without_permission`

## Ambiguedades Y Riesgos Remanentes

Estos puntos quedan fuera del arreglo minimo porque requieren decisiones de producto, arquitectura o pruebas E2E mas amplias:

1. KDS y print jobs aun tienen endpoints publicos en la vertical actual. Si KDS sera usado por roles reales, necesita permisos propios (`kds.read`, `kds.transition`, `print.jobs.manage`).
2. `platform_shell.py` mantiene llamadas legacy a endpoints operativos sin token. Si esa shell sigue siendo producto activo, debe migrarse o retirarse explicitamente.
3. La autorizacion de catalogo/inventario aun combina endpoints publicos de lectura con endpoints protegidos de escritura. Esto puede ser correcto para POS, pero debe quedar formalizado por vista.
4. El modo offline todavia no prueba RBAC local ni reconciliacion de actor en outbox/inbox. Es critico antes de operar sucursales desconectadas.
5. El cierre de caja usa `counted_cash_cents: 0` desde la UI de settings cuando se cierra turno. Debe convertirse en flujo de corte con captura real y confirmacion.
6. Auditoria existe para operaciones sensibles, pero faltan metricas/logs operativos estructurados por denegacion, apertura, cierre, pago y dashboard.

## Plan Para Resolver La Siguiente Capa

1. Formalizar permisos KDS, print jobs y reportes en PRD/SDD/BDD/TDD.
2. Migrar o retirar `platform_shell.py`; no debe quedar una UI legacy capaz de llamar endpoints sensibles sin token.
3. Implementar corte de caja completo en POS: resumen previo, captura de efectivo contado, diferencias, confirmacion y auditoria.
4. Agregar E2E con navegador para login admin, redireccion a POS, apertura de caja, venta, pago y dashboard admin.
5. Incorporar RBAC offline: actor local firmado, cola outbox con actor, revalidacion server-side y manejo de denegaciones de sincronizacion.
6. Agregar observabilidad: logs estructurados, metricas por permiso denegado, caja abierta/cerrada, pagos confirmados y ventas reflejadas en dashboard.
7. Extender matriz de trazabilidad a evidencias de comandos y resultados, no solo suites nominales.

## Criterio De Terminado De Esta Auditoria

Esta auditoria queda cerrada para el alcance RBAC POS/caja/dashboard cuando:

- los documentos PRD/SDD/BDD/TDD reflejan los permisos y escenarios,
- la matriz enlaza requisitos, escenarios y pruebas,
- la migracion de permisos aplica desde cero,
- backend rechaza actor ausente y scope incorrecto,
- Cajero opera su caja y no consulta dashboard sin permiso,
- Admin ve en dashboard la venta confirmada desde POS,
- POS usa el total calculado por backend,
- suites automatizadas y build pasan.
