# TDD — AUD-CORE-001

Diseño R3 con pruebas dirigidas implementadas; evidencia de ejecución y límites en AUD-CORE-001
§11. Cada defecto obtiene RED conductual y GREEN tras la corrección; la evidencia parcial no
acredita cierre. Mantener pruebas existentes y sus gates.
BDD: `03-BDD-system-remediation.md`; SDD §57; coordinación en el plan AUD-CORE-001.

## TDD-TS-136 Regresiones financieras, relaciones y autoridad

Fixtures deterministas: dos organizaciones, dos sucursales autorizables, almacenes y caja con
200000 centavos; cuentas con grants granulares/revocables; fechas UTC fijas y zonas IANA distintas;
insumo con varias presentaciones, recepciones repetidas de costo cero y no cero, histórico congelado.
Gastos además usa fixture sin insumos/proveedores/almacén según TS-134. Ninguna BD productiva.

Ubicaciones nuevas previstas: `apps/api/tests/test_system_remediation.py` y
`apps/api/tests/test_system_remediation_postgres.py`. Extender suites existentes cuando comparten
fixture/contrato, sin duplicar los mismos casos en ambos lugares. PostgreSQL usa
AUDCORE_TEST_POSTGRES_URL en base exclusiva audcore_* y schema aislado; localhost/127.0.0.1
validado antes de cualquier creación/eliminación. Limpieza limitada al schema propio.

### TDD-TC-332 Egreso único en ledger y conciliación

SC-615. Crear/confirmar por API compra de 30000; verificar int exacto 170000 en ledger y Decimal
1700 en daily/consolidated/xlsx. Contar por ID la categoría proveedor y ausencia en fixed/manual.
Agregar EXPENSE, compensaciones, retiros manuales y movimientos no confirmados; demostrar
clasificación exhaustiva sin solapamiento, no sólo igualdad del total. RED: daily muestra 1400.
Compensación manual PURCHASE admitida se clasifica por original y reduce proveedor, sin cambiar
status documental ni convertirla en depósito genérico. Vínculos inválidos o duplicados no se certifican.
Extender `test_branch_reconciliation_reports.py` y contratos reales de consumidores.

### TDD-TC-333 Pagos confirmados y métodos

SC-616. Fixture usando estados reales del escritor: cash 10000 + card 20000 + transfer 30000,
pagos excluidos y crédito bajo contrato vigente. Esperado incluye sólo 10000 cash; ventas 60000
para los tres pagos. Desconocido no se clasifica como cash, se trata según error de integridad
canónico. RED: filtro lowercase omite CONFIRMED. No arreglar prueba convirtiendo fixtures a lowercase.

### TDD-TC-334 Eventos, historia y límites temporales

SC-617. Reloj controlado: creación D, confirmación D+1, cancelación D+2; compra/gasto en varios
métodos. Capturar actividad calendario D+1 y huella de históricos antes/después; positivo D+1 idéntico y reversa
sólo D+2. Exactamente inicio incluido/final excluido; UTC/local y cambio de offset cuando exista
en la zona seleccionada. Consolidado es suma de días, sin duplicar evento. Probar turno cruzado
comparando saldos con su ledger y distinguiendo actividad del día del snapshot del turno;
no atribuir contado a apertura/cierre operativo. D-01/D-02: medianoche, dos turnos misma caja,
varias cajas, snapshot de cierre inmutable con efecto posterior excluido y conflicto de snapshot
explícito. Conteo completo legacy con cero real/positivo, parcial de usuario ignorado, una caja
pendiente y población vacía: counted/difference null sin certificar. JSON v2, rechazo upgrade v1,
consolidado sin duplicación y Excel con celdas vacías frente a cero. RED: población calendario
mezclada con saldo y apertura/cierre operativo convertidos a contado.

### TDD-TC-335 Cancelación de borrador sin reversa financiera

SC-618. Cancelar draft de 30000 mediante API; status cancelled/auditoría documental pero cero
recepciones/retiros/eventos positivos/reversas en `/reports/expenses`. Repetir consulta paginada,
consolidada y con draft EXP. RED: purchase_cancellation -30000 sin confirmado original.

### TDD-TC-336 Cantidad y valor agregados de cancelación

SC-619. Dos líneas de 5, existencia 5, costo cero: rechazo explícito y huella completa idéntica;
existencia 10: dos reversas y saldo cero. Parametrizar distintas presentaciones del mismo insumo,
cantidades fraccionarias, varios insumos con uno insuficiente, costo positivo, valor negativo,
stock consumido/traspasado y saldo final positivo. Oráculo Decimal agregado separado del escritor.
Mantener tolerancia existente y seis decimales; precio cero permitido. RED: saldo -5.
Verificar que estados finales, compensación cash y auditoría sólo cambian si toda la compra valida.

### TDD-TC-337 Competencia, atomicidad y reversas únicas

SC-620; ampliar TC-327/328/329 sin sustituirlos. PostgreSQL real con conexiones distintas y
barreras/eventos: confirm/confirm misma y distinta clave, confirm/cancel draft, cancel/cancel,
compra/cierre/reapertura, cancelación/consumo/traspaso y compensación manual cuando corresponda.
Ambas transacciones alcanzan explícitamente la frontera de lectura antigua en RED, no un sleep.
API/dominio rechazan originales cash/receipt con identidad inconsistente antes de replay/cancel:
source, documento, scope, unidad, importe/cantidad/costo, actor, status, flags, faltantes y extras.
El multiset de recibos coincide con todas las líneas; no se compensa inventario de otra sucursal.
Inyectar fallo después de cada escritura cash/receipt/costo/precio/historial/documento y auditoría;
reusar sesión y commit posterior no persiste ningún efecto parcial.
Como máximo un retiro y una recepción por línea; estado final y auditoría corresponden al ganador.
Intentar refutar orden de locks/deadlock; acotar timeout y exigir resultado de negocio interpretable.
SQLite focal verifica su reserva de escritura, sin afirmar que simula FOR UPDATE.
Inyectar fallo tras retiro, recepción, costo, precio proveedor, estado, auditoría y recibo cuando
exista: rollback de todas las tablas implicadas. Replays tras cierre/cancelación no escriben;
misma clave con actor/body/turno/documento distinto falla. RED de carrera se debe reproducir en PG
antes de certificar el riesgo de la auditoría como bug confirmado; si no se reproduce, registrar
contraevidencia y demostrar de todos modos el invariante antes de liberar.
Incluir clave máxima de 180 caracteres sin desbordamiento, consumo KDS real que gana antes de
cancelación y serialización por sucursal sin impedir KEY SHARE de FK de caja manual. Un consumo
posterior puede dejar negativo según la política existente; no introducir una prohibición nueva.

### TDD-TC-338 Sucursal inactiva y permisos revocados

SC-621. Crear con autoridad válida, desactivar sucursal/revocar grant y solicitar confirmar,
cancelar, replay, detalle y contexto. Rechazo conforme a la ruta, cero nuevas escrituras y mismo
histórico. Probar IDs de otra sucursal/organización y actor inactivo. RED: confirm inactiva devuelve
200 con recepción. No simular permiso por nombre de rol ni usar sólo controles UI.

### TDD-TC-339 Proveedor y sucursal de la misma organización

SC-622. HTTP y dominio: proveedor B + sucursal A, proveedor A + sucursal B, ID ausente,
sin permiso corporativo y asociación válida A/A. Huella de terms/auditoría intacta ante rechazo.
Paridad con contactos/presentaciones/creación de compras. RED: PUT persiste asociación B/A.

### TDD-TC-340 Listado por alcance resuelto

SC-623. Tres documentos de distintas sucursales/organizaciones: corporativo A sin branch devuelve
sus dos documentos; explícito A1 devuelve uno; restringido A1 omitiendo branch devuelve sólo A1;
ajeno rechazado. No exigir un listado multiempresa. Frontend prueba cambio de actor/sucursal con
respuesta antigua en vuelo y cache aislada. RED: corporativo retorna [] por IS NULL.
Conciliación: insertar relaciones existentes ajenas con FK válidas en PostgreSQL y equivalentes
SQLite; movimiento propio a turno ajeno fuera del día de apertura, movimiento posterior al cierre
en día sin turnos, concepto/versión ajenos. Daily/consolidated/xlsx fallan con conflicto redactado
sin nombre ajeno, no omiten el movimiento. Tras audit POST de A, cambiar a B y resolver A mientras
GET B está pendiente: el refresh antiguo no invalida la petición vigente ni deja loading bloqueado.
Pedido padre ajeno de pago confirmado, con FK válida, también falla; un pedido propio cuyo turno
de captura difiere del turno de cobro sigue permitido conforme ADR-026.

### TDD-TC-341 Errores HTTP y redacción

SC-624. TestClient con raise_server_exceptions=False, entradas reales sin token/fuera de alcance,
sucursal inactiva y fallo SQL inyectado con marcador sensible. Verificar status/detail canónicos
y ausencia de SQL/parámetros/token/marker en respuesta y log. Dominio prueba ausencia de efectos;
UI conserva captura/revisión ante rechazo. RED: autorización fuera de wrapper produce 500.

### TDD-TC-342 Matriz de cuentas, roles y acciones

SC-625. Parametrizar grants reales: sólo compras, sólo gastos, sólo retiro, ambos dominios,
read-only, Dueño, Supervisor/Administrador restringidos y rol personalizado con nombre imitador.
Cubrir concepto/read/write/cancel/report/cash-context; falta de cash.shift.read no impide contexto
mínimo cuando posee dominio+retiro. Históricos y permisos no se elevan por migración ni reparación.
Preservar cancelación interna de compra con purchases.manage; EXP cash requiere reglas de TS-134.

### TDD-TC-343 Separación e integración de documentos

SC-626. API: apertura 200000, compra cash 30000, gasto cash 30000 y gasto transfer 100000;
esperado 140000, Gastos neto 130000 y coste/recepción sólo por compra. Comparar contenido de todas
las tablas inventario/costos/proveedores antes/después de comandos EXP, con y sin historia.
Anular bajo condiciones distintas de cada dominio, verificar originales y enlaces. Mantener
TS-134 y pruebas de compras como regresiones, no renombrar compras para simular Gastos.

### TDD-TC-344 Consumidores, recuperación y recorrido real

SC-615/617/626 y SC-607..613. Contratos JSON/DTO, daily/consolidated/xlsx y API/backend compartido
Admin/acceso POS. Extender `test_purchase_workspace_e2e.mjs`, `test_operating_expenses_e2e.mjs`
y `test_reconciliation_reports.mjs` con verificación de comportamiento; assertions de strings no
acreditan saldo, autoridad ni recuperación. Respuesta perdida, refresh fallido, recarga, switch de
actor/sucursal, cero/una/varias cajas y cierre/reapertura. QA sólo estados/breakpoints afectados,
teclado/foco/errores en español; typecheck/build de apps/paquetes realmente afectados.
Para reportes v2: probar render pendiente, contado cero y total parcial en Admin/POS; actividad
independiente y títulos de población, descarga con autorización y errores explícitos. Respuestas
obsoletas de otro actor/sucursal no pueden reaparecer; no interpretar null como money(0).
`test_reconciliation_e2e.mjs` usa API/builds reales y fixture exclusivamente sintética repetible;
retiene la respuesta de revisión A mientras carga la fecha B para refutar contaminación obsoleta.
Verificar wire de dinero como string canónico de dos decimales contra schemas diarios/consolidados,
y presentación exacta con BigInt para valores superiores a 2^53, centavo negativo y acarreo largo;
rechazar formatos incompatibles antes de mostrar un reporte.
Población corporativa sin sucursales conserva contrato completo con nueve ceros y conteo EMPTY.
Ejecutar la guarda real del botón para cada alternativa vigente de revisión y rechazar autoridad
derivada únicamente de cash.shift.close; la API conserva su propia autorización persistida.

### TDD-TC-347 Diagnóstico histórico de sólo lectura

SC-629; SDD57.7. `test_system_diagnostics.py` usa archivos SQLite aislados y un schema PG
exclusivo: compras válidas y duplicadas, cash incoherente, movimiento huérfano de compra/gasto,
reversas duplicadas con padre válido, reversas ajenas entrantes a originales propios sin exponer
IDs ajenos, confirmación sin timestamp, terms ajenos, stock negativo
sin atribución causal y límite de cobertura. Comparar contenido
completo antes y después; intentar DML dentro del snapshot debe fallar realmente en ambos
motores. CLI sin URL, archivo inexistente y errores con marcador privado falla sin imprimir
URL/SQL/marker. No conectar producción. El gate PG se integra en el módulo obligatorio de
remediación, sin un skip nuevo.

## TDD-TS-137 Reproducibilidad de dependencias y cobertura de CI

### TDD-TC-345 Instalación limpia y equivalencia del runtime

SC-627. Gate de instalación, no test que sólo busque nombres de paquetes: entornos vacíos Python
3.12 Linux/API y Windows/gateway aplicable, locks con versiones/hashes verificables y paquete propio
instalado sin reresolver. pip check, import create_app/rutas multipart, health en test y recolección
focal. Dos instalaciones del mismo objetivo comparan inventario de versiones; manipular hash o
manifest/lock debe fallar. Acreditar build desde Dockerfiles reales con lock Python y pnpm frozen;
sin dependencia en Python global 3.14, sin remover multipart para pasar. Pruebas/gate de pipeline
previstos en `tests/architecture/test_dependency_runtime.py` y CI, según el boundary probado.

### TDD-TC-346 PostgreSQL obligatorio ejecutado en CI

SC-628. Gate parametrizado por CI explícito: si falta PCO003_TEST_POSTGRES_URL o
AUDCORE_TEST_POSTGRES_URL, servicio falla o pytest omite un caso obligatorio, ejecución no verde.
Con servicios provisionados comprobar collection/ejecución y JUnit por suite; no confiar sólo en
conteo total porque un módulo puede quedar omitido. Local sin servicio permite skip declarado;
CI exige ejecución. Mantener aislamiento y guardas de URL. CI PR y workflow_dispatch prueban el
commit del paquete. La suite completa aplicable corre una vez en CI conforme GOV-TEST-001.

## Gates y registro

Primero ejecutar módulos afectados; ruff/mypy focal y typecheck para cambios de código. Activar
PG por SQL/locks/persistencia, SQLite por paridad afectada, E2E por recorrido crítico y QA por UI.
Migración sólo si cambia schema; upgrade/downgrade/upgrade aislados y bloqueo con historia.
No extender gateway ni compras/gastos offline sin un contrato posterior. Verificar regresiones
de autoridad offline existente cuando los helpers compartidos sean afectados.

Cada cierre registra comando, commit, runtime/lock, conteo pass/fail/skip y evidencia del oráculo;
afirmación/contraejemplo/resultado/riesgo residual por invariante R3. Una auditoría Sol fresca y
CI efectivo completan el ciclo. Ningún skip, mock de FOR UPDATE o test sólo de texto sustituye PG.
