# SDD — CORTE-CIEGO-001, F1-02

Fecha: 2026-10-21. **Diseño F1-02; autoridad F1-04 y proyecciones de caja F1-05 implementadas localmente; lectores/reportes F1-06 en curso. Integración restante pendiente.**
R3 por autoridad y confidencialidad; evidencia parcial F1-04/05 en el plan de fase 1.
Extensión de [SDD §71 / ADR-048](02-SDD.md) y de las doce decisiones del
[paquete](implementation-plans/CORTE-CIEGO-001.md). No redefine importes, estados,
fuentes de venta, compensaciones ni decisiones de producto. Evidencia actual en el
[inventario F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md).

## 1. Frontera y decisión de arquitectura

Separa tres funciones en dominio: resolver autoridad vigente, ejecutar/leer el recurso
canónico y construir una proyección de salida con campos permitidos. Un controlador,
exportador, job o replay no puede serializar directamente filas de turno/corte ni
resultados guardados. La misma política gobierna los distintos transportes; no se
traslada cálculo de caja al navegador ni se altera el snapshot histórico.

Entradas de la política: actor autenticado activo, organización, sucursal del recurso,
capacidad de acción, clase de información, versión de autoridad y política de sucursal.
El servidor deriva sucursal/responsable desde el recurso; un branch_id recibido es
filtro validado, nunca sustituto de esa comprobación. Un recurso inexistente/ajeno no
debe revelar importes ni existencia de alerta en errores. Denegación por defecto.

F1 prepara la separación; activar corte ciego exige además las dependencias completas
de fases 2/3 que correspondan y CC-D11. No habilitar captura/finalización nueva mientras
falte su contrato de dominio. No crear automáticamente usuarios, grants ni delegados.

## 2. Catálogo técnico y composición

La migración 0101 instala los códigos nuevos sin asignarlos a roles. La matriz funcional
CC-P01..18 sigue gobernando la asignación individual. Capacidades no sustituyen las
guardas de estado, versión, ámbito, sustitución y motivo.

| Código | Decisión técnica / actor elegible |
|---|---|
| `cash.shift.read` | Se conserva exclusivamente como estado operativo bajo política nueva; nunca prueba lectura financiera. |
| `cash.shift.open`, `cash.shift.close` | Se conservan para las acciones existentes con sus invariantes; sólo devuelven acuse operativo. |
| `cash.user_cut.operational.read` | Nuevo: lectura de estado/acuse acotada al responsable o encargado de sucursal; Dueño puede consultar estado. |
| `cash.user_cut.capture` | Nuevo: Cajero propio; Líder en sustitución registrada. No se concede captura inicial a Dueño por inferencia. |
| `cash.user_cut.finalize` | Nuevo: encargado o Dueño, ámbito y completitud central; nunca delegado por delegación de lectura. |
| `financial.data.read` | Nuevo punto de entrada común; exige además autoridad Dueño o concesión explícita de §3. Tener la fila de permiso no basta. |
| `financial.delegations.manage` | Nuevo: exclusivamente Dueño gobernado; emite/revoca, no confiere facultades del Dueño al receptor. |
| `reports.operational.read` | Nuevo: encargado/Dueño dentro de sucursal. Cajero/Cajero jefe no lo heredan. Delegado con sales vigente puede consultar esta proyección de lectura dentro de su alcance (CC-P11), sin facultades operativas. |
| `purchases.prices.read` | Nuevo: acceso explícito y limitado a precios de compra; no nace de recibir, catalog.manage ni delegación de caja. |
| `purchases.receive` | Nuevo: encargado/Dueño, sólo recepción de cantidades de compra autorizada asignada a su sucursal/almacén. No equivale a purchases.manage/corporate.manage ni permite aprobar compra/editar catálogo. |
| `inventory.costs.read` | Nuevo: lectura administrativa de costos en ámbito revisado; no la concede inventory.read ni capturar conteo. |
| `inventory.count.capture/review/approve` | Se conservan como capacidades distintas; bajo política nueva inventory.count legacy no satisface automáticamente review/approve. Revisión individual resuelve compatibilidad amplia antes de activar. |
| `cash.user_cut.reopen.request`, `cash.user_cut.reopen.authorize` | Conservar códigos reales: request para solicitar; authorize para decidir y compensar; siempre Dueño en cada etapa y §71.7 prevalece. No habilitan reapertura editable. |

Antes de crear los schemas ejecutables, F1-03 usa estos códigos como contrato. Los
sufijos de corrección se enlazan a los permisos existentes del dominio, sin renombrar
historia: la capacidad de reportar un error operativo no equivale a solicitar corrección.
`cash.user_cut.create/read` legacy no son alias automáticos de capture/finalize/financial;
la migración de asignaciones se prepara como propuesta revisable por usuario.

`require_permission` y `organization_all_permissions` siguen existiendo para otros
dominios, pero no satisfacen por sí solos la política nueva. La comprobación Dueño usa
autoridad persistida del gobierno organizacional existente, nunca nombre, correo o UI.
El preflight incluye toda cuenta que hoy alcance `_require_owner` por grants generales:
debe identificar al Dueño real y resolver explícitamente cualquier administrador con
autoridad incompatible. No conservar un bypass y pretender corregirlo con una etiqueta.

Composición efectiva: capacidad de acción AND ámbito AND guardas del recurso; para
finanzas, AND (Dueño gobernado OR grant vigente para cada dataset/sucursal consultados).
Un grant financiero no satisface captura, finalización, corrección, pago, administración
de usuarios, emisión fiscal ni ajuste de inventario. Roles acumulados no evitan esas
condiciones. Dueño es lector financiero por defecto, sin requerir autodelegación.

Mapa de cobertura funcional (no asignaciones a personas):

| Matriz aprobada | Resolución técnica |
|---|---|
| CC-P01/02 | Permisos POS de acción existentes; lectura puntual §6 y borrador propio, sin grant financiero. |
| CC-P03/04 | Autoridad exacta encargado/Dueño del pedido/acción/versión según §71.8, además del permiso de acción; orders.amend/cancel o un token genérico no bastan. Mantener orders.discount.authorize y guardas de corrección de pagos. |
| CC-P05/06 | cash.shift.read operativo y open/close existentes scoped; gateway no lector humano. |
| CC-P07/08/09 | capture, finalize y operational.read separados; declaración propia y acuse §5. |
| CC-P10/12 | financial.data.read AND Dueño/concesión por pares; descarga revalidada. |
| CC-P11 | Reporte §6 por reports.operational.read o lector financiero sales vigente en esa sucursal. |
| CC-P13 | request/authorize AND Dueño en todas las etapas, sin segundo aprobador. |
| CC-P14 | purchases.receive scoped; precio separado, nunca conceder gestión corporativa para recibir. |
| CC-P15/16 | capture frente a review/approve explícitos; administrador designado, no delegado financiero. |
| CC-P17 | Gobierno de catálogos vigente más separación de costos; sin ampliar especialidades administrativas. |
| CC-P18 | KDS/impresión por estación/dispositivo y contexto, sin acceso a caja; §7. |

La recepción corporativa actual exige purchases.corporate.manage organizacional.
La futura entrada operativa usa purchases.receive y valida la asignación de la compra
al almacén/sucursal; reutiliza invariantes/versionado/asociaciones/idempotencia internos,
pero no exige ni concede gestión corporativa al receptor. En lectura de inventario,
la compatibilidad actual inventory.count con capture/review/approve se reemplaza por
revisión explícita para la política nueva; no retirar funciones de otras sucursales
indiscriminadamente. Si esta frontera falta, F1-08 bloquea activar ese recorrido.

## 3. Concesiones, persistencia y revocación

Se añade en implementación un registro independiente de lectura financiera humana.
No reciclar un rol de Supervisor ni una capability de agente como concesión. Cada grant
identifica organización, receptor humano, Dueño concedente, motivo y UTC de emisión.
Sus pares explícitos de sucursal/dataset no admiten comodines. Datasets cerrados:
`cash.shifts`, `cash.cuts`, `cash.movements`, `sales`, `reconciliation`, `expenses`.
Una respuesta que combine datasets requiere todos; un consolidado requiere cada
sucursal. No ampliar silenciosamente al agregar nueva sucursal, campo o dataset.
Varios grants vigentes se componen por unión de pares exactos (sucursal, dataset),
nunca producto cartesiano: cash.cuts en A y sales en B no conceden sales en A.
Revocar uno retira sus pares; un par sólo subsiste si otro grant explícito vigente
lo concede. Comprobar cobertura completa antes de consultar, sin resultados parciales
silenciosos ni filtrado de un dataset ya cargado fuera de alcance.
Precios de compra/costos administrativos permanecen independientes de esta delegación.

Modelo físico implementado en 0101, migración aditiva sin backfill de delegados inferidos:

| Relación | Campos e invariantes |
|---|---|
| `financial_access_grants` | id, organization_id, subject_user_id, issuer_user_id, issued_at, reason, authorization_version_at_issue; emisión inmutable y FK dentro de organización. |
| `financial_access_grant_scopes` | grant_id, branch_id, dataset; PK de la terna, FK a sucursal de la misma organización y dataset de catálogo cerrado. |
| `financial_access_grant_revocations` | grant_id único, revoked_by, revoked_at, reason, command_id; append-only, ninguna edición/eliminación para reactivar. Nueva concesión requiere nuevo grant. |
| `financial_access_commands` | organización, actor, key, request_hash, action, grant_id, outcome y fecha; unicidad de key en su namespace, mismo payload reproduce acuse autorizado, distinto produce conflicto. No guarda resultado monetario. |
| `blind_cash_policy_revisions` | organización/sucursal, revisión monotónica, manifest_digest, versión mínima API/cliente/gateway y evento de activación; historial append-only. Estado activo resuelto en servidor, no desde un header. |

Se reutiliza `authorization_version` de usuario para invalidar capacidades/sesión al
conceder/revocar; los cambios de rol y de autoridad del Dueño también la invalidan y
deben participar del mismo mecanismo de sincronización. El dato original de grant no
se reescribe al revocar. Emisión y revocación incluyen auditoría atómica y key idempotente.
No se establece un vencimiento de negocio nuevo: revocable desde emisión; el TTL del
lease offline es otro contrato y no convierte la concesión en permiso local.

Orden de locks futuro único para lectores financieros y mutadores de autoridad:
gobierno de organización → usuarios afectados por id ordenado → revisión de sucursal
por id → grants por id. En PostgreSQL, locks compartidos para lectura y exclusivos
para revocar/cambiar autoridad; todas las rutas de gobierno participan. Resolver
autoridad, consultar y materializar DTO dentro de esa transacción. La revocación
confirmada vence a nuevas lecturas; una respuesta ya autorizada/materializada puede
estar en tránsito. No prometer retirar bytes ya enviados o archivos ya descargados.
F1-03 debe refutar con barreras de concurrencia ambas órdenes de ejecución y cambios
de roles además del endpoint de revocación. No es evidencia proporcionada por SQLite.

Exportes diferidos: guardar actor, scope/datasets y versiones; autorizar al crear job,
al generar y al descargar. El archivo privado nunca tiene un URL público que eluda
revalidación; borrarlo por retención no sustituye control de acceso. Llamadas a modelo:
materializar sólo contexto autorizado, revalidar antes de enviarlo y antes de devolver
el resultado; no mantener locks de DB durante red. Si cambió autoridad, abortar salida.
Una llamada externa ya enviada no puede deshacerse retroactivamente.

## 4. Contratos HTTP y cierre de compatibilidad

### Precisión de implementación F1-04 (2026-10-21)

El evaluador común se implementa separado de los handlers legacy: `financial_authority`
resuelve capacidades exactas, sucursales y pares financieros bajo una transacción;
`financial_access` administra concesiones. Conectarlo a DTO y lectores existentes
corresponde a F1-05/06; F1-04 no activa corte ciego ni publica comandos nuevos de caja.

La autoridad antigua `organization_all_permissions` no distingue personas revisadas.
Se añade `financial_owner_reviews` como evidencia append-only de la revisión individual
aprobada: organización, usuario, authorization_version revisada, digest del manifiesto,
referencia de aprobación y UTC. La evidencia sola tampoco basta: se exige actualmente
la asignación organizacional de autoridad persistida. No hay endpoint para autoaprobarse,
backfill por nombre ni creación de revisiones en esta migración. Su carga gobernada
pertenece al preflight F1-09. Un cambio de authorization_version invalida la revisión,
incluso contraseñas; requiere revisión nueva, nunca
revive al restaurar roles antiguos. Se rechaza autodelegación: Dueño ya tiene lectura
por defecto y no necesita invalidar su propia revisión para obtenerla. Se prefiere denegación hasta revisar a conservar
autoridad obsoleta. El Dueño revisado obtiene los defaults explícitos de CC-P; captura
inicial continúa exigiendo permiso explícito y guardas del recurso.

Las lecturas PostgreSQL comparten el advisory lock de gobierno existente (modo shared);
mutaciones conservan su modo exclusivo y orden de usuarios. SQLite usa BEGIN IMMEDIATE
para serializar autoridad local; no representa concurrencia PostgreSQL ni delega finanzas
al gateway. El evaluador no hace commit: el consumidor debe materializar dentro de la
misma transacción y READ COMMITTED; se rechazan snapshots de aislamiento superior que
podrían conservar una autorización revocada. Emisión/revocación son transacciones completas,
incluyen auditoría y rollback ante cualquier fallo; replay reautoriza al Dueño actual.

Se añaden constraints compuestas de organización y triggers que rechazan UPDATE/DELETE
en revisiones, concesiones, alcances, revocaciones, comandos y política. Downgrade sólo
sin evidencia ni asignaciones del catálogo nuevo. El catálogo se instala sin asignarlo
a roles. Añadir capacidades nuevas a un rol, asignar ese rol o ampliar su ámbito
requiere Dueño revisado también en los comandos administrativos existentes;
admin.manage no puede autoasignarlas. La misma guarda protege inventory.count.review
y approve cuando hay política nueva activa en la organización; fuera de ella conserva
el gobierno legacy. Retirarlas sigue permitido para revocar acceso.
Las APIs de concesión exigen capacidad explícita del delegado para leer;
una concesión no la instala automáticamente ni concede acciones.

Prefijos `/api/v2`: F1-04 implementa las tres rutas financial-access/grants; F1-05 añade
turnos/cortes según la precisión de implementación al final. F1-06 añade el reporte
operativo y las páginas financieras de pagos/movimientos. Captura nueva conserva el gate de fase 2.
Usar schemas versionados separados con propiedades adicionales prohibidas y centavos
enteros donde corresponda. `projection`, `schema_version=2`, `policy_version` son
metadatos emitidos por servidor, no permisos que el cliente pueda autoconcederse.

| Ruta nueva | Autoridad / resultado |
|---|---|
| `GET /cash/shifts/current`, `/cash/shifts`, `/cash/shifts/{id}` | cash.shift.read + ámbito; `CashShiftOperationalV2`. Current incluye último cierre sólo como estado/identificador. |
| `GET /cash/user-cuts`, `/cash/user-cuts/{id}` | operational.read + ámbito/responsabilidad; `UserCashCutOperationalV2`. |
| `POST /cash/shifts/open`, `/cash/shifts/{id}/close-operationally` | Misma acción canónica autorizada; `CashCommandReceiptV2`. |
| `POST /cash/user-cuts`, `/{id}/counted-cash`, `/{id}/finalize` | capture para primeras dos; finalize para última; resto de §71.3/4/10 y acuse. Rutas contiguas se interpretan bajo `/cash/user-cuts`. No activarlas con captura fase 2 incompleta. |
| `GET /financial/cash/shifts`, `/{id}`, `/{id}/summary` | financial.data.read + dataset cash.shifts; snapshot financiero histórico y contexto de cálculo vigente, sin recalcular original. |
| `GET /financial/cash/user-cuts`, `/{id}` | Dataset cash.cuts; detalles/compensaciones bajo lectura autorizada. |
| `GET /financial/cash/movements`, `/financial/payments` | Datasets cash.movements y sales respectivamente; ámbitos completos, sin autoridad de escritura. |
| `GET /reports/operations` | reports.operational.read o lector financiero sales vigente scoped; sólo reporte de §6. |
| `POST /financial-access/grants`, `/financial-access/grants/{id}/revoke` | financial.delegations.manage AND Dueño; command key, motivo y auditoría, acuse sin datos de caja. |
| `GET /financial-access/grants` | Dueño en su organización; metadata de concesiones. Sesión del delegado recibe sólo capacidades/alcances propios, no lista de terceros. |

Los sufijos abreviados de rutas financieras mantienen el prefijo de su primera ruta
en la misma fila. No hay fallback a un contrato antiguo por error/403/409.
En sucursal con política nueva, las rutas v1 mixtas de turnos/cortes, incluidos
`cash-shifts`, summary, close, list/detail, mutaciones y reopen, responden
HTTP 409 `cash_contract_upgrade_required`, sin cuerpo guardado ni datos financieros.
La compatibilidad se resuelve en clientes antes de activar, no concediendo permisos
financieros para hacer funcionar un parser antiguo. Las acciones de corrección v2
replican los sufijos existentes bajo `/cash/user-cuts`, sólo Dueño, acuse operativo.
Fuera de sucursal activada, baseline legacy permanece; no afirmar privacidad nueva allí.
Listas/consolidados sin sucursal explícita resuelven primero todas las sucursales
implicadas: una ruta legacy mixta que incluya alguna activada devuelve upgrade para
toda la solicitud; no evade política por omitir branch_id ni mezcla DTO incompatibles.

Rutas no mixtas ya existentes pueden conservar versión y contrato financiero, agregando
la guarda vigente antes de query/salida: dashboard, reportes de ventas/gastos/envíos,
conciliación v2/export, pagos y movimientos globales. V1 de conciliación ya bloqueado
no se reabre. Clientes operativos dejan de llamar esas rutas. Para listas mixtas de
pedidos, impresión, gastos y compras se crean proyecciones operativas v2 en los mismos
paths de recurso; v1 financiero queda protegido, nunca cambia de forma silenciosa.
Recepción v2 permite cantidades/identificadores autorizados y conserva máquina de compra.

403 `financial_access_denied`: autoridad insuficiente, sin indicar resultado/alerta.
409 `cash_contract_upgrade_required`: contrato incompatible. 409
`cash_authorization_changed`: autoridad/política cambió durante operación recuperable;
refrescar sesión y reconsultar sin reejecutar el movimiento. Conflictos de key/estado y
otros errores conservan códigos canónicos. No usar 0/null para reemplazar un importe
oculto ni incluir nombres de campos financieros con valores redactados en DTO operativo.

## 5. Proyecciones y replay

| Proyección | Allowlist y restricciones |
|---|---|
| `CashShiftOperationalV2` | id, organization_id, branch_id, register_id, responsible_user_id, estado, opened_at/closed_at, versión, identificador/estado de cierre relacionado. Sin fondo, summary, totals, difference ni indicadores derivados. |
| `UserCashCutOperationalV2` | id, scope, cash_shift_id, responsable/capturista, estado, timestamps y versión; estado de custodia/completitud sólo códigos operativos sin resultado financiero. Declaración propia por separado y sólo a quien la capturó; encargado finalizador ve estado sin importes de otros. |
| `OwnDeclarationV2` | Valores introducidos por el capturista y acuse de confirmación. No precarga esperado; no expone declaración ajena al responsable ausente sólo por ser dueño del turno. El Dueño la consulta por DTO financiero. Campos nuevos de denominación/custodia se completan en fase 2. |
| `CashCommandReceiptV2` | command_id, resource_id, acción, estado operativo, versión, accepted_at, replay boolean, correlation_id y código operativo. Sin snapshot, resultado financiero, cuadratura ni existencia de alerta. |
| DTO financiero | Datos canónicos de dataset concedido; estructura separada, autoridad antes de query y salida. Lista de cortes no incluye dataset de gastos/ventas extra por conveniencia. |

No usar `dict(row)` seguido de borrar algunos campos: construir explícitamente los
DTO. Nuevos campos internos no se publican automáticamente. Cursor/metadatos de lista
operativa no contienen importes serializados; errores, enlaces, headers y eventos
tampoco revelan una condición financiera. Una confirmación que da acuse idéntico para
faltante, cero y sobrante evita el oráculo de cuadratura.

La respuesta de una escritura y su replay siempre usan acuse; el lector financiero
obtiene detalle por GET autorizado separado. `_replay`, `_store` y la recuperación
de `IntegrityError` no devuelven `command.result` directamente. Reautorizar actor,
recurso, acción de consulta del acuse y scope; proyectar la referencia/resultado ya
persistido sin ejecutar nuevamente ni recalcular su snapshot. Si perdió facultad de
ejecutar la acción pero conserva consulta del acuse propio, puede confirmar su estado;
no se le permite ejecutar una acción nueva. Si perdió también lectura, denegar.

Aplicar lo mismo a operational-intents, expense-commands, sync y jobs. No editar
resultados históricos para ocultarlos: mantenerlos internos, controlar proyección y
auditoría. La excepción concurrente es parte del contrato, no un atajo de retorno.

## 6. Reporte operativo y consulta individual

`GET /api/v2/reports/operations`: sucursal obligatoria, period day/week/month y anchor_date
local. Zona canónica de sucursal y límites UTC semiabiertos. Día civil local; semana
ISO lunes 00:00 a lunes siguiente; mes civil del día 1 al siguiente día 1. No reutilizar
el default de últimos 30 días del dashboard como mes. Respuesta: branch_id, period,
start/end, timezone, ticket_count y top_products de hasta diez objetos {position, name}.
No cantidades, precios, total, average, IDs enlazables a detalle financiero, márgenes,
moneda o indicadores de diferencia/alerta. No exportación financiera alternativa.

Ticket conserva fuente confirmada `sales_operation_snapshots` y conteo de order_id
distintos del baseline; ranking usa cantidades de `sales_operation_line_snapshots`
asociadas a esa población, agrupadas por product_id, descendente por cantidad, empate
por product_id estable. Nombre del snapshot más reciente del producto en el periodo,
empate por id de snapshot. No recalcular con precio actual ni inventar una venta al
reimprimir. Correcciones mantienen semántica canónica de sus snapshots, no una fórmula
de neteo nueva. Cantidades de ranking son dato interno de cálculo que no sale del DTO.

Pedidos: precio/importe del pedido atendido sigue visible para cobro. Las listas
operativas v2 muestran identidad, estado y datos operativos necesarios, sin totales,
pagos agregados ni descarga monetaria masiva. El detalle monetario de Cajero exige
relación persistida de atención del pedido; para encargado, un pedido específico de
su sucursal con seguimiento/autorización operativa comprobable. No aceptar un texto
libre "seguimiento" como autorización ni sólo orders.read + branch_id.

Contextos admisibles se derivan del servidor: atención vigente asignada, acción de
pedido autorizado en curso, entrega/liquidación concreta o solicitud de reimpresión
con autorización vigente. Una consulta por folio exacto puede localizar metadata,
pero no abre por sí sola importes históricos. Sin contexto, historial monetario requiere
dataset sales. Toda lectura puntual queda auditada con pedido, actor y contexto.
El contexto está persistido y ligado a actor, pedido, acción y versión; se valida
contra la autoridad actual del actor y recurso. Crear una solicitud, introducir un
motivo, hacer click o tener print.jobs.read/retry no crea ese contexto ni amplía su
alcance. Una reimpresión sólo reutiliza contexto de operación autorizado vigente;
si no existe, no abre el detalle monetario por el solo permiso de reintento.
No endpoint de lotes de detalles ni expand=payments en listas operativas; repetir
por cursor/filtros no amplía contexto. F1-03 debe probar enumeración y IDs ajenos además
del caso válido. Esto limita reconstrucción directa por API, no memoria humana.

Resolución técnica F1-06 del contexto puntual: se reutilizan las relaciones persistidas
de los comandos canónicos; no se agrega una facultad de autoadjudicarse pedidos. La
aceptación registrada con actor en `audit_events`, una modificación ejecutada en
`order_amendments` o una asignación concreta en `delivery_assignments` acreditan atención
del mismo actor mientras el pedido siga operativo y su turno asociado siga abierto.
El actor conserva `orders.read` y el permiso actual de la acción de origen. Una
reapertura `APPROVED` acredita sólo al solicitante/aprobador identificado, para ese
pedido y versión, con la facultad correspondiente vigente; `REQUESTED` no acredita
lectura monetaria. Fuera de esas relaciones se exige `sales` para la sucursal exacta.

`GET /api/v2/orders/{order_id}` exige `expected_version`: el servidor resuelve primero
autoridad y contexto, después contrasta la versión. La lectura usa lock de gobierno y
lock compartido del recurso hasta materializar el DTO. Cada lectura puntual persiste
auditoría con actor, pedido, sucursal, versión del recurso/autoridad/política y referencia
del origen autorizado, sin copiar importes. La evidencia de lectura no se acepta como
origen de un contexto posterior. El cierre del pedido/turno o la pérdida del permiso
invalida la atención ordinaria; la reapertura aprobada y el lector financiero conservan
sus propias reglas. Los comandos conservan la transacción de su llamador; el endpoint
de lectura confirma únicamente la auditoría después de materializar y validar el DTO.
El orden de adquisición es gobierno → sucursal → turno → pedido. La guarda canónica
de escritura entra al bloqueo compartido de gobierno antes de bloquear sucursal, para
que un comando que devuelve detalle no lo tome después de sus efectos. La consulta
de aprobación no espera un bloqueo de solicitud reteniendo el pedido que esa solicitud
pretende aplicar; la aplicación canónica debe adquirir sucursal/pedido para confirmar.
Cotización sobre pedido existente conserva la misma autoridad puntual y confirma la
auditoría de esa lectura; una cotización nueva no crea relación de atención.

## 7. Canales indirectos y permisos colaterales

El manifiesto F1-01 es lista de revisión por familia, incluyendo aliases. Para cada
handler, F1-03 fija negativo y positivo con el destino siguiente:

| Familia | Destino obligatorio bajo política nueva |
|---|---|
| DASH/REPORT/RECON | Guarda financial.data.read + datasets antes de consulta/Excel; operativo sólo §6. Conciliación requiere reconciliation y cualquier dataset adicional publicado. |
| AI | Ejecutivo/CRM que use ventas: sales y cada sucursal consultada antes de construir contexto/modelo. Comparación corporativa no admite branch_id=None como bypass. OCR/compras exige su autoridad administrativa propia. No dar a actor operativo un resumen de LLM derivado de contexto financiero. |
| AGENT | Capability técnica no delega autoridad humana. Lecturas financieras quedan denegadas bajo política nueva mientras no exista audiencia humana explícita con autoridad vigente; F1 no crea ese protocolo ni lo activa por defecto. Otras capabilities técnicas conservan su función scoped. |
| ORDER/PAYMENT/DRIVER/FISCAL | Detalle/comprobante de operación autorizada §6; global, histórico monetario o masivo requiere sales, más permiso fiscal/operativo original si aplica. Ni lectura ni ocultamiento autorizan emisión, cancelación o liquidación. |
| PRINT | Lista humana sólo metadata permitida; ticket puntual por contexto §6. Agente técnico recibe sólo trabajo asignado a dispositivo/branch. No usar listado, retry ni descarga de payload como exportación global. |
| SYNC/INTENT | Transporte conserva payload original para integridad; observador humano recibe estado/acuse autorizado. Device puede transportar operaciones necesarias sin convertirse en lector financiero humano. |
| PURCHASE/CASH-CONTEXT | Recepción de cantidades contra compra aprobada sin costos. XML original/preview/precios requieren purchases.prices.read además de autoridad de compra. Contexto de caja sólo ids/estado, no fondo/summary. |
| EXPENSE/MOVEMENT | Acción individual conserva sus permisos de escritura y recibo propio; historial monetario requiere expenses/cash.movements. Compensación conserva autoridad canónica, no se abre por delegación. |
| INVENTORY | Costos requieren inventory.costs.read. Conteo ciego distinto de revisión/aprobación administrativa; permisos funcionales de CC-D09 no nacen de financial.data.read. Catálogo, recetas, precios siguen gobierno administrativo. |
| AUTH | Capacidades de sesión son informativas; ninguna ruta confía sólo en su copia o etiqueta de rol. Cambios de autoridad incrementan versión e invalidan cachés. |
| PUBLIC | Cliente/canal conserva su pedido/precio por contrato propio; no tiene acceso a turnos, agregado, eventos privados ni grants de empleados. |
| CUSTOMER | Cliente operativo v2 excluye order_summary financiero, recent_orders monetarios, ticket promedio y segmentos derivados de gasto. Consulta de contacto/domicilio para venta conserva su permiso; historial/CRM financiero requiere sales y alcance de cada pedido, no sólo sucursal de origen del cliente. |
| CATALOG | Catálogo operativo mantiene precios de venta necesarios; costos/precios de compra, originales de importación y configuración administrativa conservan su autoridad específica, sin hacerlos accesibles por orders.read o financial.data.read. |
| INTEGRATION | Ingesta autenticada/idempotente conserva original. Logs humanos muestran metadata segura; payload monetario original requiere autoridad financiera y scope verificable además de permiso administrativo. |

Listados de logs de integraciones no deben devolver payload original monetario por
admin.manage a un operador. Metadata de diagnóstico sin importes; consultar original
conservado exige autoridad administrativa y financiera de las sucursales afectadas.
No eliminar evidencia ni publicar motivos libres/PII en logs generales.

Refinamiento F1-06 de logs: las cuatro listas de proveedores conservan admin.manage
y exigen identidad humana vigente. Si cualquier sucursal de la organización tuvo
activación, toda la lista usa metadata cerrada: schema_version=2, projection=operational,
id interno, proveedor, estado enumerado y fechas. Se omiten payload_raw, firma,
error_message, event_id y event_type libres; estado desconocido se presenta como unknown.
No se cargan esas columnas sensibles. Este mínimo de privacidad persiste al suspender
la política. Como el registro no tiene sucursal resuelta, ningún parámetro branch_id
ni rol permite descargar el original por estas rutas. La ingesta conserva originales;
un futuro acceso al original necesitará demostrar alcance, además de ambas autoridades.
La lista audita sólo proveedor y revalida autorización tras commit; fallo de auditoría
o revocación impide entregar respuesta. Sin activación se conserva el contrato anterior.
El límite de consulta se valida entre 1 y 200 (por defecto 50); evita que un límite
negativo se interprete como exportación ilimitada. El servicio valida autoridad incluso
cuando se invoca sin pasar por HTTP; las cuatro rutas humanas usan no-store.

## 8. Sesiones, gateway y transición

La sesión publica capability, scopes propios y versiones; ningún importe. Antes de
aplicar una respuesta tardía el cliente comprueba actor/branch/version actuales; limpiar
datos financieros en memoria al cambiar contexto/revocar. API/descargas financieras
`Cache-Control: no-store`; no persistir esos DTO en localStorage, IndexedDB ni service
worker. Excluir API del service worker actual se conserva, no basta para proteger React
state o respuestas en vuelo. No se borran outbox ni evidencias para limpiar la pantalla.

F1 no emite lectura financiera offline. Gateway sólo proyecciones operativas/contextos
individuales autorizados, scope org/branch/device/actor y lease vigente; dispatcher
`/api/v1/local/order-api/{path:path}` requiere nueva compatibilidad antes de activar.
No devolver turno completo en cash/shifts/current ni historial monetario por accounts.
Estado local de comandos filtra actor/contexto además del device. Revocación central
no promete llegar instantáneamente desconectado: expiración/fencing y pendientes de
CC-D10, sin renovar autoridad localmente. Acuse durable/conteo offline integral es fase 2.

Preflight por sucursal: turnos/conteos pendientes resueltos; fuentes sincronizadas;
usuarios revisados individualmente; grants incompatibles resueltos; leases viejos
agotados/reconciliados; versiones API, contratos, POS/Admin y gateway compatibles. No
inferir completitud por cola vacía. Revisión de política persistida tras autorización
de activación separada, entre turnos, sin mutar historia. Revisiones son monotónicas:
rollback detiene expansión/operaciones incompatibles y usa versión compatible, nunca
desactiva privacidad ni vuelve a grant amplio. Sin capacidad completa, no se activa.

## 9. Pruebas que entrega el diseño a F1-03

TC-450/451/462: fixtures dos organizaciones y sucursales, Dueño gobernado, Cajero,
Líder, Cajero jefe, Admin/Supervisor con roles acumulados, delegado de sólo cash.cuts,
revocado y dispositivo; autorización por dataset/branch/acción independiente. Baseline
conservado; nuevo RED debe alcanzar la ruta real y fallar por campo/autoridad, no 404.

Contratos de salida exhaustivos: allowlist/ausencia de claves financieras recursiva,
lista/detalle/mutaciones/replays concurrentes, intents y errores. Caso diferencial:
mismo estado operativo con diferencia positiva, cero y negativa produce acuse de la
misma forma y sin señal financiera. Alias v1 denegado sin fallback bajo nueva política.

TC-461/464: versión vieja, grants generales, carrera revocación/lectura/descarga y
sesión tardía; PostgreSQL para locks/unicidad/migración y SQLite para compatibilidad
del gateway, sin fingir que SQLite prueba concurrencia PostgreSQL. Migración aditiva
preserva hash/relaciones históricas; rollback conserva restricciones. No migración ejecutada.

TC-462: reporte day/week/month con medianoche y zona, empate, correcciones/reimpresión,
fin de año/mes y cambio horario; no cantidades/precios en JSON/descarga. Paginación,
IDs/expand y solicitudes/reintentos de impresión en serie no reconstruyen importes.
TC-452/458/459/465: lectura no finaliza/corrige, no concede captura inicial Dueño; cobro
puntual, recepción sin costos y KDS siguen autorizados. No hacer pasar tests con nuevos
silenciamientos ni omisiones. Pruebas semánticas UI verifican que no pide endpoints F.

Los cuatro problemas operativos de §71.13 conservan sus señales. Para este incremento:
denegaciones por dataset/branch/versión, replay revalidado y bloqueadores de preflight;
sin importes/payloads en logs. Evidencia y refutación documental se registran en el
plan de fase 1; implementación, CI, migraciones y piloto siguen pendientes.


## 9. Precisión de implementación F1-05

F1-05 conecta `FinancialAuthority` con `cash_views`, `cash_command_views` y sus rutas
v2; `cash_legacy_guard` bloquea todos los handlers mixtos v1 de turnos/cortes en
sucursales activadas. Sin política activa, conserva baseline v1; v2 devuelve
`cash_policy_not_active`. No se escribe ninguna revisión de política en runtime nuevo.
La activación real y compatibilidad de clientes/gateway siguen en F1-07/09 y CC-D11.

Proyecciones operativas, declaración propia, financieras, listas y current tienen
schemas cerrados. Los SELECT operativos enumeran columnas sin importes. La declaración
histórica separada `/cash/user-cuts/{id}/own-declaration` devuelve únicamente el conteo
y UTC que capturó el actor; identifica al capturador en el comando `count` persistido,
no por responsable/creador del corte. No acredita denominaciones, sustitución ni custodia
fase 2. El lector de sucursal se resuelve por Dueño revisado o capacidad exacta finalize,
además de operational.read; el resto sólo consulta sus cortes/declaraciones capturadas.

Las listas v2 usan cursor por id y límite 1..100, filtro de sucursal y caja; autorizan
cada sucursal solicitada antes de cargar resultados, incluso páginas vacías. Omitir
sucursal pide el ámbito organizacional completo, no filtrado silencioso. No se promete
compatibilidad del cursor v1. F1-07 deberá adaptar consumidores a estos contratos.
`register_id` corresponde a register_code; versión de turno 1 abierto / 2 cerrado es
metadata informativa del acuse, no un nuevo token CAS ni modificación del modelo físico.

Lectura financiera exige cash.shifts o cash.cuts según recurso. Detalle de turno incluye
snapshot histórico y cálculo canónico vigente separados; `/summary` sólo publica
identificador, cierre y resúmenes. Los schemas no rellenan claves ausentes del snapshot
antiguo. Cortes incluyen operaciones asociadas y compensaciones, sin recalcular el corte
original ni conceder datasets adicionales. No hay migración F1-05.

Comandos requieren capacidad exacta y lectura operativa del acuse antes de ejecutar;
revalidan lectura y política después del commit/recuperación. Si cambia revisión de
política devuelven `cash_authorization_changed`; se consulta/reintenta la misma key,
no se repite el efecto. Replay admite pérdida de capacidad de ejecución cuando conserva
consulta propia. La identidad incluye actor, payload, recurso y acción; nunca se
reescribe el resultado histórico. Para acuses de cortes se extraen sólo estado,
versión e identificadores del JSON persistido, sin publicar su cuerpo financiero.
Correcciones devuelven el id de solicitud/compensación y su estado (REQUESTED,
APPROVED, REJECTED o COMPENSATED); version sigue siendo la del corte original.

El HTTP nuevo de crear/contar/finalizar permite recuperar comandos propios ya
persistidos, pero bloquea efectos nuevos con `cash_capture_not_ready` hasta fase 2.
El dominio existente sí queda protegido con capacidades capture/finalize separadas y
sus invariantes anteriores; las pruebas directas verifican esa separación. Corrección
compensatoria existente mantiene Dueño en cada etapa, sin segundo aprobador.
Apertura/cierre v2 reutilizan los comandos canónicos y, cuando está habilitado el
workspace, su contexto e intent existentes; el intent recibe un acuse operativo.
Comandos toman gobierno exclusivo antes de locks de recurso; lecturas mantienen el
shared lock hasta materializar. Revalidación tras commit no revierte un efecto confirmado.

Preguntas operativas del incremento: ¿se rechazó por autoridad, contrato antiguo o
cambio de política? Usar estado HTTP/código de negocio y métrica de comando de corte
existente, sin SQL ni payload. ¿un reintento generó otro efecto? Usar command_id/replay
del acuse y evidencia persistida de key/acción; las métricas PCO-006 distinguen replay.
No añadir importes, motivos libres, claves idempotentes o conteos a logs de diagnóstico.

Evidencia R3 y límites en [plan §11](implementation-plans/CORTE-CIEGO-001-FASE-1.md#11-f1-05--proyecciones-de-turnos-y-cortes).

## 10. Precisión de implementación parcial F1-06

`financial_reads.require_financial_read` retiene el lock de gobierno durante lectura y
materialización, y conserva el baseline donde no se ha activado política. Una consulta
consolidada no se reduce a las sucursales permitidas. Los readers nuevos v2 exigen política
activa y autoridad aun si la página queda vacía. Sus cursores usan id creciente y límite
1..100; no transfieren permisos entre solicitudes. Las páginas incluyen `items` y
`next_cursor`; cada registro lleva proyección financiera, schema_version=2 y policy_version.
Los contratos publicados son `operational-report-v2`, `financial-payments-page-v2` y
`financial-movements-page-v2` en packages/contracts/schemas. No sustituyen contratos v1.

Conciliación expone simultáneamente sales, cash.shifts, cash.cuts, cash.movements y expenses:
exige esos pares además de reconciliation, y conserva permisos funcionales anteriores.
El dashboard sales mantiene su envoltura de notificaciones, pero bajo política nueva no
consulta `audit_events.payload`: sólo devuelve código de caja derivado del join, identidad,
acción y fecha. Su venta no concede lectura de payloads históricos de caja.

El ejecutivo compara todas las sucursales y utiliza costos: exige sales y
inventory.costs.read en cada una. El contexto se materializa bajo autorización; se libera
transacción, revalida y libera otra vez antes de I/O. Revalida después del proveedor y
rechaza cambio de versión/política o pérdida de alcance. Los lectores fiscales incorporan
sales a la guarda fiscal de lectura y repiten ambas después de descargar. La URL de
PDF/XML sigue siendo privada de API; no se publica el enlace original del proveedor.

Lecturas operativas adicionales de F1-06:

- `GET /api/v2/orders/accounts` exige sucursal, actor humano vigente y `orders.read`.
  Conserva filtros y cursor del feed canónico mixto (pedidos y solicitudes web pendientes),
  pero hidrata únicamente columnas operativas explícitas y el nombre del cliente extraído
  del JSON. No carga el detalle financiero ni el snapshot completo. El listado no concede
  contexto de lectura individual y no devuelve indicadores derivados de saldo/pagos.
- `GET /api/v2/customers` exige la misma autoridad de operación y política activa;
  conserva búsqueda por nombre/correo/teléfono, origen de sucursal y paginación acotada.
  Entrega contactos, domicilios, perfil fiscal y referencia de domicilio importado mediante
  schemas cerrados; excluye segmento de consumo y resumen/historial de pedidos antes de
  consultar columnas monetarias. Coordenadas mantienen precisión interna. El total del
  listado cuenta contactos, no ventas. La referencia importada se extrae como campo JSON
  aislado, con alcance de organización/sucursal; no se devuelve el payload de importación.
- Listados legacy y resumen interno de clientes requieren cobertura financiera de ventas
  organizacional: el origen del cliente no limita las sucursales de su historial. El permiso
  funcional de la ruta sigue siendo adicional. Ninguna de estas lecturas concede escritura.

Contratos publicados: `operational-order-accounts-page-v2.schema.json` y
`operational-customers-page-v2.schema.json`, comparados con modelos runtime en pruebas.
Pendiente integrar consumidores y ampliar los campos operativos necesarios sin introducir
derivados monetarios; no usar el contrato antiguo como fallback de una denegación.

El detalle individual v2 y el servicio de detalle validan el contexto de §6; la
proyección `order` conserva precio, partidas, pagos y operación de ese pedido con
contrato cerrado (`attended-order-detail-v2.schema.json`). No carga eventos/historia
de ventas/correcciones para la vista operativa ni devuelve snapshots crudos de cliente,
receta, consumo o auditoría. El detalle legacy financiero conserva su historia autorizada.

No se acredita aquí impresión contextual, replay completo, recepción, UI ni transición;
el avance y pendientes de F1-06 se mantienen en el plan, no como garantía de fase completa.


### Refinamiento F1-06: acuses humanos de impresión

Bajo política activa, el listado humano de trabajos y la respuesta de retry consultan
columnas explícitas de metadata. No seleccionan `print_jobs.payload` ni `last_error`
(texto libre); ni siquiera el lector financiero recibe un listado de tickets crudos.
El contenido persistido se conserva para la frontera técnica de impresión.

Retry exige `print.jobs.retry` vigente más contexto de pedido de §6 antes de encolar,
también al reutilizar una clave. Lectura financiera no sustituye ese permiso funcional.
El acuse contiene metadata cerrada de trabajo/intento; no incluye hash, clave ni error
capturado. La transacción serializa autoridad y efecto; la auditoría de retry agrega
origen de contexto y versiones sin importes. Después de commit vuelve a comprobar
contexto antes de entregar el acuse. Fallar después del commit puede dejar el intento
encolado: la misma clave recupera el resultado sólo si conserva autoridad.

Las rutas humanas rechazan tokens de audiencia técnica y usan respuesta no-store y
error de persistencia sin SQL. Se conserva compatibilidad previa fuera de política.
Este incremento no acredita aún asignación técnica de dispositivos, payload de cocina
ni todos los replays de pedidos; esas fronteras siguen pendientes de F1-06.


### Refinamiento F1-06: transporte técnico de impresión

Con política activa, `GET /api/v1/print-attempts/pull` entrega hasta 100 trabajos
QUEUED de la credencial/sucursal, sólo metadata, con `schema_version: 2` y timestamp
UTC. La asignación exclusiva se establece por el CAS canónico de claim. La lectura
nueva `GET /api/v1/print-attempts/{attempt_id}/payload` requiere esa misma credencial
persistida `print.agent`, vigente, organización/sucursal activas y estado CLAIMED del
intento y trabajo. No admite búsqueda histórica ni descarga después de ack/fail/recovery.

El servicio valida antes del SELECT del payload y mantiene locks compartidos de
credencial/alcance e intento/trabajo; orden de recursos: intento antes de trabajo,
como los escritores canónicos. La lectura audita sólo device/id/tipo, confirma y vuelve
a validar asignación y credencial antes de devolver. Si revocación confirma entre la
auditoría y la respuesta, deniega. Bytes entregados antes de revocar no son retractables.

Las proyecciones publicadas `print-ticket-payload-v2` y `print-kitchen-payload-v2`
son cerradas, también en modificadores. Ticket conserva precio de la operación, efectivo
y cambio si existían y cargo de entrega sin configuración cruda. Cocina conserva
folio/partidas/instrucciones/cantidades sin pagos, precios ni importes anidados. No se
reescribe el snapshot original. Datos inválidos o fallo de auditoría impiden la salida;
el error no incluye SQL ni valores capturados. Pull/claim/payload usan no-store.

Fuera de política, pull/claim conservan compatibilidad anterior; payload nuevo requiere
política activa. No se encontró un cliente/spooler de impresión ejecutable en este
repositorio: antes de activar una sucursal se debe acreditar consumidor compatible con
metadata -> claim -> payload -> impresión -> ack/fail. F1-09 debe bloquear una
configuración que sólo pueda usar el pull antiguo; no es una certificación de impresora
física ni una autorización de configuración productiva.


### Refinamiento F1-06: acuses de alta de pedido y confirmación de pago

Bajo política activa, alta de pedido, recuperación por clave y confirmación/replay
de pago devuelven `OrderCommandReceiptV2`: referencia del recurso y comando, sucursal,
acción, aceptación y fecha originales, versión de política; ningún importe, cambio,
receta ni snapshot. Se requieren clave y lectura operativa `orders.read` vigente antes
de un efecto nuevo; ejecutar exige además el permiso funcional canónico. Un acuse es
propio: el actor persistido del comando debe coincidir. Recuperarlo no exige conservar
el permiso de ejecutar otra operación, pero sí la lectura actual y el alcance.

Los lectores de comandos seleccionan metadata explícita, sin response_snapshot. Los
snapshots originales se conservan internos; fuera de política se mantiene el contrato
legacy y su permiso funcional. El hash de pago se construye con la intención recibida,
sin cargar el total histórico para reconocer una clave. Ramas de replay e IntegrityError
usan la misma proyección. La aceptación del acuse es histórica; no se presenta como
estado actual del pedido ni certificación de conciliación.

El dominio conserva `commit=False`: efecto, comando y auditoría del acuse pertenecen
a la transacción exterior. Si el efecto ya confirmó y falla después la auditoría de
entrega del acuse, responde 503; la misma clave recupera el único efecto existente.
Después de confirmar auditoría se revalida lectura/política antes de entregar el acuse.
Esto no promete rollback de un pago que ya había confirmado.

Precio y cambio se consultan en `payment-preview` del pedido con contexto §6 vigente,
antes de leer dinero. El endpoint confirma auditoría de lectura y revalida contexto/
versión antes de responder. El comando de cobro sigue recalculando y validando dentro
de sus locks; no confía en la vista previa. Consumidores de UI deberán separar preview,
acuse y detalle en F1-07. Liquidaciones por lote siguen en revisión.

### Refinamiento F1-06: recuperación de solicitudes operativas

`operational-intents` conserva su acuse cerrado de cinco campos y la prueba transaccional
de efecto/no efecto. Bajo política activa, preparar, ejecutar, listar y resolver exigen
lectura vigente del acuse propio en la sucursal: `orders.read` para pedido/pago y
`cash.shift.read` para acciones de caja. Preparar/ejecutar conservan además sus permisos
funcionales y workspace; recuperar no vuelve a exigir escritura ni renueva su autoridad.
Se verifica lectura antes de modificar estado y después del commit antes de responder;
un cambio de política durante la entrega exige reintento con la misma identidad.
Los tres endpoints humanos rechazan audiencias de agente/dispositivo.

La prueba de ejecución selecciona identificadores y enlaces, no snapshots monetarios.
Para caja extrae del JSON exclusivamente los IDs requeridos; la prueba de compensación
compara importes en SQL y devuelve sólo el resultado booleano, conservando igualdad,
dirección contraria, actor, turno, sucursal y enlaces originales. No altera snapshots,
movimientos ni la máquina de estados. La lista propia no entrega páginas parcialmente
autorizadas; valida todas las sucursales/tipos incluidos antes de devolverla.

### Refinamiento F1-06: comandos humanos de movimientos de caja

Crear/compensar un movimiento bajo política activa devuelve `CashMovementReceiptV2`,
especialización cerrada del acuse de caja: acción create/compensate, estado confirmed,
versión 1 y referencias del comando/movimiento. No incluye importe, concepto libre,
evidencias, `summary_at_commit` ni `current_summary`, incluso para un lector financiero.
El comando y sus snapshots conservan íntegros los datos históricos. La respuesta no
recalcula resúmenes en replays. Identifica el ámbito desde el movimiento persistido,
no desde una sucursal alterada en el reintento; exige actor original y `cash.shift.read`
actual antes de ejecutar/proyectar y tras commit. Una acción nueva conserva todas las
guardas canónicas (incluida autoridad de compensación y vínculo a gasto/documento).

La frontera humana envuelve el núcleo transaccional existente, sin commits internos
en modo `commit=False`; el intent conserva la transacción exterior. La reconciliación
técnica de gateway usa ese núcleo sólo después de sus guardas de dispositivo, lease,
actor y alcance, y mantiene su acuse cerrado de id/estado. No transporta el resumen
financiero interno ni obtiene autoridad humana. Audiencia técnica no se admite en
los dos endpoints humanos. Clientes se adaptan en F1-07 y compatibilidad en F1-09.

### Refinamiento F1-06: liquidaciones de repartidores

Bajo política activa, el selector de repartidores conserva identidad, nombre, estado
y número de pedidos elegibles; no proyecta ni calcula la suma monetaria. Conserva
repartidores inactivos/trasladados con cobros pendientes de la sucursal. La liquidación
mantiene pagos, enlaces y snapshot histórico atómicos, pero responde con un acuse
cerrado `DriverSettlementReceiptV2`: versión/proyección/política, acción, comando,
liquidación, sucursal, repartidor, estado, número de pedidos y fecha. No devuelve
items monetarios, total ni información del turno. La métrica de resultado no lleva importe.

La lectura del acuse exige identidad original y `orders.read` vigente en la sucursal;
se revalida después del commit. Una operación nueva conserva `payments.confirm`,
workspace, caja abierta y todas las reglas de elegibilidad existentes. Recuperar mediante
POST `/driver-cash-settlements/recover`, con el cuerpo/clave originales, no produce pagos
ni exige conservar escritura/workspace: sólo recupera un comando existente propio.
Un comando ausente falla sin ejecutar. Los replays seleccionan metadata, nunca el
snapshot monetario bajo política activa, incluyendo recuperación por conflicto de
persistencia. Las rutas humanas rechazan credenciales técnicas y usan `no-store`.
Sin política activa permanece el contrato histórico y su permiso de cobro; recuperación
sin escritura se limita a la política nueva. No cambia la fórmula ni el dominio de cobro.

### Refinamiento F1-06: acuses de reapertura/corrección de pedidos

Las respuestas de request/approve/reject/apply bajo política activa son acuses cerrados
`OrderReopenReceiptV2`: versión/proyección/política, comando, solicitud, pedido, acción,
estado histórico de esa acción, fecha y referencia de corrección sólo al aplicar.
No contienen total corregido, delta, compensación monetaria ni snapshots. El detalle
financiero de la corrección permanece en la consulta de pedido autorizada para sales;
el acuse no concede ese acceso. La regla CC-D07 de corrección de declaración de caja
no se traslada automáticamente al workflow de reapertura de pedidos.

Reintentar exige actor original, clave/cuerpo/objetivo originales y `orders.read`
vigente en la sucursal persistida. No exige conservar el permiso de ejecutar otra
acción ni reabre su estado. Nuevas acciones conservan permisos, autoridad de Dueño
para aplicar, versiones y compensaciones canónicas; no se modifica la aprobación
funcional de pedidos en este incremento. El bloqueo de gobierno precede al de
sucursal/solicitud/pedido y la auditoría del acuse comparte el commit con el efecto.
Después del commit se revalida lectura/política antes de responder.

El listado conserva su DTO operativo existente, sin cargar before_snapshot; valida
lectura vigente de todas las sucursales incluidas. Crear una solicitud sigue sin
habilitar lectura monetaria. Las rutas humanas rechazan credenciales técnicas, usan
no-store y errores de persistencia seguros. Los snapshots históricos no se reescriben.

### Refinamiento F1-06: modificación de pedidos y respuestas de envío

Bajo política activa, `amend_order` entrega `OrderAmendmentReceiptV2`: metadata de
comando/pedido/sucursal, versión resultante histórica, estado accepted, fecha y
política. No devuelve líneas monetarias, cargos, pagos ni el delivery_response guardado.
La consulta puntual autorizada entrega el detalle actual por separado. El actor
original y orders.read vigente son necesarios para recuperar; una acción nueva
conserva orders.amend, versión, producción pendiente, ausencia de pago y fencing.
La auditoría del acuse pertenece a la misma transacción; commit=False conserva al
llamador como dueño del commit, y se revalida autoridad tras confirmar.

Las nuevas modificaciones guardan el hash de intención completo en after_snapshot,
sin migrar ni reescribir historia. Para envíos antiguos se reutiliza delivery_command_hash.
Un comando histórico sin hash no permite demostrar igualdad de un cuerpo reenviado:
POST de ejecución responde order_amendment_recovery_required sin efecto. La nueva
ruta POST `/orders/{order_id}/amendments/recover` recupera sólo el acuse por pedido,
clave e identidad original, sin aceptar un cuerpo nuevo ni ejecutar si no existe.
Esta recuperación también sirve para comandos nuevos. Nunca reconstruye un hash
supuesto a partir de líneas históricas incompletas; un actor histórico nulo no prueba
propiedad del comando. Los replays leen columnas/identificadores JSON, no snapshots
monetarios. El contrato legacy se conserva fuera de política activa.

La nueva ruta de recuperación requiere política activa; fuera de ella rechaza con
cash_projection_not_available, sin recuperar snapshots ni ejecutar modificaciones.
La metadata histórica de versión no implica que el pedido siga editable o atendido.

### Refinamiento F1-06: gastos y recuperación

Los resúmenes y la lista monetaria v1 exigen dataset expenses además del permiso
funcional original. La lista operativa v2 conserva paginación/filtros sin importe,
impuesto, notas, referencia, evidencia ni snapshots; incluye id/sucursal/concepto,
fecha, estado, versión, medio de pago, autor y timestamps. El contexto de caja sólo
selecciona id/register_code/opened_at, nunca fondo o cierre.

El detalle monetario histórico exige expenses. Un borrador propio puede consultarse
con expenses.read/manage, versión esperada exacta y prueba de creación/edición ya
ejecutada por ese actor para esa misma versión. Conocer el id o crear una intención
no acredita atención. Confirmar/cancelar no concede lectura histórica; otros actores
conservan autoridad de acción, no acceso implícito al importe. La lectura puntual
queda auditada y se revalida tras commit.

Crear/editar/confirmar/cancelar gasto bajo política devuelve ExpenseCommandReceiptV2:
ids del comando/documento/sucursal, acción, versión/estado históricos, fecha y política,
sin el result monetario guardado. El hash conserva actor/kind/target/body canónicos.
Replay y GET de recuperación exigen actor original y expenses.read vigente, sin
requerir permiso de escritura. Un intento abandonado se representa explícitamente
como abandoned y no puede ejecutarse con la misma clave. Resolver un intento existente
valida tipo/objetivo/sucursal antes de recuperar. Resolver uno desconocido conserva
workspace/permisos de escritura y la lápida terminal que bloquea solicitudes tardías.
Los comandos de conceptos conservan su contrato administrativo no monetario.

Gobierno precede a comando/documento/concepto/caja; acuse y efecto comparten commit,
con revalidación posterior. Las respuestas originales internas y el ledger no se
reescriben. Todas las fronteras humanas de gastos rechazan audiencias técnicas,
usan no-store y errores de persistencia seguros. F1-07 adapta los consumidores.

### Refinamiento F1-06: respuesta de cancelación

La cancelación bajo política devuelve un acuse cerrado OrderCancellationReceiptV2:
schema/proyección/política, acción, id del pedido/sucursal, estado CANCELLED y
clasificación/tipo de cancelación. No serializa el pedido, importes, cliente ni tareas
completas. Exige lectura operativa vigente además del permiso original de cancelación;
la autorización exacta de CC-D08 sigue como gate obligatorio de F1-08.

Gobierno y autoridad preceden al bloqueo de sucursal y a la lectura del pedido. Efecto,
auditoría de negocio y auditoría del acuse comparten transacción; tras commit se revalida
la autoridad antes de entregar. commit=False conserva el control del llamador.
La frontera HTTP es humana, no-store y usa errores de persistencia seguros. La política
inactiva conserva el contrato anterior con revalidación al entregar. No se introduce un
comando idempotente nuevo: repetir una cancelación sigue rechazándose como ya cancelada;
el estado se consulta por las vistas operativas autorizadas. Se conservan las guardas de
pago, producción, liberación de reserva y merma/recuperación posteriores a producción.

### Refinamiento F1-06: aceptación y asignación

Aceptar una intención pública, aceptar un pedido pendiente y asignar un repartidor
entregan OrderAcceptanceReceiptV2 bajo política: ids, fuente/acción, estado del acuse,
fecha y política, sin importes ni snapshots. El detalle atendido sigue en su consulta
separada. Un replay exige lectura vigente y prueba persistida del actor original
(comando, auditoría de aceptación o asignación); no exige repetir permiso de escritura.
El hash de aceptación pública conserva intención, versión y repartidor originales.
Los originales internos no se reescriben ni se reconstruyen a partir del acuse.

Gobierno/actor preceden al bloqueo de sucursal y lectura de estado. Efecto y auditoría
del acuse comparten commit y se revalida al entregar. commit=False conserva la
transacción del llamador. Ambas rutas de aceptación y la asignación son humanas,
no-store y con errores seguros. Rechazos, inventario, reserva, producción y cálculo
de importes conservan el dominio existente; CC-D08 permanece como gate F1-08.

### Refinamiento F1-06: historial financiero de repartidores

GET /drivers/{driver_id}/deliveries es historia financiera, no un acuse operativo.
Con política requiere sales y admin.manage de forma independiente, antes de seleccionar
importes/snapshots. branch_id opcional limita SQL a esa sucursal; omitirlo solicita
consulta organizacional y exige todo ese alcance, nunca un subconjunto silencioso.
La sucursal actual del repartidor no autoriza su historia de otras sucursales.
El historial autorizado mantiene el contrato existente y sus originales. La consulta
es humana/no-store, audita sólo actor/recurso/alcance y revalida ambas autoridades
tras commit; fallo de auditoría o revocación impiden entregar los datos.

### Refinamiento F1-06: bandejas de canales

Las cuatro listas GET /pos/{uber-eats|didi-food|rappi|whatsapp}/orders usan el listado
operativo de pedidos bajo política, extendido sólo con channel. El contrato cerrado
ChannelOrderOperationalV2 conserva identidad, sucursal, caja/turno, estado, servicio,
fecha, etiqueta de cliente y versión; no carga importes, líneas monetarias, modificadores
con precio ni snapshots completos de cliente/domicilio. El detalle monetario mantiene
su consulta y contexto separados. El filtro status se aplica a la consulta operativa;
el límite conserva 100 resultados y no habilita expansiones financieras.

La identidad humana y orders.read de sucursal se verifican también en el servicio.
Se audita provider/política sin payload original y se revalida tras commit. Fuera de
política se conserva el contrato anterior, protegido por la misma autoridad funcional.
F1-07 adapta las cuatro bandejas al DTO; cambiar estado no es una lectura financiera
ni queda autorizado por esta proyección. Sus guardas se revisan en F1-08.

### Refinamiento F1-06: diagnóstico humano de sincronización

GET /sync/events distingue transporte del gateway autenticado de diagnóstico humano.
Bajo política, el humano con sync.events.read scoped recibe sólo id, branch_id,
sync_command_id, checkpoint y occurred_at en SyncEventOperationalV2. No se seleccionan
payload ni event_type libre; originales quedan para transporte autenticado. Se conserva
checkpoint ascendente/límite 100, auditoría, no-store y revalidación antes de entrega.
El permiso de diagnóstico no concede finanzas ni identidad técnica. Fuera de política
se conserva el contrato previo. La transición y suspensión se verifican en F1-09.

Precisión técnica F1-09: una revisión `suspended` no equivale a ausencia de política.
Los probes comunes que deciden entre v2 y legacy fallan con
`cash_policy_suspended` antes de consultar datos o ejecutar comandos; el rollback no
restaura contratos amplios. Los diagnósticos que ya tienen un mínimo permanente de
privacidad (logs de integración) conservan sólo metadatos. La suspensión no revoca
automáticamente concesiones ni modifica registros históricos. Reactivar exige revisión
monotónica compatible y preflight; este guard no habilita activación productiva.

Precisión F1-07 de sesión: `/auth/session` incorpora `financial_access` con
schema_version 2, authorization_version y una entrada por sucursal ya permitida:
branch_id, policy_version, state (legacy/active/suspended), capabilities booleanas
y datasets financieros propios. Las capacidades se calculan con el evaluador central,
no desde nombres de rol ni el grant general. Estado suspended conserva metadatos de
política pero capacidades/datasets vacíos; legacy no anuncia privacidad nueva. No
incluye concesiones de terceros, cifras ni historial. El snapshot orienta navegación;
las operaciones vuelven a autorizar en servidor y no aceptan este snapshot como token.

Una revisión prepared anterior a cualquier activación conserva el modo legacy, sin
asignar autoridad nueva. Prepared posterior a activación/suspensión nunca restablece
legacy: espera resolución explícita con privacidad conservada.
