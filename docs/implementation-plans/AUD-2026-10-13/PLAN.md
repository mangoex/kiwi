# AUD-2026-10-13 - Plan integral de remediación de RestaurantOS

**Preparado para:** Miguel Gonzalez / Humanio, Potenciando Humanos.

**Fecha:** 13 de octubre de 2026. **Estado:** propuesta de implementación, no producto corregido.

**Baseline verificado:** `origin/main e1422dc591173aed7151f7a5401f2a2a0060f558`.
**Alcance:** los 18 hallazgos H01-H18 y las 5 brechas B01-B05 de la auditoría de compras/sucursales.

## 1. Resultado esperado y autoridad

Entregar operación multisucursal consistente, recepciones exactas y recuperables, fronteras fiscales veraces, compras fiscales con cuentas por pagar y recomendaciones explicables. Cerrar un hallazgo exige su escenario negativo convertido a aceptación y evidencia del componente afectado; agregar una pantalla o pasar compilación no lo cierra.

Este paquete es documental R0 con cálculos de referencia aislados. Sus incrementos de implementación son R3 cuando afectan permisos, persistencia, caja, inventario, fiscal, offline o integraciones. No modifica runtime, documentos históricos ni estados de la matriz canónica. El plan no autoriza despliegues, migraciones, flags ni reparaciones productivas.

Se sigue el marco canónico **PRD -> SDD/ADR -> BDD -> TDD -> matriz -> implementación**. En este documento, el término SBD de la solicitud se lleva a los escenarios BDD que usa el repositorio. SDK se trata como los contratos y clientes compartidos existentes en `packages/contracts`, API versionada, API client, gateway y adaptadores; no se supone un SDK adicional ni se incorpora una dependencia nueva.

Los identificadores `REM-...`, `AC-Hxx`, `SC-Hxx`, `TC-Hxx` y sus equivalentes Bxx son locales a esta propuesta. No se asignan números PRD/BDD/TDD canónicos hasta integrar el incremento y verificar unicidad. La sección 4 contiene requisitos funcionales propuestos, aceptación BDD y verificación TDD; la sección 5 contiene SDD propuesto. La matriz local enlaza toda la cadena sin marcar implementación futura como realizada.

**Autoridades consultadas en el baseline:** `AGENTS.md`; `.agents/skills/restaurantos_dev/SKILL.md`; `docs/01-PRD.md` (FR-102..107, FR-266..268, FR-274, NFR-002/006/007/012/016/021/027/031); `docs/02-SDD.md` §§9, 51, 57, 58, 60; `docs/03-BDD-branch-scope-governance.md`; `docs/04-TDD-branch-scope-governance.md`; `docs/03-BDD-corporate-purchases.md`; `docs/04-TDD-corporate-purchases.md`; `docs/03-BDD.md` compras XML; `docs/04-TDD.md` Purchasing/Integrations; matriz; planes BRANCH-SCOPE-001, CORP-PUR-001 y AUD-CORE-001. Los paths anteriores son relativos a la raíz del repositorio del SHA indicado.

## 2. Decisiones funcionales que deben resolverse antes de su efecto

**Ejecución iniciada el 2026-10-13:** `manifest.json` conserva el diseño original propuesto y
`verificar_plan.py` verifica su integridad. `execution.json` registra el progreso real por tarea;
`DECISIONES.md` conserva las respuestas autorizadas D02/D03/D04. La implementación ocurre en
`codex/audit-remediation`, baseline sin modificar e1422dc, dentro de checkout aislado. Ningún estado
local declara CI, despliegue, migración ni comportamiento productivo aprobados. Las tareas restantes
mantienen su estado pendiente; no se reduce la cobertura de 23 hallazgos/brechas.

El plan cubre también las funciones incompletas; no convierte decisiones fiscales, contables o de abastecimiento en reglas implícitas. Estas decisiones bloquean únicamente las tareas señaladas, no las correcciones independientes.

| Decisión | Entregable requerido y recomendación | Tareas afectadas |
|---|---|---|
| D01 Alcance fiscal directo | Registrar si se incorpora CFDI directo a la versión objetivo y reconciliar README/PRD. Recomiendo incorporarlo como módulo explícito y aislado con permisos propios; mientras no se adopte, emisión/cancelación nuevas permanecen cerradas y la recuperación/consulta autorizada conserva historia. Mantener exportación existente. | F01, F03, F04, R01 |
| D02 Elegibilidad fiscal | Tabla aprobada por responsable fiscal: pedidos pagados/parciales/cancelados, individual/global, inclusión/exclusión, sustitución, emisor por razón social, impuestos, descuentos, receptor, moneda y cancelación. No inferirla del estado HTTP ni imponer una factura única por pedido. | F01, F03, F04 |
| D03 Recepciones y devolución | Diferenciar error de captura, devolución física, cierre del pendiente y nota de crédito. Fijar autorización, valoración si ya hubo consumo, inventario insuficiente/negativo, períodos cerrados y ajuste de deuda. Recomiendo documentos compensatorios vinculados, revisión de excepción y cero modificación de originales. | C01, C02 |
| D04 Crédito de proveedor | Definir cuándo nace la obligación (CFDI validado, recepción o conciliación), relación uno-a-varios con recibos/facturas, vencimiento, autorización de abono, origen de pago y reversa. Recomiendo separar deuda documentada de recepción física y conciliar diferencias antes de aplicar. | A01, A02, C02 |
| D05 Demanda | Definir ventana, días completos/operativos, horizonte que incluye o no lead time, stock de seguridad, compras pendientes, empaques, mínimos y criterio de insuficiencia. Recomiendo cálculo determinista explicable con parámetros explícitos; nunca usar cinco unidades diarias por defecto. | I03, I04 |
| D06 Costos e impuestos | Fijar impuestos recuperables/inventariables, flete, descuentos, centavos fiscales frente a costo de seis decimales, tolerancia XML-documento y corrección de costo histórico. Recomiendo preservar la fórmula canónica y registrar diferencias para conciliación; no asumir IVA 16% universal. | X02, A01, C01, F01 |

Cada decisión produce: actor responsable, opción elegida, ejemplos y contraejemplos, autoridad PRD/SDD activada y fecha. Resolverla no equivale a autorizar producción. Las pruebas de rama alternativa se mantienen hasta adoptar la decisión; una función incompleta no se habilita con valores inventados.

## 3. Matriz de cobertura y orden

| Hallazgo/brecha | Incremento principal | Contrato vigente que se reutiliza | Activación documental |
|---|---|---|---|
| H01, H02, H14 | W01-W03 | FR-267, NFR-031; SDD §58; BDD 634..639; TDD 351/352/355/356 | SDD si cambia modelo; ampliar BDD/TDD y matriz de cobertura |
| H03 | I01 | NFR-006/014, permisos/alcance canónicos | BDD/TDD; PRD si se introduce permiso IA distinto |
| H04, H15, H16 | U01-U02 | FR-274, NFR-027; BDD 670/672/675; TDD 375/376/379 | BDD/TDD; SDD para recuperación durable |
| H09, H10, H11, H12, H13 | P01-P03 | FR-274, NFR-012/021; SDD §60; TDD 374..377 | SDD fórmula/identidad; BDD/TDD; matriz |
| H05, H06, H07, H08, B05 | F01-F04 | NFR-006/007/027, adaptadores; alcance fiscal directo abierto | PRD/SDD/ADR/BDD/TDD/matriz; retirar referencia fiscal a FR-234 |
| H17 | I03-I04 | Inventario/recetas versionadas; NFR-012/027 | PRD/SDD/BDD/TDD/matriz para recomendación real y período |
| H18 | I02 | NFR-012/021/027; borrador sin efectos | PRD sólo si amplía extracción; SDD/BDD/TDD |
| B01 | W01-W05, S01-S03 | FR-266..268; ADR-040; TDD 348..356 | Reutilizar contrato y ampliar evidencia; sólo autoridad modificada |
| B02 | X01-X02, A01-A02 | FR-102..107; BDD 013/014; TDD-TS-007 | SDD/BDD/TDD/matriz; PRD sólo precisiones funcionales nuevas |
| B03 | C01-C02 | FR-274 exige corrección compensatoria, no cancelación ordinaria | PRD reglas faltantes; SDD estados/valoración; BDD/TDD/matriz |
| B04 | G01-G02, R01 | NFR-016; verificador PostgreSQL y CI existentes | TDD/matriz/evidencia; sin declarar CI ausente |

Todo incremento conserva auditoría, razón social, organización, sucursal/almacén, moneda, relaciones originales, UTC e idempotencia. No se propagan facturas, pagos ni costos a otra sucursal por cambiar contexto. Consultas corporativas, configuración heredable y operación de sucursal tienen contratos separados.

## 4. Especificaciones funcionales, aceptación BDD y pruebas TDD

### H01 - Apertura de caja que elude el bloqueo

**REM-FUN-H01 / AC-H01:** todas las operaciones operativas de sucursal exigen el workspace canónico vigente. Una selección bloqueada no autoriza una apertura directa en otro destino. Reusar FR-267/NFR-031 y la guarda común; incluir apertura/cierre, ventas, pagos, compras directas, gastos, producción, conteos e impresión operativa. Las órdenes corporativas no obtienen una sucursal implícita: usan su autoridad organizacional y destinos explícitos.

**SC-H01:** Dado un actor con workspace A y turno OPEN o CLOSING, cuando intenta seleccionar B y luego abrir directamente caja B con el mismo bearer, entonces ambas acciones son denegadas, el turno A y la versión siguen intactos y no existe turno B. Repetir desde otra pestaña/contexto supersedido.

**TC-H01:** convertir repro de `test_branch_audit.py`; parametrizar rutas operativas; comparar ledger, turnos y workspace antes/después (puede crecer sólo auditoría de denegación). PostgreSQL: apertura A contra selección B bajo barrera, un resultado compatible y cero turnos cruzados. **Tareas:** W01, W02, G02.

### H02 - Recarga que revierte la selección

**REM-FUN-H02 / AC-H02:** GET hidrata el workspace vigente, no elige primera/base; no devuelve secreto. POST reemite/rota contexto según SDD §58. El cliente conserva la mayor secret_version por context ID y descarta respuestas tardías.

**SC-H02:** Dado A -> selección B confirmada, cuando recarga POS, abre Admin o pierde la respuesta, entonces recupera B con autorización vigente; dos respuestas v3/v2 dejan v3 instalada; revocación impide recuperar autoridad. GET con branch de transición no ejecuta el cambio.

**TC-H02:** secuencia login/select/GET/reissue, replay perdido, v3-v2, token antiguo, actor desactivado, autorización incrementada. E2E con API real sintética: no enviar comandos hasta recuperar contexto y no trasladar carrito/dispositivo. **Tareas:** W01-W03.

### H03 - IA sin permisos ni filtros de sucursal

**REM-FUN-H03 / AC-H03:** actor activo, permiso vigente y branch autorizado se validan antes de leer compras/mermas. Inicialmente reutilizar permisos canónicos de lectura pertinentes y documentar la matriz, sin hacer equivalentes lectura y administración. Filtrar cada consulta por organización, branch real y destino; global sólo mediante contrato corporativo explícito.

**SC-H03:** Dado un actor sin permisos, desactivado o limitado a A, cuando solicita suggested-purchases/mermas de B o una sucursal inexistente, entonces recibe denegación estable sin proveedor, insumo, precios ni historia. Un lector A sólo obtiene datos A autorizados.

**TC-H03:** ampliar cuatro adversarios IA con mermas, rol lector positivo, dos organizaciones, branch inactiva, bypass body/query y ausencia de actor. Assert cero datos/llamadas externas; no confundir filtro UI con seguridad. **Tareas:** I01, G02.

### H04 - Campo vacío que recibe el pendiente completo

**REM-FUN-H04 / AC-H04:** vacío, no capturado y cantidad positiva son estados distintos. No sustituir vacío/0 por pendiente. Prefill permitido sólo visible y editable; confirmar muestra exactamente lo enviado. Backend vuelve a validar cantidad, versión, destino y saldo.

**SC-H04:** Dado pendiente 10, cuando el receptor borra la cantidad y confirma, entonces hay mensaje junto al campo, cero requests de recepción y cero efectos. 0, negativa, NaN, infinito, exceso y más precisión no obtienen fallback.

**TC-H04:** DOM/request en navegador, no sólo búsqueda de código; API negativa y total posterior correcto. Probar teclado, pegado y coma decimal según formato soportado. **Tareas:** U01.

### H05 - Autoridad fiscal y recibos

**REM-FUN-H05 / AC-H05:** derivar organización/razón social/branch del recurso, no de la sucursal predeterminada. Listas acotadas por alcance y detalle autorizado antes de PAC. Proponer `invoicing.read|issue|cancel|receipt.create` separados, sujetos a D01/D02 y migración de grants exactos; nunca otorgarlos por `orders.read` automáticamente.

**SC-H05:** Dado un actor limitado a A o desactivado, cuando consulta/emite/cancela/crea recibo de B, entonces no obtiene datos, no llama PAC y no crea filas; lector autorizado consulta sin emitir. Configuración/credenciales exige autoridad específica.

**TC-H05:** invertir probes fiscales, negativos por endpoint y actor, otra organización, URLs de PDF/XML con descarga autorizada y sin fuga de llaves. **Tareas:** F01, F02.

### H06 - Pedidos, sucursal e integración fiscal

**REM-FUN-H06 / AC-H06:** el conjunto recibido es íntegro, único, autorizado y pertenece al emisor/moneda establecidos por D02. Un ID desconocido no se descarta. Configuración no habilitada, emisor sin configuración o elegibilidad pendiente impiden efectos. Registrar relación de todos los pedidos, no sólo primary_order_id.

**SC-H06:** Dado pedidos A/B o un ID inexistente, cuando se pide una factura bajo A, entonces se rechaza todo antes del PAC. Con integración apagada se rechaza emisión. Un conjunto elegible autorizado conserva relaciones completas, sin omisión silenciosa.

**TC-H06:** conjunto vacío, duplicados, mezcla branch/razón social/moneda/org, parcial elegible y cancelado conforme a tabla D02. Aserción PAC.calls=0 y cero comandos aplicados en negativos. **Tareas:** F01, F03.

### H07 - Doble emisión y resultado incierto

**REM-FUN-H07 / AC-H07:** una intención fiscal tiene comando durable, hash canónico, referencia local y clave estable hasta el adaptador PAC. Un timeout representa incertidumbre; no crea otra intención. La recuperación distingue replay de un nuevo documento fiscal legítimo definido por D02.

**SC-H07:** Dada emisión que tuvo éxito externo pero cayó antes de guardar respuesta, cuando se recupera con la misma key/body, entonces se reconcilia el mismo documento y no se emite otro. Misma key/cuerpo diferente o recurso distinto produce conflicto.

**TC-H07:** FakePAC registra identidad externa; fallos antes/después del PAC y commit, dos workers, lease vencida, respuesta perdida y reinicio. PostgreSQL unique/locks; sandbox posterior separado. No prometer exactly-once universal: garantía condicionada a idempotencia/consulta del proveedor. **Tareas:** F03, F04, G02.

### H08 - Estados falsos y UUID inventado

**REM-FUN-H08 / AC-H08:** UUID fiscal nullable hasta evidencia de timbrado; UUID/local ID nunca se intercambian. Resultado pending/verifying o cancelación solicitada conserva estado pendiente. Sólo respuesta final confirmada modifica proyección final. Mantener raw response original con protección y proyección redactada.

**SC-H08:** Dada emisión pending sin UUID, cuando llega respuesta, entonces estado no es issued y uuid_sat es null. Dada cancelación pendiente, permanece pendiente hasta confirmación; rechazo mantiene la emisión y su motivo estable. Evento duplicado o tardío no retrocede estado.

**TC-H08:** respuestas pending/verifying/issued/rejected/cancelled/desconocida, webhook duplicado/firma inválida, polling, final tardío y replay. Corregir fixtures originales que normalizan defectos. **Tareas:** F04.

### H09 - Conservación de cantidad base

**REM-FUN-H09 / AC-H09:** suma de targets base por destino = base congelada de la partida y suma de deltas de recepciones = target de destino. La conversión no se vuelve a redondear independientemente por asignación. El orden de reparto se congela y la política lleva versión.

**SC-H09:** Dada cantidad 1 y yield 0.333333, distribuidas 0.5/0.5, cuando se reciben ambos destinos, entonces base total y ledger son 0.333333; nunca 0.333334. Recepción parcial sin delta base o que deja resto imposible se rechaza antes de efectos.

**TC-H09:** referencia Python de sección 6, propiedades de conservación, particiones, varios destinos/recepciones, mínimo de precisión y PostgreSQL/SQLite. **Tareas:** P01, P02.

### H10 - Costo negativo en último destino

**REM-FUN-H10 / AC-H10:** targets/deltas de costo no negativos y suma exacta al costo congelado. Costo cero de un tramo minúsculo es distinto de cantidad cero; no inventar costo mínimo. Costo promedio usa Python y política vigente de existencias; inventario físico negativo mantiene el rechazo canónico.

**SC-H10:** Dado costo 0.000002 repartido en cuatro destinos iguales, cuando recibe, entonces targets no negativos suman 0.000002 y ningún promedio es negativo. Con stock previo 10 a 20 y entrada 5 con costo 150, nuevo promedio cuantizado es 23.333333.

**TC-H10:** división no finita, cuatro destinos, orden alternativo congelado, stock previo positivo/cero, fallo tras cost-state y zero-value receipt. Conciliar valor de entradas exacto separado de promedio derivado redondeado. **Tareas:** P01, P02, G02.

### H11 - Validación del catálogo por destino

**REM-FUN-H11 / AC-H11:** utilizar reglas canónicas `presentation_values` y resolución efectiva de scope por cada destino. Validar insumo activo, pertenencia, presentación, unidades/yield, proveedor y almacén al crear/aprobar según contrato; snapshot histórico no se reescribe. Recepción revalida destinos/autoridad operativa, sin recalcular precios/yield del snapshot.

**SC-H11:** Dado insumo local A o desactivado, cuando se asigna a B, entonces rechaza sin orden. Dada orden válida y catálogo editado después, cuando se recibe, entonces usa el snapshot aprobado o conflicto explícito contractual, nunca datos nuevos silenciosos.

**TC-H11:** ID antiguo, local/global, unidad incompatible, supplier deshabilitado, dos organizaciones, almacén incorrecto y edición posterior. No basta probar options. **Tareas:** P02, S02.

### H12 - Recurso de replay sobrescrito

**REM-FUN-H12 / AC-H12:** el recurso de URL no puede ser sobreescrito por body. Esquemas estrictos por operación, envelope canónico con operación/recurso/scope/cuerpo; rechazar order_id inesperado. Reautorizar antes de devolver resultado guardado.

**SC-H12:** Dado approve A confirmado, cuando se reutiliza key/body en URL B o se inyecta body.order_id, entonces falla conflicto/esquema, no devuelve A como resultado de B y B sigue DRAFT. Mismo comando autorizado recupera A.

**TC-H12:** approve/cancel/receive/create parametrizados, campos desconocidos, URL distinta, actor/organización/versiones revocadas; efectos cero en negativos. **Tareas:** P03.

### H13 - Máximo de agregado persistible

**REM-FUN-H13 / AC-H13:** comprobar todos los agregados/productos persistidos contra `Numeric(18,6)` y límites de enteros de centavos antes de escribir; errores de negocio no SQL. No basta validar cada línea. Decimal exacto y valores finitos.

**SC-H13:** Dadas dos líneas de 600000000000, cuando se crea la orden, entonces se rechaza total 1200000000000 sin filas. Máximo contractual 999999999999.999999 se distingue del siguiente quantum.

**TC-H13:** límite exacto/overflow, descuentos/impuestos/base/cost_per_base_unit/cabecera, máximo de 200 líneas y centavos externos. Misma aceptación PostgreSQL/SQLite. **Tareas:** P02.

### H14 - Grants móviles y versiones

**REM-FUN-H14 / AC-H14:** API ordinaria no crea/retira/modifica grants gobernados ni scope de roles que los poseen. Incluir organization_branch_workspaces junto a organization_all_permissions. Mutaciones autorizadas de autoridad incrementan authorization_version de usuarios afectados en la misma transacción/lock; no inferir privilegios del nombre.

**SC-H14:** Dado rol móvil branch con grant gobernado, cuando admin.manage intenta convertirlo a organization por PUT ordinario, entonces se deniega sin alterar rol, grant, versión o sesión. Una transición dedicada autorizada invalida tokens viejos.

**TC-H14:** CRUD completo, cada grant, eliminar/reasignar roles, usuarios compartidos, fallo parcial y carrera contra lease/selección. **Tareas:** W01, W02, W05.

### H15 - Identidad visible de lo recibido

**REM-FUN-H15 / AC-H15:** detalle y confirmación identifican snapshot de insumo/SKU, presentación, unidades comercial/base, ordenado/recibido/pendiente, sucursal y almacén por renglón. Si falta identidad histórica, mostrar falta explícita y resolver por referencia autorizada; no confundir partidas ni inventar datos.

**SC-H15:** Dada orden con pan y carne, ambos pendiente 10 en un destino, cuando se abre recepción, entonces cada input se asocia inequívocamente a su partida/unidad y la confirmación identifica el mismo allocation_id.

**TC-H15:** DOM accessible name/request pairing, lectura sin mutación, nombres renombrados conservan snapshot, desktop/tablet y móvil soportado. **Tareas:** U01.

### H16 - Recuperación del intento corporativo

**REM-FUN-H16 / AC-H16:** crear/aprobar/recibir/cancelar conservan intento inmutable (key/body/recurso/actor/org/version), aislado por cuenta. Reintento usa la misma intención hasta resultado definitivo; no cambia expected_version para forzarla. Recarga ofrece recuperar, sin repetir automática y ciegamente.

**SC-H16:** Dada recepción confirmada cuya respuesta se pierde, cuando recarga y reintenta, entonces recibe el resultado original bajo autorización vigente, una recepción y un conjunto de movimientos. Cambio de usuario no puede leer ni ejecutar el pendiente anterior.

**TC-H16:** API real sintética con pérdida después de commit, reload, doble clic, cuenta distinta, payload editado, conflicto definitivo y resultado supersedido. Preferir patrón existente de compra local; no persistir secretos de workspace. **Tareas:** U02, P03.

### H17 - Demanda y ventana de merma reales

**REM-FUN-H17 / AC-H17:** recomendación sólo usa datos autorizados, unidades normalizadas y parámetros D05. Expone fuente/período/model_version, consumo, disponible, pendientes, necesidad, empaque y advertencias. Si faltan datos, devuelve insuficiencia y no constante. Mermas filtra período inclusivo/exclusivo UTC derivado de zona local.

**SC-H17:** Dado mismo insumo con ventas/stock distintos en A/B, cuando calcula, entonces propuestas responden a esas diferencias. Sin ventas ni base válida no inventa 35 unidades. Movimiento justo en inicio entra y justo en fin no entra; cambiar days modifica ventana.

**TC-H17:** datos completos vs cero real vs ausentes; recetas/versiones/mermas, reservas sin doble conteo, recepciones directas/corporativas confirmadas, pending neto de cierres/compensaciones, zonas/DST, supplier terms, Decimal y replay sin efectos. **Tareas:** I03, I04.

### H18 - Extracción sin ficción ni float

**REM-FUN-H18 / AC-H18:** texto vacío/ilegible devuelve error explícito o borrador sin partidas con advertencias, nunca dato ficticio. Campos no extraídos permanecen unknown. Importes/cantidades se normalizan con Decimal desde texto; separadores ambiguos requieren revisión. Extracción no importa XML ni aplica inventario/deuda/caja.

**SC-H18:** Dado vacío o precio 19.99, cuando extrae, entonces vacío no contiene partida y precio exacto es 1999 centavos. Documento adversario no puede instruir al sistema a crear/confirmar una compra.

**TC-H18:** 19.99/0.29/negativos/exceso/NaN/separadores/multiplicación/factura ilegible, esquema estricto, tamaño acotado y revisión humana. Si hay proveedor IA, adaptador con salida no confiable, privacidad y timeout; sin proveedor permanece captura manual. **Tareas:** I02.

### B01 - Completar alcance corporativo, workspace, offline y reasignación

**REM-FUN-B01 / AC-B01:** implementar todo BRANCH-SCOPE-001, no sólo selector. Configuración organización heredable/excepción local, consulta global autorizada y operación branch concreta separadas. Leases registradas y cambios de autoridad comparten lock. Reasignar Cajero/Cajero jefe cambia todas sus asignaciones autorizadas, no historia.

**SC-B01:** Dado catálogo corporativo, cuando se crea una sucursal nueva, entonces hereda sin clonar; excepción confirmada afecta sólo branch elegida. Dada lease vigente/comando incierto/turno, selección y reasignación se bloquean. Rollback no base entra recovery_only, permite cerrar/recuperar existentes y deniega nuevos efectos hasta drenado.

**TC-B01:** TDD 348..356 completos por módulo, dos organizaciones/seis perfiles, dos pestañas, leases legacy, emisión vs selección/reasignación, revocación, gateway A frente B, historia hash estable. **Tareas:** W01-W05, S01-S03.

### B02 - XML, equivalencias, evidencia y cuentas por pagar

**REM-FUN-B02 / AC-B02:** XML original protegido, UUID/identidad fiscal canónica, validación de emisor/receptor, equivalencias proveedor versionadas y documentos conciliados. Cuenta de crédito con vencimiento y movimientos append-only; abonos/devoluciones enlazados, sin editar saldos. Separar importación documental, recepción física y pago para evitar dobles efectos.

**SC-B02:** Dado CFDI nuevo válido y conceptos mapeados, cuando se importa, entonces crea evidencia/borrador conciliable sin recibir automáticamente. Mismo UUID concurrente conserva una importación y mismo resultado; payload diferente bajo UUID existente requiere conflicto/revisión. Obligación 10000, abono 3000 y crédito 2000 dejan 5000; reversa de abono devuelve 8000, sin borrar original.

**TC-B02:** XML bien/mal formado, DTD/entidad externa sin red, tamaño/nodos acotados, UUID repetido/hash distinto, otro RFC/org/moneda, conceptos desconocidos, pago concurrente, sobreabono, reversa, orden con varias recepciones y sin doble CxP. **Tareas:** X01-X02, A01-A02.

### B03 - Corrección de recepción corporativa

**REM-FUN-B03 / AC-B03:** comandos distintos para cerrar pendiente, corregir captura, devolver físicamente y registrar crédito. Recibo original/ledger/caja/pagos permanecen inmutables. Nuevo documento con motivo, referencia, actor, permiso, plan/version y efectos de inventario/costo/CxP definidos por D03/D06. Nunca habilitar cancelación ordinaria de APPROVED/RECEIVED para resolverlo.

**SC-B03:** Dada recepción confirmada, cuando corrección válida es aplicada, entonces original permanece idéntico y nuevos movimientos referencian originales; mismo replay no compensa dos veces. Si parte se consumió o período cerró, se aplica la política aprobada o se bloquea explícitamente, sin inventar valor/stock.

**TC-B03:** parcial/total, dos correcciones que exceden saldo, fallo tras cada efecto, consumo intermedio, stock insuficiente, crédito/pago existente, cierre pendiente sin inventario ficticio y valor histórico. PostgreSQL serializa recepciones/compensaciones. **Tareas:** C01-C02.

### B04 - Evidencia por SHA y gates reales

**REM-FUN-B04 / AC-B04:** CI debe ejecutar los gates activados y exigir cero skips en los PostgreSQL obligatorios. Confirmar collection + JUnit + run/check del mismo SHA y suite completa aplicable una vez en CI. No considerar la presencia de YAML como ejecución ni XML antiguo como evidencia nueva.

**SC-B04:** Dado gate requerido sin URL, suite no colectada o caso skipped, cuando verifica evidencia, entonces falla integración. Dado resultado completo del SHA candidato, sólo ese resultado autoriza el gate de integración; producción sigue separada.

**TC-B04:** tests negativos del verificador con suite faltante/skipped/duplicada y evidencias de nuevas suites workspace/fiscal/XML/CxP/compensación. Costeo con stock positivo, dos organizaciones y carreras reales. **Tareas:** G01-G02, R01.

### B05 - Reconciliar autoridad fiscal

**REM-FUN-B05 / AC-B05:** D01/D02 producen requisito fiscal propio o exclusión efectiva; eliminar el enlace falso a FR-234 (Google Reviews). Ningún test existente sustituye definición de alcance, permisos, fórmula o estado. Conservar consulta/recuperación de historia existente bajo guardas incluso si módulo no se amplía.

**SC-B05:** Dado la decisión de alcance registrada, cuando se recorre README/PRD/SDD/BDD/TDD/matriz/contrato/UI, entonces todas las referencias fiscales coinciden y las rutas habilitadas corresponden a esa decisión; sin configuración aprobada no hay emisión externa.

**TC-B05:** trazabilidad, contratos/frontend/API, config ausente/apagada, lector/no autorizado, downgrade/rollback con documentos existentes. **Tareas:** F01, F02, R01.

## 5. Diseño técnico propuesto (SDD/SDK)

### 5.1 Autoridad y relaciones

Workspace según SDD §58: `branch_workspace_sessions` pertenece a actor/org/branch y authorization_version; token hash y secret_version rotatorio, estados active/recovery_only/superseded/revoked/expired. Unicidad de contexto activo/recovery_only por actor. `offline_authorization_leases` enlaza actor/branch/version/hash/emisión/expiración/revocación. Selección, reasignación, reemisión, apertura de turno y emisión de lease serializan sobre autoridad del actor; luego locks de recursos en orden estable. Evitar lock inverso actor-turno que cause deadlock. No mantener lock DB durante llamadas externas.

Resolver Python común de autoridad y guardas por recurso. Enumerar endpoints operativos en W01, incluyendo rutas hermanas e indirectas. Un endpoint corporativo no usa active_branch; su permiso organizacional y conjunto explícito de destinos se resuelven en Python. Resultados idempotentes se entregan después de reautorizar; replay no reanima autoridad revocada.

ConfigurationScope compartido: `{kind:"organization", branch_id:null}` o `{kind:"branch", branch_id:UUID}`. Scope ausente/incompatible falla; requested_scope/effective_source/source_branch_id son metadata de lectura. Identidad corporativa no se clona; excepción por módulo/version y sucursal, con validez y herencia. El API client transporta scope y expected_version explícitos. Filtro de reporte no altera workspace ni configuración.

### 5.2 Compras, conversión y comandos

Reutilizar agregado actual order -> lines -> allocations -> receipts -> receipt_lines -> inventory_movements/cost_states/price_history. Preservar FKs org/razón social/sucursal/almacén. Congelar `allocation_sequence`, targets base/costo y `allocation_policy_version` para órdenes nuevas si no existe representación equivalente; ADR antes de cambiar fórmula. Identidad estable del orden de reparto no depende del orden accidental de llegada ni de UUID aleatorio.

Implementar funciones puras Python de reparto/acumulados/validación; reutilizar `purchase_line_values`, `presentation_values`, `_quantity`, `_money`, `_cost` y sus políticas. No duplicar matemática en React o controladores HTTP. API acepta/devuelve decimales como strings; centavos como enteros dentro de límites del cliente. Más allá de Number seguro, rechazar conforme al contrato o versionar representación string; TypeScript nunca redondea importes de dominio.

Envelope de identidad recomendado: `{operation, resource_id_from_route, authority_scope, normalized_body}`; ninguno de estos campos puede ser sobreescrito por `**payload`. Canonicalizar campos numéricos sin alterar intención; unknown fields rechazados. Unicidad/namespace conservan el contrato de command log vigente y ligan siempre organización, actor autorizado, operación y recurso. No ampliar recuperación a otra cuenta.

UI conserva intento congelado por cuenta/org/operación/recurso; key no se trata como credencial. Secretos de workspace sólo en memoria y jamás en persistencia de pendiente. Si el cuerpo incluye información sensible, persistir sólo datos mínimos conforme a política o usar command draft protegido del servidor. Login distinto oculta/aisla; refresh consulta/reintenta el mismo comando; conflicto definitivo permite descartar con confirmación y nueva intención diferenciada.

### 5.3 Frontera fiscal

Dominio independiente del PAC con interfaz tipada propuesta `issue(command, stable_key)`, `get(remote_id/reference)`, `request_cancel(command, stable_key)` y normalización de estado/payload. Adaptador Facturapi concreta headers, esquema, timeout y semántica de replay; no se usa external_id como unicidad fiscal. Congelar contrato externo y fixtures al implementar; credenciales únicamente backend por emisor/ambiente.

Separar estado del comando (`pending/processing/unknown/completed/rejected`) del estado fiscal (emisión pendiente/emitida/rechazada y cancelación none/requested/pending/confirmed/rejected). Mapeo exacto a proveedor en F01/F04; estados desconocidos -> reconciliation_required, nunca éxito. UUID SAT nullable; ID interno puede ser UUID propio con nombre explícito distinto. `invoice_order_links` registra todos los pedidos con snapshot/importe/currency; no se asume exclusividad universal sin D02.

Persistir intención y outbox antes de PAC. Worker adquiere lease/claim corto, suelta transacción, envía con key estable y registra respuesta en nueva transacción. Caída tras llamada deja unknown: recuperar por idempotencia/ID remoto o revisión; no reintentar con key nueva. Inbox de eventos unique por proveedor/emisor/evento, firma validada y estado monotónico. Polling como respaldo cuando proveedor soporte consulta; no inventar webhook para un evento no soportado. Payload fiscal cifrado y acceso restringido; auditoría/redactados sin RFC, receptor, XML, tokens o cuerpo.

Fuentes oficiales revalidadas para diseño: [API Facturapi](https://docs.facturapi.io/api/), [intermitencias](https://docs.facturapi.io/en/docs/guides/invoices/intermitencias/), [cancelaciones](https://docs.facturapi.io/docs/guides/invoices/cancelaciones/). La documentación contempla pendientes y cancelaciones no definitivas; el adaptador debe probar esos estados. No es dictamen fiscal.

### 5.4 Importación fiscal y CxP

XML entra por adaptador/parsing seguro, tamaño/número de nodos acotados, sin DTD/entidades/red; esquema/version fiscal soportado explícito, sin asumir validez SAT sólo por parseo. Evidencia original inmutable con hash, UUID, MIME, origen/actor/fecha, almacenamiento privado; descargas reautorizadas. Política de retención y eliminación regulada definida antes de producción, sin borrar evidencia transaccional necesaria. No crear dependencia crítica de parser/storage sin ADR.

Modelos propuestos: `supplier_document_imports`, `supplier_concept_mappings` versionados, vínculos de importación a documentos/orden/recepciones; `supplier_obligations`, `supplier_obligation_entries`, `supplier_payment_allocations` y comandos de CxP. Unicidad por identidad fiscal/org y linkage para impedir doble contabilización de CFDI y captura manual ya conciliados. Otra org no revela si existe UUID. Concepto no mapeado queda pendiente; no adivinar insumo/unidad.

Saldo y vencimiento se proyectan de movimientos originales/compensaciones. Un abono se identifica y vincula a origen de pago auditado; no genera otro retiro de caja si el origen ya existe. D04 gobierna sobrepago, anticipos y monedas; sin definición rechazar casos ambiguos. Lock de obligación y asignaciones impide sobreaplicar. No mezclar crédito de proveedor con recepción automática ni con transferencia bancaria ejecutada por el sistema.

### 5.5 Compensación y recomendaciones

Compensación tiene original, cantidades base/comerciales, plan de efecto, motivo protegido, actor/autorizador, expected_version y comando idempotente. Lock orden/asignación/recibo/stock/costo/obligación según orden global. Cierre de pendiente sólo libera compromiso de abastecimiento, no produce stock negativo ni cancela recibos. Valorar corrección después de consumo requiere D03/D06; no restar costo original al promedio actual sin explicar el resultado. Proyección rebuildable desde ledger conserva snapshots originales y emite ajustes identificables.

Motor de recomendación puro Python lee proyecciones autorizadas y fechadas: consumo confirmado, recetas versionadas cuando corresponde, stock disponible, reservas no consumidas, órdenes aprobadas pendientes de recibir y cierres/devoluciones. No sumar ventas y consumo de receta si son dos representaciones del mismo consumo. Propuesta no realiza escrituras; aplicar crea sólo borrador canónico y pide revisión. Un LLM, si se usa, explica datos allowlist y jamás calcula precio, cantidad autoritativa, IVA ni permisos.

### 5.6 Migraciones y compatibilidad

Toda tabla/constraint/índice nuevo requiere migración desde **head integrada verificada al iniciar cada PR**, un solo head y revisión Alembic única; no reservar ahora un número ni editar 0077/0082 u otra migración aplicada. Upgrade aislado SQLite/PostgreSQL, constraints y downgrade vacío; con historia se bloquea downgrade destructivo. Rollback de app conserva esquema/lectura/comandos y usa forward-fix.

P01/P02 no redistribuyen órdenes históricas silenciosamente. Preflight read-only clasifica DRAFT sin efectos, APPROVED sin recepción, parcial y completa; detecta base/costo negativo/overflow y vínculos inválidos. Para órdenes antiguas: conservar versión anterior/snapshots, bloquear nueva recepción inconsistente y generar ajuste/migración auditable sólo con decisión y autorización; un target nuevo jamás invalida un delta recibido sin corrección explícita. Mismo cuidado con UUID fiscales inventados: identificarlos para reconciliación con PAC, nunca sustituirlos por UUID reales sin evidencia y auditoría.

Gateway conserva branch del bundle y command outbox/inbox; versionar nuevos schemas y capabilities, servidor tolera lectura legacy bajo guarda sin ampliar autoridad. Los clientes viejos que carecen de contexto reciben reautenticación/actualización requerida, no bypass. Antes de reasignación drenar/invalidate leases legacy conforme FR-268. No tratar offline como caché ni permitir cambiar sucursal offline.

### 5.7 Mapa de componentes y contratos de frontera

| Incremento | Componentes actuales a modificar/reusar | Contrato/artefacto a producir |
|---|---|---|
| W01-W05 | `apps/api/restaurant_os/operations.py`, `api.py`, `models.py`, sesión POS/Admin, gateway | Extender sesión y auth/branch-selections según §58; branch-context-reissues y reasignación ya diseñados; schemas de workspace/lease versionados |
| P01-P03, U01-U02 | `corporate_purchases.py`, `purchase_workspace.py`, `presentation_rules.py`; `apps/admin-web/src/features/purchasing/CorporatePurchaseWorkspace.tsx` | DTO/schema corporativo compartido: snapshots, targets, secuencia/policy, recepción, approve/cancel y errores; migración nueva si persiste targets |
| I01-I04 | `inventory_ai.py`, rutas admin-ai, `SuggestedPurchasesModal.tsx` | Schemas de extracción/recomendación/mermas, fuentes/período/unknown, Decimal string y revisión humana |
| F01-F04 | `invoicing/service.py`, adaptador/cliente PAC, worker, `apps/pos-web/src/features/invoicing/InvoicingView.tsx` | Contrato fiscal versionado, commands/outbox/inbox, relaciones invoice-order y estado/cancelación por proveedor |
| S01-S03 | Resolutores por módulo, providers Admin, `packages/api-client`, `packages/contracts` | ConfigurationScope discriminado, fuente efectiva, expected_version y capabilities por módulo |
| X01-A02, C01-C02 | Dominio purchasing/inventory/cash, modelos/migraciones, adaptador XML, worker y Admin | Imports/mappings/obligations/entries/compensations con referencias canónicas, comandos idempotentes y schemas |

El SDK real observado es `@restaurantos/api-client`: los componentes usan `fetchApi`; se amplía allí el transporte/recuperación compatible y se comparten tipos desde `packages/contracts`, evitando interfaces financieras divergentes en cada pantalla. Las rutas siguientes se presentan con prefijo `/api/v1`; al implementar se verifica OpenAPI generado contra router real.

| Ruta | Entrada y autoridad | Salida/efecto verificable |
|---|---|---|
| POST `/auth/branch-selections`; GET `/auth/session` | Bearer, key en POST, destino/authorization_version; GET sin transición | Workspace/version; secreto sólo POST autorizado; nunca elegir branch vía GET |
| POST `/corporate-purchases/{id}/approve` | key, cuerpo estricto `{expected_version}`; id únicamente URL; permiso corporativo | Orden aprobada sin ledger/caja, replay del mismo recurso |
| POST `/corporate-purchases/{id}/receipts` | key, expected_version, branch_id/warehouse_id, received_at, lines allocation_id/quantity string | Recibo/version/estado y cantidades exactas persistidas; negativos cero efectos |
| POST `/corporate-purchases/{id}/cancel` | key, expected_version, reason limitado por contrato vigente; sólo DRAFT | Cancelación auditable, sin reinterpretar recepción como borrador |
| POST `/admin-ai/suggested-purchases`; GET `/admin-ai/inventory-yield-audit` | Actor/permiso, branch autorizado, período/parametrización explícita | Propuesta/reporte acotado, sin datos ajenos ni escrituras |
| POST `/invoicing/invoices/issue`; POST `/invoicing/invoices/{id}/cancel`; POST `/invoicing/orders/{id}/receipt` | Permiso específico, integración/eligibilidad, key estable, recurso completo | Comando durable/estado real pendiente o final; no inventar UUID/folio/enlace |
| Nuevas rutas XML/CxP/compensación | Schemas a versionar en X01/A01/C01 antes de código, actor/scope/version/key | Importación/documento/ajuste separado de recepción y pago; no diseñar endpoint genérico que edite saldo |

El cuerpo de recepción ilustrativo es `{expected_version:3, branch_id:"B", warehouse_id:"W-B", received_at:"2026-10-13T16:00:00Z", lines:[{allocation_id:"L-B", quantity:"4.000000"}]}`. B/W-B/L-B son referencias sintéticas, no UUIDs válidos para ejecutar. Unknown fields, boolean como versión, decimal no finito y recurso ajeno se rechazan por esquema/dominio antes de persistir. El cliente no envía costo calculado como autoridad ni sustituye branch por active_branch en comando corporativo.

Conservar códigos de negocio existentes para clientes compatibles; nuevos códigos sólo con contrato versionado y test de API client. Usar 401 para autenticación inválida; denegación/recurso oculto según política canónica, 409 para versión/replay/bloqueo y error de validación conforme mapper vigente. Envelope redactado con código estable y correlation_id; no devolver SQL, razón fiscal libre, secretos o payload PAC en error. Un 2xx de comando pending no es factura issued ni recepción inventada en UI.

## 6. Cálculos exactos en Python y ejemplos verificables

El anexo `calculos_referencia.py` es una especificación ejecutable aislada, sin conexión a base, PAC, stock o pagos. Se ejecutó para validar fórmulas propuestas y casos de borde. No certifica la futura integración con el producto.

**Representación:** strings -> Decimal finito; cantidades y costo interno a quantum 0.000001, importes fiscales/caja al centavo conforme fórmula vigente. `Numeric(18,6)` máximo positivo = 999999999999.999999. Rechazar inputs fuera de precisión/rango, no truncarlos. Trabajar reparto en unidades enteras del quantum y usar ROUND_HALF_UP exacto mediante cociente/resto entero para no depender de división decimal no finita.

**Reparto acumulado propuesto:** total congelado T, cantidades comerciales q_i, Q=sum(q_i), orden estable congelado. `A_i = round_half_up(T * cumulative(q_i) / Q)`; target_i = A_i - A_(i-1), A_0=0 y A_final=T. Mismo método para base y costo. Por monotonicidad, targets >=0 y la suma telescópica =T. Si un destino positivo obtiene target base cero, la distribución se rechaza/rediseña explícitamente antes de efectos; costo cero sí puede ser válido. La última diferencia absorbe el remanente sin volverse negativa.

**Recepción parcial:** target acumulado del destino = round(target * recibido_acumulado / asignado), delta = target_nuevo - target_anterior persistido; recepción final usa target completo. Conservar tanto comercial como base. Si delta base=0 o resto base=0 con comercial aún pendiente, rechazar sin efectos. Dos requests concurrentes recalculan bajo lock/versión, nunca con saldo de UI.

| Caso | Entrada | Resultado esperado |
|---|---|---|
| H09 | Base 0.333333; reparto 0.5 + 0.5 | Targets 0.166667 + 0.166666 = 0.333333 |
| H10 | Costo 0.000002; cuatro pesos iguales | Targets 0.000001, 0, 0.000001, 0; suma 0.000002 |
| Parciales | Target base 0.333333; tres tramos comerciales iguales | Deltas 0.111111 tres veces; total exacto |
| Promedio | Anterior 10 con promedio 20; entra 5 con valor 150 | (200+150)/15 = 23.333333 al quantum; valor entrada sigue 150 |
| Centavos | Decimal("19.99"), Decimal("0.29") | 1999 y 29; nunca int(float * 100) |
| Overflow | 600000000000 + 600000000000 | Error antes de persistir; máximo 999999999999.999999 |
| CxP | 10000 obligación, -3000 abono, -2000 crédito | 5000; reversa +3000 = 8000, originales conservados |
| Demanda ilustrativa D05 | Consumo/día 7, cobertura 7, seguridad 5, físico 30, reservado 4, pendiente 10, empaque 6 | Necesidad max(0,49+5-26-10)=18; 3 empaques; parámetros ilustrativos, no defaults |

La fórmula de demanda es una **opción a aprobar**: disponible=físico-reservas vigentes; necesidad=max(0,forecast+seguridad-disponible-pendiente autorizado); compra comercial=ceil(necesidad/yield). No aplicar seguridad/minimos/lead time ausentes como cero sin política aprobada. El promedio redondeado no se multiplica luego para fingir conservación exacta del valor histórico: se concilia el costo de movimientos exacto, y si se necesita carrying value contable se activa decisión/modelo específico.

## 7. Backlog ejecutable y dependencias

`manifest.json` contiene dependencias de tarea verificadas sin ciclos, mapeo hallazgo-tarea y gates. Cada tarea indica rol de ejecución, salida y prueba; ninguna está marcada implementada. Los roles son responsabilidad futura, no agentes delegados durante este plan.

| Tarea | Responsable | Trabajo y salida verificable | Depende de |
|---|---|---|---|
| G01 | Backend/QA | Baseline fresco, entorno frozen, fixtures 2 org/2 razones sociales/branches, transformar repros y provisionar gates faltantes; evidencia SHA | - |
| D00 | Producto + fiscal/contable + arquitectura | Registrar D01-D06 con ejemplos; se liberan tareas individualmente por decisión, no esperar todas para corregir guardas | G01 |
| W01 | Backend | Inventario de rutas/roles, resolver de autoridad, guardas grants/versiones y modelo workspace según contrato vigente | G01 |
| W02 | Backend | Persistencia/locks workspace y fencing de rutas, selección/reissue/replay; migración aditiva si requiere | W01 |
| W03 | Frontend | Hidratación, fencing v3/v2, aislamiento POS/Admin/pestañas, recuperación sin secretos persistidos | W02 |
| W04 | Gateway/Backend | Registro leases, outbox incierto/reconciliación, blockers compartidos y legacy drain | W02 |
| W05 | Backend/QA | Reasignación transaccional, revocación y recovery_only; historia intacta | W03, W04 |
| P01 | Backend | ADR fórmula acumulada, targets/orden/policy version, reference Python y RED conservación/no negativo | G01 |
| P02 | Backend | Validación canónica por destino/agregados, reparto/recepción/costo; preflight legacy sin reparación | P01 |
| P03 | Backend/Contracts | Schemas estrictos y replay ligado a recurso/actor/scope; error estable y reautorización | G01 |
| U01 | Frontend | Renglones identificados, input explícito y confirmación; negativos de request + QA visual | P02 |
| U02 | Frontend/Backend | Intento corporativo durable, respuesta perdida/reload/cambio cuenta y recuperación real | P03, U01 |
| I01 | Backend | Guardas IA y filtros en suggested-purchases/mermas; negativos y lector autorizado | G01 |
| I02 | Backend | Parser Decimal sin fallback ficticio, unknown, borrador/revisión y límites de entrada | I01 |
| F01 | Producto/Fiscal/Arquitectura | Decisiones D01/D02/D06, PRD y ADR fiscal, permisos, elegibilidad, estados, contrato PAC | G01 |
| F02 | Backend | Reautorizar recurso/lista/receipt/config, deny antes de PAC, migración grants sin expansión implícita | F01, W01 |
| F03 | Backend/Worker | Intención/outbox, links íntegros, key estable PAC, locks y recuperación unknown | F02, P03 |
| F04 | Backend/Frontend/QA | Máquina fiscal veraz, inbox/polling, cancelación/UUID, UX pendiente y conciliación; sandbox separado | F03 |
| S01 | Contracts/Backend | Inventario de módulos, ConfigurationScope/lectura efectiva, semántica herencia y límites | G01 |
| S02 | Backend | Productos -> recetas -> insumos -> proveedores -> presentaciones -> precios; versiones/herencia/excepciones | S01 |
| S03 | Frontend/QA | Transporte explícito, señales y confirmación; capability de release por módulo, default cerrado | S02, W03 |
| X01 | Backend/Integración | XML seguro, evidencia original privada, identidad/duplicados/UUID y original hash | I02, P03 |
| X02 | Backend/Frontend | Mapping versionado y conciliación XML-documento/orden/recibo, sin doble inventario | X01, P02 |
| A01 | Contable/Backend | D04/D06, modelo obligación/ledger/vencimiento y vínculo documental único | X02 |
| A02 | Backend/Frontend | Abonos/asignaciones/reversas, saldo proyectado, origen de pago y carreras | A01 |
| C01 | Contable/Backend | D03/D06, plan de compensación/cierre pendiente, valoración y contrato de aceptación | P02 |
| C02 | Backend/Frontend | Aplicación atómica inventario/costo/CxP, replay y UI historial/referencias | C01, A02, P03 |
| I03 | Producto/Backend | D05, proyecciones/versiones de consumo/stock/pendientes y motor puro explicable | I02, P02, S02, C02 |
| I04 | Frontend/QA | Propuesta transparente/revisión humana y auditoría temporal; nunca confirmación automática | I03 |
| G02 | QA/Backend | PostgreSQL reales y E2E por incremento, crash injection, CI colección/JUnit por SHA y auditoría Sol fresca | W05, U02, F04, S03, A02, C02, I04 |
| R01 | Operación/Producto | Cierre por AC/TC, evidencias y runbook de rollout/rollback; solicitar autorización productiva sólo con paquete revisable | G02, D00 |

**Lectura de dependencias:** `D00` reúne decisiones en un registro, pero F01/A01/C01/I03 resuelven las suyas dentro de su tarea; no hay dependencia ficticia de que todo D00 termine. `G02` representa el cierre agregado: sus pruebas se construyen/ejecutan dentro de cada incremento, no se difieren todas al final. X01 puede diseñar interfaz antes de I02; esa dependencia sólo gobierna integrar extracción/validación común. No añadir cuentas por pagar o XML como prerequisito de cerrar H01-H16.

**Ondas de entrega:**

1. Baseline G01 y guardas W01/I01/P03; abrir F01/S01/P01 y decisiones en paralelo lógico según capacidad.
2. W02-W03 y P02/U01/U02; primer candidato seguro de sucursales/recepción con sus gates. No esperar XML o demanda para estas correcciones.
3. W04-W05, F02-F04 y S02-S03 por módulo; candidatos separados con no regresión de caja/catálogo y auditoría R3.
4. X01-X02, A01-A02 y C01-C02: ciclo completo de compras, deuda y reversibilidad; D03/D04/D06 resueltas antes de efectos.
5. I03-I04: demanda con datos ya confiables; G02/R01 consolidan todos los hallazgos y releases parciales.

Duraciones/calendario no se inventan: estimar tras W01/G01 con capacidad, alcance de decisiones, CI y migraciones reales. El anexo Python calcula orden topológico y ondas mínimas de dependencias, **no fechas, costo ni velocidad del equipo**. El objetivo integral sólo termina con todos los AC cumplidos; un candidato parcial puede cerrar hallazgos individuales sin declarar terminado el sistema.

## 8. Pruebas, entornos y gates

**Fixtures:** dos organizaciones, dos razones sociales en una de ellas, A/B/C activas y una inactiva, almacenes correctos/ajenos, seis perfiles operativos, roles grant protegido, reader, actor desactivado; stock 0/positivo/negativo, yield mínimo/fraccionario, recibos parciales, compra cancelada, outbox incierto, leases legacy/expiradas, PAC fake y clocks UTC controlados. Todo sintético y reproducible, sin claves reales.

La auditoría anterior aportó 85 focales verdes, 13 nuevos casos fallidos causalmente y siete probes fiscales que **pasan afirmando defectos**. Copiar repros de `output/auditoria-2026-10-13/evidencia/` a suites mantenidas y reescribir aserciones fiscales. No invertir indiscriminadamente todos los asserts ni borrar happy paths. Cada regresión nueva debe fallar por la causa esperada en baseline, pasar tras corrección y comprobar ausencia de efectos parciales.

| Gate | Evidencia requerida | Cuándo |
|---|---|---|
| Integridad documental | referencias/23 IDs/31 tareas/dependencias/calculadoras, sin colisiones; traceability canónica al integrar IDs | Plan y cada cambio documental |
| Python focal | unit/API, Ruff y mypy de backend modificado sin nuevos silenciamientos | Cada incremento backend |
| PostgreSQL | locks/unique/checks/rollback/migraciones y JUnit sin skips; URL aislada faltante = gate pendiente/fallido | Persistencia/concurrencia/SQL afectada |
| SQLite/gateway | mismas invariantes, bundle/lease/version/outbox y recovery_only | W04/W05 y contratos offline afectados |
| Contratos/SDK | schema/API client/DTO OpenAPI: cuerpo estricto, Decimal string, scope/version/key/errores, backward compatibility explícita | Todo cambio de frontera |
| Frontend | prueba semántica + DOM/request; typecheck; build al empaquetado/flags/rutas o release | UI afectada |
| E2E/QA visual | API sintética real + navegador; sucursales, recibos, recuperación; 1440x900/1024x768 y móvil sólo si afectado | Cruce crítico/UI |
| Fiscal externo | FakePAC determinista; luego sandbox autorizado con pending/retry/cancel/documentación fixtures | F03/F04, separado de Live |
| CI | suite completa aplicable una vez, run/check/collection/JUnit ligados al mismo SHA | Cada candidato de integración |
| Revisión R3 | única auditoría Sol independiente de diff fresco: afirmación/evidencia/refutación/resultado/residual | Cada cambio R3 |
| Productivo | preflight, backup/restauración, autorización, canary compensable y conciliación | Sólo tras autorización separada |

**Comandos existentes, ejecutar desde la raíz del checkout candidato con entorno frozen:**

```text
python scripts/install_python_runtime.py --dev
python -m pytest apps/api/tests/test_branch_scope_selection.py apps/api/tests/test_corporate_purchases.py apps/api/tests/test_inventory_ai.py apps/api/tests/test_facturapi_integration.py -q
python -m pytest apps/api/tests/test_corporate_purchase_migration.py apps/api/tests/test_corporate_purchases_postgres.py -q
python -m pytest tests/architecture/test_traceability.py -q
node tests/frontend/test_corporate_purchases.mjs
node tests/frontend/test_branch_scope_headers.mjs
node tests/frontend/test_purchase_workspace.mjs
pnpm typecheck
git diff --check
```

El gate PostgreSQL actual usa `CORP_PUR_TEST_POSTGRES_URL` y el verificador `scripts/verify_postgres_evidence.py` exige cinco suites: cash_ledger, purchase_workspace, operating_expenses, system_remediation, corporate_purchases. CI declara esos entornos; su ejecución no fue acreditada en la auditoría. Ampliar el verificador para nuevas suites obligatorias, no eliminar las existentes. Un junit focal con una sola suite no satisface ese verificador completo.

Nuevos archivos previstos (todavía inexistentes): `test_branch_workspace_authority.py`, `test_invoicing_commands.py`, `test_supplier_xml_import.py`, `test_supplier_payables.py`, `test_corporate_purchase_compensations.py` y sus equivalentes PostgreSQL; navegador de receipt-intent/workspace-recovery. Sus nombres no son evidencia verde. Integrar en comandos y CI al crearlos. Los targets existentes declarados por BRANCH-SCOPE-001 pueden implementarse en lugar de duplicar suites.

## 9. Operación, revisión y rollout por incremento

Cuatro preguntas gobiernan señales; cada señal responde al menos una:

1. ¿Un actor está operando con workspace/versión inválidos o tiene turnos incompatibles? Señales de denegación por motivo, conflictos y consulta de turnos/workspace; investigar ID correlacionado sin cambiar historia.
2. ¿Targets, recepciones, costo y deuda concilian con originales? Invariantes por orden/partida/destino y obligación; violación bloquea nuevo efecto incompatible y abre revisión humana.
3. ¿Qué comandos inciertos/replays/backlogs requieren recuperación? Edad/resultado por módulo, outbox claim y reintentos; recuperar misma intención, nunca key nueva automática.
4. ¿Estado fiscal local y PAC difieren, o recomendación carece de fuente? Estado/edad de pending y model_version/datos insuficientes; conciliar fiscal y ocultar propuesta no sustentada.

Métricas con dimensión acotada módulo/operación/result/código; IDs sólo en trazas/auditoría autorizadas. Sin RFC, notas, XML, nombres, tokens, claves, precios o datos personales en labels/logs operativos. Conservar evidencia protegida donde la autoridad lo exige. Alertas por invariante y pendientes fuera de umbral aprobado, sin inventar SLO/retención durante el plan.

Cada auditoría R3 registra una tabla integrada: **afirmación -> evidencia -> intento concreto de refutación -> resultado -> residual**. Ejemplos: branch bypass, respuesta v3-v2, key misma URL distinta, quantum mínimo, crash después de PAC, dos abonos que exceden saldo, compensación contra recepción y downgrade con historia. Gate verde debe refutar el defecto específico, no sólo correr happy path.

**Secuencia productiva propuesta:** preflight read-only y verificar SHA/esquema/clientes; backup con restore probado en aislado; migración aditiva autorizada; lectura/recuperación; habilitación limitada por módulo/organización; canary sintético o documento acotado compensable según permiso; conciliación; ampliación gradual. Roles/grants legacy y filas inconsistentes bloquean activación, no se arreglan con UPDATE de saldos o historia.

**Criterios de pausa/rollback:** cualquier efecto entre branches/org, diferencia no explicada de cantidad/costo/deuda, PAC duplicado/falso final, backlog irrecuperable o grants inválidos detiene nuevos efectos del módulo. Mantener lecturas/recuperación y recovery_only donde hay pendientes; no volver silenciosamente a branch base. App rollback conserva esquema/logs; forward-fix/compensación cuando ya existe historia. No downgrade de tablas con operaciones ni cancelación remota automática para borrar errores.

## 10. Criterio de terminado y entregables

El **plan** termina cuando cubre 23 IDs con requisito/SDD/AC/SC/TC/tareas/dependencias/gates, distingue decisiones de reglas aprobadas y valida matemáticas/relaciones. La **implementación** termina cuando cada AC de sección 4 tiene test de aceptación verde, pruebas y auditoría exigidas por su riesgo, evidencia por SHA y límites declarados; deploy/migración/productivo no se confunden con Git o CI.

Entregables de implementación por incremento: diffs mínimos de autoridad activada, tests RED/GREEN, contratos y código, migración cuando aplique, matriz con estado real, evidencia exacta y una sola revisión R3. El cierre integral conserva una fila por H01-H18/B01-B05 con SHA, testcase/gate/run, resultado y residual. No ocultar casos pendientes detrás de marca Implementado.

Archivos de este paquete: `PLAN.md` (fuente revisable), `manifest.json` (matriz local y DAG), `calculos_referencia.py` (especificación matemática ejecutable) y `verificar_plan.py` (integridad/cobertura). Evidencia generada y PDF en `output/plan-remediacion-2026-10-13/` y `output/pdf/`. Ninguno reemplaza el código transaccional ni la matriz canónica sin integración posterior.

**Verificación ejecutada de esta entrega documental:** 23 IDs cubiertos, 31 tareas sin ciclos, 92 enlaces locales requisito/aceptación/escenario/caso y 18 paths de autoridad comprobados contra el SHA baseline. Python verificó 7056 repartos, 5000 secuencias parciales, ocho fronteras inválidas y ejemplos de centavos, promedio, deuda y demanda ilustrativa. Nueve pruebas canónicas de trazabilidad pasaron; `git diff --check` se aplica también a los cuatro archivos nuevos. Esta evidencia acredita el plan y sus fórmulas de referencia; no convierte las pruebas de runtime, PostgreSQL, CI o producción futuras en aprobadas.

**Reproducción del plan:** con Python 3.12 y un checkout separado del SHA baseline, ejecutar `python docs/implementation-plans/AUD-2026-10-13/verificar_plan.py --source-root RUTA_DEL_CHECKOUT --output output/plan-remediacion-2026-10-13/verificacion-plan.json`. La herramienta exige que HEAD coincida con baseline y verifica paths, cobertura y DAG; el cálculo puro sólo usa biblioteca estándar. Para integrar sobre un SHA posterior, primero reconciliar cambios del producto y actualizar baseline/evidencia, no desactivar la comprobación.
