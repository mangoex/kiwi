# POS-CAJERO-001 — implementación y evidencia local R3

Alcance: mejoras del [diagnóstico](../analysis/POS-CAJERO-001.md), PRD-FR-253..258 y FR-204/208.
Base `aa28b32`, rama `codex/pos-cashier-ux`. Paquete implementado con límites explícitos;
El estado siguiente corresponde al cierre local previo a publicación; no certifica despliegue,
migración o modificación de datos productivos. La integración Git se realiza después por PR.

## Resultado

- PointOfSale/progressiveCatalogFlow/cashierCapture: Recoger/Domicilio, modalidad de cobro
  vigente, búsqueda global, obligatorios primero, cantidades enteras positivas y notas por línea.
  Sidebar compacto; pedido, total Python y siguiente acción visibles. Sin mesas.
- cashierDrafts/useCashierDrafts: captura activa y hasta veinte pendientes locales aislados por
  usuario/sucursal/caja/transporte/gateway/dispositivo. Web Locks impide dos escritores; fallo de
  almacenamiento bloquea guardar. Navegar/recargar/intercambiar conserva selección y líneas.
  Logout/401 vigente limpia borradores. Se guardan cliente/domicilio ya registrados y seleccionados,
  no formularios parciales sin guardar. Los descuentos requieren reautorizar; no se confían precios.
- cash_tender/operaciones/API/gateway/diálogos: preview sólo lectura, recibido/cambio Python exacto,
  insuficiente bloqueado y cuerpo/clave congelados antes del comando. Reintentos inciertos conservan
  recibo técnico; rechazo definitivo no crea otro pedido. Compatibilidad del pago sin recibido.
- cashier_projection/History: contacto/referencias/notas históricos; cocina/pago/despacho/entrega
  separados. Enmienda sólo de líneas/versionado, con cliente/servicio/cortesía no editables. Notas
  históricas largas se conservan sin truncar; nuevas inválidas se rechazan antes de escribir.
  Fechas en zona de sucursal; auditoría colapsable conserva información.
- Fulfillment usa comandos/permisos existentes y confirmación física. El Cajero mantiene ocho
  permisos, sin cancelación/entrega. Impresión QUEUED no se presenta impresa; sólo se reintentan
  trabajos FAILED con los permisos existentes.
- KDS excluye CANCELLED histórico al comprobar trabajo pendiente después de enmienda; mantiene
  bloqueado READY mientras quede alguna tarea activa. No cambia transiciones ni borra historia.

No se redefinen tarifas, pago mixto, costeo, esquema, proveedor o dependencias. Los videos de Soft
Restaurant siguen siendo referencias históricas, no evidencia de su interfaz actual.

## Verificación ejecutada

RED dirigido reprodujo contacto vacío, preview ausente/tender inválido, búsqueda inicial por
categorías, identidad duplicada, notas de enmienda sin guardas y método perdido al abrir revisión.
Las causas se corrigieron sin desactivar pruebas/guardas.

| Gate local | Evidencia |
|---|---|
| Python puro | test_cash_tender.py: 22 aprobadas |
| Contrato caja | test_pos_cashier_workflow.py: 22 aprobadas; atomicidad, conservación legacy y recorrido editado hasta entrega |
| PostgreSQL SQL/KDS | test_pos_cashier_postgres.py: 5 aprobadas en PostgreSQL 18.6 temporal; migraciones canónicas, schema propio y rechazo de destinos URL alternos. CI configura gate en PostgreSQL 16 |
| Regresión existente | test_platform_api.py focal amend/payment/KDS/fulfillment/takeout/quote/modifier: 17 aprobadas, 70 deseleccionadas |
| Regresión tras corrección KDS | test_platform_api.py focal kds/cancel/fulfillment/takeout: 7 aprobadas, 80 deseleccionadas |
| Gateway | Pruebas focales cotización/preview, autoridad y pago local aprobadas |
| Python estático | Ruff focal aprobado; mypy operations/tender/projection aprobado |
| Frontend | pnpm test:frontend-semantic exit 0; seis scripts focales nuevamente exit 0 tras últimos ajustes |
| Empaquetado | POS/Admin typecheck y build aprobados; advertencia existente de chunks >500 kB sin silenciar |
| Integridad | Trazabilidad, repository policy y git diff --check aprobados |
| Auditoría | Un ciclo Sol independiente con contexto fresco; hallazgos corregidos y revisión focal final sin regresiones nuevas |

Al cierre local CI estaba pendiente. Sin canary ni PostgreSQL productivo. Se cambia un predicado SQL
KDS y se comprobó en PostgreSQL temporal; sin migración nueva o cambio de bloqueo/esquema.
Las carreras heredadas de cancelación requieren su propio gate PostgreSQL específico.
Runtime de QA portable obtenido de [binarios EDB](https://www.enterprisedb.com/download-postgresql-binaries),
sin instalar servicio del sistema ni abrir acceso fuera de loopback; se detiene al concluir pruebas.

## QA navegador y API sintética

API/SQLite aislados con fixture canónico, usuarios/contactos sintéticos. Capturas en
[assets](../analysis/POS-CAJERO-001-assets/), resumen sin tokens/PII en
[implementation-local-api-evidence.json](../analysis/POS-CAJERO-001-assets/implementation-local-api-evidence.json).

| Recorrido comprobado | Resultado / captura implementation-* |
|---|---|
| Búsqueda/cantidad/nota | Búsqueda desde categorías, repetición simple, cantidad 3 y nota; 01 |
| Espera/recuperación | Navegar/recargar/suspender/intercambiar conserva datos; segunda pestaña bloqueada, comprobada en navegador y pruebas focales; captura vacía descartada |
| Recoger diferido | Folio 1 ACCEPTED pendiente; editar 3→2 conserva folio/nota y total 190; 02/03 |
| Insuficiente/cambio | 189.99 frente a 190 bloquea pago; recibido 200/cambio 10/un pago 190; 04/05/06 |
| Recoger inmediato | Siete acciones desde POS cargada: buscar, agregar, Cobrar ahora, revisión, efectivo, recibido, confirmar; pago 95/cambio 5; 07 |
| Domicilio | Alta/selección cliente/domicilio, teléfono/ref/instrucción/nota/método; espera/intercambio/recarga conserva selección; confirmado pendiente sin tarifa inventada; 09/10 |
| Cobro domicilio | Recibido 100/cambio 5/pago 95 conserva cocina pendiente; 11 |
| Pantallas | 1366×768 y 1024×768; total/CTA visibles sin scroll (CTA 1024: x713..1006, y676..724); 12 |
| Entrega autorizada | Cajero sin fulfillment; administrador: READY→IN_DELIVERY→DELIVERED domicilio y READY→DELIVERED recogida; pago conservado; 13/14 |
| Recorrido enmendado corregido | Folio 4 por API local: CANCELLED histórica, dos tareas activas; primera IN_PRODUCTION, última READY; efectivo 285/recibido300/cambio15, replay y entrega con un pago; implementation-amended-journey.json |
| Logout | Captura/pendiente anteriores ausentes en nueva sesión; pruebas de limpieza/401 tardío aprobadas |

Primer recorrido visual: tres órdenes/tres pagos (uno por orden), tres tareas COMPLETED y una
CANCELLED histórica; seis trabajos QUEUED. El resumen JSON final añade el folio 4 de verificación
tras corregir KDS, también con un solo pago. Movimientos incluyen cuatro iniciales y reservas/
liberaciones/consumos existentes; sin editar saldos/historia directamente. Preparación KDS se ejercitó con API
autorizada, despacho/entrega con navegador. No se probó impresora física ni navegador KDS.

## Afirmaciones R3, refutación y límites

| Afirmación | Evidencia e intento de refutación | Resultado / riesgo residual |
|---|---|---|
| Captura no duplica comanda | Espera/recarga antes de confirmar sin órdenes/pagos/tareas; contratos reintentan con misma clave | Aprobado local; pérdida del dispositivo no es recuperación central |
| Autoridad aislada | Caja distinta/logout/401 actual y tardío renovado/dos pestañas/cambio de scope durante await | Hallazgos corregidos, pruebas verdes; requiere Web Locks |
| Dinero exacto sin JS | Déficit, float/bool/exponente/negativo/precisión, preview sin escrituras y pago único | Aprobado focal central/gateway; no prueba recepción física o proveedor bancario |
| Pago no entrega/prepara | Navegador conserva ACCEPTED/PENDING; entrega aparte; eventos saneados | Aprobado local; QUEUED no prueba impresión |
| Edición conserva historia | Nota inválida sin mutación; nota legacy conservada; CANCELLED histórica+activas; dos tareas completadas por separado | Enmienda/pago/KDS/entrega aprobados en SQLite/PostgreSQL y API local; no se reescribe historia previa |

Auditoría: cancel_order heredado presenta carrera frente a pago/KDS y cancelación repetida sin
serialización común. **Se retiró la nueva UI de cancelación**; habilitarla requiere corrección y
pruebas concurrentes PostgreSQL. No se amplían permisos ni se declara segura.

QA reprodujo un defecto heredado: advance_kds_task contaba CANCELLED como trabajo pendiente.
Se añadió regresión RED y se corrigió con NOT IN (COMPLETED,CANCELLED). SQLite, PostgreSQL y
folio 4 local prueban el recorrido completo; auditoría confirmó paridad gateway y estado no nullable.
También se corrigió el bypass URL host/dbname de la nueva fixture PostgreSQL y se probaron sus
guardas. La fixture usa migraciones canónicas, no create_all incompatible con restricciones legacy.
Folio 1 conserva la reproducción anterior a la corrección; no se reescribió su estado/tarea ya
completada. La corrección se aplica a futuras completaciones; una reparación de órdenes históricas
atascadas necesita revisión y autorización de datos independiente.

También permanece el destino de impresión hardcodeado preexistente: sólo se verificó sucursal
piloto. CI/producción/hardware/corte real de red/gateway/carreras cancelación PostgreSQL sin verificar.
No se declara release verde.

Preguntas operativas: eventos/cuentas distinguen orden/pago únicos; KDS se observa separado de
impresión; pruebas de identidad determinan captura recuperada; auditoría vigente conserva actor,
caja y sucursal sin agregar PII a logs. Sin cambios ceremoniales a artefactos no activados.

## Integración Git

PR #61: primer CI detectó TS6133 heredado en dos componentes compartidos de compras.
Se retiraron únicamente imports React sin uso; sin contrato/runtime nuevo. Typecheck del monorepo
y prueba semántica de compras verifican esta corrección. El resultado definitivo de CI corresponde
al SHA del PR, no sustituye QA productiva ni pruebas de hardware.

### Cierre de regresiones de CI y decisión visual (2026-10-01)

El usuario confirmó Admin moderno, claro y minimalista, con flujo familiar al sistema anterior.
R2 visual: FR-237, SDD §46.1, BDD/TDD administrativos y matriz recogen esta decisión. La QA
conserva los recorridos funcionales y sustituye neutralidad RGB por superficies claras, acentos
Kiwi, contraste AA y teclado. Se corrigió el texto de filas seleccionadas, el error de carga de
insumos ocultado como lista vacía y el alcance de impresión del catálogo para el tema moderno.
No cambian permisos, estados, cálculos ni persistencia por esta decisión visual.

CI 305 identificó además 59 fallos Python heredados: payload de corrección financiera equivocado,
fixtures PostgreSQL detenidas antes del esquema actual, fixtures sin autoridad corporativa,
unidades no canónicas, bundle offline vacío y expectativas de fuentes UI anteriores. Se corrigen
fixtures/selectores conservando escenarios, aserciones de negocio y guardas; no se desactivan
pruebas ni se añaden exclusiones. Los nombres históricos ADMINRETRO permanecen por compatibilidad.

Corrección R3 aislada: `apply_order_reopen_request` inserta `payment_adjustment` en
`order_payment_adjustments`, en vez del diccionario de producción `adjustment`. La regresión
existente reprodujo el fallo; se conserva la misma transacción, compensación y autorización.
Auditoría Sol independiente de esta corrección: sin bloqueantes, 26 pruebas aprobadas y tres
comprobaciones de payload/compilación PostgreSQL y SQLite. Sin cambio de esquema o migración.

| Gate dirigido posterior a CI RED | Evidencia local |
|---|---|
| Correcciones financieras y combos | 66 aprobadas |
| Fixtures AI, arquitectura POS, cadena Alembic y durabilidad offline | 50 aprobadas |
| PostgreSQL temporal 18.6 | 22 escenarios aprobados entre ejecución inicial y repeticiones de los fallos corregidos: correcciones, catálogo, combos, productos seleccionables y sincronización |
| Backend estático | mypy 59 módulos y Ruff aprobados |
| Integridad | Trazabilidad y política de repositorio: 15 aprobadas; diff --check sin errores |
| Admin | Typecheck/build y regresiones semánticas focales aprobadas; advertencia existente de chunk grande conservada |
| Navegador | Chrome: 390/768/1440, login con SO claro/oscuro, filas seleccionadas y teclado; productos seleccionables; asistente 390/1440; recorrido recetas 390/768/1440 |
| API → UI | SQLite sintética: prioridades/impresión/recarga/conflicto, umbrales, usos de recetas, lote versionado y combo con conflicto/revisión/versiones; sin errores de página |

| Afirmación R3 | Evidencia e intento de refutación | Resultado / límite |
|---|---|---|
| La compensación financiera recibe sus propios campos | REFUND/CHARGE/cero, enlaces e idempotencia; compilación PostgreSQL/SQLite | Aprobado por auditoría independiente; CI PostgreSQL 16 verifica el dialecto de release |
| Un fallo no deja una corrección parcial | Inyección de fallos, rollback de orden/pago/caja/producción y reintento | Pruebas focales aprobadas; no se modificaron hechos históricos |
| Repetición/concurrencia conservan una corrección | Replay, SQLite y cuatro escenarios PostgreSQL locales de corrección | Aprobado local; carreras heredadas de cancelación siguen fuera del alcance |

Preguntas operativas: ¿cada corrección aplicada tiene una compensación con signo y vínculo
correctos? ¿un fallo conserva APPROVED y permite reintentar sin duplicación? Los registros
relacionados, evento de auditoría `order.reopen.applied` y regresiones transaccionales existentes
responden ambas, sin añadir datos sensibles a logs ni instrumentación artificial.

La evidencia anterior reemplaza el diagnóstico local previo sólo en estos gates. El resultado
definitivo de release es el CI del SHA final de PR #61; Git no certifica despliegue, hardware,
canary ni reparación de datos productivos. El usuario realizará el redeploy.
