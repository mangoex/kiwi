# CORTE-CIEGO-001 — F1-01 inventario de accesos

Base: `abc4e7f`; inspección local 2026-10-21. Inventario estático terminado para
las superficies de caja, ventas y permisos colaterales definidas debajo. No es
certificación productiva ni prueba de ausencia de fugas en runtime. No se consultaron
cuentas, importes ni configuración productiva. Fuente de autoridad: [paquete](CORTE-CIEGO-001.md),
[plan de fase 1](CORTE-CIEGO-001-FASE-1.md) y [SDD técnico](../02-SDD-corte-ciego-fase-1.md).

## 1. Método y criterio de cobertura

1. Inspección AST de decoradores GET/POST/PUT/PATCH/DELETE y prefijos de routers de
   `apps/api/restaurant_os`; revisión de su registro en main.py, incluidos routers
   condicionados por configuración. Manifiesto reproducible en §5 con ruta y handler.
2. Seguimiento de servicios de caja/reportes/autoridad y sus callers: guardas, datos
   devueltos, serialización, resultados almacenados, consultas indirectas y consumidores.
3. Búsqueda transversal de cash-shifts, cash/shifts, cash/user-cuts, payments, reports,
   dashboard, executive-insights, sync, print y campos expected/difference/total en API,
   gateway, cliente compartido, POS/Admin y contratos; revisión manual del dispatcher
   dinámico del gateway y superficies no HTTP en §3.
4. Clasificación explícita de las rutas colaterales: no se presume que cada precio
   individual sea un agregado de caja ni se concede lectura financiera a toda operación.

No hay rutas financieras dinámicas adicionales registradas con add_api_route en los
módulos inspeccionados; el caso api_route del gateway se enumera aparte. Nuevas rutas,
otros commits o plugins externos obligan a actualizar el inventario. Tokens, secretos,
datos de clientes y saldos no se copian como evidencia. La revisión es del checkout,
no del despliegue ni del tráfico real. F1-03 transformará este inventario en pruebas
negativas; el baseline existente no certifica las nuevas restricciones.

## 2. Mapa origen → autoridad actual → dato → destino objetivo

Convenciones destino: O = proyección operativa; F = proyección financiera con concesión;
C = precio/costo de compras o inventario con autoridad administrativa separada;
T = transporte técnico scoped sin lector humano implícito; A = administración gobernada.
Los permisos son los actuales, no afirmación de suficiencia bajo el contrato nuevo.
Las familias del manifiesto remiten a estas filas y al SDD técnico para su resolución.

| Familia | Origen y servicio/guarda actual | Datos y consumidor | Destino y acción requerida |
|---|---|---|---|
| CASH-SHIFT | api.py: current canónico/list/detail/summary → cash.shift.read; alias current → authorize_cash_movement_scope; operations.get_cash_shift_summary/_cash_summary_for_shift | Turno, fondo, closure/summary con componentes y esperado; Settings, Dashboard, API directa | O para estado; F cash.shifts para fondo/componentes/resumen. Incluir ambos alias y cierre anterior, no sólo turno abierto. |
| CASH-WRITE | open/close-operationally y aliases → cash.shift.open/close; operaciones envueltas en operational intents | Respuesta y replay de apertura/cierre con turno/snapshot; Settings y cliente compartido | O por defecto después del comando; F sólo en endpoint financiero separado. No cambiar cálculo ni cierre. |
| CUT | UserCashCutService.create/counted_cash/finalize → cash.user_cut.create; list/detail → cash.user_cut.read; reopen → _require_owner más permisos propios | _public serializa corte completo; _replay devuelve command.result; detalle incluye operaciones/reopen; UserCashCutsPanel | Dividir captura/finalización/acuse y lectura F cash.cuts; reautorizar y reproyectar en todo replay, incluida excepción por key concurrente. |
| MOVEMENT | cash/movements → cash.movement.read; alias cash-movements → cash.shift.read; mutación/compensación con permisos propios | Importes, referencias, acumulación de entradas/salidas; CashMovements, API | F cash.movements para historial; O sólo recibo de acción autorizada. Compensar no hereda lectura global ni nueva autoridad de retiros. |
| REPORT | ReportingProjectionService._filters → reports.sales.read; ingredient_sales → reports.ingredient_sales.read; expenses → reports.expenses.read; delivery_fee_report → reports.sales.read | Ventas, impuestos, descuentos, cantidades/correcciones, gastos/envío; SalesMonitor, PCO007Reports, DeliveryFeeReport | F sales/expenses según datos; consultas de consumo mantienen permiso propio y no deben exponer agregados monetarios por inferencia. O report operativo específico sin campos financieros. |
| RECON | reconciliation_reports daily/consolidated/export → dashboard.read y resolución de sucursal; audit → audit.read/branch.admin.access/admin.manage | Esperado/contado/diferencia, XLSX e historial; BranchDailyReconciliationReport, CorporateReconciliationDashboard | F reconciliation, revisando cada sucursal de consolidado y cada descarga. V1 daily/consolidated/export ya responde upgrade; conservar cierre, no reabrirlo. Anotar revisión no concede lectura por sí sola. |
| DASH | dashboard/overview → dashboard.read → platform_data.get_dashboard_overview | total_revenue_cents, average_ticket_cents, tickets, breakdowns y cantidades; Overview Admin y DashboardOverview POS | Endpoint existente F sales; O separado para encargado, sin reusar payload financiero ocultándolo en UI. |
| AI | admin-ai/executive-insights: actor autenticado; handler llama generate_executive_insights sin guarda financiera/scope visible | executive_ai genera total/ticket promedio y comparación de sucursales; ExecutiveCopilot, posible contexto enviado a proveedor | F por todas las clases/sucursales usadas, ANTES de SQL contextual/modelo; sin contexto financiero para actor operativo. No confiar en prompt o filtro posterior. O de ranking no requiere LLM. |
| AGENT | agent_tools._agent con capability técnica y allowlist; sales/summary agent.sales.read; cash/cuts agent.cash_cuts.read | Agregados de ventas/top, cortes/compensaciones y comandos retenidos; agente externo con router opcional | Conservar identidad técnica; capacidad por sí sola no es delegación humana. Bajo nueva política, salida financiera de agente exige vínculo de audiencia autorizado o queda deshabilitada; no conceder delegación implícita a agente. |
| ORDER | orders/orders.accounts/detail, reopen y POS integraciones → orders.read/guards del dominio; cuentas tiene filtros/cursor y total_cents | Listado monetario potencialmente reconstruible, cuenta individual y correcciones; POS, Order detail, canales | O listado sin importes, detalle individual bajo atención/seguimiento autorizado; F sales para exploración histórica monetaria. Limitar consulta no equivale a sólo paginar. |
| PAYMENT | GET payments → payments.read/list_payments; preview y confirmación por pedido con guardas canónicas | Importes y método, listado por sucursal y recibo; cashierPayment y API | F sales para lista global; O recibo/pagos del pedido autorizado, sin revelar total del turno. No cambiar registro inmutable ni compensaciones. |
| DRIVER | driver-cash-settlements/drivers y POST driver-cash-settlements → dominio de entrega y payments.confirm | Candidatos y total de pedidos/dinero por entrega; liquidación de repartidor | O de entrega concreta con operaciones seleccionadas autorizadas; agregados generales F. Conservar custodia y no duplicar cobros; no ampliar facultades por ocultar vista. |
| PRINT | print-jobs/read/retry → print.jobs.read/retry; pull/claim/ack/fail/recover → print.agent scoped | Payload/ticket monetario, reimpresiones e intentos; worker/dispositivo y lista humana | T limitado al trabajo asignado; O metadata del listado sin payload masivo; ticket individual sólo autoridad de operación. Recibos financieros F antes de generar/descargar. |
| SYNC | sync/commands → gateway.sync y org/branch/device; sync/events/status → sync.events.read o capability técnica; grants/lease/reconcile/handoff → dominio offline | Payloads, command results, eventos retenidos y contexto de sesión; gateway/UI de sincronización | T procesa datos necesarios, no expone campos internos en acuse/listado humano. Reproyección y fencing también al recuperar intents/sync. Lectura financiera online, sin delegación offline en F1. |
| AUTH | auth/session, handoff, branch-selections/reissues; users/roles/permissions → gobierno de autoridad y versionado existente | permissions, admin_capabilities, pos_modules, workspace y grants generales; session POS/Admin | A para cambios y O para capacidades declaradas sin importes; servidor vuelve a autorizar. No introducir permisos financieros en alias compatibles amplios. |
| INTENT | operational-intents y resoluciones; expense-commands y command logs | Recuperación de resultados/estado ante timeout; cliente compartido y gateway | O para estado de comando/recibo autorizado; nunca cuerpo financiero antiguo por recuperar. Validar actor/scope/versión y tipo antes de resolver. |
| PURCHASE | purchases/corporate-purchases/receipts, presentations, XML y original → purchases.read/manage/corporate más guards de servicios | Precios, costos, total factura y cantidades; PurchasesList y recepción | C para importes y originales XML; O recepción contra compra sin costos por defecto. No conceder catalog.manage ni delegación de caja para recibir. |
| CASH-CONTEXT | purchases/cash-context y expenses/cash-context → gestión/withdraw; expense.cash_context devuelve identificadores de turnos abiertos | register_id/cash_shift_id/opened_at; formularios compra/gasto | O: conservar metadata mínima, no adjuntar summary/fondo; estas rutas no se bloquean sólo por nombre cash. |
| EXPENSE | expenses list/detail/summary/commands/confirm/cancel → expenses.read/manage/cancel, reports.expenses.read y retiro/compensación cuando procede | Documentos/importe/summary; ExpensesWorkspace | O del gasto individual autorizado; F expenses para agregado/historial monetario masivo; autoridad administrativa original y guardas del retiro permanecen. |
| INVENTORY | inventory/costs → inventory.read; physical counts → capture/review/approve; previews/recetas por sus permisos | Costo/teórico/diferencia, precio/valoración y captura; módulos inventario/recetas | C para consulta de costos con concesión explícita de función; captura O ciega y revisión/aprobación separadas. Delegación financiera de caja no concede catálogo/ajuste. |
| FISCAL | invoicing list/detail/pdf/xml/receipt/issue/cancel → dominio invoicing.* y emisor/sucursal | Facturas y recibos monetarios individuales/listables | Guardas fiscales siguen; recibo puntual O autorizado, búsqueda/descarga masiva financiera exige F sales además. Delegación no concede emisión/cancelación/configuración. |
| PUBLIC | public tracking/order-intents, mobile y canales externos | Precio/importe del pedido propio, catálogo público e ingreso de payload externo | Mantener autoridad por referencia/cliente/canal, no convertir visitante en empleado ni quitar precio de su compra. Sin turno/esperado/ventas globales; son entradas al ledger, no fuentes de autoridad financiera humana. |
| CUSTOMER | GET customers → orders.read + authorize_branch_scope; list_customers/list_customers_page → get_customer_order_summary | order_count, average_ticket_cents y recent_orders.total_cents; perfil/selector de cliente; summary consulta pedidos por cliente sin scope branch propio | O contacto/domicilio sin resumen monetario; F sales para historia y scope de cada pedido. CRM en customer_ai agrega total_spend_cents y VIP; no basta filtrar origen del cliente. |
| INTEGRATION | integrations/{provider}/logs → admin.manage → channel_service.list_webhook_logs; ingestión por contratos de adaptador | dict de integration_webhook_logs incluye payload_raw, status/error; panel de integración | T conserva original; O metadata de diagnóstico; F sales + autoridad administrativa para payload monetario con scope. No inferir sucursal del usuario si payload no está resuelto: denegar lectura original. |
| CATALOG | Catálogo/previews, suppliers, branch-administration y legacy-imports → guardas propias de catálogo/administración/compra | Precios de venta públicos, costos o documentos administrativos según recurso; pantallas catálogo/administración/importación | O precio de venta necesario para pedido; C costos/precios de compra, imports/XML; A gobierno. No confundir precio visible del menú con agregado de caja. |

Para guards delegadas, los handlers del manifiesto apuntan al servicio de esta tabla;
ausencia de literal de permiso en un handler no significa endpoint público. Salidas
actuales no se certifican seguras sólo por tener algún permiso. En particular la guarda
de catálogo/inventario no sustituye la autorización administrativa de costos acordada.

## 3. Superficies sin ruta única y consumidores

| Superficie | Archivos revisados / evidencia | Tratamiento objetivo |
|---|---|---|
| Resolución de autoridad | operations.require_permission/authorize_branch_scope y _assign_default_role_permissions | Hoy organization_all_permissions puede satisfacer permisos persistidos; nueva guarda financiera exige propietario gobernado o concesión explícita, no sólo require_permission. Revisar cada combinación antes de activar. |
| Compatibilidad y recepción | operations._compatible_permission_codes: purchases.read/manage admiten catalog.manage/admin.manage; inventory.count satisface capture/review/approve. corporate_purchases.receive_corporate_purchase_order exige purchases.corporate.manage organizacional | Resolver explícitamente alias y nueva recepción scoped sin otorgar gestión corporativa. No basta cambiar el permiso en frontend. |
| Replays | UserCashCutService._replay/_store/_public, operational_intents, expenses.command_status | Resultado persistido no es contrato de salida autorizado. Incluir camino de IntegrityError que recupera resultado tras carrera. |
| Cliente compartido | packages/api-client/src/index.ts: requestApi/fetchApi, intents, descarga XLSX v2 | Versión de contrato, nueva proyección y revalidación antes de publicar datos; manejo de error sin cuerpo monetario. |
| POS principal | Settings.tsx, UserCashCutsPanel.tsx/userCashCuts.ts, DashboardOverview.tsx, CashMovements.tsx, SalesMonitor.tsx/salesMonitorState.ts, PCO007Reports.tsx, DeliveryFeeReport.tsx, BranchDailyReconciliationReport.tsx, App.tsx/PosLayout.tsx | Parsers y módulos por capacidades nuevas. Parser de cortes actual requiere campos financieros; debe recibir contrato nuevo, nunca simular zeros para satisfacerlo. |
| Admin | dashboard/Overview.tsx, ExecutiveCopilot.tsx, hubs/ReportsHub.tsx, reports/CorporateReconciliationDashboard.tsx, purchasing/PurchasesList.tsx, expenses/ExpensesWorkspace.tsx, lib/adminSession.tsx/sessionRecovery.ts | Separar reportes, descarga y recepción. No asumir que acceso a Admin autoriza finanzas. |
| Operación individual | features/pos/cashierPayment.ts, CashierPaymentDialog y cuentas POS; módulos de órdenes de integraciones | Importes del pedido atendido, cambio y comprobante no son un resumen del turno; preservar capacidad útil con contexto específico. |
| Gateway cash | local_api.py: POST/GET /api/v1/local/cash/movements; grant firmado org/branch/device; GET usa outbox.list_local_status | Acuse/estado sin listado monetario completo ni datos de otro operador; revisar filtros de actor además de device. |
| Gateway orders | order_local_api.py dispatcher /api/v1/local/order-api/{path:path}; auth/session, cash/shifts/current, orders/accounts y detalle entre ramas permitidas | Aplicar mismas proyecciones O, fencing por política/lease y bloqueo de versión. No dar delegación F a un token offline. Precio individual conservado, agregado prohibido. |
| Persistencia temporal | features/cash/offlineCash.ts guarda grant en sessionStorage; session.ts limpia credenciales/contexto; gateway outbox SQLite | No borrar outbox para revocar; conservar evidencia, invalidar lector/lease y no reconstruir finanzas desde almacenamiento UI. |
| Service worker | pos-web/public/offline-shell-sw.js excluye /api/ y Authorization de caché | Conservar exclusión; invalidar shell incompatible y respuestas tardías. No afirmar que esa exclusión protege toda memoria/UI. |
| Auditoría/logs/diagnóstico | operations._observe_pco006_command/_write_audit, gateway runtime_logging/outbox._record, system_diagnostics | Guardar evidencia sensible protegida; logs sólo metadata. Diagnóstico no debe convertirse en ruta de lecturas monetarias ni imprimir payloads. |
| Contratos existentes | packages/contracts/schemas/cash-shift-* y user-cash-cut-*, reconciliation-*-v2; openapi/kiwi-agent-tools-v1.openapi.yaml | Contratos legacy retenidos como baseline; familias operativa/financiera v2 documentadas en SDD antes de crear schemas ejecutables. |

Las referencias de archivo de esta tabla son relativas a apps/api/restaurant_os,
apps/pos-web/src, apps/admin-web/src o apps/edge-gateway/edge_gateway según su familia.
Los enlaces a handlers en §5 fijan el punto de entrada exacto de la base inspeccionada.
Herramientas del navegador, extensiones ajenas, copias ya descargadas y memoria humana
no pueden revocarse retroactivamente; no se presentan como canales cubiertos por una ACL futura.

## 4. Baseline reproducible y límites

Fixtures actuales: `_new_session` de test_cash_ledger.py usa SQLite aislado; el
cliente de test_cash_concepts.py sobreescribe get_session con fixture local. Los tests
de UserCashCutService cubren dueño/cajero y alcance/estado mediante datos sintéticos.
No son las fixtures completas del contrato nuevo (delegado y política nueva van en F1-03).

Comando de baseline, sin crear código de prueba:

```powershell
.\.venv\Scripts\python.exe -B -m pytest apps/api/tests/test_user_cash_cuts.py apps/api/tests/test_user_cash_cut_contracts.py apps/api/tests/test_cash_shift_operational_close.py -q -p no:cacheprovider
```

Resultado local: **30 passed, 1 skipped** en 75.50 s. El skip es el roundtrip PostgreSQL
por ausencia de `PCO004_TEST_POSTGRES_ROUNDTRIP_URL`; warning de deprecación de
Starlette/httpx. No se añadió silenciamiento. Revisión independiente en el cierre F1-01/02.
Prueba del baseline, no RED/GREEN de F1-03. F1-01 se cierra como inventario estático y
baseline reproducible; explotación dinámica de cada vector, PostgreSQL, gateway y UI
permanecen verificaciones de implementación, no ausencias de rutas en este inventario.

## 5. Manifiesto de rutas de la base inspeccionada

Generado mediante AST sin importar ni arrancar la API. Prefijos v1/v2 resueltos desde
la declaración del router; cada alias es una fila. Incluye entradas colaterales que
pueden devolver datos monetarios individuales, además de agregados. Sus guardas/datos/
consumidores/destino se describen por familia en §2; no es un listado de rutas ya corregidas.
Gateway dinámico se describe en §3 y no se confunde con rutas centrales.

407 entradas de decoradores centrales (260 principales y 147 colaterales adicionales), equivalentes a 405 combinaciones método/ruta únicas. Exclusiones: configuración general de organización/sucursal, almacenes, asistencia, lotes de producción, KDS y tarifas/alcances de entrega sin lectura de caja. Sus interfaces operativas conservan autoridad propia; cualquier embedding monetario agregado queda sujeto al SDD. Catálogos, clientes y logs de integraciones se incluyen expresamente por sus salidas indirectas.

| Familia | Método y ruta | Archivo / handler / línea base |
|---|---|---|
| INTENT | `POST /api/v1/operational-intents` | [api.py](../../apps/api/restaurant_os/api.py) · `prepare_operational_intent` · 635 |
| INTENT | `GET /api/v1/operational-intents` | [api.py](../../apps/api/restaurant_os/api.py) · `pending_operational_intents` · 659 |
| INTENT | `POST /api/v1/operational-intents/{intent_id}/resolve` | [api.py](../../apps/api/restaurant_os/api.py) · `resolve_operational_intent` · 673 |
| DASH | `GET /api/v1/dashboard/overview` | [api.py](../../apps/api/restaurant_os/api.py) · `get_dashboard_overview_endpoint` · 702 |
| AUTH | `POST /api/v1/auth/login` | [api.py](../../apps/api/restaurant_os/api.py) · `login` · 720 |
| AUTH | `POST /api/v1/auth/supervisor-authorize` | [api.py](../../apps/api/restaurant_os/api.py) · `supervisor_authorize_endpoint` · 736 |
| AUTH | `GET /api/v1/auth/session` | [api.py](../../apps/api/restaurant_os/api.py) · `get_authenticated_session_endpoint` · 760 |
| AUTH | `POST /api/v1/auth/branch-selections` | [api.py](../../apps/api/restaurant_os/api.py) · `select_authenticated_pos_branch_endpoint` · 802 |
| AUTH | `POST /api/v1/auth/branch-context-reissues` | [api.py](../../apps/api/restaurant_os/api.py) · `reissue_authenticated_branch_context_endpoint` · 816 |
| AUTH | `POST /api/v1/auth/pos-handoffs` | [api.py](../../apps/api/restaurant_os/api.py) · `issue_pos_session_handoff_endpoint` · 832 |
| AUTH | `POST /api/v1/auth/pos-handoffs/exchange` | [api.py](../../apps/api/restaurant_os/api.py) · `exchange_pos_session_handoff_endpoint` · 842 |
| DRIVER | `GET /api/v1/driver-cash-settlements/drivers` | [api.py](../../apps/api/restaurant_os/api.py) · `get_driver_cash_settlement_candidates` · 983 |
| AUTH | `GET /api/v1/roles` | [api.py](../../apps/api/restaurant_os/api.py) · `get_roles` · 1056 |
| AUTH | `POST /api/v1/roles` | [api.py](../../apps/api/restaurant_os/api.py) · `post_role` · 1070 |
| AUTH | `GET /api/v1/users` | [api.py](../../apps/api/restaurant_os/api.py) · `get_users` · 1083 |
| AUTH | `POST /api/v1/users` | [api.py](../../apps/api/restaurant_os/api.py) · `post_user` · 1097 |
| AUTH | `POST /api/v1/users/{user_id}/roles` | [api.py](../../apps/api/restaurant_os/api.py) · `post_user_role` · 1126 |
| ORDER | `POST /api/v1/orders/assisted-draft` | [api.py](../../apps/api/restaurant_os/api.py) · `post_assisted_order_draft` · 1159 |
| AI | `POST /api/v1/admin-ai/proposals` | [api.py](../../apps/api/restaurant_os/api.py) · `post_admin_ai_proposal` · 1217 |
| AI | `GET /api/v1/admin-ai/proposals/{proposal_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_admin_ai_proposal` · 1292 |
| AI | `POST /api/v1/admin-ai/proposals/{proposal_id}/review` | [api.py](../../apps/api/restaurant_os/api.py) · `post_admin_ai_review` · 1303 |
| AI | `POST /api/v1/admin-ai/executive-insights` | [api.py](../../apps/api/restaurant_os/api.py) · `post_executive_ai_insights` · 1340 |
| AI | `POST /api/v1/admin-ai/suggested-purchases` | [api.py](../../apps/api/restaurant_os/api.py) · `post_suggested_purchases` · 1377 |
| AI | `GET /api/v1/admin-ai/inventory-yield-audit` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_yield_audit` · 1418 |
| AI | `POST /api/v1/admin-ai/parse-invoice-ocr` | [api.py](../../apps/api/restaurant_os/api.py) · `post_parse_invoice_ocr` · 1444 |
| PUBLIC | `POST /api/v1/public/order-upsell-recommendations` | [api.py](../../apps/api/restaurant_os/api.py) · `post_public_order_upsell_recommendations` · 1467 |
| AI | `POST /api/v1/admin-ai/customer-recommendations` | [api.py](../../apps/api/restaurant_os/api.py) · `post_customer_recommendations` · 1490 |
| AI | `GET /api/v1/admin-ai/customer-crm-segments` | [api.py](../../apps/api/restaurant_os/api.py) · `get_customer_crm_segments` · 1520 |
| AI | `POST /api/v1/admin-ai/customer-retargeting-message` | [api.py](../../apps/api/restaurant_os/api.py) · `post_customer_retargeting_message` · 1544 |
| INVENTORY | `GET /api/v1/inventory/overview` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_overview` · 1782 |
| INVENTORY | `GET /api/v1/inventory/stock` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_stock` · 1823 |
| INVENTORY | `GET /api/v1/inventory/kardex` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_kardex` · 1838 |
| INVENTORY | `POST /api/v1/inventory/opening-balances` | [api.py](../../apps/api/restaurant_os/api.py) · `post_inventory_opening_balance` · 1854 |
| INVENTORY | `GET /api/v1/recipes` | [api.py](../../apps/api/restaurant_os/api.py) · `get_recipes` · 1876 |
| CASH-SHIFT | `GET /api/v1/cash/shifts/current` | [api.py](../../apps/api/restaurant_os/api.py) · `get_current_cash_shift` · 1894 |
| CASH-SHIFT | `GET /api/v1/cash-shifts/current` | [api.py](../../apps/api/restaurant_os/api.py) · `get_current_cash_shift_legacy` · 1949 |
| CASH-WRITE | `POST /api/v1/cash/shifts/open` | [api.py](../../apps/api/restaurant_os/api.py) · `open_current_cash_shift` · 1975 |
| CASH-WRITE | `POST /api/v1/cash-shifts/open` | [api.py](../../apps/api/restaurant_os/api.py) · `open_current_cash_shift` · 1975 |
| CASH-SHIFT | `GET /api/v1/cash-shifts/summary` | [api.py](../../apps/api/restaurant_os/api.py) · `get_current_cash_shift_summary` · 2100 |
| CASH-WRITE | `POST /api/v1/cash-shifts/close` | [api.py](../../apps/api/restaurant_os/api.py) · `close_current_cash_shift` · 2122 |
| CASH-WRITE | `POST /api/v1/cash/shifts/{cash_shift_id}/close-operationally` | [api.py](../../apps/api/restaurant_os/api.py) · `close_cash_shift_operational_endpoint` · 2229 |
| CASH-SHIFT | `GET /api/v1/cash/shifts` | [api.py](../../apps/api/restaurant_os/api.py) · `list_cash_shifts_endpoint` · 2287 |
| CASH-SHIFT | `GET /api/v1/cash/shifts/{cash_shift_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_cash_shift_endpoint` · 2336 |
| CUT | `POST /api/v1/cash/user-cuts` | [api.py](../../apps/api/restaurant_os/api.py) · `create_user_cash_cut_endpoint` · 2374 |
| CUT | `GET /api/v1/cash/user-cuts` | [api.py](../../apps/api/restaurant_os/api.py) · `list_user_cash_cuts_endpoint` · 2393 |
| CUT | `GET /api/v1/cash/user-cuts/{cash_cut_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_user_cash_cut_endpoint` · 2429 |
| CUT | `POST /api/v1/cash/user-cuts/{cash_cut_id}/counted-cash` | [api.py](../../apps/api/restaurant_os/api.py) · `count_user_cash_cut_endpoint` · 2445 |
| CUT | `POST /api/v1/cash/user-cuts/{cash_cut_id}/finalize` | [api.py](../../apps/api/restaurant_os/api.py) · `finalize_user_cash_cut_endpoint` · 2466 |
| CUT | `POST /api/v1/cash/user-cuts/{cash_cut_id}/reopen-requests` | [api.py](../../apps/api/restaurant_os/api.py) · `request_user_cash_cut_reopen_endpoint` · 2487 |
| CUT | `POST /api/v1/cash/user-cuts/reopen-requests/{request_id}/approve` | [api.py](../../apps/api/restaurant_os/api.py) · `approve_user_cash_cut_reopen_endpoint` · 2508 |
| CUT | `POST /api/v1/cash/user-cuts/reopen-requests/{request_id}/reject` | [api.py](../../apps/api/restaurant_os/api.py) · `reject_user_cash_cut_reopen_endpoint` · 2532 |
| CUT | `POST /api/v1/cash/user-cuts/reopen-requests/{request_id}/compensate` | [api.py](../../apps/api/restaurant_os/api.py) · `compensate_user_cash_cut_reopen_endpoint` · 2556 |
| REPORT | `GET /api/v1/reports/sales-monitor` | [api.py](../../apps/api/restaurant_os/api.py) · `sales_monitor_endpoint` · 2579 |
| REPORT | `GET /api/v1/reports/sales-monitor/drill-down` | [api.py](../../apps/api/restaurant_os/api.py) · `sales_monitor_drill_down_endpoint` · 2610 |
| REPORT | `GET /api/v1/reports/ingredient-sales` | [api.py](../../apps/api/restaurant_os/api.py) · `ingredient_sales_report_endpoint` · 2647 |
| REPORT | `GET /api/v1/reports/expenses` | [api.py](../../apps/api/restaurant_os/api.py) · `expenses_report_endpoint` · 2674 |
| RECON | `GET /api/v1/reports/branch-reconciliation/daily` | [api.py](../../apps/api/restaurant_os/api.py) · `legacy_reconciliation_daily_endpoint` · 2717 |
| RECON | `GET /api/v1/reports/branch-reconciliation/consolidated` | [api.py](../../apps/api/restaurant_os/api.py) · `legacy_reconciliation_consolidated_endpoint` · 2729 |
| RECON | `GET /api/v1/reports/branch-reconciliation/export` | [api.py](../../apps/api/restaurant_os/api.py) · `legacy_reconciliation_export_endpoint` · 2742 |
| RECON | `GET /api/v2/reports/branch-reconciliation/daily` | [api.py](../../apps/api/restaurant_os/api.py) · `branch_reconciliation_daily_endpoint` · 2755 |
| RECON | `GET /api/v2/reports/branch-reconciliation/consolidated` | [api.py](../../apps/api/restaurant_os/api.py) · `branch_reconciliation_consolidated_endpoint` · 2776 |
| RECON | `POST /api/v1/reports/branch-reconciliation/audit` | [api.py](../../apps/api/restaurant_os/api.py) · `branch_reconciliation_audit_endpoint` · 2798 |
| RECON | `GET /api/v2/reports/branch-reconciliation/export` | [api.py](../../apps/api/restaurant_os/api.py) · `branch_reconciliation_export_endpoint` · 2815 |
| ORDER | `GET /api/v1/orders` | [api.py](../../apps/api/restaurant_os/api.py) · `get_recent_orders` · 2839 |
| ORDER | `GET /api/v1/orders/accounts` | [api.py](../../apps/api/restaurant_os/api.py) · `get_order_accounts` · 2854 |
| ORDER | `GET /api/v1/orders/pending-count` | [api.py](../../apps/api/restaurant_os/api.py) · `get_pending_order_count` · 2891 |
| ORDER | `POST /api/v1/orders/{order_id}/reopen-requests` | [api.py](../../apps/api/restaurant_os/api.py) · `create_order_reopen_request_endpoint` · 2902 |
| ORDER | `GET /api/v1/orders/reopen-requests` | [api.py](../../apps/api/restaurant_os/api.py) · `get_order_reopen_requests` · 2917 |
| ORDER | `POST /api/v1/orders/reopen-requests/{request_id}/approve` | [api.py](../../apps/api/restaurant_os/api.py) · `approve_order_reopen_request_endpoint` · 2937 |
| ORDER | `POST /api/v1/orders/reopen-requests/{request_id}/reject` | [api.py](../../apps/api/restaurant_os/api.py) · `reject_order_reopen_request_endpoint` · 2954 |
| ORDER | `POST /api/v1/orders/reopen-requests/{request_id}/apply` | [api.py](../../apps/api/restaurant_os/api.py) · `apply_order_reopen_request_endpoint` · 2971 |
| ORDER | `POST /api/v1/orders/quote` | [api.py](../../apps/api/restaurant_os/api.py) · `quote_order` · 2986 |
| DRIVER | `POST /api/v1/driver-cash-settlements` | [api.py](../../apps/api/restaurant_os/api.py) · `post_driver_cash_settlement` · 3021 |
| AUTH | `POST /api/v1/orders/adjustments/authorize` | [api.py](../../apps/api/restaurant_os/api.py) · `authorize_order_adjustment_endpoint` · 3056 |
| ORDER | `POST /api/v1/orders/{order_id}/fulfillment/{command}` | [api.py](../../apps/api/restaurant_os/api.py) · `fulfill_order_endpoint` · 3090 |
| ORDER | `POST /api/v1/orders` | [api.py](../../apps/api/restaurant_os/api.py) · `create_order` · 3117 |
| ORDER | `POST /api/v1/orders/recover` | [api.py](../../apps/api/restaurant_os/api.py) · `recover_order_creation` · 3207 |
| PUBLIC | `GET /api/v1/public/branches` | [api.py](../../apps/api/restaurant_os/api.py) · `public_branches_endpoint` · 3228 |
| PUBLIC | `GET /api/v1/public/catalog` | [api.py](../../apps/api/restaurant_os/api.py) · `public_catalog_endpoint` · 3247 |
| PUBLIC | `GET /api/v1/public/branches/{public_key}/catalog` | [api.py](../../apps/api/restaurant_os/api.py) · `public_catalog_by_key_endpoint` · 3346 |
| PUBLIC | `POST /api/v1/public/branches/{public_key}/order-intents` | [api.py](../../apps/api/restaurant_os/api.py) · `create_public_order_intent_endpoint` · 3357 |
| PUBLIC | `GET /api/v1/public/order-intents/{public_reference}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_public_order_intent_endpoint` · 3467 |
| PUBLIC | `POST /api/v1/public/feedback` | [api.py](../../apps/api/restaurant_os/api.py) · `submit_customer_feedback_endpoint` · 3505 |
| PUBLIC | `POST /api/v1/order-intents/{intent_id}/accept` | [api.py](../../apps/api/restaurant_os/api.py) · `accept_public_order_intent_endpoint` · 3584 |
| PUBLIC | `POST /api/v1/order-intents/{intent_id}/reject` | [api.py](../../apps/api/restaurant_os/api.py) · `reject_public_order_intent_endpoint` · 3609 |
| PUBLIC | `POST /api/v1/public/orders` | [api.py](../../apps/api/restaurant_os/api.py) · `public_create_order` · 3634 |
| ORDER | `GET /api/v1/orders/{order_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_order_detail_endpoint` · 3639 |
| ORDER | `POST /api/v1/orders/{order_id}/accept` | [api.py](../../apps/api/restaurant_os/api.py) · `accept_order_endpoint` · 3650 |
| ORDER | `PUT /api/v1/orders/{order_id}/delivery-assignment` | [api.py](../../apps/api/restaurant_os/api.py) · `put_order_delivery_assignment` · 3693 |
| ORDER | `POST /api/v1/orders/{order_id}/amendments` | [api.py](../../apps/api/restaurant_os/api.py) · `amend_order_endpoint` · 3712 |
| ORDER | `POST /api/v1/orders/{order_id}/cancel` | [api.py](../../apps/api/restaurant_os/api.py) · `cancel_order_endpoint` · 3736 |
| ORDER | `POST /api/v1/orders/{order_id}/payment-preview` | [api.py](../../apps/api/restaurant_os/api.py) · `preview_order_payment_endpoint` · 3752 |
| PAYMENT | `POST /api/v1/orders/{order_id}/payments` | [api.py](../../apps/api/restaurant_os/api.py) · `create_order_payment` · 3784 |
| ORDER | `POST /api/v1/orders/{order_id}/repeat` | [api.py](../../apps/api/restaurant_os/api.py) · `repeat_order_endpoint` · 3850 |
| PAYMENT | `GET /api/v1/payments` | [api.py](../../apps/api/restaurant_os/api.py) · `get_payments` · 3863 |
| PRINT | `GET /api/v1/print-jobs` | [api.py](../../apps/api/restaurant_os/api.py) · `get_print_jobs` · 3931 |
| PRINT | `POST /api/v1/print-jobs/{job_id}/retry` | [api.py](../../apps/api/restaurant_os/api.py) · `retry_print_job_endpoint` · 3944 |
| PRINT | `GET /api/v1/print-attempts/pull` | [api.py](../../apps/api/restaurant_os/api.py) · `pull_print_attempts` · 3967 |
| PRINT | `POST /api/v1/print-attempts/{attempt_id}/claim` | [api.py](../../apps/api/restaurant_os/api.py) · `claim_print_attempt_endpoint` · 3979 |
| PRINT | `POST /api/v1/print-attempts/{attempt_id}/ack` | [api.py](../../apps/api/restaurant_os/api.py) · `acknowledge_print_attempt_endpoint` · 3998 |
| PRINT | `POST /api/v1/print-attempts/{attempt_id}/fail` | [api.py](../../apps/api/restaurant_os/api.py) · `fail_print_attempt_endpoint` · 4024 |
| PRINT | `POST /api/v1/print-attempts/{attempt_id}/recover-expired-claim` | [api.py](../../apps/api/restaurant_os/api.py) · `recover_expired_print_claim_endpoint` · 4048 |
| SYNC | `POST /api/v1/sync/commands` | [api.py](../../apps/api/restaurant_os/api.py) · `sync_command` · 4079 |
| AUTH | `POST /api/v1/auth/offline-grants` | [api.py](../../apps/api/restaurant_os/api.py) · `offline_cash_grant` · 4108 |
| SYNC | `GET /api/v1/sync/events` | [api.py](../../apps/api/restaurant_os/api.py) · `get_sync_events` · 4131 |
| SYNC | `GET /api/v1/sync/status` | [api.py](../../apps/api/restaurant_os/api.py) · `sync_status` · 4158 |
| AUTH | `PUT /api/v1/users/{user_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_user` · 4173 |
| AUTH | `DELETE /api/v1/users/{user_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_user_endpoint` · 4244 |
| PURCHASE | `POST /api/v1/purchases/xml-imports/branches/{branch_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `post_supplier_xml_original` · 4507 |
| PURCHASE | `POST /api/v1/purchases/xml-imports/resolve` | [api.py](../../apps/api/restaurant_os/api.py) · `resolve_supplier_xml_command` · 4532 |
| PURCHASE | `GET /api/v1/purchases/xml-imports/{import_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_supplier_xml_metadata` · 4550 |
| PURCHASE | `GET /api/v1/purchases/xml-imports/{import_id}/original` | [api.py](../../apps/api/restaurant_os/api.py) · `get_supplier_xml_original` · 4560 |
| AUTH | `PUT /api/v1/roles/{role_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_role` · 4588 |
| AUTH | `DELETE /api/v1/roles/{role_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_role_endpoint` · 4602 |
| AUTH | `GET /api/v1/permissions` | [api.py](../../apps/api/restaurant_os/api.py) · `get_permissions` · 4613 |
| AUTH | `GET /api/v1/roles/{role_id}/permissions` | [api.py](../../apps/api/restaurant_os/api.py) · `get_role_permissions` · 4627 |
| AUTH | `PUT /api/v1/roles/{role_id}/permissions` | [api.py](../../apps/api/restaurant_os/api.py) · `put_role_permissions` · 4642 |
| INVENTORY | `GET /api/v1/inventory/units` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_units` · 4713 |
| INVENTORY | `POST /api/v1/inventory/units` | [api.py](../../apps/api/restaurant_os/api.py) · `post_inventory_unit` · 4728 |
| INVENTORY | `PUT /api/v1/inventory/units/{unit_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_inventory_unit` · 4745 |
| INVENTORY | `GET /api/v1/inventory/items` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_items` · 4764 |
| INVENTORY | `POST /api/v1/inventory/items` | [api.py](../../apps/api/restaurant_os/api.py) · `post_inventory_item` · 4779 |
| INVENTORY | `PUT /api/v1/inventory/items/{item_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_inventory_item` · 4796 |
| INVENTORY | `GET /api/v1/products/{product_id}/recipe` | [api.py](../../apps/api/restaurant_os/api.py) · `get_recipe` · 4973 |
| INVENTORY | `GET /api/v1/recipes/workspace` | [api.py](../../apps/api/restaurant_os/api.py) · `get_recipes_workspace_route` · 4988 |
| INVENTORY | `POST /api/v1/recipes/ai-parse` | [api.py](../../apps/api/restaurant_os/api.py) · `post_recipe_ai_parse` · 5007 |
| INVENTORY | `PUT /api/v1/products/{product_id}/recipe` | [api.py](../../apps/api/restaurant_os/api.py) · `put_recipe` · 5235 |
| INVENTORY | `POST /api/v1/admin-catalog/recipes/bulk-preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_admin_bulk_recipe_preview` · 5359 |
| INVENTORY | `POST /api/v1/admin-catalog/recipes/bulk-apply` | [api.py](../../apps/api/restaurant_os/api.py) · `post_admin_bulk_recipe_apply` · 5378 |
| INVENTORY | `GET /api/v1/admin-catalog/items/{item_id}/recipe-usages` | [api.py](../../apps/api/restaurant_os/api.py) · `get_admin_recipe_usages` · 5458 |
| INVENTORY | `POST /api/v1/production-recipes` | [api.py](../../apps/api/restaurant_os/api.py) · `post_production_recipe` · 6054 |
| PURCHASE | `POST /api/v1/purchases/preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_purchase_preview` · 6326 |
| PURCHASE | `GET /api/v1/corporate-purchases/options` | [api.py](../../apps/api/restaurant_os/api.py) · `get_corporate_purchase_options` · 6337 |
| PURCHASE | `GET /api/v1/corporate-purchases` | [api.py](../../apps/api/restaurant_os/api.py) · `get_corporate_purchases` · 6349 |
| PURCHASE | `GET /api/v1/corporate-purchases/{order_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_corporate_purchase` · 6365 |
| PURCHASE | `POST /api/v1/corporate-purchases` | [api.py](../../apps/api/restaurant_os/api.py) · `post_corporate_purchase` · 6380 |
| PURCHASE | `POST /api/v1/corporate-purchases/{order_id}/approve` | [api.py](../../apps/api/restaurant_os/api.py) · `approve_corporate_purchase` · 6398 |
| PURCHASE | `POST /api/v1/corporate-purchases/{order_id}/receipts` | [api.py](../../apps/api/restaurant_os/api.py) · `receive_corporate_purchase` · 6417 |
| PURCHASE | `POST /api/v1/corporate-purchases/{order_id}/cancel` | [api.py](../../apps/api/restaurant_os/api.py) · `cancel_corporate_purchase` · 6436 |
| PURCHASE | `POST /api/v1/purchase-presentations/preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_presentation_preview` · 6455 |
| INVENTORY | `POST /api/v1/recipes/{product_id}/preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_recipe_preview` · 6466 |
| INVENTORY | `POST /api/v1/inventory/items/{item_id}/cost-preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_item_cost_preview` · 6478 |
| PURCHASE | `GET /api/v1/purchase-presentations` | [api.py](../../apps/api/restaurant_os/api.py) · `get_purchase_presentations` · 6490 |
| PURCHASE | `POST /api/v1/purchase-presentations` | [api.py](../../apps/api/restaurant_os/api.py) · `post_purchase_presentation` · 6505 |
| PURCHASE | `PUT /api/v1/purchase-presentations/{presentation_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_purchase_presentation` · 6516 |
| PURCHASE | `PUT /api/v1/purchase-presentations/{presentation_id}/price` | [api.py](../../apps/api/restaurant_os/api.py) · `put_purchase_presentation_price` · 6530 |
| PURCHASE | `GET /api/v1/purchases` | [api.py](../../apps/api/restaurant_os/api.py) · `get_purchases` · 6546 |
| PURCHASE | `POST /api/v1/purchases` | [api.py](../../apps/api/restaurant_os/api.py) · `post_purchase` · 6561 |
| CASH-CONTEXT | `GET /api/v1/purchases/cash-context` | [api.py](../../apps/api/restaurant_os/api.py) · `purchase_cash_context` · 6585 |
| PURCHASE | `POST /api/v1/purchases/{purchase_id}/confirm` | [api.py](../../apps/api/restaurant_os/api.py) · `confirm_purchase_endpoint` · 6601 |
| PURCHASE | `POST /api/v1/purchases/{purchase_id}/cancel` | [api.py](../../apps/api/restaurant_os/api.py) · `cancel_purchase_endpoint` · 6627 |
| MOVEMENT | `GET /api/v1/cash/concepts/effective` | [api.py](../../apps/api/restaurant_os/api.py) · `get_effective_cash_concepts` · 6649 |
| MOVEMENT | `GET /api/v1/cash/concepts` | [api.py](../../apps/api/restaurant_os/api.py) · `get_cash_concepts` · 6670 |
| MOVEMENT | `POST /api/v1/cash/concepts` | [api.py](../../apps/api/restaurant_os/api.py) · `post_cash_concept` · 6680 |
| MOVEMENT | `PUT /api/v1/cash/concepts/{concept_id}/versions` | [api.py](../../apps/api/restaurant_os/api.py) · `put_cash_concept_version` · 6694 |
| MOVEMENT | `POST /api/v1/cash/concepts/{concept_id}/archive` | [api.py](../../apps/api/restaurant_os/api.py) · `post_cash_concept_archive` · 6711 |
| MOVEMENT | `POST /api/v1/cash/movements` | [api.py](../../apps/api/restaurant_os/api.py) · `post_cash_movement` · 6725 |
| MOVEMENT | `POST /api/v1/cash/movements/{movement_id}/compensations` | [api.py](../../apps/api/restaurant_os/api.py) · `post_cash_movement_compensation` · 6763 |
| MOVEMENT | `GET /api/v1/cash/movements` | [api.py](../../apps/api/restaurant_os/api.py) · `get_cash_movement_ledger` · 6802 |
| MOVEMENT | `GET /api/v1/cash-movements` | [api.py](../../apps/api/restaurant_os/api.py) · `get_cash_movements` · 6833 |
| INVENTORY | `GET /api/v1/inventory/costs` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_costs` · 6845 |
| INVENTORY | `GET /api/v1/inventory/waste-reasons` | [api.py](../../apps/api/restaurant_os/api.py) · `get_waste_reasons` · 6857 |
| INVENTORY | `POST /api/v1/inventory/waste-reasons` | [api.py](../../apps/api/restaurant_os/api.py) · `post_waste_reason` · 6872 |
| INVENTORY | `PUT /api/v1/inventory/waste-reasons/{reason_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_waste_reason` · 6883 |
| INVENTORY | `GET /api/v1/inventory/wastes` | [api.py](../../apps/api/restaurant_os/api.py) · `get_waste_records_endpoint` · 6895 |
| INVENTORY | `POST /api/v1/inventory/wastes` | [api.py](../../apps/api/restaurant_os/api.py) · `post_waste_record_endpoint` · 6911 |
| INVENTORY | `POST /api/v1/inventory/wastes/{waste_id}/confirm` | [api.py](../../apps/api/restaurant_os/api.py) · `confirm_waste_record_endpoint` · 6923 |
| INVENTORY | `POST /api/v1/inventory/wastes/{waste_id}/reverse` | [api.py](../../apps/api/restaurant_os/api.py) · `reverse_waste_record_endpoint` · 6937 |
| INVENTORY | `GET /api/v1/inventory/transfer-destinations` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_transfer_destinations` · 6954 |
| INVENTORY | `GET /api/v1/inventory/transfers` | [api.py](../../apps/api/restaurant_os/api.py) · `get_inventory_transfers_endpoint` · 6987 |
| INVENTORY | `POST /api/v1/inventory/transfers` | [api.py](../../apps/api/restaurant_os/api.py) · `post_inventory_transfer_endpoint` · 7003 |
| INVENTORY | `POST /api/v1/inventory/transfers/{transfer_id}/send` | [api.py](../../apps/api/restaurant_os/api.py) · `send_inventory_transfer_endpoint` · 7014 |
| INVENTORY | `POST /api/v1/inventory/transfers/{transfer_id}/receive` | [api.py](../../apps/api/restaurant_os/api.py) · `receive_inventory_transfer_endpoint` · 7028 |
| INVENTORY | `POST /api/v1/inventory/transfers/{transfer_id}/cancel` | [api.py](../../apps/api/restaurant_os/api.py) · `cancel_inventory_transfer_endpoint` · 7045 |
| INVENTORY | `GET /api/v1/inventory/physical-counts` | [api.py](../../apps/api/restaurant_os/api.py) · `get_physical_counts_endpoint` · 7061 |
| INVENTORY | `GET /api/v1/inventory/physical-counts/options` | [api.py](../../apps/api/restaurant_os/api.py) · `get_physical_count_options_endpoint` · 7076 |
| INVENTORY | `POST /api/v1/inventory/physical-counts` | [api.py](../../apps/api/restaurant_os/api.py) · `post_physical_count_endpoint` · 7094 |
| INVENTORY | `PUT /api/v1/inventory/physical-counts/{count_id}/lines/{line_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_physical_count_line_endpoint` · 7105 |
| INVENTORY | `PUT /api/v1/inventory/physical-counts/{count_id}/lines/{line_id}/entries` | [api.py](../../apps/api/restaurant_os/api.py) · `put_physical_count_line_entries_endpoint` · 7127 |
| INVENTORY | `PUT /api/v1/inventory/physical-counts/{count_id}/lines` | [api.py](../../apps/api/restaurant_os/api.py) · `put_physical_count_lines_endpoint` · 7150 |
| INVENTORY | `POST /api/v1/inventory/physical-counts/{count_id}/submit` | [api.py](../../apps/api/restaurant_os/api.py) · `submit_physical_count_endpoint` · 7169 |
| INVENTORY | `POST /api/v1/inventory/physical-counts/{count_id}/approve` | [api.py](../../apps/api/restaurant_os/api.py) · `approve_physical_count_endpoint` · 7180 |
| INVENTORY | `POST /api/v1/inventory/physical-counts/{count_id}/close` | [api.py](../../apps/api/restaurant_os/api.py) · `close_physical_count_endpoint` · 7194 |
| INVENTORY | `POST /api/v1/inventory/physical-counts/{count_id}/cancel` | [api.py](../../apps/api/restaurant_os/api.py) · `cancel_physical_count_endpoint` · 7205 |
| ORDER | `GET /api/v1/pos/uber-eats/orders` | [api.py](../../apps/api/restaurant_os/api.py) · `get_pos_uber_eats_orders` · 8790 |
| ORDER | `POST /api/v1/pos/uber-eats/orders/{order_id}/status` | [api.py](../../apps/api/restaurant_os/api.py) · `post_pos_uber_eats_order_status` · 8803 |
| ORDER | `GET /api/v1/pos/didi-food/orders` | [api.py](../../apps/api/restaurant_os/api.py) · `get_pos_didi_food_orders` · 8818 |
| ORDER | `POST /api/v1/pos/didi-food/orders/{order_id}/status` | [api.py](../../apps/api/restaurant_os/api.py) · `post_pos_didi_food_order_status` · 8831 |
| ORDER | `GET /api/v1/pos/rappi/orders` | [api.py](../../apps/api/restaurant_os/api.py) · `get_pos_rappi_orders` · 8846 |
| ORDER | `POST /api/v1/pos/rappi/orders/{order_id}/status` | [api.py](../../apps/api/restaurant_os/api.py) · `post_pos_rappi_order_status` · 8859 |
| ORDER | `GET /api/v1/pos/whatsapp/orders` | [api.py](../../apps/api/restaurant_os/api.py) · `get_pos_whatsapp_orders` · 8874 |
| ORDER | `POST /api/v1/pos/whatsapp/orders/{order_id}/status` | [api.py](../../apps/api/restaurant_os/api.py) · `post_pos_whatsapp_order_status` · 8887 |
| FISCAL | `GET /api/v1/invoicing/emitters` | [api.py](../../apps/api/restaurant_os/api.py) · `list_fiscal_emitters` · 8922 |
| FISCAL | `GET /api/v1/invoicing/emitters/{legal_entity_id}/configuration` | [api.py](../../apps/api/restaurant_os/api.py) · `read_fiscal_emitter_configuration` · 8932 |
| FISCAL | `PUT /api/v1/invoicing/emitters/{legal_entity_id}/configuration` | [api.py](../../apps/api/restaurant_os/api.py) · `put_fiscal_emitter_configuration` · 8945 |
| FISCAL | `POST /api/v1/invoicing/emitters/{legal_entity_id}/test-connection` | [api.py](../../apps/api/restaurant_os/api.py) · `test_fiscal_emitter_connection` · 8959 |
| FISCAL | `GET /api/v1/invoicing/invoices` | [api.py](../../apps/api/restaurant_os/api.py) · `list_cfdi_invoices` · 9012 |
| FISCAL | `GET /api/v1/invoicing/invoices/{invoice_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_cfdi_invoice_detail` · 9030 |
| FISCAL | `POST /api/v1/invoicing/invoices/issue` | [api.py](../../apps/api/restaurant_os/api.py) · `issue_cfdi_invoice` · 9049 |
| FISCAL | `GET /api/v1/invoicing/invoices/{invoice_id}/pdf` | [api.py](../../apps/api/restaurant_os/api.py) · `download_cfdi_invoice` · 9066 |
| FISCAL | `GET /api/v1/invoicing/invoices/{invoice_id}/xml` | [api.py](../../apps/api/restaurant_os/api.py) · `download_cfdi_invoice` · 9066 |
| FISCAL | `POST /api/v1/invoicing/invoices/{invoice_id}/cancel` | [api.py](../../apps/api/restaurant_os/api.py) · `cancel_cfdi_invoice` · 9092 |
| FISCAL | `POST /api/v1/invoicing/orders/{order_id}/receipt` | [api.py](../../apps/api/restaurant_os/api.py) · `generate_order_receipt` · 9110 |
| SYNC | `POST /api/v1/offline-orders/lease` | [api.py](../../apps/api/restaurant_os/api.py) · `acquire_offline_order_lease` · 9125 |
| SYNC | `POST /api/v1/offline-orders/grants` | [api.py](../../apps/api/restaurant_os/api.py) · `offline_order_grant` · 9153 |
| SYNC | `POST /api/v1/offline-orders/bootstrap` | [api.py](../../apps/api/restaurant_os/api.py) · `bootstrap_offline_orders` · 9198 |
| SYNC | `POST /api/v1/offline-orders/reconcile` | [api.py](../../apps/api/restaurant_os/api.py) · `reconcile_offline_order` · 9238 |
| SYNC | `POST /api/v1/offline-orders/handoff` | [api.py](../../apps/api/restaurant_os/api.py) · `handoff_offline_orders` · 9280 |
| SYNC | `POST /api/v1/offline-orders/catalog-renew` | [api.py](../../apps/api/restaurant_os/api.py) · `renew_offline_order_catalog` · 9322 |
| SYNC | `POST /api/v1/offline-orders/recover-lease` | [api.py](../../apps/api/restaurant_os/api.py) · `recover_offline_order_lease` · 9363 |
| SYNC | `POST /api/v1/offline-orders/catalog-ack` | [api.py](../../apps/api/restaurant_os/api.py) · `acknowledge_classification_catalog` · 9420 |
| EXPENSE | `GET /api/v1/expense-concepts` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_concepts_read` · 9443 |
| EXPENSE | `POST /api/v1/expense-concepts` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_concept_create` · 9457 |
| EXPENSE | `PATCH /api/v1/expense-concepts/{concept_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_concept_edit` · 9473 |
| EXPENSE | `POST /api/v1/expense-concepts/{concept_id}/archive` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_concept_archive` · 9490 |
| CASH-CONTEXT | `GET /api/v1/expenses/cash-context` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_cash_context` · 9507 |
| EXPENSE | `GET /api/v1/expenses/summary` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_summary` · 9518 |
| INTENT | `GET /api/v1/expense-commands/{command_key}` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_recover` · 9562 |
| INTENT | `POST /api/v1/expense-commands/{command_key}/resolve` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_resolve` · 9573 |
| EXPENSE | `GET /api/v1/expenses` | [api.py](../../apps/api/restaurant_os/api.py) · `expenses_read` · 9593 |
| EXPENSE | `GET /api/v1/expenses/{expense_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_read` · 9613 |
| EXPENSE | `POST /api/v1/expenses` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_create` · 9624 |
| EXPENSE | `PATCH /api/v1/expenses/{expense_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_edit` · 9648 |
| EXPENSE | `POST /api/v1/expenses/{expense_id}/confirm` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_confirm` · 9671 |
| EXPENSE | `POST /api/v1/expenses/{expense_id}/cancel` | [api.py](../../apps/api/restaurant_os/api.py) · `expense_cancel` · 9694 |
| REPORT | `GET /api/v1/reports/delivery-fees` | [delivery_fee_api.py](../../apps/api/restaurant_os/delivery_fee_api.py) · `delivery_report` · 23 |
| PUBLIC | `POST /api/v1/mobile/branches/{public_key}/access/register` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `register` · 196 |
| PUBLIC | `POST /api/v1/mobile/branches/{public_key}/access/login` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `login` · 210 |
| PUBLIC | `PUT /api/v1/mobile/branches/{public_key}/profile/password` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `change_password` · 224 |
| PUBLIC | `PUT /api/v1/mobile/branches/{public_key}/profile/phone` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `change_phone` · 240 |
| PUBLIC | `POST /api/v1/mobile/branches/{public_key}/access/start` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `start` · 256 |
| PUBLIC | `POST /api/v1/mobile/branches/{public_key}/profile/phone/start` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `start_phone_change` · 267 |
| PUBLIC | `POST /api/v1/mobile/branches/{public_key}/access/verify` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `verify` · 284 |
| PUBLIC | `GET /api/v1/mobile/branches/{public_key}/profile` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `profile` · 324 |
| PUBLIC | `PUT /api/v1/mobile/branches/{public_key}/profile` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `update_profile` · 333 |
| PUBLIC | `POST /api/v1/mobile/branches/{public_key}/logout` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `logout` · 349 |
| PUBLIC | `GET /api/v1/mobile/branches/{public_key}/catalog` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `catalog` · 368 |
| PUBLIC | `POST /api/v1/mobile/branches/{public_key}/order-intents` | [mobile_customer_api.py](../../apps/api/restaurant_os/mobile_customer_api.py) · `order` · 378 |
| AGENT | `GET /api/v1/integrations/grokbot/config` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `get_grokbot_config` · 336 |
| AGENT | `PUT /api/v1/integrations/grokbot/config` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `save_grokbot_config` · 345 |
| AGENT | `PUT /api/v1/integrations/grokbot/identities/{profile}` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `update_grokbot_identity` · 459 |
| AGENT | `POST /api/v1/integrations/grokbot/identities/{profile}/rotate-secret` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `rotate_grokbot_identity_secret` · 590 |
| AGENT | `POST /api/v1/agent-auth/token` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `issue_agent_token` · 707 |
| AGENT | `GET /api/v1/agent-tools/context` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `agent_context` · 868 |
| AGENT | `GET /api/v1/agent-tools/catalog/items` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_catalog` · 1235 |
| AGENT | `GET /api/v1/agent-tools/sales/summary` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `get_agent_sales_summary` · 1318 |
| AGENT | `GET /api/v1/agent-tools/cash/cuts` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_cash_cuts` · 1518 |
| AGENT | `GET /api/v1/agent-tools/inventory/items` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_inventory_items` · 1651 |
| AGENT | `GET /api/v1/agent-tools/inventory/stock` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_stock` · 1691 |
| AGENT | `GET /api/v1/agent-tools/inventory/movements` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_inventory_movements` · 1743 |
| AGENT | `GET /api/v1/agent-tools/recipes` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_recipes` · 1820 |
| AGENT | `GET /api/v1/agent-tools/suppliers` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_suppliers` · 1925 |
| AGENT | `GET /api/v1/agent-tools/purchase-presentations` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_purchase_presentations` · 1966 |
| AGENT | `GET /api/v1/agent-tools/purchases/history` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_purchase_history` · 2047 |
| AGENT | `GET /api/v1/agent-tools/purchase-needs` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `list_agent_purchase_needs` · 2198 |
| AGENT | `POST /api/v1/agent-tools/proposals/catalog` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `create_catalog_proposal` · 2629 |
| AGENT | `POST /api/v1/agent-tools/proposals/inventory-items` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `create_inventory_item_proposal` · 2699 |
| AGENT | `POST /api/v1/agent-tools/proposals/recipes` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `create_recipe_proposal` · 2765 |
| AGENT | `POST /api/v1/agent-tools/purchase-drafts` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `create_purchase_draft` · 2873 |
| AGENT | `GET /api/v1/agent-tools/operations/{operation_id}` | [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py) · `get_agent_operation` · 2952 |

| CATALOG | `GET /api/v1/catalog/products` | [api.py](../../apps/api/restaurant_os/api.py) · `get_catalog_products` · 1142 |
| CATALOG | `GET /api/v1/catalog/cleanup-status` | [api.py](../../apps/api/restaurant_os/api.py) · `get_catalog_cleanup_status_endpoint` · 1569 |
| CATALOG | `POST /api/v1/catalog/load-real-excels` | [api.py](../../apps/api/restaurant_os/api.py) · `post_load_real_excels_endpoint` · 1583 |
| CATALOG | `POST /api/v1/catalog/products` | [api.py](../../apps/api/restaurant_os/api.py) · `post_catalog_product` · 1616 |
| CATALOG | `POST /api/v1/catalog/products/upload-image` | [api.py](../../apps/api/restaurant_os/api.py) · `post_catalog_product_upload_image` · 1673 |
| CATALOG | `POST /api/v1/catalog/product-configurations` | [api.py](../../apps/api/restaurant_os/api.py) · `post_product_configuration` · 1728 |
| CATALOG | `PUT /api/v1/catalog/product-configurations/{product_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_product_configuration` · 1747 |
| CATALOG | `GET /api/v1/catalog/products/{product_id}/pos-preview` | [api.py](../../apps/api/restaurant_os/api.py) · `get_catalog_product_pos_preview` · 1768 |
| CATALOG | `PUT /api/v1/catalog/products/{product_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_catalog_product` · 4303 |
| CATALOG | `DELETE /api/v1/catalog/products/{product_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_catalog_product_endpoint` · 4352 |
| CATALOG | `GET /api/v1/categories` | [api.py](../../apps/api/restaurant_os/api.py) · `get_categories` · 4834 |
| CATALOG | `POST /api/v1/categories` | [api.py](../../apps/api/restaurant_os/api.py) · `post_category` · 4854 |
| CATALOG | `PUT /api/v1/categories/{category_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_category` · 4870 |
| CATALOG | `GET /api/v1/categories/{category_id}/selection-group` | [api.py](../../apps/api/restaurant_os/api.py) · `get_category_selection_group` · 4889 |
| CATALOG | `POST /api/v1/categories/{category_id}/selection-group` | [api.py](../../apps/api/restaurant_os/api.py) · `post_category_selection_group` · 4900 |
| CATALOG | `GET /api/v1/catalog/category-option-groups/{group_id}/coverage` | [api.py](../../apps/api/restaurant_os/api.py) · `get_category_option_group_coverage` · 4914 |
| CATALOG | `POST /api/v1/catalog/category-option-groups/{group_id}/values` | [api.py](../../apps/api/restaurant_os/api.py) · `post_category_option_value` · 4927 |
| CATALOG | `PUT /api/v1/catalog/category-option-groups/{group_id}/values/{value_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_category_option_value` · 4941 |
| CATALOG | `PUT /api/v1/catalog/category-option-groups/{group_id}/assignments/{product_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_product_category_option_assignment` · 4956 |
| CATALOG | `POST /api/v1/catalog/onboarding-ai/message` | [api.py](../../apps/api/restaurant_os/api.py) · `post_catalog_onboarding_ai_message` · 5160 |
| CATALOG | `POST /api/v1/catalog/onboarding-ai/confirm` | [api.py](../../apps/api/restaurant_os/api.py) · `post_catalog_onboarding_ai_confirm` · 5212 |
| CATALOG | `GET /api/v1/products/{product_id}/composition` | [api.py](../../apps/api/restaurant_os/api.py) · `get_product_composition` · 5269 |
| CATALOG | `PUT /api/v1/products/{product_id}/composition` | [api.py](../../apps/api/restaurant_os/api.py) · `put_product_composition` · 5285 |
| CATALOG | `GET /api/v1/admin-catalog/category-priorities` | [api.py](../../apps/api/restaurant_os/api.py) · `get_admin_category_priorities` · 5322 |
| CATALOG | `PUT /api/v1/admin-catalog/category-priorities` | [api.py](../../apps/api/restaurant_os/api.py) · `put_admin_category_priorities` · 5332 |
| CATALOG | `GET /api/v1/admin-catalog/stock-thresholds` | [api.py](../../apps/api/restaurant_os/api.py) · `get_admin_stock_thresholds` · 5406 |
| CATALOG | `PUT /api/v1/admin-catalog/stock-thresholds/{item_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_admin_stock_threshold` · 5417 |
| CATALOG | `DELETE /api/v1/admin-catalog/stock-thresholds/{item_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_admin_stock_threshold` · 5440 |
| CATALOG | `GET /api/v1/products/{product_id}/modifiers` | [api.py](../../apps/api/restaurant_os/api.py) · `get_product_modifiers` · 5474 |
| CATALOG | `POST /api/v1/products/{product_id}/modifier-groups` | [api.py](../../apps/api/restaurant_os/api.py) · `post_modifier_group` · 5490 |
| CATALOG | `GET /api/v1/products/{product_id}/modifier-groups` | [api.py](../../apps/api/restaurant_os/api.py) · `get_modifier_catalog_groups` · 5502 |
| CATALOG | `GET /api/v1/products/{product_id}/modifier-configuration` | [api.py](../../apps/api/restaurant_os/api.py) · `get_product_modifier_configuration` · 5518 |
| CATALOG | `POST /api/v1/products/{product_id}/modifier-configuration/copy` | [api.py](../../apps/api/restaurant_os/api.py) · `post_modifier_configuration_copy` · 5529 |
| CATALOG | `POST /api/v1/products/{product_id}/modifier-configuration/selection-preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_modifier_selection_preview` · 5546 |
| CATALOG | `PUT /api/v1/products/{product_id}/modifier-configuration` | [api.py](../../apps/api/restaurant_os/api.py) · `put_product_modifier_configuration` · 5560 |
| CATALOG | `PATCH /api/v1/modifier-groups/{group_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `patch_modifier_group` · 5577 |
| CATALOG | `DELETE /api/v1/modifier-groups/{group_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_modifier_group_endpoint` · 5589 |
| CATALOG | `GET /api/v1/catalog/variation-notes` | [api.py](../../apps/api/restaurant_os/api.py) · `get_variation_notes` · 5600 |
| CATALOG | `POST /api/v1/products/{product_id}/variation-notes` | [api.py](../../apps/api/restaurant_os/api.py) · `post_variation_note` · 5611 |
| CATALOG | `PUT /api/v1/variation-notes/{option_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_variation_note` · 5623 |
| CATALOG | `GET /api/v1/catalog/order-comments` | [api.py](../../apps/api/restaurant_os/api.py) · `get_order_comments` · 5635 |
| CATALOG | `GET /api/v1/catalog/modifier-sets` | [api.py](../../apps/api/restaurant_os/api.py) · `get_modifier_sets` · 5646 |
| CATALOG | `POST /api/v1/catalog/modifier-sets` | [api.py](../../apps/api/restaurant_os/api.py) · `post_modifier_set` · 5656 |
| CATALOG | `GET /api/v1/catalog/modifier-sets/{modifier_set_id}/configuration` | [api.py](../../apps/api/restaurant_os/api.py) · `get_shared_modifier_configuration` · 5670 |
| CATALOG | `PUT /api/v1/catalog/modifier-sets/{modifier_set_id}/configuration` | [api.py](../../apps/api/restaurant_os/api.py) · `put_shared_modifier_configuration` · 5683 |
| CATALOG | `PUT /api/v1/catalog/modifier-sets/{modifier_set_id}/products` | [api.py](../../apps/api/restaurant_os/api.py) · `put_shared_modifier_products` · 5700 |
| CATALOG | `POST /api/v1/catalog/order-comments/bulk/preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_order_comments_bulk_preview` · 5717 |
| CATALOG | `POST /api/v1/catalog/order-comments/bulk` | [api.py](../../apps/api/restaurant_os/api.py) · `post_order_comments_bulk` · 5728 |
| CATALOG | `PUT /api/v1/catalog/order-comments/{comment_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_order_comment` · 5739 |
| CATALOG | `PUT /api/v1/catalog/order-comments/{comment_id}/products` | [api.py](../../apps/api/restaurant_os/api.py) · `put_order_comment_products` · 5751 |
| CATALOG | `GET /api/v1/catalog/ingredient-extras/available` | [api.py](../../apps/api/restaurant_os/api.py) · `get_available_ingredient_extras` · 5765 |
| CATALOG | `GET /api/v1/catalog/ingredient-variations` | [api.py](../../apps/api/restaurant_os/api.py) · `get_ingredient_variations` · 5778 |
| CATALOG | `POST /api/v1/catalog/ingredient-variations` | [api.py](../../apps/api/restaurant_os/api.py) · `post_ingredient_variation` · 5790 |
| CATALOG | `GET /api/v1/catalog/ingredient-variations/{variation_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `get_ingredient_variation_endpoint` · 5801 |
| CATALOG | `PUT /api/v1/catalog/ingredient-variations/{variation_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_ingredient_variation` · 5812 |
| CATALOG | `POST /api/v1/catalog/ingredient-variations/{variation_id}/assignments/preview` | [api.py](../../apps/api/restaurant_os/api.py) · `post_ingredient_variation_assignment_preview` · 5826 |
| CATALOG | `PUT /api/v1/catalog/ingredient-variations/{variation_id}/assignments` | [api.py](../../apps/api/restaurant_os/api.py) · `put_ingredient_variation_assignments` · 5840 |
| CATALOG | `PUT /api/v1/catalog/ingredient-variations/{variation_id}/assignments/{product_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_ingredient_variation_assignment` · 5857 |
| CATALOG | `DELETE /api/v1/catalog/ingredient-variations/{variation_id}/assignments/{product_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_ingredient_variation_assignment` · 5880 |
| CATALOG | `POST /api/v1/modifier-groups/{group_id}/options` | [api.py](../../apps/api/restaurant_os/api.py) · `post_modifier_option` · 5894 |
| CATALOG | `PUT /api/v1/modifier-groups/{group_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_modifier_group` · 5906 |
| CATALOG | `DELETE /api/v1/modifier-groups/{group_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_modifier_group` · 5918 |
| CATALOG | `PUT /api/v1/modifier-options/{option_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_modifier_option` · 5929 |
| CATALOG | `DELETE /api/v1/modifier-options/{option_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_modifier_option` · 5941 |
| CATALOG | `POST /api/v1/modifier-groups/{group_id}/clone` | [api.py](../../apps/api/restaurant_os/api.py) · `post_clone_modifier_group` · 5952 |
| CATALOG | `POST /api/v1/products/{product_id}/clone-modifiers` | [api.py](../../apps/api/restaurant_os/api.py) · `post_clone_all_modifiers` · 5968 |
| CATALOG | `PUT /api/v1/products/{product_id}/modifier-groups/reorder` | [api.py](../../apps/api/restaurant_os/api.py) · `put_reorder_modifier_groups` · 5984 |
| CATALOG | `PUT /api/v1/modifier-groups/{group_id}/options/reorder` | [api.py](../../apps/api/restaurant_os/api.py) · `put_reorder_modifier_options` · 6000 |
| CATALOG | `PATCH /api/v1/modifier-options/{option_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `patch_modifier_option` · 6016 |
| CATALOG | `DELETE /api/v1/modifier-options/{option_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_modifier_option_endpoint` · 6028 |
| CATALOG | `PUT /api/v1/modifier-options/{option_id}/branches/{branch_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_branch_modifier_option` · 6039 |
| CUSTOMER | `GET /api/v1/customers` | [api.py](../../apps/api/restaurant_os/api.py) · `get_customers` · 6117 |
| CUSTOMER | `POST /api/v1/customers` | [api.py](../../apps/api/restaurant_os/api.py) · `post_customer` · 6138 |
| CUSTOMER | `POST /api/v1/customers/{customer_id}/addresses` | [api.py](../../apps/api/restaurant_os/api.py) · `post_customer_address` · 6163 |
| CUSTOMER | `PUT /api/v1/customers/{customer_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_customer` · 6181 |
| CUSTOMER | `PUT /api/v1/customers/{customer_id}/addresses/{address_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_customer_address` · 6199 |
| CUSTOMER | `PUT /api/v1/customers/{customer_id}/tax-profile` | [api.py](../../apps/api/restaurant_os/api.py) · `put_customer_tax_profile` · 6220 |
| CATALOG | `GET /api/v1/suppliers` | [api.py](../../apps/api/restaurant_os/api.py) · `get_suppliers` · 6240 |
| CATALOG | `POST /api/v1/suppliers` | [api.py](../../apps/api/restaurant_os/api.py) · `post_supplier` · 6255 |
| CATALOG | `PUT /api/v1/suppliers/{supplier_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_supplier` · 6266 |
| CATALOG | `DELETE /api/v1/suppliers/{supplier_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_supplier_route` · 6278 |
| CATALOG | `POST /api/v1/suppliers/{supplier_id}/contacts` | [api.py](../../apps/api/restaurant_os/api.py) · `post_supplier_contact` · 6289 |
| CATALOG | `PUT /api/v1/suppliers/{supplier_id}/branches/{branch_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_supplier_branch_terms` · 6301 |
| CATALOG | `GET /api/v1/branch-administration/context` | [api.py](../../apps/api/restaurant_os/api.py) · `get_branch_admin_context` · 7226 |
| CATALOG | `GET /api/v1/branch-administration/staff` | [api.py](../../apps/api/restaurant_os/api.py) · `get_branch_admin_staff` · 7237 |
| CATALOG | `GET /api/v1/branch-administration/catalog/products` | [api.py](../../apps/api/restaurant_os/api.py) · `get_branch_admin_catalog_products` · 7248 |
| CATALOG | `GET /api/v1/branch-administration/catalog/products/all-active-summary` | [api.py](../../apps/api/restaurant_os/api.py) · `get_all_active_branch_admin_catalog_products` · 7261 |
| CATALOG | `GET /api/v1/branch-administration/catalog/variation-notes` | [api.py](../../apps/api/restaurant_os/api.py) · `get_branch_admin_variation_notes` · 7273 |
| CATALOG | `GET /api/v1/branch-administration/imports` | [api.py](../../apps/api/restaurant_os/api.py) · `get_branch_admin_imports` · 7284 |
| CATALOG | `PUT /api/v1/branch-administration/catalog/products/{product_id}/availability` | [api.py](../../apps/api/restaurant_os/api.py) · `put_branch_admin_availability` · 7297 |
| CATALOG | `PUT /api/v1/branch-administration/catalog/products/{product_id}/availability/all-active` | [api.py](../../apps/api/restaurant_os/api.py) · `put_all_active_branch_admin_availability` · 7315 |
| CATALOG | `PUT /api/v1/branch-administration/catalog/products/{product_id}/digital-menu-visibility` | [api.py](../../apps/api/restaurant_os/api.py) · `put_branch_admin_digital_menu_visibility` · 7340 |
| CATALOG | `PUT /api/v1/branch-administration/catalog/products/{product_id}/digital-menu-visibility/all-active` | [api.py](../../apps/api/restaurant_os/api.py) · `put_all_active_branch_admin_digital_menu_visibility` · 7371 |
| CATALOG | `PUT /api/v1/branch-administration/catalog/variation-notes/{option_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_branch_admin_variation_note` · 7394 |
| CATALOG | `GET /api/v1/branch-administration/catalog/ingredient-variations` | [api.py](../../apps/api/restaurant_os/api.py) · `get_branch_admin_ingredient_variations` · 7411 |
| CATALOG | `PUT /api/v1/branch-administration/catalog/ingredient-variations/{option_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `put_branch_admin_ingredient_variation` · 7424 |
| INTEGRATION | `POST /api/v1/legacy-imports` | [api.py](../../apps/api/restaurant_os/api.py) · `post_legacy_import_batch` · 7446 |
| INTEGRATION | `GET /api/v1/legacy-imports` | [api.py](../../apps/api/restaurant_os/api.py) · `get_legacy_import_batches` · 7466 |
| INTEGRATION | `POST /api/v1/legacy-imports/{batch_id}/records` | [api.py](../../apps/api/restaurant_os/api.py) · `post_legacy_import_records` · 7477 |
| INTEGRATION | `GET /api/v1/legacy-imports/{batch_id}/records` | [api.py](../../apps/api/restaurant_os/api.py) · `get_legacy_import_records` · 7493 |
| INTEGRATION | `POST /api/v1/legacy-imports/{batch_id}/complete` | [api.py](../../apps/api/restaurant_os/api.py) · `post_complete_legacy_import` · 7512 |
| INTEGRATION | `POST /api/v1/integrations/uber-eats/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `post_uber_eats_webhook` · 7529 |
| INTEGRATION | `POST /api/v1/v1/integrations/uber-eats/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `post_uber_eats_webhook` · 7529 |
| INTEGRATION | `GET /api/v1/integrations/uber-eats/config` | [api.py](../../apps/api/restaurant_os/api.py) · `get_uber_eats_config` · 7608 |
| INTEGRATION | `PUT /api/v1/integrations/uber-eats/config` | [api.py](../../apps/api/restaurant_os/api.py) · `put_uber_eats_config` · 7628 |
| INTEGRATION | `GET /api/v1/integrations/uber-eats/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `get_uber_eats_store_mappings` · 7640 |
| INTEGRATION | `POST /api/v1/integrations/uber-eats/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `post_uber_eats_store_mapping` · 7651 |
| INTEGRATION | `DELETE /api/v1/integrations/uber-eats/stores/{mapping_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_uber_eats_store_mapping` · 7672 |
| INTEGRATION | `GET /api/v1/integrations/uber-eats/logs` | [api.py](../../apps/api/restaurant_os/api.py) · `get_uber_eats_webhook_logs` · 7685 |
| INTEGRATION | `POST /api/v1/integrations/uber-eats/test-order` | [api.py](../../apps/api/restaurant_os/api.py) · `post_uber_eats_test_order` · 7697 |
| INTEGRATION | `POST /api/v1/integrations/didi-food/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `post_didi_food_webhook` · 7758 |
| INTEGRATION | `POST /api/v1/v1/integrations/didi-food/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `post_didi_food_webhook` · 7758 |
| INTEGRATION | `GET /api/v1/integrations/didi-food/config` | [api.py](../../apps/api/restaurant_os/api.py) · `get_didi_food_config` · 7842 |
| INTEGRATION | `PUT /api/v1/integrations/didi-food/config` | [api.py](../../apps/api/restaurant_os/api.py) · `put_didi_food_config` · 7862 |
| INTEGRATION | `GET /api/v1/integrations/didi-food/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `get_didi_food_store_mappings` · 7874 |
| INTEGRATION | `POST /api/v1/integrations/didi-food/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `post_didi_food_store_mapping` · 7885 |
| INTEGRATION | `DELETE /api/v1/integrations/didi-food/stores/{mapping_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_didi_food_store_mapping` · 7906 |
| INTEGRATION | `GET /api/v1/integrations/didi-food/logs` | [api.py](../../apps/api/restaurant_os/api.py) · `get_didi_food_webhook_logs` · 7919 |
| INTEGRATION | `POST /api/v1/integrations/didi-food/simulate` | [api.py](../../apps/api/restaurant_os/api.py) · `post_didi_food_test_order` · 7932 |
| INTEGRATION | `POST /api/v1/integrations/didi-food/test-order` | [api.py](../../apps/api/restaurant_os/api.py) · `post_didi_food_test_order` · 7932 |
| INTEGRATION | `POST /api/v1/integrations/rappi/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `post_rappi_webhook` · 8051 |
| INTEGRATION | `POST /api/v1/v1/integrations/rappi/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `post_rappi_webhook` · 8051 |
| INTEGRATION | `GET /api/v1/integrations/rappi/config` | [api.py](../../apps/api/restaurant_os/api.py) · `get_rappi_config` · 8140 |
| INTEGRATION | `PUT /api/v1/integrations/rappi/config` | [api.py](../../apps/api/restaurant_os/api.py) · `put_rappi_config` · 8160 |
| INTEGRATION | `GET /api/v1/integrations/rappi/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `get_rappi_store_mappings` · 8172 |
| INTEGRATION | `POST /api/v1/integrations/rappi/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `post_rappi_store_mapping` · 8183 |
| INTEGRATION | `DELETE /api/v1/integrations/rappi/stores/{mapping_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_rappi_store_mapping` · 8204 |
| INTEGRATION | `GET /api/v1/integrations/rappi/logs` | [api.py](../../apps/api/restaurant_os/api.py) · `get_rappi_webhook_logs` · 8217 |
| INTEGRATION | `POST /api/v1/integrations/rappi/simulate` | [api.py](../../apps/api/restaurant_os/api.py) · `post_rappi_test_order` · 8230 |
| INTEGRATION | `POST /api/v1/integrations/rappi/test-order` | [api.py](../../apps/api/restaurant_os/api.py) · `post_rappi_test_order` · 8230 |
| INTEGRATION | `GET /api/v1/integrations/whatsapp/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `get_whatsapp_webhook` · 8349 |
| INTEGRATION | `POST /api/v1/integrations/whatsapp/webhook` | [api.py](../../apps/api/restaurant_os/api.py) · `post_whatsapp_webhook` · 8375 |
| INTEGRATION | `GET /api/v1/integrations/whatsapp/config` | [api.py](../../apps/api/restaurant_os/api.py) · `get_whatsapp_config` · 8534 |
| INTEGRATION | `POST /api/v1/integrations/whatsapp/regenerate-secret` | [api.py](../../apps/api/restaurant_os/api.py) · `post_whatsapp_regenerate_secret` · 8563 |
| INTEGRATION | `PUT /api/v1/integrations/whatsapp/config` | [api.py](../../apps/api/restaurant_os/api.py) · `put_whatsapp_config` · 8592 |
| INTEGRATION | `POST /api/v1/integrations/whatsapp/config` | [api.py](../../apps/api/restaurant_os/api.py) · `put_whatsapp_config` · 8592 |
| INTEGRATION | `GET /api/v1/integrations/whatsapp/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `get_whatsapp_store_mappings` · 8604 |
| INTEGRATION | `POST /api/v1/integrations/whatsapp/stores` | [api.py](../../apps/api/restaurant_os/api.py) · `post_whatsapp_store_mapping` · 8615 |
| INTEGRATION | `DELETE /api/v1/integrations/whatsapp/stores/{mapping_id}` | [api.py](../../apps/api/restaurant_os/api.py) · `delete_whatsapp_store_mapping` · 8644 |
| INTEGRATION | `GET /api/v1/integrations/whatsapp/logs` | [api.py](../../apps/api/restaurant_os/api.py) · `get_whatsapp_webhook_logs` · 8657 |
| INTEGRATION | `POST /api/v1/integrations/whatsapp/simulate` | [api.py](../../apps/api/restaurant_os/api.py) · `post_whatsapp_test_order` · 8670 |
| INTEGRATION | `POST /api/v1/integrations/whatsapp/test-order` | [api.py](../../apps/api/restaurant_os/api.py) · `post_whatsapp_test_order` · 8670 |
| INTEGRATION | `GET /api/v1/integrations/facturapi/config` | [api.py](../../apps/api/restaurant_os/api.py) · `get_facturapi_config` · 8972 |
| INTEGRATION | `POST /api/v1/integrations/facturapi/config` | [api.py](../../apps/api/restaurant_os/api.py) · `save_facturapi_config` · 8987 |
| INTEGRATION | `POST /api/v1/integrations/facturapi/test-connection` | [api.py](../../apps/api/restaurant_os/api.py) · `test_facturapi_connection` · 9000 |
| CATALOG | `GET /api/v1/catalog/classification-rollout` | [api.py](../../apps/api/restaurant_os/api.py) · `get_classification_rollout` · 9394 |
| CATALOG | `POST /api/v1/catalog/classification-rollout` | [api.py](../../apps/api/restaurant_os/api.py) · `post_classification_rollout` · 9404 |

El manifiesto contiene 407 registros de decorador y 405 pares método/ruta únicos.
Se conservan dos declaraciones DELETE duplicadas existentes de modifier-groups y
modifier-options en api.py: son handlers distintos de catálogo; el inventario no
deduce precedencia de despacho ni los corrige. F1-03 debe cubrir la ruta efectiva
y verificar registro/precedencia si esa superficie se modifica.

Reproducción del manifiesto: analizar con `ast.parse` los cuatro módulos enlazados;
resolver `APIRouter(prefix=...)`, enumerar cada decorador HTTP literal y conservar
los aliases. Clasificar por familias de §2; comprobar separadamente registro en main.py
y dispatcher `api_route` del gateway. No requiere credenciales ni ejecución de rutas.


## Delta F1-06 — transporte de impresión

El conteo inicial de 407 entradas corresponde al baseline, no al checkout posterior.
Nueva superficie implementada: `GET /api/v1/print-attempts/{attempt_id}/payload`,
handler `api.print_attempt_payload_endpoint`; credencial print.agent de organización/
sucursal y asignación CLAIMED vigente antes del payload; proyección cerrada ticket o
cocina, auditoría y revalidación. Sin acceso humano ni listado histórico. Las rutas
pull/claim existentes se adaptan bajo política activa según SDD del incremento.

## Delta F1-06 — liquidaciones

`GET /api/v1/driver-cash-settlements/drivers` conserva lectura operativa de candidatos
sin suma monetaria bajo política; `POST /api/v1/driver-cash-settlements` conserva
workspace y permiso de cobro y proyecta acuse cerrado, incluidos replays.
Nueva ruta `POST /api/v1/driver-cash-settlements/recover`, handler
`api.recover_driver_cash_settlement`: sólo comando propio existente con cuerpo/clave
originales y lectura vigente, sin efecto ni escritura/workspace implícitos. Todas
son humanas/no-store; snapshots siguen internos. Contratos publicados de candidato
y acuse v2. Integración POS y reconciliación completa del manifiesto siguen pendientes.

## Delta F1-06 — reapertura/corrección de pedidos

Las cinco rutas existentes de solicitud, listado, aprobación, rechazo y aplicación
(`api.*order_reopen_request*`) quedan como fronteras humanas/no-store. Comandos y
replays bajo política activa pasan por `order_reopen_views.reopen_command`; el
listado selecciona metadata sin before_snapshot. El resultado financiero histórico
se conserva para la consulta de pedido con autoridad sales. No se añaden rutas;
la adaptación de UI y el cierre del manifiesto completo siguen pendientes.

## Delta F1-06 — modificaciones de pedidos

`POST /api/v1/orders/{order_id}/amendments` conserva los permisos/guardas de escritura
y entrega acuse operativo bajo política activa. Nueva ruta
`POST /api/v1/orders/{order_id}/amendments/recover`, handler
`api.recover_order_amendment_endpoint`, sólo consulta metadata de un comando propio
existente con orders.read vigente; no acepta nueva intención ni ejecuta cambios.
Ambas son humanas/no-store. La recuperación exige política activa. Los originales
financieros siguen internos y el detalle puntual tiene autorización separada.
F1-07 debe adaptar el consumidor POS y F1-10 reconciliar el manifiesto completo.

## Delta F1-06 — logs de integración

Las cuatro rutas GET `/integrations/{uber-eats|didi-food|rappi|whatsapp}/logs`
conservan admin.manage, ahora en el servicio además de identidad humana HTTP/no-store.
Si cualquier sucursal tuvo activación, la proyección sólo contiene id interno,
proveedor, estado enumerado y fechas; no selecciona payload_raw, firma, errores ni
eventos/identificadores externos libres. Suspender no vuelve al contrato amplio.
Sin sucursal resuelta en el registro, branch_id/include_payload no prueban acceso al
original. No se agrega descarga de originales ni se cambia la ingesta. F1-07 adapta
la tabla de IntegrationsHub al contrato publicado integration-log-metadata-v2.

## Delta F1-06 — gastos

Las 14 rutas humanas EXP-001 usan identidad humana/no-store. La lista monetaria y
resumen exigen dataset expenses además del permiso original; nueva
`GET /api/v2/expenses` devuelve metadata con la paginación/filtros existentes.
`GET /api/v1/expenses/{expense_id}` admite expected_version para borrador propio
con creación/edición ejecutada en esa versión, expenses.read/manage actuales;
las demás lecturas monetarias exigen autoridad financiera. Confirmar o cancelar
no concede consulta del historial. Cash-context selecciona sólo id/caja/fecha.

Comandos, replays y recuperación de documentos devuelven acuse cerrado bajo política;
result histórico queda interno. GET de recuperación exige lectura, no escritura;
resolve conserva workspace y abandono terminal, validando tipo/objetivo/sucursal.
Los conceptos mantienen contrato administrativo. F1-07 adapta ExpensesWorkspace,
su parser y recuperación para no tratar un acuse como documento monetario.

## Delta F1-06 — cancelación

`POST /api/v1/orders/{order_id}/cancel` mantiene las reglas de cancelación y entrega
OrderCancellationReceiptV2 bajo política activa. La frontera HTTP usa identidad humana,
no-store y error seguro. El servicio exige lectura vigente además de cancelación,
serializa antes de leer estado y conserva transacción del llamador con commit=False.
No hay nueva ruta ni clave de idempotencia: el duplicado se rechaza sin nuevos movimientos.
La autorización exacta CC-D08 y la adaptación del consumidor permanecen F1-08/F1-07.

## Delta F1-06 — aceptación y asignación

POST /order-intents/{intent_id}/accept, POST /orders/{order_id}/accept y
PUT /orders/{order_id}/delivery-assignment usan identidad humana/no-store y errores
seguros. Bajo política, OrderAcceptanceReceiptV2 sustituye el resultado monetario.
El replay requiere actor original y lectura vigente, no permiso de escritura ni
fence de un nuevo efecto. Sólo nuevas acciones adquieren el fence de sucursal;
aceptación pública serializa además la clave organizacional antes de cualquier efecto.
La prueba de pendiente exige auditoría de transición PENDING a ACCEPTED, no cualquier
hecho de aceptación. Los originales permanecen internos y el detalle atendido conserva
su ruta y autoridad independientes. Las transacciones del llamador no se confirman.
F1-07 adapta consumidores de aceptación/asignación.

## Delta F1-06 — historial de repartidores y bandejas de canales

GET /drivers/{driver_id}/deliveries conserva admin.manage y exige autoridad financiera
sales vigente para todas las sucursales consultadas antes de leer importes. branch_id
acota explícitamente; omitirlo no selecciona silenciosamente el subconjunto delegado.
Identidad humana, no-store, auditoría y revalidación posterior al commit. Historial
original intacto. Verificación dirigida local y PostgreSQL registrada en el plan.

GET /pos/{uber-eats,didi-food,rappi,whatsapp}/orders exige usuario humano actual,
orders.read y ámbito también en el servicio. Bajo política entrega exclusivamente
ChannelOrderOperationalV2, incluso al Dueño: sin total, líneas monetarias, payloads ni
direcciones completas. Consulta SQL por campos, filtro de estado antes de límite 100,
auditoría sin importes y revalidación de versión/permisos antes de responder.
Los cuatro POST de estado no están cubiertos por esta lectura; su autoridad exacta
permanece en F1-08. Consumidores de bandejas siguen F1-07.

## Delta F1-06/07/09 — sync, sesión y suspensión

GET /sync/events: humano recibe SyncEventOperationalV2 bajo política; dispositivo
gateway.sync conserva transporte original scoped. No se carga payload/event_type
en diagnóstico humano. Descargas fiscales y de impresora revalidan después del commit.

/auth/session: metadatos efectivos por sucursal, sin dinero ni concesiones ajenas;
no-store e identidad humana. El cliente descarta respuestas de un contexto anterior.
Los probes de política bloquean suspended en vez de abrir lectura legacy; prepared
anterior a activación conserva compatibilidad. Preflight y consumidores siguen abiertos.
