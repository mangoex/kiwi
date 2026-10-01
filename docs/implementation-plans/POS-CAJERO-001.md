# POS-CAJERO-001 — implementación y evidencia local R3

Alcance: mejoras del [diagnóstico](../analysis/POS-CAJERO-001.md), PRD-FR-253..258 y FR-204/208.
Base `aa28b32`, rama `codex/pos-cashier-ux`. Paquete implementado con límites explícitos;
no se certifica liberación productiva. Sin commit, merge, push, despliegue, migración o datos productivos.

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

CI pendiente: rama no publicada. Sin canary ni PostgreSQL productivo. Se cambia un predicado SQL
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
