# TDD — POS-CAJERO-001

QA visual focal del detalle de carrito: nombres completos de 18 px sin imagen, complementos de
13 px, precio base e importe cotizado separados y control vertical con blancos táctiles de 44 px.
Comprobar dos productos, nombre largo, modificadores, nota y estado sin cotización; sumar/restar,
editar cantidad y eliminar reutilizan sus handlers existentes. Verificar escritorio y vista estrecha
con scroll del carrito, sin cambios en catálogo, resumen, cobro ni fórmulas.

## TDD-TS-126 Flujo de caja y recuperación

Pruebas semánticas ejecutables de búsqueda global, cantidades/notas, modo recoger/cobro,
serialización/aislamiento de borradores, fallo de almacenamiento y recuperación incierta.
Scripts: `tests/frontend/test_pos_cashier_capture.mjs`,
`tests/frontend/test_pos_cashier_drafts.mjs`, `test_pos_cashier_payment.mjs` y `test_pos_progressive_catalog.mjs`.
Integración navegador con API sintética: recoger y domicilio, navegar/recargar/suspender,
modificadores, edición del mismo folio, confirmar pago una vez y acciones por permiso.

## TDD-TC-293 Captura y borradores

Verificar campos completos, no confiar precios guardados, aislar usuario/sucursal/caja/transporte,
limpiar logout, impedir suspensión de edición/checkout incierto, cuotas y datos inválidos. Borrar
carrito no cancela orden. Notas de líneas diferentes no se fusionan. QA 1366×768 y 1024×768.

## TDD-TS-127 Proyecciones y cálculo Python

Pruebas Python dirigidas de snapshots estructurados/legacy y cálculo exacto de recibido/cambio;
contratos autenticados central/gateway, alcance y ausencia de escrituras por preview. Regresión
Archivos focales: `apps/api/tests/test_cash_tender.py`, `test_pos_cashier_workflow.py` y
`test_gateway_order_service.py`. Regresión de pagos y enmiendas: historial inmutable,
mismas claves, una orden y pago por reintento. Tender insuficiente revierte pago/outbox;
preview no agrega comandos. Cantidad monetaria recibida como float/bool/texto/null se rechaza.

## TDD-TC-294 Snapshot histórico y fronteras monetarias

Teléfono primario activo, domicilio estructurado completo, referencia/instrucción, legacy,
sin modificar snapshot. Efectivo con cero, exacto, exceso, insuficiente, centavos; rechazar float,
bool, exponente, negativos y precisión excesiva. Total deriva de Python, no del cliente.

## TDD-TC-295 Cocina, pago y autorización

Estados/tareas/pago independientes. Rol Cajero sin cancel/fulfill conserva guardas; actor
autorizado usa transición vigente con clave estable. Confirmar/reintentar no duplica pagos,
reservas ni tareas activas. Impresión QUEUED no se marca impresa. Verificar gateway si cambia
frontera y PostgreSQL cuando cambie persistencia/SQL. Auditoría independiente R3 antes de cierre.

Notas: enmienda rechaza notas nuevas de 501 o tipo objeto sin cambiar versión/líneas/tareas;
cotización permite nota histórica de longitud mayor sin escritura y creación la rechaza.
Recuperación exige caja exacta; logout limpia recibo fulfillment. Gateway401 invalida captura,
no borra intención incierta; indisponibilidad conserva captura. No se expone cancelación nueva.

Regresión KDS tras enmienda: conservar tarea CANCELLED histórica, completar tareas activas una
por una; no habilitar READY mientras quede otra activa. La última habilita fulfillment canónico
sin cambiar pago/consumo previo ni eliminar historial. Mismo recorrido dirigido en SQLite y
PostgreSQL aislados, activado por corrección del predicado SQL.
`test_pos_cashier_postgres.py` valida URL efectiva sin query override y migra un schema UUID
propio; CI configura POS_CASHIER_TEST_POSTGRES_URL sobre una base dedicada.

Regresiones de revisión PR #61: reconciliar payment_already_confirmed por GET del ID exacto,
conservar recibo si falla o sigue PENDING, sin un segundo POST ni tender inventado; los tres
caminos de cobro usan el mismo comando. Nota histórica: fuente propia activa, no repetida,
producto y texto exactos; borrar/reordenar conserva supersedes_line_id. Copia sin fuente,
fuente ajena/inactiva/duplicada y modificación mayor de 500 fallan sin cambiar líneas/tareas.
Si todas las líneas son nuevas, POS envía fuentes null y ninguna reclama linaje histórico.
La proyección histórica conserva el teléfono normalizado con país, sin lookup del cliente.
PostgreSQL verifica el linaje con 500 caracteres, su límite VARCHAR; SQLite verifica también
la excepción de texto histórico de 501. No se amplía el esquema para fabricar historia imposible.
