# TDD — INV-VIEW-001

Estado: pruebas dirigidas implementadas y ejecutadas localmente; resultados y límites en plan
INV-VIEW-2026-10-19. RED observado antes del código: capacidades ausentes en sesión y módulo de
estado frontend inexistente. CI y release no acreditados por estos resultados locales.
Autoridad: PRD-FR-279/280, SDD §68, BDD-FEAT-151/152.

## TDD-TS-151 Contrato y lectura de inventario administrativo

Pruebas: `apps/api/tests/test_inventory_overview.py` y
`apps/api/tests/test_inventory_overview_postgres.py`. La segunda está conectada a base/env propia
y al verificador obligatorio de ejecución PG en CI; no contar skips como aprobación.

### TDD-TC-422 Alcance y autorización desde el servidor

BDD-SC-723, BDD-SC-725. Fixtures reproducibles de dos organizaciones, Centro/Norte activas,
sucursal inactiva, actor corporativo, lector sólo Centro y actor con rol llamado Administrador
sin autoridad organizacional. `/auth/session` proyecta capacidades de consulta sin conceder permisos.
Probar organization/branch, IDs ajenos/inactivos, acceso revocado, UUID inválido, scope omitido,
combinación ambigua y falta de inventario.read. Verificar 401/403/422 y ausencia de filas/conteos
ajenos en cuerpo y error. Un permiso inventory.read sólo local junto a otro rol organizacional
no concede lectura global. Guardas de rutas/hub no habilitan acciones por nombre de rol.

### TDD-TC-423 Pares cero y equivalencia aritmética

BDD-SC-723, BDD-SC-726, BDD-SC-727. Comparar agregado contra ledger independiente con Decimal;
saldo inicial 10, reserva -3 -> física 10/reserva 3/disponible 7; release +3 y consumo -3 ->
7/0/7. Incluir cancelación/liberación, compensación, negativos, seis decimales, reserva
incoherente sin clamp, artículos locales/globales y sin movimientos. Verificar todos los tipos
inventariables vigentes, pertenencia almacén/sucursal y exclusión de catálogo inactivo.
Comparar física con la referencia de umbrales y disponible con la referencia legacy; no cambiar
las referencias para obtener verde. Un insumo local de Centro no genera cero ficticio en Norte.

### TDD-TC-424 Snapshot PostgreSQL y ausencia de interferencia operativa

BDD-SC-726, BDD-SC-729. Interceptor de la lectura exitosa detecta DML/DDL y adquisición de locks
advisory operativos; auditoría existente de negativas de autorización se prueba por separado.
Carrera de reserva/consumo y lectura con barreras deterministas: filas/conteos de una respuesta
comparten snapshot, no mezclan estados anterior/posterior. Probar consultas paralelas sin bloquear
una escritura de inventario por locks agregados. SQLite valida aritmética/alcance, no certifica
aislamiento PostgreSQL. Capturar SQL/EXPLAIN y cantidad de sentencias sin N+1 en dataset de 7
sucursales y 1000 artículos globales (fixture de carga, no restricción del producto).
Definir timeout/presupuesto de latencia con baseline antes de declarar gate operativo verde.

### TDD-TC-425 Filtros paginación y fallos explícitos

BDD-SC-727, BDD-SC-729. Nombre/SKU, q vacío/largo, caracteres especiales como datos, unidad,
disponible positivo/cero/negativo sin redondeo previo, límites de página y orden con empates.
Los conteos son de filas del conjunto filtrado completo. Sucursal sin almacén válido o fallo SQL
no devuelve 200 con conjunto parcial ni ceros; errores no exponen SQL. Verificar Cache-Control
no-store y as_of de servidor distinto de last_movement_at nullable. Entre páginas hay snapshots
nuevos explícitos; no prometer sesión de reporte congelada ni totales de cantidades heterogéneas.

## TDD-TS-152 Contexto y experiencia administrativa de inventario

Pruebas: `tests/frontend/test_inventory_query_scope.mjs` y
`tests/browser/test_inventory_visibility.mjs`, más extensión focal de
`tests/frontend/test_admin_catalog_tools.mjs` y pruebas API de umbrales existentes.
El navegador ejecuta componentes y API real con SQLite aislada; usa intercepción sólo para
demoras/409/503/revocación. Captura payload/destino de edición, conserva valor legacy y verifica
cuenta local real, foco, estado offline, filtros y descarte de respuesta tardía.
Los tests de comportamiento deben ejecutar componentes/cliente; búsquedas estáticas no bastan
para demostrar permisos, aislamiento de caché ni funcionamiento de filtros.

### TDD-TC-426 Consulta independiente y respuestas fuera de orden

BDD-SC-724, BDD-SC-728. Simular Centro tardío/Norte temprano, revocación y cambio de usuario;
comprobar aislamiento de caché/DOM y descarte por generación/aborto. Capturar requests: filtrar
no llama branch-selections ni branch-context-reissues. Capturar antes/después active_branch,
workspace, caja, turno y borrador POS. Variantes de ambos flags encendidos y apagados, UI nueva
contra API sin proyección (mensaje de incompatibilidad, sin consulta global inferida).

### TDD-TC-427 Umbrales con destino congelado y permisos

BDD-SC-730, BDD-SC-731, BDD-SC-734. Abrir desde Norte, cambiar filtro, guardar/retirar sólo contra
Norte y versión congelada; verificar ausencia de escritura global. 403 por revocación y 409 por
versión no sobrescriben. Stock, reservas, costos, historia y Centro quedan iguales; auditoría
conserva actor/destino. Probar doble click y recuperación del resultado usando semántica vigente
de versión, sin inventar replay ni fabricar una nueva mutación. Usuarios de lectura no reciben
acciones de configuración por entrar a Existencias.

### TDD-TC-428 Precisión captura y fechas

BDD-SC-732, BDD-SC-733. 12, 12.5, 12.50 válidos con presentación de dos decimales; 12.345 nuevo
bloquea envío sin redondeo silencioso. Cero, negativos y máximo menor que mínimo según contrato.
Umbral legacy 12.345678: guardar sin tocarlo o cambiar sólo el otro campo conserva ese valor
exacto. Mostrar cantidades 0.004000 como 0.00 sin convertirlo en cero para el filtro.
Zonas America/Mazatlan y otra sucursal con zona distinta, límites de día, DST cuando aplique;
global UTC explícito, detalle local etiquetado. Timestamp completo sigue disponible de forma accesible.

### TDD-TC-429 Recorrido y QA visual focal

BDD-SC-723, BDD-SC-727, BDD-SC-729, BDD-SC-733. Navegador contra API local aislada con fixture real:
Admin abre global, busca/filtra Norte, pagina, abre umbrales, valida error y vuelve al POS sin
modificar contexto. Estados carga/vacío/error/401/403/desconexión, sin convertir errores en ceros.
390/1024/1440 px, teclado, foco modal de ida/vuelta, labels, unidad y sucursal visibles,
desbordamiento limitado a tabla, controles compartidos y fechas legibles. Capturas revisadas
visualmente; imagen guardada por sí sola no certifica QA.

## Gates de implementación y límites

Backend: casos de TDD-TS-151, regresiones focales de stock/umbrales/RBAC, Ruff y mypy afectados.
Frontend: TDD-TS-152, pruebas semánticas afectadas, typecheck Admin/api-client y build por ruta
nueva. PostgreSQL requerido por agregado SQL/snapshot; SQLite verifica compatibilidad de lectura,
sin activar gateway/offline completo por una pantalla Admin online. E2E y QA visual de TC429.
CI ejecuta suite completa aplicable una vez; si no cubre una suite, agregar su gate o correrla
focalmente y declarar el límite. Auditoría R3 independiente con contexto fresco antes de release.

La movilidad POS se valida con PRD-FR-267, BDD-SC-635..639/645/700 y TDD-TS-138/146 existentes:
rollout apagado, selección autorizada, bloqueos, respuesta incierta, reemisión, concesiones y
carreras PostgreSQL. No se acredita ni habilita por aprobar las suites nuevas de inventario.
