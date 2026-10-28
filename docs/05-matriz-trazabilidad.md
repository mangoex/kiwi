# Matriz de trazabilidad

Estado permitido: `Propuesto`, `Disenado`, `Scaffold`, `Probado`, `Implementado`.

CORTE-CIEGO-001: PRD-FR-289..300 están `Disenado`, con CC-D01..12 aprobadas y
formalización documental. F1-04 aporta implementación/pruebas parciales de autoridad;
F1-06 añade cobertura parcial de lectores/reportes, sin cierre de fase:
[casos](../apps/api/tests/test_corte_ciego_f106.py),
[agentes](../apps/api/tests/test_corte_ciego_f106_agents.py),
[listados operativos](../apps/api/tests/test_corte_ciego_f106_operational.py),
[detalle por contexto](../apps/api/tests/test_corte_ciego_f106_orders.py),
[concurrencia del detalle](../apps/api/tests/test_corte_ciego_f106_order_postgres.py),
[descargas](../apps/api/tests/test_corte_ciego_f106_fiscal.py) y
[PostgreSQL](../apps/api/tests/test_corte_ciego_f106_postgres.py), vinculados a
TC-450/451/461/462/463 y PRD-FR-289/290/299/300 según TDD y [plan §12](implementation-plans/CORTE-CIEGO-001-FASE-1.md#12-f1-06--avance-de-lectores-y-reportes);
ningún requisito integral de corte ciego se acredita todavía. Proyecciones de caja F1-05 verificadas localmente: [plan F1 §11](implementation-plans/CORTE-CIEGO-001-FASE-1.md#11-f1-05--proyecciones-de-turnos-y-cortes). Evidencia de autoridad: [plan F1 §10](implementation-plans/CORTE-CIEGO-001-FASE-1.md#10-f1-04--capacidades-delegación-y-alcance). Los estados y
resultados históricos de PCO-006/PRD-FR-219 y contratos relacionados se conservan como
baseline, sin acreditar el nuevo contrato. Las precisiones en BDD-SC-286/328/330/331
y TDD-TC-114/118 requieren nueva evidencia. Autoridad/lecturas financieras de filas
anteriores, incluidos PRD-FR-005/218/220/271, se subordinan a SDD §71 al activar la
política; una capacidad operativa o nombre de rol no sustituye la concesión financiera.

Evidencia AUD-CORE-001: CI #343 sobre f2a0afa y PR #67, según plan §12.1.
Los estados baseline de requisitos más amplios se conservan; este cierre acredita las correcciones
y regresiones del paquete, sin certificar despliegue o datos productivos.

## Requisitos funcionales

| Requisito | Diseno | Escenario BDD | Suite TDD | Estado |
|---|---|---|---|---|
| PRD-FR-289 | CORTE-CIEGO-001 CC-D01; SDD §71.1/ADR-048; proyecciones operativa/financiera y delegación revocable; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-767, BDD-SC-768 | TDD-TS-157, TDD-TC-450, TDD-TC-465; [RED F1-03](../apps/api/tests/test_corte_ciego_f1_red.py); [autoridad F1-04 parcial](../apps/api/tests/test_corte_ciego_f104.py); [proyecciones/acuses F1-05 parcial](../apps/api/tests/test_corte_ciego_f105.py) | Disenado |
| PRD-FR-290 | CORTE-CIEGO-001 CC-D02; SDD §71.2; roles y revisión individual de grants efectivos; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-769, BDD-SC-770 | TDD-TS-157, TDD-TC-451, TDD-TC-465; [RED F1-03](../apps/api/tests/test_corte_ciego_f1_red.py); [autoridad F1-04 parcial](../apps/api/tests/test_corte_ciego_f104.py); [proyecciones/acuses F1-05 parcial](../apps/api/tests/test_corte_ciego_f105.py) | Disenado |
| PRD-FR-291 | CORTE-CIEGO-001 CC-D03; SDD §71.3; captura propia/sustituta y finalización central autorizada; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-771, BDD-SC-772, BDD-SC-793, BDD-SC-794 | TDD-TS-158, TDD-TC-452, TDD-TC-463, TDD-TC-465; [RED F1-03](../apps/api/tests/test_corte_ciego_f1_red.py); [autoridad F1-04 parcial](../apps/api/tests/test_corte_ciego_f104.py); [proyecciones/acuses F1-05 parcial](../apps/api/tests/test_corte_ciego_f105.py) | Disenado |
| PRD-FR-292 | CORTE-CIEGO-001 CC-D04; SDD §71.4; denominaciones MXN, borrador, confirmación única y custodia | BDD-SC-773, BDD-SC-774, BDD-SC-793, BDD-SC-794 | TDD-TS-158, TDD-TC-453, TDD-TC-454, TDD-TC-463, TDD-TC-465 | Disenado |
| PRD-FR-293 | CORTE-CIEGO-001 CC-D05; SDD §71.5; conciliación por medio y pendientes externos explícitos | BDD-SC-775, BDD-SC-776, BDD-SC-777 | TDD-TS-158, TDD-TC-455, TDD-TC-465 | Disenado |
| PRD-FR-294 | CORTE-CIEGO-001 CC-D06; SDD §71.6; tolerancia cero y evidencia de aviso; entrega/reintentos en fase 3 sin canal elegido | BDD-SC-778, BDD-SC-779 | TDD-TS-158, TDD-TC-456, TDD-TC-465 | Disenado |
| PRD-FR-295 | CORTE-CIEGO-001 CC-D07; SDD §71.7; reporte operativo y compensación exclusiva Dueño sin segundo aprobador | BDD-SC-780, BDD-SC-781 | TDD-TS-158, TDD-TC-457, TDD-TC-465; [proyecciones/acuses F1-05 parcial](../apps/api/tests/test_corte_ciego_f105.py) | Disenado |
| PRD-FR-296 | CORTE-CIEGO-001 CC-D08; SDD §71.8; autorización exacta sin evadir guardas de pago/producción; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-782, BDD-SC-783 | TDD-TS-159, TDD-TC-458, TDD-TC-465 | Disenado |
| PRD-FR-297 | CORTE-CIEGO-001 CC-D09; SDD §71.9; recepción sin costos y ajuste administrativo separado; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-784, BDD-SC-785 | TDD-TS-159, TDD-TC-459, TDD-TC-465 | Disenado |
| PRD-FR-298 | CORTE-CIEGO-001 CC-D10; SDD §71.10; SQLite durable, acuse provisional y completitud central; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-786, BDD-SC-787, BDD-SC-788, BDD-SC-793, BDD-SC-794 | TDD-TS-160, TDD-TC-460, TDD-TC-463, TDD-TC-465 | Disenado |
| PRD-FR-299 | CORTE-CIEGO-001 CC-D11; SDD §71.11; transición entre turnos y reversión sin pérdida de historia/confidencialidad; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-789, BDD-SC-790 | TDD-TS-160, TDD-TC-461, TDD-TC-464, TDD-TC-465; [concurrencia de DTO F1-05 parcial](../apps/api/tests/test_corte_ciego_f105_postgres.py) | Disenado |
| PRD-FR-300 | CORTE-CIEGO-001 CC-D12; SDD §71.12; tickets/ranking restringidos y consulta individual acotada; [F1-02](02-SDD-corte-ciego-fase-1.md), [accesos F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md) | BDD-SC-791, BDD-SC-792 | TDD-TS-157, TDD-TC-462, TDD-TC-465; [RED F1-03](../apps/api/tests/test_corte_ciego_f1_red.py); [autoridad F1-04 parcial](../apps/api/tests/test_corte_ciego_f104.py) | Disenado |
| PRD-FR-283 | DELIVERY-FEE-001 SDD §70.1 / ADR-047; catálogo separado, revisiones y política scoped; alta/edición en diálogo, encabezado corporativo y reglas por sucursal con vista previa (TC438/439 browser); evidencia local y límites en plan §7; CI/release pendientes | BDD-SC-745, BDD-SC-746, BDD-SC-747 | TDD-TS-154, TDD-TC-438, TDD-TC-439, TDD-TS-156, TDD-TC-445 | Probado |
| PRD-FR-284 | DELIVERY-FEE-001 SDD §70.2/70.3/70.4; selección única, retiro persistente, permisos y comanda; panel compacto con envío desplegable y QA de área de productos/confirmación (TC440 browser); núcleo online local; límites/pendientes en plan §7 | BDD-SC-748, BDD-SC-749, BDD-SC-750, BDD-SC-751 | TDD-TS-155, TDD-TC-440, TDD-TC-441, TDD-TS-156, TDD-TC-445 | Probado |
| PRD-FR-285 | DELIVERY-FEE-001 SDD §70.2; base tras descuentos sin envío/propina, umbral inclusivo y precedencia del retiro; comanda exenta muestra Gratis sin precio de lista ni desglose cero (TC442 browser); núcleo online local; límites/pendientes en plan §7 | BDD-SC-752, BDD-SC-753, BDD-SC-754 | TDD-TS-155, TDD-TC-442 | Probado |
| PRD-FR-286 | DELIVERY-FEE-001 SDD §70.1/70.3/70.4; precio exacto, snapshots, transacción, replay y carrera con pago; evidencia SQLite/PG local; CI/release pendientes | BDD-SC-755, BDD-SC-756, BDD-SC-757, BDD-SC-758 | TDD-TS-155, TDD-TC-443, TDD-TC-444 | Probado |
| PRD-FR-287 | DELIVERY-FEE-001 SDD §70.4; ticket, cocina, reportes, recaudación y concepto fiscal sin doble conteo; conserva OPEN-006/007; núcleo online local; límites/pendientes en plan §7 | BDD-SC-759, BDD-SC-760, BDD-SC-761, BDD-SC-762 | TDD-TS-156, TDD-TC-446, TDD-TC-447 | Scaffold |
| PRD-FR-288 | DELIVERY-FEE-001 SDD §70.5/70.6; canales por procedencia, SQLite/gateway, rollout/drenado y migración aditiva; sin activación | BDD-SC-763, BDD-SC-764, BDD-SC-765, BDD-SC-766 | TDD-TS-156, TDD-TC-448, TDD-TC-449 | Scaffold |
| PRD-FR-279 | INV-VIEW-001 SDD §68.1..68.3 y §68.5; API/SQLite/PostgreSQL, snapshot, pares cero, aislamiento y navegador local; auditoría independiente cerrada; gates CI configurados, ejecución CI y release pendientes; evidencia en plan INV-VIEW-2026-10-19 | BDD-SC-723, BDD-SC-724, BDD-SC-725, BDD-SC-726, BDD-SC-727, BDD-SC-728, BDD-SC-729 | TDD-TS-151, TDD-TC-422, TDD-TC-423, TDD-TC-424, TDD-TC-425, TDD-TS-152, TDD-TC-426, TDD-TC-429 | Probado |
| PRD-FR-280 | INV-VIEW-001 SDD §68.4; edición por destino y versión, precisión legacy, UX y errores probados localmente; conserva PRD-FR-240/NFR-012; CI y release pendientes | BDD-SC-730, BDD-SC-731, BDD-SC-732, BDD-SC-733, BDD-SC-734 | TDD-TS-152, TDD-TC-427, TDD-TC-428, TDD-TC-429 | Probado |
| PRD-FR-275 | SDD §61, §61.1 y §63; I01/I02 y captura asistida documental/multimodal hacia borrador de compra (`PUR-AI-CAPTURE-001`) verificados localmente; D05_v1 diseño y referencia aritmética, integración I03/I04 pendiente; no certifica demanda real, calendario UTC ni pendientes transaccionales | BDD-SC-677, BDD-SC-678, BDD-SC-685, BDD-SC-686, BDD-SC-804 | TDD-TS-141, TDD-TC-380, TDD-TC-381, TDD-TC-474, TDD-TS-143, TDD-TC-388, TDD-TC-389 | Scaffold |
| PRD-FR-276 | FISCAL-001 SDD §62; ADR-043; autoridad, lectura corporativa/histórica con alcance exacto, descargas y configuración versionada por emisor con evidencia local parcial F02/D02; preparación durable cifrada F03 con vínculos/reservas/outbox. Dinero fiscal exacto, dispatch/recuperación externa F03 y estados F04/CI del incremento pendientes; autorización productiva separada | BDD-SC-679, BDD-SC-680, BDD-SC-681, BDD-SC-682, BDD-SC-683, BDD-SC-684 | TDD-TS-142, TDD-TC-382, TDD-TC-383, TDD-TC-384, TDD-TC-385, TDD-TC-386, TDD-TC-387 | Scaffold |
| PRD-FR-277 | WHATSAPP-ASISTTO-001 SDD §65; ADR-044; adaptador simétrico Asistto Tech Provider, agente conversacional con Master Prompt, reconocimiento de cliente y pedidos directos al POS sin exigir turno de caja | BDD-SC-695, BDD-SC-696, BDD-SC-697, BDD-SC-698, BDD-SC-699 | TDD-TS-145, TDD-TC-398, TDD-TC-399, TDD-TC-400, TDD-TC-401 | Scaffold |
| PRD-FR-278 | SDD ADR-015; visibilidad pública separada de disponibilidad, selector autorizado por sucursal, resumen y comando atómico para sucursales activas actuales, default visible y captura pública fail-closed; evidencia local SQLite/API/frontend: 4 pruebas de alcance/atomicidad, 26 regresiones públicas, 23 de arquitectura, semántica, typecheck/build, Ruff y mypy verdes; PostgreSQL concurrente, QA visual, CI y release pendientes | BDD-SC-706, BDD-SC-707 | TDD-TS-147, TDD-TC-408, TDD-TC-409 | Probado |
| PRD-FR-274 | CORP-PUR-001 SDD §60 y ADR-042; asignaciones exactas congeladas, catálogo por destino, rechazo histórico, recepción legible y journal durable. Evidencia local SQLite/PostgreSQL y navegador sintético, auditoría independiente de asignaciones/UI cerrada; CI y compensaciones posteriores pendientes | BDD-SC-669, BDD-SC-670, BDD-SC-671, BDD-SC-672, BDD-SC-673, BDD-SC-674, BDD-SC-675, BDD-SC-676 | TDD-TS-140, TDD-TC-374, TDD-TC-375, TDD-TC-376, TDD-TC-377, TDD-TC-378, TDD-TC-379 | Probado |
| PRD-FR-266 | BRANCH-SCOPE-001 SDD §58.1/58.5; ADR-040; configuración corporativa heredable, scope explícito y excepciones por dominio; UI parcial con selector único/default global, confirmación, señal y bloqueo local fail-closed | BDD-SC-630, BDD-SC-631, BDD-SC-632, BDD-SC-633, BDD-SC-644, BDD-SC-701 | TDD-TS-138, TDD-TC-348, TDD-TC-349, TDD-TC-350, TDD-TC-355, TDD-TS-146, TDD-TC-403 | Scaffold |
| PRD-FR-267 | BRANCH-SCOPE-001 SDD §58.2/58.3; ADR-040; workspace durable, emisión/rotación sin secreto persistido, grant y versión; selección sobrevive GET; apertura caja, seis rutas humanas KDS/impresión/sync y ocho escrituras de compras/gastos cercadas, reemisión y Admin documental sin POS, seis nuevas carreras PostgreSQL probadas y devices independientes; cliente con fencing de respuesta y journal scoped; Copiloto Ejecutivo cancela consultas sustituidas y desmonta por sucursal (TC352); gate CI exige ejecución PG de autoridad/workspace; registro offline compartido y bloqueadores de grants vigentes probados localmente; versión firmada opt-in, fence de reconciliación y acuse mínimo con evidencia focal API/gateway/PG en TC354; preparación controlada de adopción con recibo/NULL histórico, reloj independiente y CLI, evidencia local TC355; registro central0090 previo al envío de pedido/pago/movimiento con recuperación mínima, contexto bloqueado y ocho carreras/downgrades PG locales en TC354; extensión0091 de apertura/ambos cierres/compensación con namespace compartido, atomicidad, recuperación mínima, regresiones de evidencia/métricas/retención y carreras PG locales en TC354; ejecución productiva, otros comandos/outbox offline y cobertura restante de rutas/reasignación/rollback/CI pendientes | BDD-SC-634, BDD-SC-635, BDD-SC-636, BDD-SC-637, BDD-SC-638, BDD-SC-639, BDD-SC-645, BDD-SC-700 | TDD-TS-138, TDD-TC-351, TDD-TC-352, TDD-TC-354, TDD-TC-355, TDD-TC-356, TDD-TS-146, TDD-TC-402 | Scaffold |
| PRD-FR-268 | BRANCH-SCOPE-001 SDD §58.4/58.5; ADR-040; reasignación transaccional, idempotente y auditable sin reescribir historia | BDD-SC-640, BDD-SC-641, BDD-SC-642, BDD-SC-643 | TDD-TS-138, TDD-TC-353, TDD-TC-354, TDD-TC-355, TDD-TC-356 | Disenado |
| PRD-FR-269 | GROKBOT-001 SDD §59.1/59.7/59.8; ADR-041; conector default-off separado de identidades, secretos no recuperables, salud, callback SSRF-safe y bitácora redactada | BDD-SC-647, BDD-SC-656, BDD-SC-660, BDD-SC-663 | TDD-TS-139, TDD-TC-358, TDD-TC-364, TDD-TC-365 | Scaffold |
| PRD-FR-270 | GROKBOT-001 SDD §59.1/59.2/59.3/59.9; ADR-041; un orquestador visible, cuatro identidades de servicio, capacidades y branches por intersección, rotación, revocación y drenado | BDD-SC-648, BDD-SC-649, BDD-SC-650, BDD-SC-655, BDD-SC-659, BDD-SC-662 | TDD-TS-139, TDD-TC-359, TDD-TC-360, TDD-TC-363, TDD-TC-365, TDD-TC-368 | Scaffold |
| PRD-FR-271 | GROKBOT-001 SDD §59.3/59.4/59.7; proyecciones paginadas, allowlist y minimización por sucursal; stock con mínimos/máximos anulables por almacén en unidad base (TC358/360); catálogo corporativo sin branch fija; ventas confirmadas agregadas desde snapshots inmutables; cortes finalizados con compensación efectiva reservados al Administrador por capacidad explícita; movimientos de inventario acotados desde el ledger; precios vigentes e historial confirmado reservados a Compras | BDD-SC-650, BDD-SC-661, BDD-SC-664, BDD-SC-666, BDD-SC-667, BDD-SC-668 | TDD-TS-139, TDD-TC-358, TDD-TC-360, TDD-TC-361, TDD-TC-369, TDD-TC-371, TDD-TC-372, TDD-TC-373 | Scaffold |
| PRD-FR-272 | GROKBOT-001 SDD §59.4/59.5; propuestas y compra DRAFT con revisión humana y servicios canónicos | BDD-SC-651, BDD-SC-652, BDD-SC-653, BDD-SC-657 | TDD-TS-139, TDD-TC-361, TDD-TC-362, TDD-TC-363 | Scaffold |
| PRD-FR-273 | GROKBOT-001 SDD §59.6/59.7/59.8/59.9; command log idempotente, outbox/callback firmado, recuperación autoritativa, drenado y evidencia cifrada | BDD-SC-654, BDD-SC-655, BDD-SC-656, BDD-SC-657, BDD-SC-658, BDD-SC-659, BDD-SC-660 | TDD-TS-139, TDD-TC-363, TDD-TC-364, TDD-TC-366, TDD-TC-367 | Scaffold |
| PRD-FR-263 | EXP-001 SDD §56.1/56.2; catálogo propio y permisos; evidencia local en plan EXP-001; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-599, BDD-SC-603, BDD-SC-625, BDD-SC-626 | TDD-TS-134, TDD-TC-316, TDD-TC-323, TDD-TS-136, TDD-TC-342, TDD-TC-343 | Implementado |
| PRD-FR-264 | EXP-001 SDD §56.2/56.3/56.5; documento sin inventario, retiro condicional y compensación; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-600, BDD-SC-601, BDD-SC-602, BDD-SC-603, BDD-SC-604, BDD-SC-605, BDD-SC-625, BDD-SC-626 | TDD-TS-134, TDD-TC-317, TDD-TC-318, TDD-TC-319, TDD-TC-320, TDD-TC-321, TDD-TC-323, TDD-TS-136, TDD-TC-342, TDD-TC-343 | Implementado |
| PRD-FR-265 | EXP-001 SDD §56.4; proyección documental por todos los medios y conciliación cash separada; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-605, BDD-SC-606, BDD-SC-626 | TDD-TS-134, TDD-TC-321, TDD-TC-322, TDD-TC-323, TDD-TS-136, TDD-TC-343, TDD-TC-344 | Implementado |
| PRD-FR-237 | SDD §46.1: orden Agentes/POS; Admin moderno claro minimalista, flujo familiar | BDD-SC-489, BDD-SC-490, BDD-SC-491, BDD-SC-563 | TDD-TS-109, TDD-TC-242, TDD-TS-125, TDD-TC-291 | Probado |
| PRD-FR-238 | SDD §46.2: prioridades administrativas independientes | BDD-SC-492 | TDD-TS-110, TDD-TC-243, TDD-TS-111, TDD-TC-245 | Probado |
| PRD-FR-239 | SDD §46.2: comando masivo atómico versionado | BDD-SC-493, BDD-SC-494 | TDD-TS-110, TDD-TC-244, TDD-TS-111, TDD-TC-245 | Probado |
| PRD-FR-240 | SDD §46.2: umbrales y proyección del ledger | BDD-SC-495, BDD-SC-496 | TDD-TS-110, TDD-TC-243, TDD-TS-111, TDD-TC-245 | Probado |
| PRD-FR-241 | SDD §46.2: usos directos de recetas efectivas | BDD-SC-497 | TDD-TS-110, TDD-TC-244, TDD-TS-111, TDD-TC-245 | Probado |
| PRD-FR-242 | SDD §46.4: composiciones fijas y snapshots operativos; online probado, BDD-SC-501 diferido ; SDD §47 / ADR035 | BDD-SC-004, BDD-SC-498, BDD-SC-499, BDD-SC-500, BDD-SC-501 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-112, TDD-TC-246, TDD-TC-247, TDD-TC-248 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Scaffold |
| PRD-FR-243 | SDD §48 / ADR-036 aceptada: comando estricto, atómico, idempotente y versionado de producto, precio y subgrupo | BDD-SC-517, BDD-SC-518, BDD-SC-519, BDD-SC-520, BDD-SC-703 | TDD-TS-115, TDD-TC-258, TDD-TC-259, TDD-TC-260, TDD-TC-261, TDD-TS-146, TDD-TC-405 | Implementado |
| PRD-FR-244 | SDD §48: borrador veraz, secciones accesibles, selección con detalle visible, alta contextual de grupos/subgrupos, receta efectiva y comprobación POS sin efectos | BDD-SC-515, BDD-SC-520, BDD-SC-521, BDD-SC-522, BDD-SC-523, BDD-SC-524, BDD-SC-525, BDD-SC-526 | TDD-TS-116, TDD-TC-262, TDD-TC-263, TDD-TC-264, TDD-TC-265, TDD-TC-266 | Implementado |
| PRD-FR-001 | Organization module | BDD-SC-025, BDD-SC-046, BDD-SC-056, BDD-SC-058 | TDD-TS-014, TDD-TS-026, TDD-TS-033, TDD-TS-035 | Scaffold |
| PRD-FR-002 | Organization module | BDD-SC-025, BDD-SC-046, BDD-SC-047, BDD-SC-058, BDD-SC-453 | TDD-TS-014, TDD-TS-026, TDD-TS-027, TDD-TS-035, TDD-TC-214 | Scaffold |
| PRD-FR-003 | Organization module | BDD-SC-025, BDD-SC-047, BDD-SC-453 | TDD-TS-014, TDD-TS-027, TDD-TC-214 | Scaffold |
| PRD-FR-004 | Inventory module | Pendiente | TDD-TS-002 | Disenado |
| PRD-FR-005 | RBAC scoped authorization; SDD §23.1 recuperación Admin | BDD-SC-021, BDD-SC-025, BDD-SC-043, BDD-SC-044, BDD-SC-045, BDD-SC-057, BDD-SC-058, BDD-SC-059, BDD-SC-060, BDD-SC-061, BDD-SC-063, BDD-SC-064, BDD-SC-065, BDD-SC-066, BDD-SC-067, BDD-SC-068, BDD-SC-118, BDD-SC-119, BDD-SC-123, BDD-SC-125, BDD-SC-126, BDD-SC-127, BDD-SC-132, BDD-SC-133, BDD-SC-136, BDD-SC-137, BDD-SC-141, BDD-SC-143, BDD-SC-193, BDD-SC-385, BDD-SC-453, BDD-SC-560, BDD-SC-561, BDD-SC-562 | TDD-TS-012, TDD-TS-014, TDD-TS-025, TDD-TS-034, TDD-TS-035, TDD-TS-036, TDD-TS-037, TDD-TS-038, TDD-TS-050, TDD-TS-051, TDD-TS-052, TDD-TS-060, TDD-TC-031, TDD-TC-043, TDD-TC-044, TDD-TC-045, TDD-TC-055, TDD-TC-214, TDD-TS-125, TDD-TC-290 | Scaffold |
| PRD-FR-006 | Devices, registers, stations, printers | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-007 | Audit events append-only | BDD-SC-007, BDD-SC-012, BDD-SC-021, BDD-SC-025, BDD-SC-043, BDD-SC-044, BDD-SC-045, BDD-SC-057, BDD-SC-061, BDD-SC-062, BDD-SC-063, BDD-SC-066, BDD-SC-122, BDD-SC-193 | TDD-TS-012, TDD-TS-014, TDD-TS-017, TDD-TS-025, TDD-TS-034, TDD-TS-037, TDD-TS-050, TDD-TC-031, TDD-TC-043, TDD-TC-054 | Scaffold |
| PRD-FR-008 | Configuration inheritance | BDD-SC-118, BDD-SC-122, BDD-SC-129 | TDD-TS-012, TDD-TS-050, TDD-TS-051 | Scaffold |
| PRD-FR-009 | Business unit hierarchy | BDD-SC-124, BDD-SC-193 | TDD-TS-038, TDD-TS-050, TDD-TC-054 | Scaffold |
| PRD-FR-010 | Catalog module; SDD §46.4 para composición fija de combos; SDD §48 para editor confiable y alta contextual de grupos/subgrupos | BDD-SC-026, BDD-SC-027, BDD-SC-048, BDD-SC-056, BDD-SC-058, BDD-SC-488, BDD-SC-498, BDD-SC-499, BDD-SC-500, BDD-SC-501, BDD-SC-515, BDD-SC-517, BDD-SC-518, BDD-SC-520, BDD-SC-521, BDD-SC-522, BDD-SC-523, BDD-SC-524, BDD-SC-525, BDD-SC-526, BDD-SC-703 | TDD-TS-015, TDD-TS-016, TDD-TS-027, TDD-TS-033, TDD-TS-035, TDD-TS-108, TDD-TC-241, TDD-TS-112, TDD-TC-246, TDD-TC-247, TDD-TC-248, TDD-TS-115, TDD-TC-258, TDD-TC-260, TDD-TC-261, TDD-TS-116, TDD-TC-262, TDD-TC-263, TDD-TC-264, TDD-TC-265, TDD-TC-266, TDD-TS-146, TDD-TC-405 | Scaffold |
| PRD-FR-011 | Station-aware products; SDD §48 usa códigos canónicos con etiquetas operativas | BDD-SC-004, BDD-SC-048, BDD-SC-517, BDD-SC-520 | TDD-TS-006, TDD-TS-027, TDD-TS-115, TDD-TC-258, TDD-TC-261 | Scaffold |
| PRD-FR-012 | Shared menu by channel | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-013 | Sale schedules | Pendiente | TDD-TS-009 | Propuesto |
| PRD-FR-014 | Branch stockouts | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-015 | Price versioning; SDD §48 evita versiones duplicadas y coordina rollback | BDD-SC-026, BDD-SC-027, BDD-SC-048, BDD-SC-517, BDD-SC-519 | TDD-TS-015, TDD-TS-016, TDD-TS-027, TDD-TS-115, TDD-TC-258, TDD-TC-259, TDD-TC-260 | Scaffold |
| PRD-FR-016 | External product mappings | BDD-SC-013 | TDD-TS-009 | Disenado |
| PRD-FR-017 | Canonical catalog consistency | BDD-SC-110, BDD-SC-111, BDD-SC-114, BDD-SC-122, BDD-SC-129 | TDD-TS-047, TDD-TS-050, TDD-TS-051, TDD-TC-040, TDD-TC-043, TDD-TC-044 | Scaffold |
| PRD-FR-018 | SDD §25.1 Administración única; política compartida; TDD-TS-052 API y navegador | BDD-SC-113, BDD-SC-118, BDD-SC-119, BDD-SC-120, BDD-SC-121, BDD-SC-122, BDD-SC-123, BDD-SC-125, BDD-SC-126, BDD-SC-127, BDD-SC-128, BDD-SC-129, BDD-SC-130, BDD-SC-133, BDD-SC-136, BDD-SC-137, BDD-SC-138, BDD-SC-139, BDD-SC-141, BDD-SC-142, BDD-SC-143 | TDD-TS-047, TDD-TS-050, TDD-TS-051, TDD-TS-052, TDD-TC-040, TDD-TC-043, TDD-TC-044, TDD-TC-045 | Scaffold |
| PRD-FR-019 | SDD §25.1/§58.2/58.3 Sesión canónica Admin/POS, workspace durable, reemisión y transición POST | BDD-SC-112, BDD-SC-118, BDD-SC-121, BDD-SC-125, BDD-SC-131, BDD-SC-134, BDD-SC-135, BDD-SC-140, BDD-SC-157, BDD-SC-162, BDD-SC-634, BDD-SC-635, BDD-SC-636, BDD-SC-637, BDD-SC-638, BDD-SC-639, BDD-SC-645 | TDD-TS-047, TDD-TS-050, TDD-TS-051, TDD-TS-052, TDD-TS-055, TDD-TS-138, TDD-TC-044, TDD-TC-045, TDD-TC-048, TDD-TC-351, TDD-TC-352, TDD-TC-354, TDD-TC-355, TDD-TC-356 | Scaffold |
| PRD-FR-020 | Orders module | BDD-SC-001, BDD-SC-030, BDD-SC-063, BDD-SC-066, BDD-SC-160, BDD-SC-161, BDD-SC-381, BDD-SC-402, BDD-SC-702 | TDD-TS-003, TDD-TS-018, TDD-TS-037, TDD-TS-055, TDD-TC-031, TDD-TC-048, TDD-TC-180, TDD-TS-146, TDD-TC-404 | Scaffold |
| PRD-FR-021 | Channel adapters | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-022 | Integration idempotency | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-023 | Original payload retention | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-024 | Customer/address/channel data | BDD-SC-016, BDD-SC-159, BDD-SC-160, BDD-SC-166 | TDD-TS-008, TDD-TS-055, TDD-TS-056, TDD-TC-048, TDD-TC-049 | Scaffold |
| PRD-FR-025 | Order totals and payments | BDD-SC-011, BDD-SC-030, BDD-SC-032, BDD-SC-033, BDD-SC-062, BDD-SC-066, BDD-SC-230 | TDD-TS-005, TDD-TS-018, TDD-TS-020, TDD-TS-037, TDD-TS-060, TDD-TS-068, TDD-TC-031, TDD-TC-063 | Scaffold |
| PRD-FR-026 | Historical catalog snapshots | Pendiente | TDD-TS-003, TDD-TC-004 | Disenado |
| PRD-FR-027 | Order events/state machine | BDD-SC-001, BDD-SC-030 | TDD-TS-003, TDD-TS-018 | Implementado |
| PRD-FR-028 | Cancellation rules | BDD-SC-006, BDD-SC-007, BDD-SC-054, BDD-SC-055 | TDD-TS-003, TDD-TS-031, TDD-TS-032 | Implementado |
| PRD-FR-029 | Notes by order/product/station | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-030 | Offline-safe folios | BDD-SC-001, BDD-SC-002, BDD-SC-030 | TDD-TS-004, TDD-TS-018, TDD-TC-031 | Scaffold |
| PRD-FR-031 | Customer identity and phones | BDD-SC-069, BDD-SC-157, BDD-SC-163, BDD-SC-164 | TDD-TS-039, TDD-TS-055, TDD-TS-056, TDD-TC-048, TDD-TC-049 | Scaffold |
| PRD-FR-032 | Unlimited customer addresses | BDD-SC-070, BDD-SC-159, BDD-SC-160, BDD-SC-166 | TDD-TS-039, TDD-TS-055, TDD-TS-056, TDD-TC-049 | Scaffold |
| PRD-FR-033 | Separate customer tax profile | BDD-SC-069, BDD-SC-073 | TDD-TS-039 | Scaffold |
| PRD-FR-034 | Customer and address snapshots | BDD-SC-071, BDD-SC-072, BDD-SC-158 | TDD-TS-039, TDD-TS-055 | Scaffold |
| PRD-FR-035 | Repeat order with current rules | BDD-SC-074 | TDD-TS-039 | Scaffold |
| PRD-FR-040 | Production tasks | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-041 | Station model | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-042 | Timing, priority and delays | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-043 | Production state machine | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-044 | Authorized reopen/reprint | BDD-SC-018, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-045 | Incidents and stockouts | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-046 | Print service | BDD-SC-018, BDD-SC-035, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-047 | Printer routing | BDD-SC-018, BDD-SC-035 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-048 | Print audit trail | BDD-SC-018, BDD-SC-035, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-050 | Cash shifts | BDD-SC-011, BDD-SC-028, BDD-SC-029, BDD-SC-061, BDD-SC-066 | TDD-TS-005, TDD-TS-017, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-FR-051 | Opening cash fund | BDD-SC-011, BDD-SC-028, BDD-SC-061, BDD-SC-066 | TDD-TS-005, TDD-TS-017, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-FR-052 | Cash movements; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-011, BDD-SC-615, BDD-SC-626 | TDD-TS-005, TDD-TS-136, TDD-TC-332, TDD-TC-343 | Disenado |
| PRD-FR-053 | Payment methods | BDD-SC-012, BDD-SC-032, BDD-SC-033, BDD-SC-062, BDD-SC-063, BDD-SC-230, BDD-SC-403 | TDD-TS-005, TDD-TS-020, TDD-TS-037, TDD-TS-060, TDD-TS-068, TDD-TC-063, TDD-TC-181 | Scaffold |
| PRD-FR-054 | Immutable payments | BDD-SC-012, BDD-SC-032, BDD-SC-033, BDD-SC-062, BDD-SC-230, BDD-SC-403 | TDD-TS-005, TDD-TS-020, TDD-TS-037, TDD-TS-060, TDD-TS-068, TDD-TC-063, TDD-TC-181 | Scaffold |
| PRD-FR-055 | Partial close | BDD-SC-011 | TDD-TS-005 | Propuesto |
| PRD-FR-056 | Cash count differences | BDD-SC-011, BDD-SC-034 | TDD-TS-005, TDD-TS-021 | Scaffold |
| PRD-FR-057 | Final close | BDD-SC-011, BDD-SC-029, BDD-SC-034, BDD-SC-061, BDD-SC-066 | TDD-TS-005, TDD-TS-017, TDD-TS-021, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-FR-058 | Reopen evidence and audit | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-059 | Driver cash settlement; SDD §66; API, rollback, idempotencia, migración SQLite, frontend y QA visual 1440/390 probados localmente; PostgreSQL/CI pendientes | BDD-SC-708, BDD-SC-709, BDD-SC-710, BDD-SC-711, BDD-SC-712, BDD-SC-713, BDD-SC-714 | TDD-TS-148, TDD-TC-410, TDD-TC-411, TDD-TC-412, TDD-TC-413, TDD-TC-414, TDD-TC-415 | Probado |
| PRD-FR-060 | Inventory ledger | BDD-SC-005, BDD-SC-049, BDD-SC-050, BDD-SC-056, BDD-SC-058 | TDD-TS-002, TDD-TS-028, TDD-TS-033, TDD-TS-035 | Scaffold |
| PRD-FR-061 | Units by process | BDD-SC-005, BDD-SC-049, BDD-SC-050 | TDD-TS-002, TDD-TS-028 | Scaffold |
| PRD-FR-062 | Exact conversions | BDD-SC-005, BDD-SC-049, BDD-SC-050 | TDD-TS-002, TDD-TS-028 | Scaffold |
| PRD-FR-063 | Inventory reservation | BDD-SC-005, BDD-SC-052 | TDD-TS-002, TDD-TS-030 | Scaffold |
| PRD-FR-064 | Consumption | BDD-SC-005, BDD-SC-053 | TDD-TS-002, TDD-TS-030 | Scaffold |
| PRD-FR-065 | Release reservation | BDD-SC-006, BDD-SC-054 | TDD-TS-002, TDD-TS-031 | Scaffold |
| PRD-FR-066 | Post-production cancellation | BDD-SC-007, BDD-SC-055 | TDD-TS-002, TDD-TS-032 | Scaffold |
| PRD-FR-067 | Lots and expirations | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-068 | Counts and authorized adjustments | BDD-SC-021, BDD-SC-057, BDD-SC-105, BDD-SC-106, BDD-SC-107, BDD-SC-108, BDD-SC-109, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141, BDD-SC-580, BDD-SC-581, BDD-SC-582, BDD-SC-583, BDD-SC-584, BDD-SC-585 | TDD-TS-002, TDD-TS-034, TDD-TS-046, TDD-TS-052, TDD-TS-131, TDD-TC-039, TDD-TC-045, TDD-TC-302 | Implementado |
| PRD-FR-069 | Transfers | BDD-SC-015, BDD-SC-100, BDD-SC-101, BDD-SC-102, BDD-SC-103, BDD-SC-104, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-002, TDD-TS-045, TDD-TS-052, TDD-TC-038, TDD-TC-045 | Scaffold |
| PRD-FR-070 | Kardex and theoretical stock | BDD-SC-005, BDD-SC-049, BDD-SC-050, BDD-SC-056, BDD-SC-162 | TDD-TS-002, TDD-TS-028, TDD-TS-033, TDD-TS-055 | Scaffold |
| PRD-FR-071 | Classified real waste | BDD-SC-095, BDD-SC-096, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-044, TDD-TS-052, TDD-TC-045 | Scaffold |
| PRD-FR-072 | Configurable waste reasons | BDD-SC-095, BDD-SC-096 | TDD-TS-044 | Scaffold |
| PRD-FR-073 | Authorized idempotent waste confirmation | BDD-SC-097, BDD-SC-098 | TDD-TS-044, TDD-TC-037 | Scaffold |
| PRD-FR-074 | Immutable waste compensation | BDD-SC-099 | TDD-TS-044, TDD-TC-037 | Scaffold |
| PRD-FR-075 | Waste costing and reconciliation | BDD-SC-097, BDD-SC-099 | TDD-TS-044, TDD-TC-037 | Scaffold |
| PRD-FR-076 | Transfer document and states | BDD-SC-100 | TDD-TS-045 | Scaffold |
| PRD-FR-077 | Authorized idempotent transfer out | BDD-SC-101, BDD-SC-102 | TDD-TS-045, TDD-TC-038 | Scaffold |
| PRD-FR-078 | Explicit destination receipt | BDD-SC-103, BDD-SC-104 | TDD-TS-045, TDD-TC-038 | Scaffold |
| PRD-FR-079 | Transfer differences and costing | BDD-SC-103, BDD-SC-104 | TDD-TS-045, TDD-TC-038 | Scaffold |
| PRD-FR-080 | Recursive recipes | BDD-SC-008, BDD-SC-051, BDD-SC-056, BDD-SC-086, BDD-SC-087 | TDD-TS-001, TDD-TS-029, TDD-TS-033, TDD-TS-042 | Scaffold |
| PRD-FR-081 | Cycle detection | BDD-SC-009, BDD-SC-088 | TDD-TS-001, TDD-TS-042 | Scaffold |
| PRD-FR-082 | Recipe versioning | BDD-SC-051, BDD-SC-085 | TDD-TS-001, TDD-TS-029, TDD-TS-042, TDD-TC-004 | Scaffold |
| PRD-FR-083 | Yield | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-084 | Planned and real waste | BDD-SC-010, BDD-SC-084 | TDD-TS-001, TDD-TS-042 | Scaffold |
| PRD-FR-085 | Batch production | BDD-SC-010, BDD-SC-086, BDD-SC-087, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-006, TDD-TS-042, TDD-TS-052, TDD-TC-045 | Scaffold |
| PRD-FR-086 | Lot traceability | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-087 | Real batch cost | BDD-SC-010, BDD-SC-086 | TDD-TS-001, TDD-TS-042 | Scaffold |
| PRD-FR-088 | Theoretical product cost | BDD-SC-008, BDD-SC-051, BDD-SC-084, BDD-SC-085 | TDD-TS-001, TDD-TS-029, TDD-TS-042, TDD-TS-120 | Implementado |
| PRD-FR-089 | Weighted average cost | BDD-SC-005 | TDD-TS-001 | Disenado |
| PRD-FR-090 | Standard cost | BDD-SC-008 | TDD-TS-001 | Disenado |
| PRD-FR-091 | Central suppliers; ficha adaptable sin datos financieros simulados y crédito cero preservado (BDD-SC-704 / TDD-TC-406); AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1; baseline Implementado restaurado tras corrección verificada | BDD-SC-075, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141, BDD-SC-142, BDD-SC-622, BDD-SC-624, BDD-SC-704 | TDD-TS-040, TDD-TS-052, TDD-TC-045, TDD-TS-121, TDD-TS-136, TDD-TC-339, TDD-TC-341, TDD-TC-406 | Implementado |
| PRD-FR-092 | Supplier contacts and branch terms; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1; baseline Implementado restaurado tras corrección verificada | BDD-SC-075, BDD-SC-076, BDD-SC-622 | TDD-TS-040, TDD-TS-121, TDD-TS-136, TDD-TC-339 | Implementado |
| PRD-FR-093 | Purchase presentations; SDD §58.1 corrección central | BDD-SC-077, BDD-SC-078, BDD-SC-739 | TDD-TS-040, TDD-TS-122, TDD-TC-434 | Implementado |
| PRD-FR-094 | SDD §58.1; baseline corporativo y precio/costo/historial efectivo branch-scoped con resolver compartido | BDD-SC-077, BDD-SC-633 | TDD-TS-040, TDD-TS-138, TDD-TC-033, TDD-TC-207, TDD-TC-350, TDD-TC-355 | Scaffold |
| PRD-FR-095 | Modifier groups and cardinality | BDD-SC-089, BDD-SC-090, BDD-SC-404, BDD-SC-405, BDD-SC-442, BDD-SC-444, BDD-SC-445, BDD-SC-591 | TDD-TS-043, TDD-TC-182, TDD-TS-122, TDD-TC-308 | Implementado |
| PRD-FR-096 | Modifier inventory effects, kitchen text and exact administrative surcharge capture | BDD-SC-091, BDD-SC-092, BDD-SC-093, BDD-SC-404, BDD-SC-419, BDD-SC-441, BDD-SC-442, BDD-SC-443, BDD-SC-444, BDD-SC-445, BDD-SC-591 | TDD-TS-043, TDD-TC-036, TDD-TC-182, TDD-TC-192, TDD-TS-122, TDD-TC-308 | Implementado |
| PRD-FR-097 | Effective modifier snapshot | BDD-SC-089, BDD-SC-094, BDD-SC-404, BDD-SC-405 | TDD-TS-043, TDD-TC-182 | Scaffold |
| PRD-FR-098 | Modified reservation and consumption | BDD-SC-091, BDD-SC-092, BDD-SC-093 | TDD-TS-043, TDD-TC-036 | Scaffold |
| PRD-FR-099 | Backend modifier pricing | BDD-SC-094, BDD-SC-404, BDD-SC-419 | TDD-TS-043, TDD-TC-036, TDD-TC-182, TDD-TC-192 | Scaffold |
| PRD-FR-245 | Producto compuesto seleccionable administrado desde Modificadores; producto hijo configurable incluso sin precio independiente, precio/consumo Python, snapshot y tarea por estación; implementación local con gates runtime R3 pendientes | BDD-SC-527, BDD-SC-528, BDD-SC-529, BDD-SC-530, BDD-SC-591, BDD-SC-797, BDD-SC-798, BDD-SC-799, BDD-SC-800 | SDD §48.7, TDD-TS-117, TDD-TS-161, TDD-TC-267, TDD-TC-268, TDD-TC-269, TDD-TC-270, TDD-TC-308, TDD-TC-468, TDD-TC-469, TDD-TC-470 | Scaffold |
| PRD-FR-100 | Direct receipts | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-101 | Supplier presentation and lot | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-102 | SDD §64 captura privada unverified X01: parser, identidad, receptor autorizado, API/evidencia cifrada, replay y migration0092; validación fiscal completa, conceptos y conciliación pendientes | BDD-SC-013, BDD-SC-689, BDD-SC-690, BDD-SC-691, BDD-SC-692, BDD-SC-693, BDD-SC-694 | TDD-TS-007, TDD-TS-144, TDD-TC-392, TDD-TC-393, TDD-TC-394, TDD-TC-395, TDD-TC-396, TDD-TC-397 | Scaffold |
| PRD-FR-103 | SDD §64.2 org/UUID declarado, key/hash, conflicto privado inmutable; integración fiscal/compras pendiente | BDD-SC-014, BDD-SC-691, BDD-SC-693 | TDD-TS-007, TDD-TS-144, TDD-TC-394, TDD-TC-396 | Scaffold |
| PRD-FR-104 | Supplier mappings | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-105 | Accounts payable | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-106 | AP payments and balances | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-107 | SDD §64.2 original cifrado scoped, descarga reautorizada/auditada, downgrade no destructivo; pipeline completo pendiente | BDD-SC-013, BDD-SC-691, BDD-SC-692, BDD-SC-694 | TDD-TS-007, TDD-TS-144, TDD-TC-394, TDD-TC-395, TDD-TC-397 | Scaffold |
| PRD-FR-108 | Direct purchase and cash reconciliation; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-079, BDD-SC-080, BDD-SC-081, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141, BDD-SC-615, BDD-SC-618, BDD-SC-619, BDD-SC-620, BDD-SC-626 | TDD-TS-041, TDD-TS-052, TDD-TC-045, TDD-TC-212, TDD-TS-136, TDD-TC-332, TDD-TC-335, TDD-TC-336, TDD-TC-337, TDD-TC-343 | Scaffold |
| PRD-FR-109 | Receipt-driven weighted average cost; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-082, BDD-SC-619, BDD-SC-626 | TDD-TS-041, TDD-TS-136, TDD-TC-336, TDD-TC-343 | Scaffold |
| PRD-FR-110 | Purchase idempotency and compensations; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-080, BDD-SC-081, BDD-SC-617, BDD-SC-619, BDD-SC-620 | TDD-TS-041, TDD-TS-136, TDD-TC-334, TDD-TC-336, TDD-TC-337 | Scaffold |
| PRD-FR-111 | SDD §57 y §63 D06_v1; evidencia AUD-CORE-001 conservada, referencia aritmética de impuesto/reparto/compensación; XML, CxP y ledger v1 pendientes | BDD-SC-082, BDD-SC-083, BDD-SC-619, BDD-SC-687, BDD-SC-688 | TDD-TS-041, TDD-TS-136, TDD-TC-336, TDD-TS-143, TDD-TC-390, TDD-TC-391 | Scaffold |
| PRD-FR-120 | Delivery zones | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-121 | Geocoding | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-122 | Distance and ETA | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-123 | Route optimization | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-124 | Multi-order driver routes | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-125 | Delivery windows | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-126 | Manual route override | BDD-SC-017 | TDD-TS-008 | Disenado |
| PRD-FR-127 | Manual dispatch fallback | BDD-SC-017 | TDD-TS-008 | Disenado |
| PRD-FR-128 | Delivery state registration | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-129 | Exact driver cash settlement; SDD §66; API, rollback, idempotencia, migración SQLite, frontend y QA visual 1440/390 probados localmente; PostgreSQL/CI pendientes | BDD-SC-708, BDD-SC-709, BDD-SC-710, BDD-SC-711, BDD-SC-712, BDD-SC-713, BDD-SC-714 | TDD-TS-148, TDD-TC-410, TDD-TC-411, TDD-TC-412, TDD-TC-413, TDD-TC-414, TDD-TC-415 | Probado |
| PRD-FR-140 | Versioned APIs | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-141 | Idempotent webhooks | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-142 | Integration health/errors | BDD-SC-023 | TDD-TS-009 | Disenado |
| PRD-FR-143 | Safe retries | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-144 | Pause branch in channels | BDD-SC-023 | TDD-TS-009 | Disenado |
| PRD-FR-145 | Chatbot system queries | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-146 | Chatbot no invention | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-147 | External adapters | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-160 | Individual export | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-161 | Global export | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-162 | Legal entity separation | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-163 | Export canonical data | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-164 | Export deduplication | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-165 | Re-export | BDD-SC-020 | TDD-TS-010 | Disenado |
| PRD-FR-166 | CONTPAQi adapters | BDD-SC-020 | TDD-TS-010 | Disenado |
| PRD-FR-167 | Export history and reconciliation | BDD-SC-020 | TDD-TS-010 | Disenado |
| PRD-FR-180 | Edge gateway; PCO-008 local para caja manual ; SDD §47 / ADR035 | BDD-SC-001, BDD-SC-037, BDD-SC-038, BDD-SC-039, BDD-SC-041, BDD-SC-042, BDD-SC-393, BDD-SC-397, BDD-SC-401 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TS-023, TDD-TS-024, TDD-TC-171, TDD-TC-175, TDD-TC-179 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Scaffold |
| PRD-FR-181 | Local coordination ; SDD §47 / ADR035 | BDD-SC-001, BDD-SC-037, BDD-SC-041 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TS-023, TDD-TS-024 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Scaffold |
| PRD-FR-182 | Two-hour offline ; SDD §47 / ADR035 | BDD-SC-001, BDD-SC-041 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TS-024 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Scaffold |
| PRD-FR-183 | Several offline registers ; SDD §47 / ADR035 | Pendiente , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TC-003 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Disenado |
| PRD-FR-184 | Outbox, inbox, idempotency; PCO-008 cash manual ; SDD §47 / ADR035 | BDD-SC-002, BDD-SC-037, BDD-SC-038, BDD-SC-039, BDD-SC-041, BDD-SC-042, BDD-SC-393, BDD-SC-395, BDD-SC-397, BDD-SC-401 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TS-023, TDD-TS-024, TDD-TC-171, TDD-TC-173, TDD-TC-175, TDD-TC-179 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Scaffold |
| PRD-FR-185 | Reconciliation allowlisted de caja manual ; SDD §47 / ADR035; SDD §58.3 autoridad vigente para nueva ejecución y acuse mínimo confirmado, evidencia incremental TC354; adopción y comandos inciertos pendientes | BDD-SC-002, BDD-SC-037, BDD-SC-038, BDD-SC-039, BDD-SC-042, BDD-SC-395, BDD-SC-396, BDD-SC-398 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508, BDD-SC-509, BDD-SC-510, BDD-SC-639 | TDD-TS-004, TDD-TS-023, TDD-TS-024, TDD-TC-173, TDD-TC-174, TDD-TC-176 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254, TDD-TC-255, TDD-TC-256, TDD-TS-138, TDD-TC-354 | Scaffold |
| PRD-FR-186 | Sync status POS PCO-008 ; SDD §47 / ADR035 | BDD-SC-001, BDD-SC-037, BDD-SC-040, BDD-SC-399 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TS-023, TDD-TC-177 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Scaffold |
| PRD-FR-187 | No duplicate/loss ; SDD §47 / ADR035 | BDD-SC-002, BDD-SC-038, BDD-SC-039, BDD-SC-041, BDD-SC-042, BDD-SC-401 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TS-023, TDD-TS-024, TDD-TC-179 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Scaffold |
| PRD-FR-188 | Local KDS and printing ; SDD §47 / ADR035 | BDD-SC-001, BDD-SC-018 , BDD-SC-502, BDD-SC-503, BDD-SC-504, BDD-SC-505, BDD-SC-506, BDD-SC-507, BDD-SC-508 | TDD-TS-004, TDD-TS-011 , TDD-TS-113, TDD-TC-249, TDD-TC-250, TDD-TC-251, TDD-TC-252, TDD-TC-253, TDD-TC-254 | Disenado |
| PRD-FR-189 | External continuity | BDD-SC-022, BDD-SC-023 | TDD-TS-009 | Disenado |
| PRD-FR-190 | Idempotent legacy import batches | BDD-SC-144 | TDD-TS-053, TDD-TC-046 | Scaffold |
| PRD-FR-191 | Organization catalog with branch operations | BDD-SC-145, BDD-SC-146, BDD-SC-149, BDD-SC-150, BDD-SC-200 | TDD-TS-053, TDD-TC-046, TDD-TS-062, TDD-TC-057 | Scaffold |
| PRD-FR-192 | Deterministic station or product review | BDD-SC-145, BDD-SC-152, BDD-SC-154, BDD-SC-198, BDD-SC-199, BDD-SC-201 | TDD-TS-053, TDD-TC-046, TDD-TS-054, TDD-TC-047, TDD-TS-062, TDD-TC-057 | Scaffold |
| PRD-FR-193 | Incomplete presentation and recipe review | BDD-SC-147, BDD-SC-148, BDD-SC-152, BDD-SC-153 | TDD-TS-053, TDD-TC-046, TDD-TS-054, TDD-TC-047 | Scaffold |
| PRD-FR-194 | Legacy cost is non-operational reference | BDD-SC-146 | TDD-TS-053, TDD-TC-046 | Scaffold |
| PRD-FR-195 | Paginated branch customer directory | BDD-SC-149, BDD-SC-150, BDD-SC-157, BDD-SC-158, BDD-SC-163, BDD-SC-164 | TDD-TS-053, TDD-TS-055, TDD-TS-056, TDD-TC-046, TDD-TC-048, TDD-TC-049 | Scaffold |
| PRD-FR-196 | Corporate catalog and local availability adjustments | BDD-SC-151, BDD-SC-152, BDD-SC-153, BDD-SC-154, BDD-SC-155, BDD-SC-200, BDD-SC-202 | TDD-TS-053, TDD-TC-046, TDD-TS-054, TDD-TC-047, TDD-TS-062, TDD-TC-057 | Scaffold |
| PRD-FR-197 | Import retry and audit | BDD-SC-144, BDD-SC-151 | TDD-TS-053, TDD-TC-046 | Scaffold |
| PRD-FR-198 | Phone-first POS customer registration | BDD-SC-163, BDD-SC-164, BDD-SC-165, BDD-SC-166, BDD-SC-167 | TDD-TS-056, TDD-TC-049 | Scaffold |
| PRD-FR-199 | Organization-wide order comments assigned through expandable operational categories and stable `category_id` subcategory checkboxes, with independent catalog/error loading, current-preview confirmation, safe bulk archive, audited deletion of current and inherited presets, offline purge, rounded controls, visible cart text and reversible 0028 state restoration | BDD-SC-168, BDD-SC-169, BDD-SC-170, BDD-SC-171, BDD-SC-172, BDD-SC-173, BDD-SC-174, BDD-SC-185, BDD-SC-186, BDD-SC-190, BDD-SC-191, BDD-SC-194, BDD-SC-203, BDD-SC-204, BDD-SC-205, BDD-SC-206, BDD-SC-207, BDD-SC-795, BDD-SC-796 | TDD-TS-057, TDD-TC-050, TDD-TS-059, TDD-TC-052, TDD-TS-063, TDD-TC-058, TDD-TC-466, TDD-TC-467 | Implementado |
| PRD-FR-200 | Universal add-only extras with complete canonical configuration, exact 1..99 POS portions and no sale through historical option IDs | BDD-SC-175, BDD-SC-176, BDD-SC-177, BDD-SC-178, BDD-SC-179, BDD-SC-180, BDD-SC-181, BDD-SC-182, BDD-SC-183, BDD-SC-184, BDD-SC-187, BDD-SC-188, BDD-SC-189, BDD-SC-190, BDD-SC-191, BDD-SC-208, BDD-SC-209, BDD-SC-210, BDD-SC-211, BDD-SC-212 | TDD-TS-058, TDD-TC-051, TDD-TS-059, TDD-TC-052, TDD-TS-063, TDD-TC-058 | Implementado |
| PRD-FR-201 | Separate canonical comments and extras; legacy product-assignment endpoints are read-only in new configuration | BDD-SC-185, BDD-SC-186, BDD-SC-187, BDD-SC-188, BDD-SC-189, BDD-SC-190, BDD-SC-191, BDD-SC-204, BDD-SC-205, BDD-SC-209, BDD-SC-210, BDD-SC-212 | TDD-TS-059, TDD-TC-052, TDD-TS-063, TDD-TC-058 | Implementado |
| PRD-FR-261 | Inspectable product membership, partial subcategory selection and exact per-comment replacement without branch overrides or historical mutation | BDD-SC-586, BDD-SC-587, BDD-SC-588, BDD-SC-589, BDD-SC-590 | TDD-TS-132, TDD-TC-303, TDD-TC-304, TDD-TC-305, TDD-TC-306, TDD-TC-307 | Implementado |
| PRD-FR-202 | Reversible legacy catalog cleanup | BDD-SC-196, BDD-SC-197, BDD-SC-198, BDD-SC-199, BDD-SC-200, BDD-SC-201, BDD-SC-202 | TDD-TS-062, TDD-TC-057 | Probado |
| PRD-FR-203 | Single product grid and removable POS cart lines | BDD-SC-213, BDD-SC-232 | TDD-TS-064 | Implementado |
| PRD-FR-204 | Pedidos detail, exact active-branch PENDING notification, selected-order edit routing, snapshot-backed cart restoration and versioned amendment | BDD-SC-214, BDD-SC-215, BDD-SC-216, BDD-SC-217, BDD-SC-235, BDD-SC-248, BDD-SC-455 | TDD-TS-064, TDD-TC-059, TDD-TS-069, TDD-TS-073, TDD-TC-069, TDD-TS-100, TDD-TC-216 | Implementado |
| PRD-FR-205 | Supervisor-authorized courtesy adjustments; auditoría 2026-08-19 detectó UI simulada sin autoridad backend | BDD-SC-218, BDD-SC-219, BDD-SC-220, BDD-SC-221, BDD-SC-222, BDD-SC-361, BDD-SC-362 | TDD-TS-065, TDD-TC-060, TDD-TS-090, TDD-TC-146, TDD-TC-147 | Implementado |
| PRD-FR-206 | Branch-originated supplier creation; contrato/permiso/atomicidad implementados | BDD-SC-223, BDD-SC-224, BDD-SC-225, BDD-SC-228, BDD-SC-363, BDD-SC-364 | TDD-TS-066, TDD-TC-061, TDD-TS-090, TDD-TC-148 | Implementado |
| PRD-FR-207 | Baseline de compras, alcance y cancelación implementado; incremento PUR-CASH-001 SDD §51.8 diseñado, pendiente de runtime y gates R3; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-226, BDD-SC-227, BDD-SC-228, BDD-SC-229, BDD-SC-365, BDD-SC-366, BDD-SC-607, BDD-SC-608, BDD-SC-609, BDD-SC-610, BDD-SC-611, BDD-SC-612, BDD-SC-613, BDD-SC-621, BDD-SC-623, BDD-SC-624 | TDD-TS-067, TDD-TC-062, TDD-TS-090, TDD-TC-149, TDD-TC-150, TDD-TS-135, TDD-TC-212, TDD-TC-324, TDD-TC-325, TDD-TC-326, TDD-TC-327, TDD-TC-328, TDD-TC-329, TDD-TC-330, TDD-TS-136, TDD-TC-338, TDD-TC-340, TDD-TC-341 | Disenado |
| PRD-FR-208 | Deferred payment confirmation attributed to the OPEN collection shift under the shared cash guard | BDD-SC-233, BDD-SC-234, BDD-SC-235, BDD-SC-307 | TDD-TS-069, TDD-TC-065, TDD-TC-090 | Implementado |
| PRD-FR-209 | POS-only navigation, inventory under Administration, four category-first operational groups and local product-specific Favorites that open directly to concrete products | BDD-SC-236, BDD-SC-237, BDD-SC-238 | TDD-TS-070, TDD-TC-066 | Implementado |
| PRD-FR-210 | Audited corporate driver catalog assigned by branch | BDD-SC-239, BDD-SC-240, BDD-SC-241, BDD-SC-242 | TDD-TS-071, TDD-TC-067 | Implementado |
| PRD-FR-211 | Branch-scoped POS and public-order driver assignment with immutable delivery history and first-assignment recovery | BDD-SC-243, BDD-SC-244, BDD-SC-245, BDD-SC-246, BDD-SC-247, BDD-SC-735, BDD-SC-736, BDD-SC-737, BDD-SC-738 | TDD-TS-072, TDD-TC-068, TDD-TC-430, TDD-TC-431, TDD-TC-432, TDD-TC-433 | Implementado |
| PRD-FR-212 | POS attendance clock with six-character organization-unique staff identifiers, atomic administrator self-edit recovery, branch-local daily pairing and scoped report | BDD-SC-249, BDD-SC-250, BDD-SC-251, BDD-SC-252, BDD-SC-253, BDD-SC-254 | TDD-TS-074, TDD-TC-070 | Implementado |
| PRD-FR-213 | Required single-select category option before concrete POS product, integrated Group/Subgroup administration, empty-subgroup counts, contextual product creation, protected destructive cleanup, and SDD §48 atomic product assignment | BDD-SC-255, BDD-SC-256, BDD-SC-257, BDD-SC-258, BDD-SC-259, BDD-SC-260, BDD-SC-261, BDD-SC-262, BDD-SC-263, BDD-SC-511, BDD-SC-512, BDD-SC-513, BDD-SC-516, BDD-SC-517, BDD-SC-518, BDD-SC-802, BDD-SC-803 | TDD-TS-075, TDD-TC-071, TDD-TS-114, TDD-TC-257, TDD-TC-472, TDD-TC-473, TDD-TS-115, TDD-TC-258 | Scaffold |
| PRD-FR-214 | Compact fallback and legible name only for concrete POS products without a usable photograph; photographed products and category preselector preserve current behavior | BDD-SC-265, BDD-SC-266, BDD-SC-267, BDD-SC-268, BDD-SC-269 | TDD-TS-076, TDD-TC-072 | Implementado |
| PRD-FR-229 | Progressive POS catalog stages with Group/Subgroup language, persistent menu reset with direct-product Favorites exception, compact previous context and modifier-group tabs without changing catalog, pricing, cart or order authority | BDD-SC-425, BDD-SC-426, BDD-SC-427, BDD-SC-428, BDD-SC-429, BDD-SC-430, BDD-SC-514 | TDD-TS-098, TDD-TC-193, TDD-TS-114, TDD-TC-257 | Implementado |
| PRD-FR-215 | Perfiles persistidos, autorización branch/org, movilidad de Supervisor/Administrador por SDD §58.2, bootstrap/mapping gobernados y contención forward-only de 0049 sin inferir autoridad | BDD-SC-270, BDD-SC-271, BDD-SC-272, BDD-SC-273, BDD-SC-274, BDD-SC-275, BDD-SC-276, BDD-SC-277, BDD-SC-290, BDD-SC-291, BDD-SC-293, BDD-SC-298, BDD-SC-299, BDD-SC-300, BDD-SC-454, BDD-SC-634, BDD-SC-635 | TDD-TS-077, TDD-TS-138, TDD-TC-073, TDD-TC-081, TDD-TC-082, TDD-TC-083, TDD-TC-211, TDD-TC-215, TDD-TC-351, TDD-TS-084, TDD-TS-085, TDD-TS-087, TDD-TS-088 | Scaffold |
| PRD-FR-216 | PCO-002/003 más PCO-008P para caja manual offline; publicación pendiente de CI/PR | BDD-SC-278, BDD-SC-279, BDD-SC-280, BDD-SC-289, BDD-SC-294, BDD-SC-296, BDD-SC-301, BDD-SC-302, BDD-SC-303, BDD-SC-304, BDD-SC-305, BDD-SC-306, BDD-SC-393, BDD-SC-394, BDD-SC-395, BDD-SC-396, BDD-SC-397, BDD-SC-398, BDD-SC-399, BDD-SC-400 | TDD-TS-078, TDD-TC-074, TDD-TC-079, TDD-TS-083, TDD-TC-084, TDD-TC-085, TDD-TC-086, TDD-TC-087, TDD-TC-088, TDD-TC-089, TDD-TC-168, TDD-TS-092, TDD-TC-158, TDD-TC-171, TDD-TC-172, TDD-TC-173, TDD-TC-174, TDD-TC-175, TDD-TC-176, TDD-TC-177, TDD-TC-178 | Probado |
| PRD-FR-217 | Account consultation plus implemented PCO-005A request/decision and PCO-005B linked compensating correction | BDD-SC-281, BDD-SC-282, BDD-SC-283, BDD-SC-312, BDD-SC-313, BDD-SC-314, BDD-SC-315, BDD-SC-316, BDD-SC-317, BDD-SC-318, BDD-SC-319, BDD-SC-320, BDD-SC-321, BDD-SC-322, BDD-SC-323, BDD-SC-324, BDD-SC-325, BDD-SC-326 | TDD-TS-079, TDD-TC-075, TDD-TC-096, TDD-TC-097, TDD-TC-098, TDD-TC-099, TDD-TC-100, TDD-TC-101, TDD-TC-102, TDD-TC-103, TDD-TC-104, TDD-TC-105, TDD-TC-106, TDD-TC-107, TDD-TC-108, TDD-TC-109, TDD-TC-110, TDD-TC-111, TDD-TC-112 | Implementado |
| PRD-FR-218 | PCO-004 operational shift lifecycle and snapshot-backed traceable sales monitor | BDD-SC-284, BDD-SC-285, BDD-SC-292, BDD-SC-307, BDD-SC-308, BDD-SC-309, BDD-SC-310, BDD-SC-311 | TDD-TS-080, TDD-TC-076, TDD-TC-090, TDD-TC-091, TDD-TC-092, TDD-TC-093, TDD-TC-094, TDD-TC-095 | Implementado |
| PRD-FR-219 | PCO-006 implementado y auditado localmente: cajero/turno canónicos, snapshot Python exacto, asociaciones exclusivas y reapertura compensatoria; PostgreSQL CI y QA visual permanecen como gates de cierre | BDD-SC-286, BDD-SC-287, BDD-SC-295, BDD-SC-327, BDD-SC-328, BDD-SC-329, BDD-SC-330, BDD-SC-331, BDD-SC-332, BDD-SC-333, BDD-SC-334 | TDD-TS-081, TDD-TC-077, TDD-TC-080, TDD-TC-113, TDD-TC-114, TDD-TC-115, TDD-TC-116, TDD-TC-117, TDD-TC-118, TDD-TC-119, TDD-TC-120 | Probado |
| PRD-FR-220 | Branch/corporate recipe versioning, historical ingredient sales and canonical scoped expense reports; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1; baseline Implementado restaurado tras corrección verificada | BDD-SC-275, BDD-SC-276, BDD-SC-288, BDD-SC-297, BDD-SC-335, BDD-SC-336, BDD-SC-337, BDD-SC-338, BDD-SC-339, BDD-SC-340, BDD-SC-341, BDD-SC-342, BDD-SC-617, BDD-SC-618, BDD-SC-626 | TDD-TS-082, TDD-TC-078, TDD-TC-121, TDD-TC-122, TDD-TC-123, TDD-TC-124, TDD-TC-125, TDD-TC-126, TDD-TC-127, TDD-TC-128, TDD-TS-136, TDD-TC-334, TDD-TC-335, TDD-TC-343 | Implementado |
| PRD-FR-221 | SDD §39.1/39.3, ADR-030 aprobada: scanner y guards focales implementados; el cierre transversal de rutas default-deny, KDS, sync y seed sigue pendiente de evidencia completa | BDD-SC-355, BDD-SC-356, BDD-SC-357, BDD-SC-358 | TDD-TS-089, TDD-TC-141, TDD-TC-142, TDD-TC-143, TDD-TC-145, TDD-TC-213 | Scaffold |
| PRD-FR-222 | SDD §39.1/39.3: impresión verificable; cotización Python compartida; pago, KDS y fulfillment como autoridades separadas | BDD-SC-359, BDD-SC-360, BDD-SC-367, BDD-SC-380 | TDD-TS-089, TDD-TC-144, TDD-TS-090, TDD-TC-151, TDD-TC-166 | Implementado |
| PRD-FR-223 | SDD §39.2, ADR-031: intención pública idempotente, terminal y validada en Python; rechazo autorizado sin efectos y expiración reservada | BDD-SC-368, BDD-SC-369, BDD-SC-370, BDD-SC-371, BDD-SC-372, BDD-SC-376, BDD-SC-389, BDD-SC-390, BDD-SC-391, BDD-SC-392 | TDD-TS-091, TDD-TC-152, TDD-TC-153, TDD-TC-154, TDD-TC-155, TDD-TC-169, TDD-TC-170 | Implementado |
| PRD-FR-224 | SDD §39.2/39.3: aceptación autenticada por dominio compartido, reserva de inventario atómica, sin turno público fantasma | BDD-SC-373, BDD-SC-374, BDD-SC-375 | TDD-TS-091, TDD-TC-156, TDD-TC-157 | Scaffold |
| PRD-FR-225 | Generación automática de conciliación diaria de sucursal (corte Z extendido, desglose multicanal y balance sobrante/faltante); AUD-CORE-001 SDD §57: D-01/D-02 aprobadas 2026-10-09; contrato v2 con saldo por apertura, actividad independiente y arqueo nullable; implementación/consumidores y CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1; baseline Implementado restaurado tras corrección verificada | BDD-SC-343, BDD-SC-344, BDD-SC-345, BDD-SC-346, BDD-SC-347, BDD-SC-615, BDD-SC-616, BDD-SC-617, BDD-SC-626 | TDD-TS-093, TDD-TC-159, TDD-TC-160, TDD-TS-136, TDD-TC-332, TDD-TC-333, TDD-TC-334, TDD-TC-343, TDD-TC-344 | Implementado |
| PRD-FR-226 | Consolidado multi-sucursal diario/mensual, estado de auditoría y exportación a Excel (.xlsx formato Kiwi); AUD-CORE-001 SDD §57: D-01/D-02 aprobadas 2026-10-09; contrato v2 con saldo por apertura, actividad independiente y arqueo nullable; implementación/consumidores y CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1; baseline Implementado restaurado tras corrección verificada | BDD-SC-348, BDD-SC-349, BDD-SC-350, BDD-SC-351, BDD-SC-352, BDD-SC-615, BDD-SC-617, BDD-SC-623 | TDD-TS-094, TDD-TC-161, TDD-TC-162, TDD-TC-163, TDD-TS-136, TDD-TC-332, TDD-TC-334, TDD-TC-340, TDD-TC-344 | Implementado |
| PRD-FR-227 | Autoservicio web móvil y captura con intención canónica; seguimiento público por referencia opaca según SDD §67, sin escrituras ni exposición personal | BDD-SC-377, BDD-SC-378, BDD-SC-379, BDD-SC-382, BDD-SC-383, BDD-SC-384, BDD-SC-715, BDD-SC-716, BDD-SC-717, BDD-SC-718, BDD-SC-719 | TDD-TS-091, TDD-TC-154, TDD-TS-095, TDD-TC-164, TDD-TC-165, TDD-TC-167, TDD-TS-149, TDD-TC-416, TDD-TC-417, TDD-TC-418, TDD-TC-419 | Scaffold |
| PRD-FR-228 | SDD §41, ADR-032/033: diálogo asistido con OpenRouter redactado, preguntas canónicas y borrador sin autoridad de pedido | BDD-SC-406, BDD-SC-407, BDD-SC-408, BDD-SC-409, BDD-SC-410, BDD-SC-411, BDD-SC-412, BDD-SC-413, BDD-SC-414, BDD-SC-415, BDD-SC-416, BDD-SC-417, BDD-SC-418 | TDD-TS-096, TDD-TS-097, TDD-TC-183, TDD-TC-184, TDD-TC-185, TDD-TC-186, TDD-TC-187, TDD-TC-188, TDD-TC-189, TDD-TC-190, TDD-TC-191 | Implementado |
| PRD-FR-230 | SDD §43, ADR-034: implementación conservada pero acceso frontend suspendido por compuerta default-off; reactivación requiere evidencia de proyecciones canónicas | BDD-SC-431, BDD-SC-432, BDD-SC-433, BDD-SC-434, BDD-SC-435, BDD-SC-436, BDD-SC-437, BDD-SC-438, BDD-SC-439, BDD-SC-440, BDD-SC-446, BDD-SC-447, BDD-SC-448, BDD-SC-449, BDD-SC-450, BDD-SC-451 | TDD-TS-099, TDD-TC-194, TDD-TC-195, TDD-TC-196, TDD-TC-197, TDD-TC-198, TDD-TC-199, TDD-TC-200, TDD-TC-201, TDD-TC-202, TDD-TC-203, TDD-TC-204, TDD-TC-205, TDD-TC-206, TDD-TC-207, TDD-TC-208, TDD-TC-209 | Probado |
| PRD-FR-231 | SDD §44: portada estática aislada, selección móvil sólo en `/`, variantes no cacheables y recursos contenidos | BDD-SC-456, BDD-SC-457, BDD-SC-458 | TDD-TS-101, TDD-TC-217, TDD-TC-218, TDD-TC-219 | Implementado |
| PRD-FR-232 | SDD §5.12: Hub de Integraciones desacoplado, configuración segura y adaptadores Uber Eats / DiDi Food / Rappi con validación HMAC e idempotencia | BDD-SC-459, BDD-SC-460, BDD-SC-461, BDD-SC-462, BDD-SC-463, BDD-SC-464, BDD-SC-466, BDD-SC-467, BDD-SC-468, BDD-SC-469, BDD-SC-470, BDD-SC-471, BDD-SC-476, BDD-SC-477, BDD-SC-478, BDD-SC-479, BDD-SC-480, BDD-SC-481 | TDD-TS-103, TDD-TC-221, TDD-TC-222, TDD-TC-223, TDD-TC-224, TDD-TS-104, TDD-TC-226, TDD-TC-227, TDD-TC-228, TDD-TC-229, TDD-TS-106, TDD-TC-233, TDD-TC-234, TDD-TC-235, TDD-TC-236 | Implementado |
| PRD-FR-233 | SDD §5.12: Monitor y gestión de pedidos Uber Eats / DiDi Food / Rappi en terminal POS con control de estados, despacho y visibilidad fail-closed según configuración efectiva | BDD-SC-465, BDD-SC-472, BDD-SC-482, BDD-SC-483, BDD-SC-646 | TDD-TS-103, TDD-TC-225, TDD-TS-104, TDD-TC-230, TDD-TS-106, TDD-TC-237, TDD-TC-357 | Implementado |
| PRD-FR-234 | Configuración multi-sucursal de enlace directo de Google Reviews en Administrador y exposición pública | BDD-SC-473, BDD-SC-474 | TDD-TS-105, TDD-TC-231 | Implementado |
| PRD-FR-235 | Smart Rating de satisfacción en confirmación de pedido y retención de feedback privado | BDD-SC-475 | TDD-TS-105, TDD-TC-232 | Implementado |
| PRD-FR-236 | SDD §45: venta cruzada determinista, complementaria y acotada al catálogo efectivo de la sucursal, sin autoridad sobre checkout | BDD-SC-484, BDD-SC-485, BDD-SC-486, BDD-SC-487 | TDD-TS-107, TDD-TC-238, TDD-TC-239, TDD-TC-240 | Implementado |

Evidencia operativa de `PRD-FR-208` y `PRD-FR-218`: PCO-004 fue publicado mediante PR #24 y la
compatibilidad histórica gobernada mediante PR #25. El despliegue productivo quedó en
`0038_cash_shift_closures_sales_monitor (head)`; health confirmó PostgreSQL/Redis y el canary vacío
`QA-PCO004` verificó apertura/cierre idempotentes, monitor/drill-down, un cierre operativo y cero
cortes finales. La evidencia detallada y los residuales PostgreSQL aislado/QA visual están en
`docs/implementation-reports/PCO-004.md`.

Evidencia operativa de `PRD-FR-216`: PCO-003 fue publicado y migrado a `0037` en producción el
2026-08-12. El canary empresarial autenticado creó un retiro de 100 centavos, verificó
`500 -> 499 -> 500` MXN y lo compensó, dejando efecto neto cero; la evidencia está en
`docs/implementation-plans/PCO-003-SOL-AUDIT.md`.

Evidencia de implementación de `PRD-FR-219`: PCO-006 pasó dominio/API/contratos, migración SQLite,
Ruff, prueba semántica POS, TypeScript estricto y build en la auditoría local. El gate PostgreSQL
aislado está cableado a CI con `PCO006_TEST_POSTGRES_URL`; la QA visual no pudo ejecutarse porque no
había navegador conectado. Los conteos exactos y residuales están en
`docs/implementation-reports/PCO-006.md`.

| PRD-FR-246 | SDD §49.1/49.2 CAT-CLASS-001; evidencia local, CI/canary pendientes | BDD-SC-531, BDD-SC-532 | TDD-TS-118, TDD-TC-271 | Probado |
| PRD-FR-247 | SDD §49.1/49.3/49.4 CAT-CLASS-001; evidencia local, CI/canary pendientes | BDD-SC-533, BDD-SC-534, BDD-SC-535, BDD-SC-536, BDD-SC-537 | TDD-TS-118, TDD-TC-272, TDD-TC-273, TDD-TC-274, TDD-TC-275, TDD-TC-276 | Probado |
| PRD-FR-248 | SDD §50 RECIPES-UX-001; editor efectivo inmediato sin nueva autoridad backend; evidencia local y auditoría R3 verdes; QA visual/CI pendientes | BDD-SC-538, BDD-SC-539, BDD-SC-540, BDD-SC-541 | TDD-TS-119, TDD-TC-277, TDD-TC-278, TDD-TC-279 | Probado |

| PRD-FR-249 | SDD §51.1/51.2/51.4/51.5 y §61.1; ADR-037/038; producto+SKU/presentación y excepción con evidencia local/auditoría verdes; fecha local, entrega, controles compactos TDD-TC-407 y autocompletado documental/multimodal PUR-AI-CAPTURE-001 TDD-TC-474 implementados con evidencia focal local; PostgreSQL/CI pendientes | BDD-SC-542, BDD-SC-543, BDD-SC-544, BDD-SC-545, BDD-SC-558, BDD-SC-559, BDD-SC-574, BDD-SC-575, BDD-SC-705, BDD-SC-804 | TDD-TS-123, TDD-TS-128, TDD-TS-141, TDD-TC-280, TDD-TC-281, TDD-TC-282, TDD-TC-283, TDD-TC-296, TDD-TC-297, TDD-TC-407, TDD-TC-474 | Probado |
| PRD-FR-250 | SDD §51.3; previews Python puros; sustituye aritmética permitida en §50.2; evidencia local; SR-WORKSPACE-001 cierre local; CI/canary pendientes | BDD-SC-546, BDD-SC-547, BDD-SC-548, BDD-SC-549 | TDD-TS-123, TDD-TC-284, TDD-TC-285 | Probado |
| PRD-FR-251 | SDD §51.1/51.5; ADR-038; proveedor explícito y excepción urgente trazable con no-reprecio probado localmente; PostgreSQL/CI pendientes | BDD-SC-550, BDD-SC-551, BDD-SC-552, BDD-SC-553, BDD-SC-575 | TDD-TS-124, TDD-TS-128, TDD-TC-286, TDD-TC-287, TDD-TC-297 | Probado |
| PRD-FR-252 | SDD §51.6; copia completa con versiones; sin ampliar componentes; SR-WORKSPACE-001 cierre local; CI/canary pendientes | BDD-SC-554, BDD-SC-555, BDD-SC-556, BDD-SC-557 | TDD-TS-124, TDD-TC-288, TDD-TC-289 | Probado |

| PRD-FR-253 | SDD §52.1; captura con dos destinos y modalidad de cobro conservada | BDD-SC-566, BDD-SC-567 | TDD-TS-126, TDD-TC-293 | Probado |
| PRD-FR-254 | SDD §52.1; líneas, notas y complementos | BDD-SC-567 | TDD-TS-126, TDD-TC-293 | Probado |
| PRD-FR-255 | SDD §52.2; borradores aislados y recuperación | BDD-SC-568, BDD-SC-569, BDD-SC-570 | TDD-TS-126, TDD-TC-293 | Probado |
| PRD-FR-256 | SDD §52.1; proyección histórica y estados independientes | BDD-SC-571 | TDD-TS-127, TDD-TC-294 | Probado |
| PRD-FR-257 | SDD §52.3; cálculo Python y confirmación estable | BDD-SC-572 | TDD-TS-127, TDD-TC-294, TDD-TC-295 | Probado |
| PRD-FR-258 | SDD §52.1/52.4; comandos y permisos vigentes | BDD-SC-573 | TDD-TS-127, TDD-TC-295 | Probado |
| PRD-FR-259 | SDD §53; ADR-039; preferencia por sucursal, gateway aditivo y downgrade protegido probados localmente; PostgreSQL/QA visual/CI pendientes | BDD-SC-576, BDD-SC-577 | TDD-TS-129, TDD-TC-298, TDD-TC-299 | Probado |
| PRD-FR-260 | SDD §42/54 UIX-CATALOG-COLOR-001; base clara neutra y regresiones de catálogo; QA visual local, CI pendiente | BDD-SC-578, BDD-SC-579 | TDD-TS-130, TDD-TC-300, TDD-TC-301 | Probado |
| PRD-FR-262 | SDD §55 MODIFIER-SCOPE-001 y §48.7; set corporativo versionado renombrable y archivable, productos componentes configurables, motor POS común y transporte offline aditivo; implementación local con gates runtime R3 pendientes | BDD-SC-592, BDD-SC-593, BDD-SC-594, BDD-SC-595, BDD-SC-596, BDD-SC-597, BDD-SC-598, BDD-SC-614, BDD-SC-797, BDD-SC-798, BDD-SC-799, BDD-SC-800, BDD-SC-801 | TDD-TS-133, TDD-TS-161, TDD-TC-309, TDD-TC-310, TDD-TC-311, TDD-TC-312, TDD-TC-313, TDD-TC-314, TDD-TC-331, TDD-TC-468, TDD-TC-469, TDD-TC-470, TDD-TC-471 | Scaffold |

`PRD-FR-253..258`: Probado describe evidencia local del paquete POS-CAJERO-001, no aprobación
de release. [Evidencia y límites](implementation-plans/POS-CAJERO-001.md): CI se verifica por SHA,
cancelación nueva retirada; recorrido KDS enmendado corregido y probado en SQLite/PostgreSQL.

| PRD-FR-281 | CRM-MOBILE-001 SDD §69; ADR-046; CRM-MOBILE-002 acceso por contraseña y perfil propio; revisión de evidencia en plan CRM-MOBILE-002 | BDD-SC-740, BDD-SC-741, BDD-SC-744 | TDD-TS-153, TDD-TC-435, TDD-TC-436, TDD-TC-437 | Probado |
| PRD-FR-282 | CRM-MOBILE-001 SDD §69; cumpleaños parcial, domicilios y consumo por ID; vinculación segura por cuenta; revisión en plan CRM-MOBILE-002 | BDD-SC-742, BDD-SC-743 | TDD-TS-153, TDD-TC-435, TDD-TC-436, TDD-TC-437 | Probado |

## Requisitos no funcionales

| Requisito | Diseno | Escenario BDD | Suite TDD | Estado |
|---|---|---|---|---|
| PRD-NFR-001 | Offline-first gateway | BDD-SC-001 | TDD-TS-004 | Disenado |
| PRD-NFR-002 | Idempotency and command log; PCO-008P publicado sólo tras CI/PR; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-002, BDD-SC-003, BDD-SC-393, BDD-SC-395, BDD-SC-397, BDD-SC-398, BDD-SC-401, BDD-SC-402, BDD-SC-403, BDD-SC-620, BDD-SC-628 | TDD-TS-004, TDD-TS-009, TDD-TC-171, TDD-TC-173, TDD-TC-175, TDD-TC-176, TDD-TC-179, TDD-TC-180, TDD-TC-181, TDD-TS-136, TDD-TC-337, TDD-TS-137, TDD-TC-346 | Probado |
| PRD-NFR-003 | Performance envelope | Pendiente | Performance tests | Propuesto |
| PRD-NFR-004 | Local latency | BDD-SC-001, BDD-SC-255, BDD-SC-256 | Performance tests, TDD-TS-075 | Propuesto |
| PRD-NFR-005 | Cloud latency | BDD-SC-003 | Performance tests | Propuesto |
| PRD-NFR-006 | Security; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1; diagnóstico histórico sólo lectura SDD57.7 verificado en CI; ejecución productiva no autorizada | BDD-SC-021, BDD-SC-057, BDD-SC-059, BDD-SC-060, BDD-SC-061, BDD-SC-063, BDD-SC-064, BDD-SC-065, BDD-SC-066, BDD-SC-193, BDD-SC-452, BDD-SC-621, BDD-SC-622, BDD-SC-623, BDD-SC-624, BDD-SC-625, BDD-SC-629 | TDD-TS-012, TDD-TS-034, TDD-TS-036, TDD-TS-037, TDD-TS-060, TDD-TC-031, TDD-TC-055, TDD-TC-210, TDD-TS-136, TDD-TC-338, TDD-TC-339, TDD-TC-340, TDD-TC-341, TDD-TC-342, TDD-TC-347 | Scaffold |
| PRD-NFR-007 | Auditability | BDD-SC-007, BDD-SC-012, BDD-SC-021 | TDD-TS-012 | Disenado |
| PRD-NFR-008 | Recovery | Pendiente | Recovery tests | Propuesto |
| PRD-NFR-009 | Observability | BDD-SC-023, BDD-SC-024 | TDD-TS-009, TDD-TS-013 | Scaffold |
| PRD-NFR-010 | Maintainability and pull-request quality ratchet | BDD-SC-024, BDD-SC-195, BDD-SC-255, BDD-SC-261, BDD-SC-420 | TDD-TS-013, TDD-TS-061, TDD-TC-056, TDD-TS-075, TDD-TS-102, TDD-TC-220 | Scaffold |
| PRD-NFR-011 | Portability | BDD-SC-024, BDD-SC-192, Docker/Easypanel | TDD-TS-013, TDD-TC-053, CI checks | Scaffold |
| PRD-NFR-012 | Exact arithmetic; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1; SDD-ADR-010 y RECIPES-DEC-001: captura/visualización de dos decimales aplicada al editor canónico de recetas, preservando precisión interna; evidencia en docs/implementation-reports/RECIPES-DEC-001.md; demás interfaces pendientes | BDD-SC-008, BDD-SC-263, BDD-SC-615, BDD-SC-616, BDD-SC-619, BDD-SC-626, BDD-SC-720, BDD-SC-721, BDD-SC-722 | TDD-TS-001, TDD-TC-071, TDD-TS-136, TDD-TC-332, TDD-TC-333, TDD-TC-336, TDD-TC-343, TDD-TS-150, TDD-TC-420, TDD-TC-421 | Disenado |
| PRD-NFR-013 | Future multi-company | Organization module | TDD-TS-012 | Disenado |
| PRD-NFR-014 | Privacy | Security design | TDD-TS-012 | Propuesto |
| PRD-NFR-015 | Gateway compatibility | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-NFR-016 | Frontend CI quality gate; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-115, BDD-SC-255, BDD-SC-259, BDD-SC-627, BDD-SC-628 | TDD-TS-048, TDD-TC-041, TDD-TS-075, TDD-TS-137, TDD-TC-345, TDD-TC-346 | Scaffold |
| PRD-NFR-017 | Alembic revision capacity and percent-safe ConfigParser adapter | BDD-SC-116, BDD-SC-117, BDD-SC-264 | TDD-TS-049, TDD-TC-042, TDD-TS-075 | Scaffold |
| PRD-NFR-018 | Operational localization | BDD-SC-156, BDD-SC-231, BDD-SC-255, BDD-SC-262 | TDD-TS-055, TDD-TC-048, TDD-TC-064, TDD-TS-075 | Scaffold |
| PRD-NFR-019 | Step-up supervisor authorization | BDD-SC-218, BDD-SC-220, BDD-SC-221 | TDD-TS-065, TDD-TC-060 | Disenado |
| PRD-NFR-020 | PCO-001 aporta autorización acumulativa; PCO-006 implementa actor, permiso, alcance, Dueño exclusivo y respuestas redactadas con auditoría; AUD-CORE-001 SDD §57: correcciones locales y regresiones verificadas; Linux/Docker/CI #343 verificados sobre f2a0afa, cierre Git en plan §12.1 | BDD-SC-271, BDD-SC-291, BDD-SC-327, BDD-SC-328, BDD-SC-331, BDD-SC-332, BDD-SC-621, BDD-SC-625 | TDD-TS-077, TDD-TS-081, TDD-TS-086, TDD-TC-113, TDD-TC-114, TDD-TC-118, TDD-TC-119, TDD-TS-136, TDD-TC-338, TDD-TC-342 | Probado |
| PRD-NFR-021 | Cálculo financiero exacto y append-only implementado para ledger y corte PCO-006; concurrencia PostgreSQL queda como gate CI | BDD-SC-279, BDD-SC-280, BDD-SC-286, BDD-SC-288, BDD-SC-294, BDD-SC-295, BDD-SC-297, BDD-SC-329, BDD-SC-330, BDD-SC-333, BDD-SC-334 | TDD-TS-078, TDD-TS-081, TDD-TS-082, TDD-TC-079, TDD-TC-080, TDD-TC-115, TDD-TC-116, TDD-TC-117, TDD-TC-119, TDD-TC-120, TDD-TC-168 | Probado |
| PRD-NFR-022 | Offline outbox/inbox y reautorización; PostgreSQL PCO-008P pendiente de CI | BDD-SC-289, BDD-SC-393, BDD-SC-394, BDD-SC-395, BDD-SC-396, BDD-SC-397, BDD-SC-398, BDD-SC-399, BDD-SC-400 | TDD-TS-083, TDD-TC-171, TDD-TC-172, TDD-TC-173, TDD-TC-174, TDD-TC-175, TDD-TC-176, TDD-TC-177, TDD-TC-178 | Probado |
| PRD-NFR-023 | Cash security audit and observability; publicación PCO-008P pendiente de CI | BDD-SC-291, BDD-SC-293, BDD-SC-400 | TDD-TS-086, TDD-TS-087, TDD-TC-178 | Probado |
| PRD-NFR-024 | Baseline PCO-001/006/0058 probado conserva historia; extensión BRANCH-SCOPE-001 SDD §58 diseñada y pendiente conserva branch/historial financiero y operativo al seleccionar o reasignar, sin reconstrucción automática | BDD-SC-290, BDD-SC-334, BDD-SC-400, BDD-SC-454, BDD-SC-633, BDD-SC-643, BDD-SC-645 | TDD-TS-084, TDD-TS-087, TDD-TS-138, TDD-TC-120, TDD-TC-178, TDD-TC-211, TDD-TC-215, TDD-TC-350, TDD-TC-353, TDD-TC-355, TDD-TC-356 | Disenado |
| PRD-NFR-025 | Implemented PCO-005B atomic idempotent compensating correction with Python authority, locking, rollback and redaction | BDD-SC-322, BDD-SC-324, BDD-SC-326 | TDD-TC-101, TDD-TC-102, TDD-TC-107, TDD-TC-108, TDD-TC-109, TDD-TC-110 | Implementado |
| PRD-NFR-026 | SDD §39.1: política de repositorio, fixtures sintéticos y contención separada | BDD-SC-358 | TDD-TS-089, TDD-TC-145 | Implementado |
| PRD-NFR-027 | SDD §39.1/39.2/23.1/58.3: éxito sólo por respuesta persistida, replay reautorizado y reemisión recuperable sin secreto plano | BDD-SC-359, BDD-SC-362, BDD-SC-367, BDD-SC-369, BDD-SC-371, BDD-SC-564, BDD-SC-565, BDD-SC-635, BDD-SC-636 | TDD-TS-089, TDD-TS-090, TDD-TS-091, TDD-TS-125, TDD-TS-138, TDD-TC-144, TDD-TC-147, TDD-TC-151, TDD-TC-153, TDD-TC-154, TDD-TC-292, TDD-TC-352 | Disenado |
| PRD-NFR-028 | SDD §39.2: esquema, límites, rate limiting y PII redactada en escritura pública | BDD-SC-368, BDD-SC-372, BDD-SC-376 | TDD-TS-091, TDD-TC-152, TDD-TC-155 | Disenado |
| PRD-NFR-029 | SDD §41, ADR-032/033: OpenRouter sólo en backend, PII redactada, salida estricta y autoridad Python intacta | BDD-SC-409, BDD-SC-410, BDD-SC-411, BDD-SC-412, BDD-SC-413, BDD-SC-415, BDD-SC-416 | TDD-TS-096, TDD-TS-097, TDD-TC-184, TDD-TC-185, TDD-TC-186, TDD-TC-187, TDD-TC-188, TDD-TC-189 | Implementado |
| PRD-NFR-030 | SDD §43, ADR-034: frontera backend default-off, contexto mínimo, logs redactados y autoridad Python probados sin red real | BDD-SC-433, BDD-SC-434, BDD-SC-435, BDD-SC-437, BDD-SC-439, BDD-SC-440 | TDD-TS-099, TDD-TC-194, TDD-TC-195, TDD-TC-196, TDD-TC-197, TDD-TC-198, TDD-TC-199, TDD-TC-203, TDD-TC-204, TDD-TC-205 | Probado |
| PRD-NFR-031 | BRANCH-SCOPE-001 SDD §58.2..58.6; workspace fail-closed, stale response, lease registry/offline, idempotencia, drenado y observabilidad redactada | BDD-SC-631, BDD-SC-632, BDD-SC-634, BDD-SC-636, BDD-SC-637, BDD-SC-638, BDD-SC-639, BDD-SC-641, BDD-SC-642, BDD-SC-643, BDD-SC-644, BDD-SC-645 | TDD-TS-138, TDD-TC-348, TDD-TC-349, TDD-TC-351, TDD-TC-352, TDD-TC-353, TDD-TC-354, TDD-TC-355, TDD-TC-356 | Disenado |
| PRD-NFR-032 | GROKBOT-001 SDD §59.3/59.6/59.7/59.8; ADR-041; autenticación de servicio, esquema estricto, privacidad, reautorización, SSRF, rate limiting distribuido y observabilidad redactada | BDD-SC-649, BDD-SC-650, BDD-SC-655, BDD-SC-656, BDD-SC-658, BDD-SC-660, BDD-SC-661, BDD-SC-665 | TDD-TS-139, TDD-TC-359, TDD-TC-360, TDD-TC-361, TDD-TC-363, TDD-TC-364, TDD-TC-366, TDD-TC-370 | Scaffold |

## Regla de mantenimiento

La [correspondencia de pantallas de Soft Restaurant con historias de análisis](../Pantallas/HISTORIAS.md)
añade evidencia de contexto para catálogos, proveedores, presentaciones, recetas y almacenes.
Sus identificadores locales `SR-HU-*` son identificadores de descubrimiento y no sustituyen
escenarios BDD o pruebas TDD. El paquete ADMIN-RETRO-001 concreta las candidatas SR-HU-16 a 19
y los combos SR-HU-14 mediante PRD-FR-238 a 242 y las filas anteriores. Los estados de esas
filas, no las fotografías, determinan su evidencia de implementación.

No se acepta una nueva historia sin:

- requisito PRD,
- impacto SDD,
- escenario BDD,
- suite y caso TDD,
- estado de implementacion.


Evidencia parcial adicional CORTE-CIEGO-001, TDD-TC-450/462 y BDD-SC-792:
`apps/api/tests/test_corte_ciego_f106_print.py` y
`apps/api/tests/test_corte_ciego_f106_print_postgres.py` cubren metadata humana,
retry contextual y conservación de payload. No cambian el estado global de los
requisitos ni acreditan la entrega técnica a dispositivos o el cierre de fase 1.


Impresión técnica, evidencia parcial BDD-SC-792 / TDD-TC-450/462:
`test_corte_ciego_f106_print_devices.py`, `test_corte_ciego_f106_device_postgres.py`
y schemas `print-ticket-payload-v2` / `print-kitchen-payload-v2`. No acredita hardware,
compatibilidad de consumidores externos ni cierre de fase 1.


Evidencia parcial BDD-SC-768/792 y TDD-TC-450/462: `test_corte_ciego_f106_command_receipts.py`,
`test_corte_ciego_f106_receipt_postgres.py` y schema `order-command-receipt-v2`.
Cubre acuses propios de alta/pago y preview contextual; no cambia el estado global
ni acredita todavía todas las liquidaciones o consumidores de fase 1.

Solicitudes operativas, evidencia parcial BDD-SC-768/792 y TDD-TC-450/461/462:
`test_corte_ciego_f106_intents.py` y `test_corte_ciego_f106_intent_postgres.py`:
lectura vigente del acuse propio, audiencia humana, metadata SQL/JSON, integridad de
compensación y recuperación concurrente. No cambia el estado global ni acredita
las respuestas monetarias de otros comandos o la transición de F1-09.

Movimientos humanos, evidencia parcial BDD-SC-767/768 y TDD-TC-450/451/461:
`test_corte_ciego_f106_movements.py`, `test_corte_ciego_f106_movement_postgres.py`
y contrato `cash-movement-command-receipt-v2.schema.json` cubren acuses, permisos
vigentes, snapshots conservados, duplicados y transacciones reales. La prueba de
sync activo conserva el acuse técnico existente y no acredita el rollout de F1-09.
Los estados globales permanecen pendientes de completar integración y auditoría.

Liquidaciones de repartidores: `test_corte_ciego_f106_settlements.py` vincula
BDD-SC-767/768/792 con TDD-TC-450/451/461/462 (cobertura parcial F1-06).
El selector y los acuses preservan la operación sin conceder lectura financiera;
el estado global sigue pendiente de integración, transición y auditoría.

Reapertura de pedidos: `test_corte_ciego_f106_reopen.py` enlaza BDD-SC-767/768/792
con TDD-TC-450/451/461/462 de F1-06, sin dar por concluida la separación integral
de permisos ni el workflow de corrección de conteos de fase 2.

La evidencia de reapertura se complementa con `test_corte_ciego_f106_reopen_postgres.py`
y `order-reopen-receipt-v2.schema.json`: atomicidad, duplicados, revocación y paridad
de contrato. Mantiene el estado parcial del paquete hasta F1-10/11.

Modificaciones de pedido: `test_corte_ciego_f106_amendments.py`,
`test_corte_ciego_f106_amendment_postgres.py` y contrato
`order-amendment-receipt-v2.schema.json` enlazan BDD-SC-768/792 con
TDD-TC-450/451/461/462 parcial: recuperación propia sin dinero ni reejecución,
historia sin hash, revocación, atomicidad y concurrencia. F1-06 sigue en curso.

Logs de integraciones: `test_corte_ciego_f106_integration_logs.py` y contrato
`integration-log-metadata-v2.schema.json` enlazan BDD-SC-767/768 con
TDD-TC-450/451/461 parcial: listas humanas sin originales, permisos actuales,
auditoría, revalidación y suspensión sin retorno al payload. Conserva el estado
parcial de fase 1; adaptación de Admin y auditoría integral aún pendientes.
`test_corte_ciego_f106_integration_logs_postgres.py` complementa el mismo enlace con
evidencia del dialecto PostgreSQL y atomicidad de auditoría, sin sustituir F1-10/11.

Gastos: `test_corte_ciego_f106_expenses.py` y
`test_corte_ciego_f106_expense_postgres.py` enlazan BDD-SC-767/768/792 con
TDD-TC-450/451/461/462 parcial. Contratos `expense-command-receipt-v2`,
`expense-operational-page-v2` y `expense-draft-v2`: acuses propios, metadata,
borrador acreditado por versión y lecturas financieras separadas. Preservan
confirmación/compensación y abandono terminal; no completan la UI ni transición.
Evidencia parcial F1-06 (PRD-FR-289/290/300; BDD-767/768/792; TC-450/451/462):
`apps/api/tests/test_corte_ciego_f106_cancellations.py` y
`apps/api/tests/test_corte_ciego_f106_cancellation_postgres.py`, contrato
`packages/contracts/schemas/order-cancellation-receipt-v2.schema.json`.
No cierra la fase ni acredita la autorización exacta de acciones pendiente de F1-08.

Evidencia parcial F1-06 (PRD-FR-289/290/300; BDD-767/768/792; TC-450/451/462):
`apps/api/tests/test_corte_ciego_f106_acceptance.py`,
`apps/api/tests/test_corte_ciego_f106_acceptance_postgres.py` y contrato
`packages/contracts/schemas/order-acceptance-receipt-v2.schema.json`.

Evidencia parcial F1-06 / PRD-FR-289/290/300, BDD-767/768/792, TC-450/451/462:
`apps/api/tests/test_corte_ciego_f106_driver_history.py` y
`apps/api/tests/test_corte_ciego_f106_driver_history_postgres.py`.

Evidencia parcial F1-06 / PRD-FR-289/290/300, BDD-767/768/792, TC-450/451/462:
`apps/api/tests/test_corte_ciego_f106_channel_orders.py`,
`apps/api/tests/test_corte_ciego_f106_channel_orders_postgres.py` y contrato
`packages/contracts/schemas/channel-order-operational-v2.schema.json`.

Evidencia parcial adicional F1-06 para BDD-767/792 y TDD-TC-450/462: diagnóstico humano
de sync en `apps/api/tests/test_corte_ciego_f106_sync_events.py` y
`apps/api/tests/test_corte_ciego_f106_sync_events_postgres.py`. No cierra fase 1.

Evidencia parcial F1-09: `apps/api/tests/test_corte_ciego_f109_suspension.py` relaciona
TDD-TC-461/464 y el criterio de reversión sin reapertura de información de CC-D11.
Preflight, clientes y leases todavía no se declaran completos.

Evidencia F1-07 TDD-TC-450/461/462: `tests/frontend/test_corte_ciego_f107_read_context.mjs`
verifica invalidación de respuesta tardía en la frontera compartida del cliente.

F1-07 sesión efectiva: `apps/api/tests/test_corte_ciego_f107_session.py` para
TDD-TC-450/451/461; consumidores aún requieren integración completa.
