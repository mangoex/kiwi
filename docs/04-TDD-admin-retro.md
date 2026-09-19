# TDD — Administración retro y hallazgos del sistema de referencia

## TDD-TS-112 Composición y operación de combos fijos

Pruebas dirigidas de administración, contrato HTTP y dominio de composición; integración de
aceptación, estaciones, reservas, preparación, edición y cancelaciones con snapshots reales.
La cobertura debe atravesar Python y persistencia; un seed llamado Combo no acredita el flujo.

Las suites focales son `apps/api/tests/test_combo_compositions.py`,
`apps/api/tests/test_combo_operational_channels.py`, `apps/api/tests/test_combo_migration.py`
y `apps/api/tests/test_combo_postgres.py`. La suite PostgreSQL exige `COMBOS_TEST_POSTGRES_URL` con host
localhost/127.0.0.1, nombre `combo_test*` y sin parámetros que puedan redirigir la conexión.
CI provisiona `combo_test_ci` separado de la base de catálogo, para que los resets de estas
pruebas no compartan datos con otras suites. Un test omitido por falta de URL no acredita el gate.

## TDD-TC-246 Versionado y autorización de composiciones

Probar scope corporativo/local, componentes inválidos/ajenos/anidados, cantidades no finitas
o fraccionarias de unidades de producto (sin restringir fracciones de insumos en recetas),
revisión obsoleta, idempotencia y writers concurrentes. Afirmar ausencia de escrituras parciales.
Migración/reversión conserva datos previos y rechaza destruir evidencia de pedidos existentes.

## TDD-TC-247 Precio, consumo y estaciones de un combo

Dos unidades de un combo de cocina y bebidas conservan precio propio exacto, cantidades de
recetas efectivas y una sola reserva por consumo. Reintento no duplica. Preparar ambas estaciones
es necesario para empaque. Cambiar luego la composición/receta no cambia el pedido congelado.
Ejecutar edición y cancelación antes/después de producción, comprobando movimientos y
compensaciones, sin emplear cantidades calculadas en JavaScript como autoridad.

## TDD-TC-248 Paridad local, sincronización y administración de combos

En ADMIN-RETRO-001 probar persistencia SQLite/PostgreSQL y replay de comandos online,
verificando snapshots y tareas sin duplicados. El transporte y replay de eventos de pedidos
offline (BDD-SC-501) quedan pendientes para un incremento posterior, acordado con el usuario. Recorrido Admin → API → persistencia para configurar
componentes, revisar y guardar nueva versión, rechazar conflicto conservando borrador y recargar
la composición vigente. La interfaz permanece retro y accesible en los anchos afectados.
La revisión de versión vigente conserva el borrador y muestra el contenido servidor; comprobar
que no reintenta automáticamente y que un fallo de esa lectura no habilita sobrescritura.

## TDD-TS-110 Contratos de catálogo administrativo

Suite focal `apps/api/tests/test_admin_catalog.py` con HTTP y servicios reales en base aislada:
autenticación, scope corporativo/sucursal, campos extra, decimales no finitos, fronteras y
versiones esperadas. Comparar stock con proyección canónica. Verificar que vistas previas y
configuraciones no generan movimiento, precio ni cambio en pedidos.

## TDD-TC-243 Prioridades y umbrales independientes

Guardar órdenes distintos, modificar uno y comprobar conservación del otro; rechazar
categorías duplicadas/ajenas/omitidas. Configurar umbrales para dos sucursales, leer por scope,
probar cantidades por debajo, iguales y por encima, retirar configuración y comparar ledger
y costo antes/después. Una escritura concurrente con revisión vieja debe fallar completa.

## TDD-TC-244 Recetas masivas y consulta inversa

Preview no escribe; apply versiona todos los destinos; modificación entre preview/apply,
fallo inyectado en segundo destino y reintento prueban ausencia de aplicación parcial.
Replay mismo actor/payload conserva IDs; actor/payload distintos o permiso retirado fallan.
Dos writers concurrentes sobre un destino producen un ganador, sin sobreescritura silenciosa.
Consulta inversa excluye receta central cuando una local efectiva ya no usa el insumo, así
como recetas de otras organizaciones, versiones retiradas y costos no autorizados.

## TDD-TS-111 Persistencia y flujos integrados ADMIN-RETRO-001

`apps/api/tests/test_admin_catalog_postgres.py`: PostgreSQL local aislado con variable
`ADMINRETRO_TEST_POSTGRES_URL`, host localhost/127.0.0.1 y nombre `adminretro_test*`; rechazar
otros destinos antes de cualquier reset. Pruebas de migración desde head previo, downgrade
que preserve recetas históricas, upgrade repetido y concurrencia/rollback del comando masivo.
SQLite verifica la misma semántica transaccional y serialización sin depender de FOR UPDATE.

## TDD-TC-245 Recorridos y reversibilidad

E2E local de UI → API → persistencia para prioridades/impresión, umbrales, usos y lote revisado;
recargar y comprobar resultado persistido, error visible y conservación del borrador ante
rechazo. El UI sólo envía cantidades exactas, no calcula stock, merma ni costo con Number.
Upgrade/downgrade se ejecutan sólo en bases sintéticas y conservan datos canónicos previos.

## TDD-TS-109 Presentación administrativa aislada

Comprobar semántica de navegación y tema acotado a Admin, carga de formularios, estados y
diálogos. Typecheck estricto y build de Admin; no relajar pruebas previas ni usar únicamente
presencia de CSS como evidencia de presentación. La QA en navegador usa un fixture local
sintético y capturas de login, catálogo, detalle/diálogo, carga, vacío y error, en los anchos
afectados 390, 768 y 1440 px. Comprobar foco por teclado, ausencia de desborde de página,
contraste y neutralidad de colores calculados; las fotos de producto son contenido.

El job frontend de CI ejecuta `tests/browser/test_admin_retro.mjs` contra el build servido por
Vite preview, con Playwright 1.63.0 instalado en un directorio temporal aislado. Sus respuestas
API simuladas verifican presentación y accesibilidad; no sustituyen el recorrido con API y
persistencia reales de TDD-TC-245. Las variables ADMINRETRO_BASE_URL y
ADMINRETRO_PLAYWRIGHT_IMPORT permiten ejecutar el mismo script localmente sin rutas personales
en el código de pruebas.

El mismo job también crea una base SQLite sintética nueva con
`tests/e2e/admin_retro_fixture.py`, sirve el build desde una API local en el puerto 8002 y
ejecuta `tests/browser/test_admin_retro_e2e.mjs`. La cuenta QA obtiene sus permisos mediante
roles y autoridad corporativa persistidos. El fixture rechaza sobreescritura de archivos y
el runner obtiene su configuración de `ADMINRETRO_E2E_MANIFEST`; no usa datos productivos.

## TDD-TC-242 Recorrido visual y funcional administrativo

Abrir Admin con usuario autorizado, seleccionar sucursal y recorrer Productos, Insumos,
Presentaciones, Proveedores, Recetas y Almacenes. Abrir y cerrar un diálogo, comprobar que los
controles siguen accesibles por teclado y conservar la sucursal al navegar. Forzar un error y
un resultado vacío sin simular éxito. Comparar estilos de POS/KDS/mobile para verificar aislamiento.
