# AUD-CORE-001 — Plan integral de remediación de la auditoría

Fecha: 2026-10-09. Base inspeccionada: main, 39094e3460dafb52129f6630b5e4b9ca864e93df.
Estado: **implementación local y decisiones D-01/D-02 verificadas; publicación Git autorizada, gates Linux/Docker/CI pendientes**.
Entrega documental R0; implementación conjunta R3 por dinero, inventario, alcance, concurrencia,
persistencia y dependencias de operación. La autorización Git posterior consta en §12; operación
productiva conserva autorización separada.

## 1. Resultado y autoridad

Resolver todos los hallazgos de la auditoría del 2026-10-09 sin confundir Compras con Gastos,
sin alterar movimientos históricos y sin acreditar resultados futuros con pruebas baseline.
El marco solicitado se aplica como PRD + SDD + BDD + TDD + ADR cuando corresponda + matriz,
con AGENTS.md como proceso canónico. Cada cambio obtiene contrato antes del runtime y RED
conductual antes de GREEN; no fabricar RED para este documento R0.

| Autoridad | Artefacto y activación real |
| --- | --- |
| PRD | [01-PRD](../01-PRD.md): conservar FR-052, FR-091/092, FR-108..111, FR-207, FR-220, FR-225/226 y FR-263..265. NFR-016 se amplía para instalación Python reproducible y gates efectivos. |
| SDD | [02-SDD §57](../02-SDD.md): proyección, fechas, locks, reversas agregadas, relaciones, errores y dependencias. §38/40/51.8/56 siguen siendo autoridad complementaria. |
| BDD | [03-BDD-system-remediation](../03-BDD-system-remediation.md): SC-615..629. Reutilizar SC-607..613 de PUR-CASH y SC-599..606 de EXP. |
| TDD | [04-TDD-system-remediation](../04-TDD-system-remediation.md): TS-136/137, TC-332..347. Reutilizar TS-135/TC-324..330 y TS-134/TC-316..323. |
| Matriz | [05-matriz-trazabilidad](../05-matriz-trazabilidad.md): relaciones añadidas y correcciones pendientes explícitas; requisitos con defecto confirmado no conservan cierre acreditado. |
| ADR | No hay nueva dependencia crítica ni arquitectura transaccional. Activar sólo si una decisión de ejecución cambia esa condición; no crear un ADR ceremonial. |
| Coordinación | Este plan contiene secuencia, tareas, gates, riesgos y handoff; no crear planes paralelos que copien las especificaciones. |

[PUR-CASH-001](PUR-CASH-001.md) es un subpaquete obligatorio de este plan, no otra implementación
de Compras. [EXP-001](EXP-001.md) permanece baseline y gate de regresión, no se reconstruye.
Los estados de documentación describen evidencia y no significan despliegue o reparación de datos.

## 2. Inventario completo y cierre por hallazgo

Prioridad P1/P2 no sustituye clasificación de riesgo. Toda corrección de dinero, inventario o
autoridad se integra bajo R3 aunque el defecto sea P2. Las ubicaciones se verifican por símbolo
en la base actual; no depender de números de línea que cambiarán durante implementación.

| ID / prioridad | Evidencia de auditoría | Solución y oráculo de cierre | Especificación/prueba | Paquete |
| --- | --- | --- | --- | --- |
| H01 P1 Doble egreso | Compra cash 300 con apertura 2000: ledger 1700, daily 1400 | Un retiro, una categoría; ledger/daily/consolidado/Excel 1700 para el mismo alcance | SDD57.1; SC-615; TC-332/344 | P4 |
| H02 P1 Pagos omitidos | Pago cash CONFIRMED 100: ledger 100, daily 0 | Predicado de estado/método canónico; cash/card/transfer correctos, sin fallback de método | SDD57.1; SC-616; TC-333 | P4 |
| H03 P1 Cash incoherente | cash + paid_from_cash false confirma inventario sin retiro | Implementar PUR-CASH completo: cuatro métodos, equivalencia bidireccional, contexto y turno revisado | SDD51.8/57.2; SC-607..613; TC-324..330 | P2 |
| H04 P1 Cancelación por filas | Dos recepciones de 5, quedan 5, costo cero: cancela y deja -5 | Sumar cantidades/costos por insumo y prevalidar todo; rechazo mantiene saldo 5, con 10 admite reversas | SDD57.3; SC-619; TC-336 | P3 |
| H05 P1 Carrera de confirmación | Evidencia estática; PostgreSQL aún no reproducido | Reproducir interleaving en RED, lock/relectura/predicado de estado; un ganador, cero duplicados | SDD51.8/57.2; SC-611/620; TC-327/328/337 | P2/P3 |
| H06 P2 Reversa de borrador | Draft cancelado genera -30000 sin positivo anterior | Reversa sólo de documento previamente confirmado; draft no genera evento financiero | SDD57.1; SC-618; TC-335 | P4 |
| H07 P2 Sucursal inactiva | Confirmación después de desactivar sucursal responde 200 y recibe | Guardar autoridad vigente en comando/replay; nueva transición rechazada sin efectos | SDD57.2; SC-621; TC-338 | P1/P2 |
| H08 P2 Proveedor ajeno | Terms proveedor B/sucursal A persiste | Validar ambos extremos bajo la misma organización y permiso corporativo | SDD57.4; SC-622; TC-339 | P1 |
| H09 P2 Consulta corporativa vacía | Con branch devuelve documento; sin branch devuelve [] | Alcance None corporativo filtra organización y sucursales autorizadas, no IS NULL | SDD57.4; SC-623; TC-340 | P1 |
| H10 P2 Errores 500 por alcance | Autorización fuera del wrapper en listados compras/proveedores | Auth/validación dentro del wrapper; 401/403/409/503 redactados según contrato | SDD57.4; SC-624; TC-341 | P1 |
| H11 P2 Fechas e historia | Lectura por created_at/status actual; evidencia estática | Confirmación y cancelación por eventos/ledger y periodo local; pasado conserva positivo | SDD57.1; SC-617; TC-334/344 | P4 |
| H12 Entorno local incompleto | .venv no pudo recolectar por falta de python-multipart | Instalación vacía del proyecto completo carga rutas multipart y health, sin Python global | NFR-016/SDD57.5; SC-627; TC-345 | P0/P5 |
| H13 Resolución Python no congelada | pyproject declara rangos; Docker/CI resuelven al instalar | Lock runtime/dev por objetivo con hashes, instaladores equivalentes y pnpm frozen | NFR-016/SDD57.5; SC-627; TC-345 | P5 |
| H14 Gate PG no configurado | Hallazgo adicional de planificación: test_cash_ledger_postgres exige PCO003_TEST_POSTGRES_URL, ci.yml no la define | Provisionar bases exclusivas; gate falla si URL/servicio/casos obligatorios faltan | NFR-016/SDD57.5; SC-628; TC-346 | P0/P5 |
| H15 P2 Paridad booleana de metadata | PostgreSQL rechaza metadata.create_all por comparar booleanos con 0/1 en ingredient_variation_products; migración 0026 ya es correcta | Modelo usa las expresiones booleanas canónicas de 0026, sin reescribir migraciones; setup PG y regresión SQLite de variaciones | SDD57.5; SC-627; TC-345 | P0/P5 |

H12 es un problema del entorno inspeccionado, no prueba de dependencia ausente en el manifiesto.
H13 no es una vulnerabilidad confirmada ni autorización para actualizar todos los paquetes.
H05 fue reproducido en PostgreSQL 16.15: dos claves confirman el mismo draft; una clave genera
violación de unicidad en efectos. Locks y relectura pasan los casos focales y las carreras locales
registradas en §11; la evidencia del commit en CI sigue pendiente.
H11 conserva su evidencia por evento; D-01/D-02 fueron aprobadas y verificadas localmente según §8.1/11.

## 3. Invariantes y límites de alcance

- Compras exige proveedor, presentación activa, insumo, unidades coherentes y almacén de sucursal.
  Recepción/costo sólo al confirmar. Excepción de proveedor urgente conserva su contrato explícito.
- Gastos no usa insumos, presentaciones, proveedores, recetas o almacén; cualquier método o transición
  debe conservar idéntico su contenido e historial. No cash no exige turno ni mueve caja/banco.
- Cada efecto se contabiliza una vez; ledger es autoridad del efectivo y documentos de Gastos son
  autoridad de sus estadísticas. Desgloses no producen una segunda resta.
- Dinero int/Decimal, cantidades/costos Decimal y cuantización aprobada; no trasladar cálculo a JS.
  Conservar impuesto informativo, descuento, flete cero, conversión y política de costo negativa.
- Pago/movimiento original inmutable, reversa referenciada y auditada. No borrar historia ni alterar
  snapshots de cierre para que el reporte cuadre. No emitir compensaciones financieras ficticias.
- Identidad de cuenta, grants y alcance vigentes autorizan; sucursal, caja y turno coinciden.
  Sin grants nuevos, elevación por nombre ni cambio de política de cancelación de Compras/Gastos.
- Mantener compatibilidad de clientes explícitos legacy de §51.8; no ampliar defaults al contrato
  estricto ni corregir silenciosamente borradores incoherentes. Cancelar/recapturar conforme al SDD.
- Mantener contratos offline y consumidores históricos. No crear compras/gastos offline ni ampliar
  bundles. Un helper compartido modificado activa regresiones de gateway/autoridad existentes.
- Sin reglas nuevas de fondos insuficientes, crédito directo, pago mixto, deuda, dinero personal,
  caja automática, devolución postcierre o política de disponibilidad de reservas.

## 4. Dependencias y secuencia de ejecución

```text
P0 entorno, contratos, fixtures y gates efectivos
  -> P1 alcance, relaciones y errores
  -> P2 PUR-CASH-001 y confirmación serializada
  -> P3 cancelación agregada y atomicidad
  -> P4 proyecciones, fechas y consumidores
  -> P5 locks de dependencias y equivalencia Docker/CI
  -> P6 integración, evidencia y auditoría independiente
  -> P7 publicación autorizada y liberación productiva separada
```

Preparar pruebas de P4/P5 puede avanzar después de P0, pero no acreditar integración hasta los
prerrequisitos. No hacer un big bang ni publicar frontend con contratos backend aún ausentes.
P0 instala únicamente en un entorno de prueba aislado durante implementación; no modifica el entorno
productivo. Si una corrección de lectura P4 necesita salir antes, conserva su frontera y pasa todos
sus gates R3/consumidores, con autorización de publicación independiente; no rebajar los demás.

| Paquete | Tareas concretas y módulos | Entrada y salida verificable |
| --- | --- | --- |
| P0 | Comprobar branch/HEAD/trabajo local; preparar Python 3.12 aislado con API/dev; fijar reloj/fixtures/huellas; provisionar PG de pruebas; mapear locks reales de compra/cierre/consumo/transferencia/compensación; convertir repros previos en tests | Specs/IDs íntegros y baseline medible; infraestructura apta para RED. Ningún fallo de importación acredita RED de dominio |
| P1 | Corregir autoridad en transitions/listados; supplier_branch_terms filtra proveedor y sucursal; corporativo vs restringido; wrappers y consultas cache por actor/org/branch. operations.py, api.py, PurchasesList.tsx y clientes afectados | TC-338..342 RED/GREEN y regresiones permisos; errores redactados, sin effects ni grants nuevos |
| P2 | Ejecutar D1..D5 de PUR-CASH dentro del paquete: DTO/schema, resolver de expenses.cash_context parametrizado, selector único, revisión y expected shift, intento congelado, lock/relectura/state predicate, identidad/replay | TC-324..328 y TC-337 verdes en PG/SQLite; confirmar 300 descuenta una vez; nueva UI nunca sustituye turno |
| P3 | Compartir serialización con cancelación; preagregar cantidades/costos y proyectar todo antes de escribir; una reversa por original y estado final por insumo; mantener turno original y policy por dominio | TC-336/337/329 GREEN; stock no negativo por reversa y cero parcialidad tras cada fallo |
| P4 | Centralizar predicados/cálculos de proyección; separar categorías por vínculo; CONFIRMED; eventos de confirmación/anulación, sin reversa de draft; integrar daily/consolidated/export/general; actualizar contratos y consumidores juntos | TC-332..335/343/344 GREEN; valores exactos e historia conservada; ningún impuesto/gasto no cash afecta esperado |
| P5 | Generar locks Python runtime/dev para plataformas objetivo con herramienta fijada; instalación sin re-resolver propios; modificar Dockerfiles/CI/bootstrap de test para locks y pnpm frozen; provisionar PCO003/AUDCORE y rechazar skips obligatorios | TC-345/346, build objetivo e inventario de versiones equivalentes; dependency review aplicable no bloqueante |
| P6 | Recorrido Admin/acceso POS, recuperación/cambio de contexto, reportes/Excel y EXP no inventario; checks focales, E2E/QA, suite CI completa una vez, handoff único y auditoría Sol fresca | Todos los criterios cubiertos con evidencia del mismo commit; cero hallazgos bloqueantes abiertos |
| P7 | Publicar sólo con autorización aplicable; revisar compatibilidad de release, diagnóstico histórico sólo lectura, despliegue y canary explícitos separados | Git, CI, deployment y comportamiento productivo registrados por separado; operación histórica compensable si aplica |

La ejecución de P2 incluye todo PUR-CASH requerido por H03/H05, no sólo cambiar un if. La lista
P1..P5 referencia casos canónicos; no copiar nuevamente cada escenario en un reporte de implementación.

## 5. Criterios verificables de aceptación del paquete

| ID | Criterio de terminado del comportamiento | Oráculo/gate |
| --- | --- | --- |
| AC01 | Apertura 200000 - compra cash 30000 = 170000 en ledger y consumidores equivalentes | TC-332; igualdad de componentes, clasificación sin solapamiento |
| AC02 | CONFIRMED cash/card/transfer conserva total 60000 y cash 10000; estados excluidos no participan | TC-333; escritores/fixtures reales |
| AC03 | Cash iff paid_from_cash, cuatro métodos; caja/turno revisados y nuevo turno no sustituido; no cash sin ledger | TC-324..326/329; contratos/Admin/acceso POS |
| AC04 | Dos partidas de 5 con existencia 5 rechazan sin efectos; con existencia 10 revierten a cero conservando originales | TC-336; costo cero y positivo/fracciones/presentaciones múltiples |
| AC05 | Una transición ganadora; replays idénticos no duplican; intención distinta falla; fallo tras cualquier escritura revierte | TC-327/328/337; PostgreSQL real, locks/commit/cancel/cierre |
| AC06 | Draft cancelado no produce positivo ni negativo financiero | TC-335; reporte API y huellas |
| AC07 | Actor/grants/sucursal/organización vigentes en nuevas transiciones y replay; inactiva no recibe efectos | TC-338/342; negativos API/dominio |
| AC08 | Terms sólo une proveedor y sucursal de la organización autorizada | TC-339; referencia ajena en ambos extremos |
| AC09 | Corporativo sin branch ve su alcance; restringido sin branch conserva su sucursal; no cache ajeno | TC-340; respuesta tardía y filtros |
| AC10 | Denegación no produce 500 ni fuga; HTTP/códigos canónicos y 503 almacenamiento redactado | TC-341; marcador sensible/log/response |
| AC11 | Creación D no cuenta; confirmación D+1 y anulación D+2 conservan el pasado; límites sin solapamiento | TC-334/344; diario/consolidado/Excel y snapshots |
| AC12 | Compra cash 30000 + gasto cash 30000 + gasto transfer 100000: caja 140000, Gastos 130000; EXP no altera inventario/proveedores | TC-343; fixtures vacías y con historia |
| AC13 | Instalación vacía, multipart, health, versions/hashes y Docker/CI reproducibles sin globales | TC-345; lock/project instalado y build real |
| AC14 | Todos los gates PG activados se ejecutan en CI o el pipeline falla | TC-346; JUnit por suite y configuración negativa |
| AC15 | Specs/IDs/matriz, pruebas nuevas, CI del commit y auditoría independiente acreditan el alcance completo | Trazabilidad, handoff, cierre R3; sin silenciamientos/exclusiones nuevas |
| AC16 | Diagnóstico histórico preparado, limitado a organización explícita y sólo lectura; detecta discrepancias conocidas sin reparar ni acreditar cobertura incompleta | SDD57.7; SC-629; TC-347; rechazo real de DML en SQLite/PG y huella completa idéntica |

## 6. Estrategia RED/GREEN y gates proporcionados

1. Capturar contenido/conteos exactos antes del comando y observar el resultado público, no sólo
   strings del código. RED debe fallar por la conducta del hallazgo; importar sin multipart o
   faltar PG es un bloqueo de infraestructura, no el RED solicitado.
2. Para H05 introducir barrera determinista con PostgreSQL real y conexiones separadas antes de
   dar por demostrado el defecto. Si la ejecución refuta la hipótesis, registrar el resultado y
   ajustar la corrección dentro del contrato; no fabricar un fallo ni omitir el invariante.
3. Corregir el mínimo y ejecutar primero el caso y módulo afectados. Mantener baseline y pruebas
   adversariales activas; no sustituir seis decimales por float ni normalizar datos de fixtures.
4. Completar gates de superficie cuando su cambio los activa; la suite completa aplicable corre
   una vez en CI, no en cada microtarea. Repetir sólo por cambio/fallo nuevo, según GOV-TEST-001.

| Gate | Activación y evidencia requerida |
| --- | --- |
| Documental | `python -m pytest tests/architecture/test_traceability.py -q -p no:cacheprovider`, links/IDs/matriz y `git diff --check` |
| Python focal | Nuevos módulos de remediación + test_purchase_workspace, test_branch_purchases_and_courtesies, test_cash_ledger, test_branch_reconciliation_reports, test_pco007_recipe_reports, test_operating_expenses y test_audit_money_public_regressions según paquete |
| Calidad Python | `python -m ruff check` para archivos modificados y `python -m mypy apps/api/restaurant_os` sin nuevas exclusiones; puede acotarse al módulo si CI cubre el resto del gate |
| PostgreSQL | Nuevos tests remediación, cash_ledger_postgres, purchase_workspace_postgres y operating_expenses_postgres según locks/helpers; base/schema propios, URLs locales validadas, timeout y barreras |
| SQLite | Mismos invariantes del escritor central y reserva de escritura; no certificar carreras PG con SQLite |
| Gateway/offline | Sólo helpers o compatibilidad dual afectados: regresiones cash/outbox/reconcile existentes y autoridad de catálogo; cero nuevas escrituras EXP/PUR locales |
| Contratos | purchase_workspace_contract, operating_expenses_contract, esquemas de caja/reportes y respuestas 401/403/409/503; consumidor estricto junto al productor |
| Frontend | Prueba semántica de interacción afectada y `pnpm typecheck`; build apps afectadas antes de release o si rutas/contrato/empaquetado/dependencias cambian |
| E2E/QA | Workspace compras, gastos, caja/reportes/Excel y accesos Admin/POS con API/BD aisladas; context switch, errores, respuesta perdida, desktop/ancho reducido y teclado |
| Instalación/build | TC-345: paquete propio instalado, pip check, import/rutas/health y Docker real; locks y pnpm frozen, CI con runtime objetivo |
| CI | Suite completa aplicable del commit una vez; PG mandatory sin skip, jobs/frontend/dependency review/build relevantes efectivos |
| Revisión R3 | Un ciclo Terra/handoff + Sol independiente con contexto fresco; AppSec focal origen -> autoridad/destino, locks/compensación/redacción dentro de esa auditoría |

Comandos para ejecución focal (los módulos ya existen; preparar primero el entorno aislado indicado):

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
# Después de preparar el entorno y la base aislados de P0:
.\.venv-audcore\Scripts\python.exe -m pytest -p no:cacheprovider apps/api/tests/test_system_remediation.py -q
.\.venv-audcore\Scripts\python.exe -m pytest -p no:cacheprovider apps/api/tests/test_system_remediation_postgres.py -q
.\.venv-audcore\Scripts\python.exe -m pytest -p no:cacheprovider tests/contract/test_purchase_workspace_contract.py tests/contract/test_operating_expenses_contract.py -q
```

No grabar credenciales reales en comandos/evidencia. URLs de prueba se configuran en el entorno
aislado/servicio CI. No usar DATABASE_URL productiva ni modificar el Python global del usuario.

## 7. Migraciones, compatibilidad y datos históricos

No se presume migración: comenzar con locks, filtros y referencias existentes. Antes de P2:
probar que actor/clave/documento/caja/turno persistidos bastan para reautorizar/reconocer replay
conforme TC-328, incluidos documentos legacy. Si no bastan, revisar SDD/contratos y añadir migración
aditiva nueva con pruebas upgrade/downgrade/upgrade SQLite/PG y bloqueo con historia. Esa necesidad
no autoriza ejecutar una migración productiva ni reescribir las migraciones 0037/0076 congeladas.

Antes de publicar P4 confirmar JSON/DTO/Excel contra consumidores reales. Preservar llaves/tipos
de pesos y redondeo en frontera; componentes internos enteros/Decimal. Campos/enum nuevos son
aditivos únicamente si los consumidores lo admiten; en otro caso versionar el contrato afectado.
§51.8 ya especifica compatibilidad legacy de confirmación; no ampliarla ni usarla para eludir
el expected shift de los clientes nuevos. Leer datos históricos no permite normalizarlos por UPDATE.

Herramienta preparada: `python -m restaurant_os.system_diagnostics --organization-id <id>
--limit 100`, con URL explícita en `AUDCORE_DIAGNOSTIC_DATABASE_URL`, sin fallback a DATABASE_URL.
El CLI abre SQLite existente en mode=ro/query_only o snapshot PG READ ONLY/REPEATABLE READ;
exit 2 ante error no emite un reporte exitoso ni excepción/URL/SQL. No ejecutar producción sin
autorización separada. La preparación y verificación local no autorizan esa ejecución.

El diagnóstico **sólo lectura** identifica: confirmaciones con
recepciones/retiros duplicados, cash incoherente, stock negativo candidato a investigación,
reversas duplicadas/incoherentes, terms entre organizaciones, vínculos huérfanos y periodos con
compras cash cuya proyección requiere revisión. Mostrar
IDs/referencias opacas en evidencia acotada sin exportar payloads sensibles al chat.

Los resultados distinguen stock negativo candidato de causalidad confirmada, y periodos locales
candidatos a recalcular de reportes históricamente ejecutados. No existe historial verificable de
todas las ejecuciones de reporte: no presumir que una fecha fue publicada incorrectamente.
Reversas cash/inventario se comprueban por cardinalidad, referencias y magnitudes contra originales;
costo y cantidad de inventario conservan el quantum canónico de seis decimales del escritor.
Límites de documentos, reversas y evidencias producen coverage_partial explícito, nunca historia
sana acreditada. La salida omite folios, notas, importes, actores, payloads e IDs ajenos.

Clasificar cada discrepancia como defecto de lectura o dato transaccional ya materializado.
La corrección de lectura se aplica por proyección. Datos transaccionales requieren procedimiento
específico autorizado, evidencia física cuando proceda, compensaciones y validación de caja/stock;
no hay permiso para fabricar devoluciones, alterar saldos, borrar movimientos o reparar un cierre.
No marcar cortes históricamente revisados como revisados otra vez automáticamente.

## 8. Decisiones de ejecución y límites explícitos

| Decisión / gate previo | Regla que impide una implementación arbitraria |
| --- | --- |
| Locks reales de todos los escritores | P0 dibuja el orden incluyendo guards operativos, manual compensation, consumo y transferencias. P2/P3 sólo aceptan un orden sin inversión demostrado por TC-337; no añadir un lock aislado que cree deadlock |
| Replay legacy y evidencia faltante | Usar sólo hechos persistidos. Insuficiencia activa revisión/migración aditiva, no actor/turno inferidos ni éxito supuesto |
| Turno cruzado o sin arqueo | Mantener alcance vigente del turno y fecha de actividad explícitos; no inventar counted_cash/fondo de arrastre. Si el contrato no permite representarlos correctamente, cerrar la decisión focal en SDD40/BDD antes de liberar reportes afectados |
| Datos ya dañados | Diagnóstico sólo lectura; reparación posterior con autorización productiva y compensación específica. Código verde no demuestra historia sana |
| Locks de dependencias por plataforma | Runtime objetivo comprobado en CI/Docker, resolución directa/transitiva con hashes. No congelar ciegamente el entorno global ni actualizar paquetes sin prueba |
| Migración/ADR | Activarlos por cambio real de modelo/decisión crítica, sin documentos para declarar sin cambios |

Estas decisiones son tareas verificables de implementación; no autorizan nuevas reglas de negocio.
Si una decisión exige una política que no existe en PRD/SDD, se presenta su evidencia y la propuesta
concreta antes de cambiar runtime. El resto del paquete puede continuar dentro del contrato vigente.

### 8.1 Decisiones funcionales aprobadas; implementación y gates

El usuario aprobó ambas recomendaciones mediante «Adelante» el 2026-10-09. Se implementa saldo
por apertura de turnos y actividad separada (D-01), y contado/diferencia nulos hasta arqueo completo
equivalente (D-02). Son decisiones de §40/57.1, no permisos de publicación o despliegue.

| Decisión | Evidencia previa | Solución aprobada |
| --- | --- | --- |
| D-01 Población del saldo diario | Apertura en D y retiro en D+1: ledger 170000; daily separaba apertura y retiro, presentando 2000 y -300 pesos | Conciliar los turnos abiertos en D usando su ledger completo y snapshot de cierre inmutable cuando exista. Mostrar actividad por fecha de evento con población/etiqueta independiente; nunca sumar componentes de ambas poblaciones. Día local IANA con intervalo semiabierto UTC; consolidado incluye cada turno una vez por apertura. |
| D-02 Ausencia de arqueo | Sin cierre usaba apertura como contado; cierre operativo sin closing_cash_cents se volvía cero. El cierre operativo no contiene conteo físico; cortes por usuario tienen otra población | Estado PENDING/COUNTED/EMPTY con IDs de turnos contados y pendientes. Contado/diferencia nulos hasta existir conteo físico completo de la misma población; cero real permanece cero. Cierre operativo y cortes por usuario no acreditan conteo equivalente. Artefacto legacy FINAL válido requiere vínculo, estado CLOSED, instante de cierre y alcance coincidentes. |

Secuencia: actualizar la regla funcional activada en PRD/§40, fórmulas/poblaciones y
contrato de respuesta en SDD, SC-617 y TC-334/344, luego matriz. Si aparecen campos nullable o
secciones con población diferente, adaptar JSON/DTO, daily, consolidated, Admin/acceso POS y Excel
en el mismo paquete compatible; versionar si el contrato existente no admite el cambio.

Gate D-01: turno cruza medianoche, dos turnos de la misma caja, varias cajas, evento exactamente
en ambos límites, DST 23/25 horas y cierre inmutable. Cada saldo coincide con su ledger/snapshot;
actividad no se duplica al consolidar días, y no se reescriben positivos históricos.
Gate D-02: OPEN sin conteo, CLOSED operativo sin conteo, conteo físico cero real, conteo válido,
parcial por usuario y varias cajas con una pendiente. Diferencia sólo usa conteo equivalente real;
los lectores y Excel distinguen null de cero y no certifican una población incompleta.

Las pruebas de D-01/D-02 son criterios de aceptación del paquete, no nuevos comandos
de arqueo ni autorización para editar cierres o migrar datos productivos.

## 9. Evidencia R3, señales y revisión independiente

El cierre/handoff único incluye por cada afirmación: afirmación, evidencia, intento de refutación,
resultado y riesgo residual. No abrir una segunda auditoría para repetir las mismas conclusiones.

| Afirmación a demostrar | Contraejemplo exigido | Evidencia de cierre |
| --- | --- | --- |
| Egreso/saldo únicos | Documento + ledger + categorías, métodos no cash y compensaciones | TC-332/333/343/344; sumas/int/Decimal/IDs |
| Compra/cancelación seriales y atómicas | Dos claves, actor distinto, cierre/reapertura, fallo tras cada escritura | TC-327/328/337; PostgreSQL y huellas completas |
| Reversa no crea stock/valor ilegales | Partidas repetidas de costo cero/positivo, uno insuficiente, fracciones | TC-336; rechazo sin partials y oráculo agregado |
| Históricos y periodos íntegros | Confirmación/anulación en días distintos, borde local/UTC, draft | TC-334/335; snapshots idénticos y eventos únicos |
| Sin fuga o elevación de alcance | Sucursal inactiva, otra org, grant revocado, nombre imitador, error SQL | TC-338..342; respuesta/log/BD |
| Gastos conserva separación | Todos los medios/estados, fixture vacía y fixture histórica | TS-134 y TC-343; contenido no inventariable idéntico |
| Entorno y CI reales | Venv vacía, hash alterado, PG URL ausente/skip obligatorio | TC-345/346; build/lock/JUnit del commit |

Preguntas operativas y señales están en SDD57.6. El handoff enlaza eventos/movimientos/auditoría,
versiones del build y resultados de gate sin folios, notas libres, credenciales, claves crudas ni
PII en logs. La auditoría Sol R3 recibe contexto fresco, specs y diff final, prueba a prueba y
límites pendientes; su veredicto no sustituye CI, build ni autorización productiva.

## 10. Publicación, liberación y reversibilidad

Después de preparar el plan, el usuario invocó la skill RestaurantOS con `proceed` y autorizó
la implementación del paquete. Esa autorización mantiene separadas las operaciones productivas.
La evidencia siguiente corresponde a trabajo local en codex/aud-core-001 aún sin publicar.

Para una implementación autorizada: rama codex/aud-core-001 o worktree adecuado preservando trabajo
ajeno; commits por paquetes coherentes, PR con títulos/contratos/evidencia finales y CI del HEAD.
Commit/merge/push sólo dentro de autorización Git aplicable. Actualizar estados de evidencia en
matriz sólo cuando el incremento realmente pase; no usar un CI de otro commit como certificado.

Despliegue/configuración/migración/datos productivos conservan autorización explícita separada
según GOV-REL-001. Antes de esa etapa: backup/restauración aplicable, lectores compatibles, build
identificado, baseline de observación y diagnóstico histórico sólo lectura autorizado.

Canary R3 propuesto: una sucursal/caja/turno y cuentas autorizadas, durante operaciones reales de
importe controlado; observar una compra y gasto cash, un gasto no cash, efectos/saldos/estadísticas
y replay seguro. Cancelar sólo cuando exista devolución real y turno/política permitan compensar.
No generar compras/ventas ficticias productivas ni probar concurrencia con dinero real. Ampliar
sucursales únicamente con diferencias explicadas, evidencia de comportamiento y usuario autorizado.

Detener expansión ante duplicado, discrepancia monetaria, inventario ilegal, fuga de alcance,
incompatibilidad de lectores o pérdidas de auditoría. Contener nuevas escrituras afectadas con
procedimiento operativo validado; conservar lecturas e historia. No volver automáticamente a la
versión vulnerable ni borrar tablas/recibos. Preferir corrección hacia adelante; si hay schema
aditivo, reversión de aplicación compatible y downgrade sólo cuando no elimine historia.

## 11. Estado, evidencia anterior y criterio de cierre

Evidencia del turno de auditoría anterior: 127 pruebas focales aprobadas, una omitida por falta
de PostgreSQL de migración y tres comprobaciones frontend aprobadas; reproducciones aisladas
H01/H02/H03/H04/H06/H07/H08/H09/H10. H05 y atribución H11 tuvieron evidencia estática. Es baseline
fechado, no ejecución de TC-332..346 ni prueba de concurrencia PG, CI o despliegue de la solución.
Verificación de esta entrega documental: `python -m pytest tests/architecture/test_traceability.py
-q -p no:cacheprovider` obtuvo **9 passed, 0.45 s**; enlaces relativos resueltos sin faltantes e
inventario H01..H14/AC01..AC15 completo; `git diff --check` limpio. No acredita runtime, CI,
PostgreSQL ni comportamiento productivo de la solución.

- [x] Inventario H01..H15 y vínculos a contratos/criterios/pruebas diseñado.
- [x] PRD activado por reproducibilidad/CI y decisiones funcionales D-01/D-02; SDD, BDD, TDD y matriz actualizados proporcionalmente.
- [x] P0 entorno y RED conductual focal; PostgreSQL real disponible en bases de prueba exclusivas.
- [x] Correcciones locales y evidencia focal registradas abajo; auditoría Sol independiente del mismo ciclo realizada.
- [x] Diagnóstico histórico de sólo lectura preparado; su ejecución productiva permanece separada.
- [x] P1..P4 implementación y GREEN locales focales/PG/SQLite/contratos/consumidores.
- [ ] P5 equivalencia de instalación Linux e imágenes Docker reales; evidencia Windows registrada.
- [x] P6 integración/QA local y auditoría Sol independiente del ciclo.
- [ ] P6 CI efectivo del commit final y suites que configura.
- [ ] P7 Git/autorizaciones, liberación/canary y evidencia productiva si se autoriza.
- [ ] Diagnóstico de historia productiva y reparación compensatoria específica si hay discrepancias y autorización.

El paquete de código termina cuando AC01..AC16, gates activados y revisión independiente están
verdes sin hallazgos bloqueantes. La operación termina sólo tras validación productiva autorizada;
si existen datos dañados, su reparación y evidencia quedan pendientes hasta resolverlos por el
procedimiento autorizado. Distinguir esos cierres, sin presentar un plan o un push como sistema resuelto.

### Avance local 2026-10-09; no constituye cierre

- Ramas/archivos ajenos preservados; sin despliegue, migración productiva ni reparación de historia.
- Python 3.12.10 y PostgreSQL 16.15 aislados. H05 RED real: dos confirmaciones con claves distintas
  producen dos resultados confirmados; con igual clave fallan por duplicidad de efectos.
  El caso focal pasa después de bloquear/releer documento e identidad de clave.
- H01/H02/H06/H11: seis regresiones financieras RED, después seis GREEN. El reporte se basa en
  movimientos; los documentos aportan identidad/descripción y los eventos conservan historia.
- Auditoría independiente reprodujo ocho casos adicionales (auth/redacción y vínculos falsos):
  ocho RED, después ocho GREEN. Dos RED adicionales por compensaciones históricas duplicadas y
  clasificación de devolución EXP pasan en el módulo financiero actual: 12 casos GREEN.
- Roles combinados: un rol corporativo sin permiso ampliaba lectura de otra sucursal. Regresión
  RED y dos GREEN actuales: alcance restringido y autoridad corporativa real por grant persistido.
- Clave externa de 180 caracteres desbordaba VARCHAR de efectos en PG (RED). Derivación interna
  acotada pasa tanto cash como no cash. Predicados de estado y comprobación de rowcount agregados.
- PG: cuatro carreras confirm/cancel y doble cancel pasan; caja manual con FK frente al lock de
  sucursal pasa; consumo KDS ganador rechaza reversa sin parcialidad y KDS real espera el lock.
  No se introduce una política nueva que prohíba negativos de consumo posterior.
- Dos instalaciones vacías desde dev-windows-py312.lock producen el mismo inventario de 76
  distribuciones; pip check y health (3 casos por instalación) pasan. Hash alterado y manifest
  desalineado se rechazan. Descarga de wheels Linux/API bajo hashes pasa; no equivale a ejecutar
  Linux ni Docker. CI añade build real de ambos Dockerfiles y verifica cada caso PG contra JUnit.
- 34 regresiones focales de perfiles/compras/trazabilidad/runtime pasan. Mypy completo: 63
  archivos sin errores. Builds Admin/POS pasan con advertencia de tamaño de bundle ya existente.
- Recorrido navegador Admin/acceso POS: captura de tres partidas, contextual, respuesta perdida
  de creación, misma clave/body, confirmación y compensación pasan. Recuperación de confirmación
  perdida antes de llegar a API + cierre/reapertura de turno reprodujo bloqueo UI (RED) y ahora
  pasa: no sustituye intento hasta recibir rechazo definitivo, luego permite nueva revisión.
- Originales y lectores: cuatro RED de identidad cash/receipt y cuatro RED de hijos ajenos;
  validación completa/cardinalidad y lectura cerrada pasan negativos ampliados. El módulo final
  `test_system_remediation.py` obtuvo **85 passed, 245.32 s**, sin omisiones. Incluye ocho casos
  de fracciones/presentaciones/valor residual, diez fallos después de escrituras, seis grants
  granulares y cuatro replays con actor/grant/inactiva/cierre-reapertura.
- Conjunto de Compras/Gastos/caja/remediación: **173 passed, 728.55 s** en snapshot anterior a
  los últimos negativos de lector/replay; éstos fueron cubiertos por el módulo final de 85.
  No sumar estos conteos: comparten casos.
- Cuatro suites PostgreSQL obligatorias: **28 passed, 431.65 s**, collection y JUnit verificados
  por caso (cash 4, compras 8, EXP 5, remediación 11). Después de validar originales se repitieron
  cash/remediación: **15 passed, 246.41 s**. Un gate PG nuevo de manual compensation contra cancel
  pasa de entrada (**1 passed, 24.91 s**): unicidad/rollback refutan el duplicado; no se inventó RED
  ni cambio runtime. Remediación PG tiene ahora 12 casos; ese caso nuevo consta por separado,
  no se presenta el JUnit previo como ejecución de los 29 casos actuales.
- Reportes, contratos JSON y trazabilidad: **39 passed, 49.44 s**. Daily/consolidado/XLSX preservan
  1700 para compra 300/apertura 2000 del mismo alcance. PCO-007, regresiones monetarias y contrato
  EXP: **19 passed, 37.48 s**; fixture monetario conserva oráculos 19.99 y 1.005 -> 1.01, ahora con
  retiro/turno/confirmed_at reales en vez de sólo documento cash sin ledger.
- Cash sync/grants: **15 passed, 23.90 s**; gateway cash outbox/runtime: **10 passed, 7.07 s**.
  Runtime/trazabilidad: **20 passed, 35.51 s**. Sin nuevas escrituras offline EXP/PUR.
- `pnpm test:frontend-semantic` termina con exit 0; `pnpm typecheck` pasa los siete proyectos.
  Build Admin final pasa tras manejo de foco. E2E actual termina con exit 0 en ambas entradas:
  pérdida aplicada + recarga conserva clave/body; legacy incompleto no permite enviar ni muestra
  un turno actual como revisado; Tab permanece en revisión, foco se restaura cuando procede y
  diálogo/editor caben a 390 px. Capturas revisadas; tablas conservan scroll interno.
- Ruff de archivos afectados y mypy de 63 fuentes pasan; integridad documental focal pasa y
  `git diff --check` limpio. Auditoría Sol de este mismo ciclo: ocho casos independientes verdes,
  P2 lector cerrado, sin bloqueantes de código reproducibles en el alcance revisado. Su veredicto
  no aprueba el paquete por las decisiones y evidencia todavía ausentes.
- Diagnóstico histórico de §7/SDD57.7 preparado y probado sólo con fixtures aisladas: dos RED
  iniciales válidos de cash duplicado/incoherente; fixture de receipt corregida para duplicar
  PURCHASE_RECEIPT real. EXP huérfano y confirmación sin evento tuvieron RED/GREEN propios.
  Sol reprodujo en PG omisión de fuentes CANCELLATION, reversas duplicadas con padre válido y
  reversas ajenas entrantes a originales propios; root añadió regresiones RED y corrigió cada
  lector. Falso positivo de costo 0.145 fue corregido usando _money/_quantity canónicos de seis
  decimales, sin modificar fórmulas del escritor ni datos reales.
  Ejecución final `test_system_diagnostics.py` + trazabilidad: **24 passed, 124.63 s** (15 casos
  de diagnóstico y 9 documentales), sin omisiones; JUnit `diagnostic-final.xml` en entorno
  temporal aislado. Tres casos PG de snapshot/orphans reales: **3 passed, 42.59 s**; el caso
  nuevo de conjuntos duplicados y scope entrante final: **1 passed, 39.60 s** por separado.
  El módulo PG tiene ahora 16 casos, no se presenta el JUnit anterior como ejecución completa
  actual. Recolección actual de las cuatro suites obligatorias: 33 casos, sin confundir colección
  con ejecución. Ruff/mypy focales verdes y `git diff --check` limpio. Revalidación Sol final en PG:
  historia legítima sin hallazgos, tres contraejemplos ahora detectados, sin IDs ajenos y huella
  completa idéntica; sin bloqueante reproducible del incremento en su alcance. No diagnosticar
  producción, atribuir causas ni reparar historia automáticamente.
- Gate Linux/Docker revalidado en este host: docker no está disponible, su ruta estándar no
  existe y `wsl --list --verbose` devuelve que el subsistema Linux no está instalado. No se
  instalaron componentes del sistema, habilitaron virtualización ni configuraron servicios para
  simular el gate. Se conserva la descarga Linux verificada como evidencia distinta del runtime.
- **Pendientes de cierre tras D-01/D-02:** instalación Linux e imágenes Docker reales, CI del
  commit y publicación autorizada. No hubo commit, push,
  despliegue, migración productiva, canary ni diagnóstico/reparación de datos productivos.

### Incremento D-01/D-02 aprobado y verificado localmente, 2026-10-09

Contratos primero: PRD FR-225/226, SDD §40/57.1/57.4, SC-617/623, TC-334/340/344 y matriz.
API de lectura/exportación v2, schemas/DTO compartidos y consumidores Admin/POS/Excel actualizados
juntos. Dinero HTTP es string decimal de dos posiciones; dominio usa Decimal/int y presentación
BigInt sin perder centavos. Lectores v1 autorizados reciben 409 reconciliation_contract_upgrade_required;
la revisión gerencial conserva su endpoint v1. Se requiere liberar API y consumidores compatibles
juntos. No se agregó comando de arqueo ni se modificó ningún cierre histórico.

| Afirmación R3 | Evidencia e intento de refutación | Resultado y riesgo residual |
| --- | --- | --- |
| Saldo y actividad representan poblaciones explícitas | RED con turno cruzado y expected 2000 frente a 1700; bordes/DST, múltiples turnos/cajas, artefactos congelados y bloqueo de escritor en PG | GREEN focal; saldo usa ledger completo/artefacto equivalente, actividad selecciona eventos propios. FOR SHARE protege la lectura y puede aumentar espera de escritores en reportes mensuales/Excel; no se reprodujo deadlock. |
| Ausencia de arqueo no equivale a cero | RED por apertura usada como contado y cero real ignorado; OPEN, cierre operativo, cortes parciales, población mixta y vacía | GREEN de dominio/HTTP/render; COUNTED exige población completa equivalente. Excel mensual esperado 3900, contado/diferencia vacíos y estado Pendiente de arqueo verificados en archivo descargado real. |
| Ningún vínculo ajeno entra en proyección | Sol reprodujo concepto/turno ajenos; regresiones de pedido ajeno y pedido propio con distintos turnos de captura/cobro | Rechazo de vínculos ajenos antes de sumar/describir; captura/cobro distintos propios admitidos. Validación batched de padres, estado y tiempos, errores redactados, sin reparar registros. |
| Dinero exacto y respuesta vigente llegan al consumidor | HTTP real refutó DTO numérico; parser estricto/string y BigInt corregidos; prueba independiente con valores mayores a 2^53, -0.01 y acarreo de 31 dígitos; revisión A termina durante carga de fecha B | GREEN focal y E2E real: B conserva su respuesta/fecha, revisión no fabrica conteo, descarga lleva Bearer sin token en URL. Fixture sintética restablece revisión para repetir el recorrido. |

Evidencia de este incremento, sin sumar conjuntos que comparten casos:

- `python -m pytest apps/api/tests/test_reconciliation_populations.py
  apps/api/tests/test_system_remediation_reports.py apps/api/tests/test_branch_reconciliation_reports.py
  apps/api/tests/test_audit_money_public_regressions.py tests/architecture/test_traceability.py
  -q -p no:cacheprovider`: **67 passed, 65.76 s**, una advertencia preexistente de Starlette.
- Módulo PostgreSQL de remediación: **18 passed, 191.33 s** en snapshot D-01/D-02 inicial.
  Después de las guardas: **4 passed, 16 deselected, 48.50 s** para conciliación/locks/vínculos
  y **2 passed, 20 deselected, 26.50 s** para pedidos. El módulo actual contiene 22 casos;
  no se atribuye una ejecución completa de esos 22 al JUnit inicial.
- `node tests/frontend/test_reconciliation_reports.mjs` exit 0; `pnpm typecheck` exit 0 en siete
  proyectos; builds Admin/POS finales exit 0, con advertencia de bundle grande ya existente.
  Ruff focal y mypy de reconciliation_reports/api/main con follow-imports=silent verdes.
- `node tests/browser/test_reconciliation_e2e.mjs` exit 0 sobre API y builds reales en base
  exclusivamente sintética: pendiente/cero/múltiples cajas/actividad/Excel autenticado/carrera
  revisión-fecha en desktop y 390 px. Repetición sobre el mismo fixture exit 0 después de reset
  sintético explícito. Capturas `output/playwright/reconciliation-{admin,pos}-390.png` revisadas;
  workbook `output/playwright/reconciliation-month.xlsx` inspeccionado con openpyxl.
- Sol independiente del mismo ciclo: pedidos PG **2 passed**, wire HTTP **2 passed**, semántica
  frontend y refutaciones monetarias verdes; sin bloqueante reproducible restante en el incremento
  focal. Su veredicto asesor no certifica E2E de root, Linux, Docker, CI ni producción.
- Última refutación local: consolidado sin sucursales devolvía actividad incompleta y la guarda
  POS de revisión no reflejaba alternativas de permisos del backend. Dos RED propios; nueve
  totales cero con EMPTY y guarda audit.read/branch.admin.access/admin.manage corregidos, sin
  añadir grants. Módulo de poblaciones final **31 passed, 42.07 s**, semántica frontend exit 0,
  rebuild POS/typecheck exit 0 y mypy focal **3 fuentes sin errores** después de estas correcciones.
  Sol refutó resultado real SQLite → wire → parser, omitiendo cada clave, y evaluó 32 combinaciones
  de permisos sobre la guarda real: sin bloqueantes focales restantes.
  E2E repetido con API reiniciada y último bundle POS: exit 0 en el mismo recorrido desktop/390 px.
- Recolección final de las cuatro suites PG obligatorias: **39 casos, 8.71 s** (4 cash,
  8 compras, 5 EXP, 22 remediación). Es colección, no una ejecución completa final ni CI.
  Integridad documental final **9 passed, 0.55 s** y `git diff --check` limpio.

Servicios PostgreSQL y API locales de prueba detenidos tras la verificación; fixtures y artefactos
de evidencia conservados. No queda un servicio creado por este incremento ejecutándose.

Los estados pendientes de matriz conservan los gates externos sin acreditar cierre total. Este
incremento concluye la implementación/verificación local de las decisiones aprobadas; el paquete
integral todavía requiere la evidencia Linux/Docker/CI y los pasos autorizados de publicación.

## 12. Publicación Git autorizada

El usuario solicitó «Haz commit, merge y push» el 2026-10-09. Se publica AUD-CORE-001 completo
en su rama, con PR hacia main para ejecutar el CI configurado únicamente en pull_request o
workflow_dispatch. Integración y push a main pertenecen a esta autorización. El cierre del chat
registra hashes, PR, estado CI y sincronización remota observados, sin anticipar resultados.
Despliegue, migraciones, configuración y diagnóstico/reparación de datos productivos conservan
autorización explícita separada conforme GOV-REL-001.
