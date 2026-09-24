# TDD — CAT-CLASS-001 (pruebas implementadas; evidencia en CAT-CLASS-001)

## TDD-TS-118 Clasificación, seguridad y continuidad operativa

### TDD-TC-271 Jerarquía y separación operativa

Cubre BDD-SC-531/532. Fixtures sintéticos de cerveza, alimento en barra, grupo mixto, subgrupo
opcional y producto no vendible. Ejecutar helpers reales de filtrado y render/eventos de Admin/POS;
no aceptar búsquedas de cadenas fuente como único oráculo. Verificar altas normal/contextual,
clasificación heredada, cambio de grupo, foco/teclado, errores, borrador, favoritos, carrito y búsqueda.
Probar escritorio y ancho móvil afectado con evidencia visual; comparar preview y POS real.

### TDD-TC-272 Autorización y entradas hostiles

Cubre BDD-SC-533. Matriz anónimo, corporativo permitido, corporativo sin permiso, sucursal con
permiso, actor revocado y otra organización; lectura, alta, actualización, replay e importador.
Usar organizaciones con entidades reales distintas. Probar IDOR, mass assignment, NULL en modo
explícito, enums desconocidos, versiones negativas/no enteras y errores sin datos ajenos. Comparar
filas y auditoría antes/después, incluidas rutas hermanas. Mantener filtros públicos y por sucursal.
Probar explícitamente GET categorías sin branch con rol de sucursal y GET con branch ajeno;
el DTO operativo no filtra versiones de escritura ni metadata administrativa.

### TDD-TC-273 Atomicidad, concurrencia e idempotencia

Cubre BDD-SC-534. Inyectar fallo después de actualizar y antes de auditar/confirmar comando;
assert sobre grupo, versión, comando y auditoría. Dos sesiones PostgreSQL sincronizadas compiten
con misma versión y con misma clave; una sola escritura, replay coherente. Probar cambio de hash,
autorización revocada y escritor heredado concurrente. SQLite verifica rollback y CAS sin simular
que demuestra bloqueos PostgreSQL. No aceptar tests omitidos por falta de URL como gate verde.

### TDD-TC-274 Migración y mapping reanudable

Cubre BDD-SC-535. Upgrade desde head anterior en PostgreSQL y SQLite con grupos vacíos, mixtos,
archivados y estaciones antiguas; preservar fingerprints de datos ajenos. NULL no se rellena por
inferencia. Aplicar mapping dos veces, interrumpir/reanudar, introducir versión obsoleta y comprobar
resultado por fila. Ensayar downgrade vacío y rechazo con historia, backup/restore en entorno
sintético. Probar gate de activación y reactivación. Resolver revisión Alembic contra head al ejecutar.

### TDD-TC-275 Compatibilidad y fallos offline

Cubre BDD-SC-536. Matriz lector antiguo/nuevo por bundle v1/v2/v3 y modo legacy/explícito, incluyendo
capacidad ausente. Ejercitar emisor, firma, refresh, hidratación SQLite y lectura real del gateway.
Probar subgrupos, alcance ajeno, firma/hash inválidos, paquete incompleto, corte durante instalación
y proceso reiniciado. El último catálogo válido permanece utilizable y el cambio es atómico.
Comprobar ausencia de filas de otras organizaciones/sucursales, no sólo igualdad visual.
Instalar v3, reinyectar v1/v2 firmado y v3 con generación menor; deben rechazarse incluso después
de reiniciar. Misma generación con distinto hash/modo falla; mismo hash es replay inocuo. Reversión
legacy válida sólo con generación superior. Fallar entre catálogo y marcador prueba atomicidad.
Desconectar tras acuse de preparación y antes de instalación explícita: organización permanece
en adopting y sucursal en su modo confirmado. Acuses de otro hash, modo, generación o sucursal
no cuentan. Probar invalidación de preparación por alta/reactivación de grupo o nueva sucursal.

### TDD-TC-276 Regresión operativa y reversión

Cubre BDD-SC-537. Con pedidos ya aceptados y nuevas ventas sintéticas, comparar precio total,
snapshot/consumo de receta, destino KDS/impresión, inventario reservado/confirmado y reportes antes
y después de reclasificación. Verificar combos/componentes, disponibilidad, mobile/público y reglas
operativas por estación. Con mismo snapshot de catálogo, el conjunto vendible debe ser idéntico.
Revertir modo con nodos online y desconectados y venta posterior: conservar comandos/auditoría,
snapshots y datos nuevos; no ejecutar restore destructivo. Medir consultas y latencia contra baseline.

## Archivos y ejecución

Suites focales implementadas: `apps/api/tests/test_catalog_classification.py`,
`test_catalog_classification_postgres.py`, `test_catalog_classification_migration.py` y contrato en
`tests/contract/test_catalog_classification_contract.py`; frontend en
`tests/frontend/test_catalog_classification.mjs` (semántica ejecutable) y recorrido browser en
`tests/browser/test_catalog_classification.mjs`. Extender `test_offline_order_catalog.py` y
`test_gateway_catalog_refresh.py`. La suite offline se concreta además en `test_catalog_classification_offline.py`, y rollout en
`test_catalog_classification_rollout.py`/`test_catalog_classification_http_rollout.py`. El resultado
de ejecución, no la existencia del archivo, constituye evidencia; ver cierre CAT-CLASS-001.

RED: clasificación comercial distinta de estación debe fallar porque el filtro actual usa estación;
la autorización/versionado y el gate de activación se prueban con fallos del comportamiento real.
La ausencia de dependencias no acredita RED. Capturar comando, revisión y salida RED/GREEN.

Comandos reproducibles de verificación (PowerShell, desde raíz):

```powershell
python -m pytest apps/api/tests/test_catalog_classification.py apps/api/tests/test_catalog_classification_migration.py tests/contract/test_catalog_classification_contract.py -q
# CATCLASS_TEST_POSTGRES_URL debe apuntar exclusivamente a una base de pruebas desechable.
python -m pytest apps/api/tests/test_catalog_classification_postgres.py -q
python -m pytest apps/api/tests/test_offline_order_catalog.py apps/api/tests/test_gateway_catalog_refresh.py -q
node --test tests/frontend/test_catalog_classification.mjs
node tests/browser/test_catalog_classification.mjs
pnpm --filter @restaurantos/admin-web typecheck
pnpm --filter @restaurantos/pos-web typecheck
python -m pytest tests/architecture/test_traceability.py -q
git diff --check
```

Ruff y mypy focales de módulos Python modificados, typechecks y builds Admin/POS ejecutados.
Los cambios mobile preexistentes no forman parte de esta implementación. Las nuevas suites están
configuradas en el job backend/servicio PostgreSQL y la cadena frontend de CI. CI ejecuta suite completa aplicable una vez; suite local focal primero. Browser/E2E
requiere servicios y fixture autenticado sintético, sin credenciales productivas. El cierre R3 exige
auditoría independiente y canary autorizado; la configuración de CI no acredita una ejecución remota de este diff.


## Evidencia y límites actuales

TC-271: semántica de helpers y browser render/eventos en 1440/390 px. TC-272/273: comando/HTTP,
roles negativos, rollback inyectado y carreras PostgreSQL reales. TC-274: upgrade/roundtrip SQLite
y PostgreSQL con conservación de filas y rechazo de historia. TC-275: offline v1/v2/v3, scopes,
firmas, replay y crash/restart; TC-276: snapshots de pedido, inventario y outbox conservados durante
refresh, adopción/reversión por ACK. Los escenarios productivos de KDS/impresión, restauración y
latencia en infraestructura real quedan al canary autorizado; las pruebas locales no los certifican.
CI backend recibe CATCLASS_TEST_POSTGRES_URL y frontend incluye test:catalog-classification;
ejecución remota de este diff todavía pendiente.

Backup/restore sintético PostgreSQL aprobado: 139 tablas y 50 filas con hashes y conteos
idénticos. Evidencia en `output/cat-class-backup-check.json`. Medición de 1000 productos: baseline
294.90 ms/3 consultas y cambio 441.00 ms/14 consultas (medianas locales); requiere validación con
catálogo real antes de release. Evidencia en `output/cat-class-benchmark.json`.
