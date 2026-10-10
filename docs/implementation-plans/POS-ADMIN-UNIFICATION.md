# Administración desde el POS — plan de implementación

Estado: implementado y verificado localmente; CI/PostgreSQL pendientes. Fecha: 2026-10-07.
Base revisada: `e5e94cc38950818602596f3f11b89b5c37c38c4b`.

> **Contrato supersedido parcialmente el 2026-10-10:** BRANCH-SCOPE-001/SDD §58 conserva esta
> unificación de pantallas, pero reemplaza el cambio mediante `/auth/session?branch_id=...` por
> `POST /auth/branch-selections`, workspace durable y `GET /auth/session` sólo de hidratación. El
> texto siguiente documenta el baseline implementado, no la transición futura autorizada.

## Decisión y resultado esperado

Usar las pantallas existentes de `admin-web` como implementación única de las funciones
administrativas. El menú Administración del POS será un acceso a esas pantallas, filtrado por
las capacidades de la cuenta. No reconstruir Producción, Mermas, Traspasos, Compras o Conteos
dentro del POS, ni copiar sus componentes para mantener dos implementaciones.

Al entrar desde caja, la persona conserva su identidad y la sucursal seleccionada. Sólo ve las
funciones y acciones que ya permite su cuenta; puede regresar a caja sin perder la captura.
Abrir el administrador no concede permisos corporativos a un usuario de sucursal.

La revisión inicial encontró que Admin usaba datos locales/nombres de rol para parte de su
navegación y selección de sucursal. La implementación alinea ese contexto mediante `/auth/session`
antes de montar las rutas administrativas alcanzables desde el POS.

Plan documental inicial: R0. Implementación: R3 por autorización, alcance de sucursal y acceso
a operaciones de caja/inventario. Sigue el proceso proporcional de `AGENTS.md` y el skill
`restaurantos-development`; requiere auditoría independiente del cambio antes de publicación.

## Alcance acotado

- Navegación POS → Admin → POS y conservación de contexto/captura.
- Sesión canónica, sucursal, menú, rutas y acciones de los módulos administrativos alcanzables.
- Reutilización de páginas, editores y comandos existentes del administrador.
- Retiro del uso de las pantallas administrativas duplicadas del POS una vez validado el reemplazo.
- Corrección focal de los rechazos de autorización de consultas de Mermas/Traspasos que producen 500.

Sin cambios a dependencias, cálculos, estados de negocio, reglas de inventario, dinero histórico,
roles concedidos, catálogo existente ni contrato de operación offline. No rehacer el administrador.
No se prevé migración para el recorrido productivo de mismo origen; cualquier necesidad posterior
de persistencia debe justificarse antes de ampliar el alcance.

## Destinos

| Acceso del POS | Pantalla canónica |
| --- | --- |
| Productos y recetas | `/admin/products`, con sus herramientas de receta actuales |
| Comentarios del pedido | `/admin/variations` |
| Ingredientes adicionales | `/admin/ingredient-extras` |
| Inventario | `/admin/inventory`, filtrando las herramientas internas permitidas |
| Proveedores | `/admin/suppliers`; presentaciones mediante `/admin/purchase-presentations` |
| Compras | `/admin/purchases` |
| Producción | `/admin/production` |
| Mermas | `/admin/inventory/waste` |
| Traspasos | `/admin/inventory/transfers` |
| Conteos físicos administrativos | `/admin/inventory/counts` |
| Checador | Conservar el reporte POS existente; no tiene pantalla administrativa equivalente |
| Monitor de ventas y reportes históricos | Conservar los módulos POS que el Overview administrativo ya reutiliza |

La captura operativa de conteo en caja continúa en su ruta POS; no se confunde con aprobar/cerrar
conteos. Las configuraciones locales de disponibilidad no se convierten en modificaciones del
catálogo central: conservar sus datos y comandos existentes, y trasladar sus controles autorizados
a una sección de disponibilidad por sucursal en las pantallas administrativas correspondientes.
Esa sección reutiliza los endpoints actuales con `branch_id` explícito; no reconstruye el catálogo.

## Secuencia de implementación

### 1. Contrato y pruebas de regresión

- Actualizar los artefactos activados en orden PRD → SDD/ADR → BDD → TDD → matriz. BA-003 hoy
  prescribe rutas locales y separación de pantallas; el nuevo contrato sustituye esa decisión.
- Construir una matriz única módulo → destino → capacidades de consulta/acción → alcance a partir
  de los contratos actuales del servidor. Considerar compatibilidad de permisos existente sin
  inventar reglas distintas por pantalla.
- Crear pruebas dirigidas que fallen por las causas ya reproducidas: cuenta de consulta con botones
  de escritura, tarjeta/ruta/API incoherentes, sucursal seleccionada distinta del destino y 500 al
  rechazar permiso. Conservar el caso de cajero sin acceso administrativo.

### 2. Contexto canónico del administrador

- Baseline 2026-10-07: revalidar mediante `/auth/session?branch_id=...`. Este mecanismo queda
  supersedido por BRANCH-SCOPE-001: la implementación siguiente usa `POST /auth/branch-selections`,
  reemisión de workspace y GET sólo para hidratación.
- Usar esa sesión para las capacidades de navegación y las rutas/acciones alcanzables. No usar
  nombres como “Supervisor” ni valores editables de localStorage como autorización.
- Mantener sucursal fija para alcance de sucursal. Permitir cambiarla únicamente dentro de
  `allowed_branch_ids` y revalidar antes de cargar datos o habilitar comandos.
- Evitar solicitudes sin contexto confirmado, respuestas de la cuenta/sucursal anterior y fallback
  silencioso a la primera sucursal. Mantener preferencias de sucursal sólo después de validarlas.
- Enviar el `branch_id` validado en consultas y mutaciones dependientes de sucursal. Corregir además
  los tres clientes actuales de disponibilidad mientras sigan siendo alcanzables, para que la
  transición no deje el defecto activo.

### 3. Permisos de extremo a extremo

- Reutilizar la matriz de capacidades en el acceso POS, sidebar/hubs administrativos y guardas de
  las rutas alcanzables. Ocultar opciones no permitidas; no mostrarlas como “Restringido”.
- Separar lectura y acción. En Compras, una cuenta de consulta no ve crear/confirmar/cancelar;
  tampoco puede ejecutar esos comandos mediante acceso directo. Aplicar la misma separación a
  acciones de catálogo, producción, mermas, traspasos y conteos según sus permisos actuales.
- Mantener como autoridad final las validaciones del backend. No resolver discrepancias ampliando
  permisos, asignando roles o debilitando guardas.
- Envolver también la autorización de GET Mermas/Traspasos en el manejo canónico de errores, para
  responder 403 en vez de 500. Verificar que los datos no se consultan ni se exponen tras el rechazo.

### 4. Navegación y regreso a caja

- Mantener Administración del POS como lanzador: las tarjetas administrativas abren los destinos
  existentes, sin formularios ni handlers de negocio propios. Los módulos operativos POS conservan
  sus destinos actuales.
- En producción de mismo origen, reutilizar la sesión autenticada y revalidar contexto en Admin.
  No incluir tokens en URL, hash o query. Los destinos y regreso salen de una lista interna;
  no aceptar URLs arbitrarias ni redirecciones externas.
- Añadir “Volver a caja” conservando usuario, sucursal y captura protegida. Usar las guardas y
  persistencia de captura existentes para evitar perder un pedido o una operación pendiente.
- El handoff actual sólo tiene destino `pos`; no asumir que funciona al revés. Para desarrollo con
  distintos puertos, comprobar el recorrido con proxy de mismo origen. Si el despliegue realmente
  usa orígenes separados, especificar antes un intercambio de código de un solo uso y expiración,
  reutilizando el patrón actual sin copiar tokens; ese caso activa una decisión técnica adicional.
- Sin conexión, no simular nuevas operaciones administrativas offline: mantener el contrato vigente
  y un estado explícito de falta de conexión sin perder la captura POS.

### 5. Consolidar y retirar duplicados

- Reutilizar las páginas existentes de Admin y sus editores compartidos. Incorporar únicamente los
  controles locales de disponibilidad necesarios para no perder esa capacidad vigente.
- Retirar las rutas hacia resúmenes/formularios administrativos duplicados del POS después de
  aprobar sus destinos. Enlaces antiguos conocidos redirigen al destino autorizado conservando el
  contexto; una cuenta sin permiso recibe acceso denegado y no llega a cargar datos.
- Mantener endpoints, auditoría, datos e historial: esta consolidación no elimina contratos de
  negocio ni borra configuraciones. Eliminar código muerto sólo cuando no tenga consumidores.

### 6. Verificar y publicar el paquete

- Pruebas semánticas/API focales y typecheck/build de POS y Admin; trazabilidad y `git diff --check`.
- Navegador con cuatro perfiles: cajero sin administración, usuario de consulta, administrador de
  sucursal y administrador corporativo. Probar permisos parciales por módulo además de perfiles
  completos, enlace directo, pérdida de permiso, sesión caducada y cambio de cuenta.
- Recorrido real local POS → módulo Admin → regreso a caja, con captura pendiente y dos sucursales.
  Comprobar en la API/base aislada qué sucursal se consultó o modificó, no sólo el encabezado.
- Verificar mismos componentes y mismo comando/contrato que la entrada directa desde Admin; no
  ejecutar acciones financieras o de inventario contra producción para obtener esta evidencia.
- Suite aplicable una vez en CI y auditoría R3 independiente con contexto fresco. PostgreSQL focal
  si se cambian consultas/transacciones/alcance que dependan del dialecto; no ejecutar suites
  universales o migraciones por una modificación de navegación.
- Commit/merge/push y despliegue sólo bajo sus autorizaciones respectivas. Un push no prueba que
  el paquete esté desplegado. Este plan no incluye ejecutar ninguna de esas acciones.

## Criterios de aceptación

1. El cajero sólo ve módulos administrativos que realmente puede consultar.
2. Cada tarjeta abre la misma pantalla administrativa que se abre directamente desde Admin.
3. La cuenta de consulta no ve ni puede ejecutar acciones de escritura; rutas y API concuerdan.
4. La sucursal mostrada, consultada y modificada es la misma sucursal autorizada seleccionada.
5. El usuario de sucursal no obtiene selección corporativa ni nuevos permisos al navegar.
6. Volver a caja conserva captura/contexto y respeta las guardas de operaciones pendientes.
7. Permisos faltantes producen rechazo controlado; no hay carga indebida de datos ni errores 500
   en los casos reproducidos. Las capacidades locales de disponibilidad siguen correctamente acotadas.
8. No quedan implementaciones administrativas paralelas alcanzables para los módulos migrados.

## Preguntas operativas y señales

- ¿Qué usuario y sucursal autorizada recibió cada comando? Auditoría existente del comando y prueba
  focal de correspondencia con la sesión seleccionada; no registrar tokens.
- ¿Una función desapareció por permiso o falló por sesión/conexión? Estados diferenciados y código
  de error canónico en los casos de aceptación.
- ¿Se volvió a caja con la misma captura? Evidencia del recorrido y recuperación existente por
  contexto; no registrar el contenido sensible del pedido.
- ¿Qué costo agrega proyectar las capacidades? Medición focal de solicitudes de sesión y consultas
  SQL en base aislada, sin incluir credenciales ni contenido del pedido.

## Evidencia base y límites

La revisión previa encontró pantallas separadas, botones de Compras para cuentas de consulta,
guardas incoherentes, errores 500 y una mutación de disponibilidad en sucursal incorrecta, reproducida
sólo en SQLite en memoria. El material local está en `output/playwright/admin-parity/`.

La implementación usa `adminAccess.ts`, contexto canónico de Admin y destinos internos fijos.
Se retiraron cinco archivos administrativos duplicados sin consumidores del POS; sus rutas
heredadas redirigen al módulo autorizado. Se mantienen captura POS, Checador, monitor e históricos.
Disponibilidad local vive en `CatalogAdministration`, con sucursal explícita en consulta y comando.
No se cambiaron dependencias, fórmulas, concesiones, estados, saldos, existencias ni datos productivos.

### Evidencia local del cierre

| Gate | Resultado |
| --- | --- |
| `python -m pytest apps/api/tests/test_admin_unification.py apps/api/tests/test_admin_unification_postgres.py -q` | 9 pasan en SQLite; 9 PostgreSQL omitidas por variable/servidor local ausente |
| `test_platform_api.py` focal de sesión, disponibilidad/auditoría y bloqueo de catálogo corporativo | 3 pasan; 87 casos fuera de ese alcance |
| `python -m pytest tests/architecture -q` | 150 pasan; última ampliación de guardas/trazabilidad: 17 pasan |
| `pnpm test:frontend-semantic` | Pasa completo; política compartida incluida en el gate CI |
| Typecheck/build de `admin-web` y `pos-web` | Pasan; Vite conserva advertencia de bundle mayor de 500 kB |
| Ruff y mypy focales de API, operaciones y proyección de recetas | Pasan |
| `git diff --check` | Pasa |
| Navegador Chrome con perfiles y respuestas locales | Cajero, consulta, sucursal, corporativo, permisos parciales, revocación, cambio de cuenta, 401 y desconexión pasan |
| Navegación/captura y visual | POS A → Admin B → caja A conserva cantidad y nota; Back/click bloqueados con confirmación incierta; formulario se conserva al reenfocar la misma autoridad; tarjetas visibles a 390px |

Navegador usa respuestas sintéticas para revisar montaje, acciones y navegación; los contratos API
se prueban contra base SQLite aislada. No se presentan esas respuestas sintéticas como prueba de
persistencia PostgreSQL, gateway real ni comportamiento productivo. Scripts/capturas locales:
`output/playwright/admin-parity/`. No se ejecutó la suite universal de API: la revisión se acotó
a los contratos afectados y tres regresiones existentes. La suite completa aplicable queda en CI.

### Auditoría R3: afirmaciones y refutación

| Afirmación | Evidencia e intento de refutación | Resultado y riesgo residual |
| --- | --- | --- |
| Abrir Admin no amplía autoridad | Política runtime, perfiles parciales, roles/permisos locales falsificados, acceso directo sin permiso, consulta sin escritura, revocación/cambio de cuenta/401 | Rechazo antes de montar datos; backend sigue siendo autoridad final. CI pendiente |
| El contexto de sucursal coincide con la acción | Mutación de disponibilidad B verifica que A no cambió; recetas filtran global/sucursal; cuenta mixta organizacional de consulta + producción sólo de sucursal intenta lectura sin parámetro | Filtrado y 403 controlados; falta confirmar estos mismos contratos en PostgreSQL |
| La captura no se pierde al navegar | Cantidad y nota reales de la UI persisten A → Admin B → A; prueba de Back con checkout incierto; RED/GREEN de formulario al focus | Se conserva con sesión equivalente y se bloquea salida incierta. Sin conexión Admin se cierra; sólo formularios con snapshot registrado pueden recuperarse tras fallo de revalidación |
| Un contexto anterior no contamina el siguiente | Cliente de consultas nuevo, pruebas de 401 tardío y mutación tardía, aborto de validación vieja y remount por cambio de identidad/alcance/capacidades | Cache separado y cierre ante error; no certifica comandos ya enviados, cuya resolución mantiene contratos/idempotencia existentes |

La auditoría Sol independiente del mismo ciclo encontró y cerró: permisos parciales de Conteos,
Presentaciones y Producción; directorios dependientes de administración corporativa; alcance por
defecto de recetas en cuentas mixtas; pérdida de estado de React Router; regreso tras cambiar Admin
de sucursal y escritura incorrecta de la preferencia POS. La prueba real de navegador también
detectó que POP debía instalarse antes del Router; se corrigió en los entrypoints y se verificó Back.
La revisión final no reportó nuevos defectos verificables; no sustituyó los gates ni CI.
Medición puntual del perfil en SQLite aislado: 23 capacidades, 56 consultas SQL y 137 ms por una
solicitud. No representa percentiles ni latencia productiva/PostgreSQL; esa medición queda pendiente.

### Publicación y límites

PR #64 publica el paquete. El primer CI detectó hashes desactualizados de fixtures sintéticos;
se actualizaron únicamente las entradas exactas existentes, sin nuevas excepciones ni cambiar el
detector. Los fixtures de navegador ahora responden con sesión/capacidades canónicas y conservan
las comprobaciones anteriores; se completó la respuesta sintética de previsualización de receta,
se corrigieron dos textos de prueba con codificación dañada y se espera el montaje tras revalidar
sesión. Catálogo, recetas, producto compuesto y recuperación 401 pasan en navegador local; las
14 pruebas de política/ratchet pasan. El resultado definitivo de CI se informa en el cierre.
La primera suite Python aprobó 1126 casos y detectó 9 errores de preparación del fixture nuevo
PostgreSQL: `metadata.create_all` incluye expresiones SQLite. El fixture ahora aplica las
migraciones canónicas existentes en su base descartable, conserva sus restricciones y carga
datos deterministas, igual que las suites PostgreSQL hermanas. No modifica modelos ni migraciones
productivas. La entrada de compras desde POS y la clasificación del catálogo se verifican en
navegador con el contrato canónico; el recorrido real local de compras/reautenticación también pasa.
La ejecución posterior aprobó 1134 pruebas, incluidos los 9 contratos PostgreSQL. Su único fallo
fue clasificar el módulo auxiliar compartido como ejecutable de navegador; se trasladó a
`tests/fixtures`, manteniendo las pruebas y la política de CI. El alta rápida espera el autofoco
de inicialización antes de capturar valores para evitar una carrera de automatización.

CI ahora provisiona `admin_unification_test_ci` y ejecuta los 9 contratos PostgreSQL con una URL
restringida a host local, nombre exacto y sin parámetros de conexión alternos. No se ejecutaron
localmente: no hay PostgreSQL/Docker disponible. Es un gate pendiente, no aprobado.
Commit, merge y push autorizados por el usuario el 2026-10-07. Publicación mediante PR y CI;
el resultado remoto se informa en el cierre. No hubo despliegue, migración ni cambios productivos.
Publicar y aprobar CI precede a un despliegue separado. Para el canary R3, usar una cuenta de consulta
y una de sucursal, confirmar destinos/403 y retorno de captura sin enviar comandos de dinero o
inventario; cualquier prueba productiva requiere autorización separada.
El recorrido cubre mismo origen. Orígenes separados requieren el intercambio especificado antes
de ampliar el alcance. Este cierre no certifica todas las funcionalidades del administrador.
