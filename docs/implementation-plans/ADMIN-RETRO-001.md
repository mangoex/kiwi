# ADMIN-RETRO-001 — hallazgos de pantallas y administración retro

Solicitud del 2026-09-18. Paquete integral R3. Autoridad: AGENTS.md; alcance de descubrimiento
en Pantallas/HISTORIAS.md, cadena canónica PRD → SDD §46 → BDD/TDD admin-retro → matriz.
El usuario autorizó implementación con Terra y auditoría Sol; durante la ejecución autorizó
commit, merge y push al terminar. Despliegue/migración productiva siguen separados. Se preservan
los cambios locales previos de operations.py y mobile.

## Secuencia y propiedad

1. Raíz: contratos, IDs, matriz, resolución de hallazgos/documentación y verificación integrada.
2. Terra Admin: presentación retro de toda la aplicación administrativa; después UI de flujos.
3. Terra Backend: servicios y API, migración aditiva y pruebas focales de capacidades nuevas.
4. Sol: una auditoría independiente con contexto fresco al integrar el paquete, con intentos de
   refutación y evidencia R3. Sus correcciones forman parte del mismo ciclo.

## Alcance completo a comprobar

| Hallazgo | Trabajo y evidencia requerida |
|---|---|
| SR-HU-01/02/04/05/06/07/09/10/11/12/13/15 | Verificar flujos existentes y completar huecos observados; conservar contratos y aplicar tema administrativo |
| SR-HU-03 | Resolver clasificación usando catálogo canónico, sin cuentas contables ni tipos de pedido inventados |
| SR-HU-08 | Resolver grupos/tamaños usando categorías y opciones canónicas, sin duplicar productos |
| SR-HU-14 | Composición fija versionada y precio propio según PRD-FR-242/SDD §46.4; cerrar administración, consumo, estaciones y snapshots |
| SR-HU-16 | Prioridades independientes y salida impresa administrativa real |
| SR-HU-17 | Preview y aplicación atómica versionada a múltiples destinos, con replay y conflictos |
| SR-HU-18 | Configuración y proyección determinista de umbrales en sucursal |
| SR-HU-19 | Usos directos efectivos de un insumo, con navegación al detalle y scope |
| Apariencia | Login, shell, listas, diálogos y nuevos flujos retro claro monocromático; sin alterar POS/KDS/mobile |

## Gates y cierre

RED dirigido antes de implementar comportamiento; pruebas Python de contrato y dominio,
PostgreSQL/SQLite para persistencia y concurrencia, upgrade/downgrade, Ruff y mypy focales.
Admin typecheck/build y pruebas semánticas, E2E de flujos que crucen componentes, QA visual
390/768/1440 y teclado. Gate de trazabilidad y git diff --check. CI sólo acredita suites
realmente ejecutadas; conservar evidencia local y no declarar CI ni producción sin verificar.
La auditoría Sol registra afirmación, evidencia, refutación, resultado y riesgo residual.
No cerrar el objetivo con una entrega sólo visual ni dejando candidatos/combos sin resolver.

## Evidencia vigente

- Git: base d59c166, rama codex/admin-retro-catalog. Pull ff-only confirmó que estaba actualizado.
  Sin commit, push, merge ni despliegue de este paquete. Trabajo ajeno respaldado en temporal;
  tres archivos mobile conservan sus hashes; operations.py necesita staging selectivo.
- Contexto: 27 imágenes ordenadas/renombradas; los 27 SHA256 coinciden con manifest.csv.
  Historias y referencias en Pantallas/HISTORIAS.md. No se importaron datos reales de las capturas.
- Catálogo: test_admin_catalog + test_admin_catalog_postgres, 15 PASS sin skips. PostgreSQL
  sintético loopback55432; concurrencia, replay, rollback y downgrade0065 cubiertos.
- Combos: Terra reportó 13 PASS canales/migración, 4 casos críticos posteriores y 3 PASS PostgreSQL.
  El caso SQLite de enmienda pasó con foreign_keys=ON. Core: 11 PASS antes de las últimas
  regresiones de replay; requiere resultado actualizado de esas regresiones.
- Frontend: build Admin+TypeScript PASS, 1630 módulos, aviso de chunk783kB. Dos contratos
  semánticos PASS. Build posterior al filtro de componentes PASS; mock1440 volvió a pasar con
  cambio CENTRO/NORTE/corporativo y reinicio de revisión al cambiar alcance.
- Navegador real: test_admin_retro_e2e PASS contra API y SQLite nueva. Acredita prioridades e
  impresión, conflicto preservando borrador, umbrales, usos/detalle, aplicación de dos recetas,
  composición v1 tras recargar, conflicto v2, revisión explícita y guardado v3.
- Mock: 390/768 y1440 PASS en corridas secuenciales; incluye GET fallido durante revisión409,
  borrador intacto y Save bloqueado hasta lectura vigente exitosa. QA visual inspeccionada.
  Las esperas observan estado DOM; no usan pausas fijas para ocultar fallos.
- Integridad: trazabilidad8PASS; repository_policy/quality_ratchet14PASS; policy sobre archivos
  rastreados y nuevos previstos PASS; diffcheck PASS. Outputs de navegador no forman parte del commit.
- Python: Ruff focal PASS. Mypy admin_catalog y combo PASS antes del último fix; operations/service
  conservan 10 errores basales frente a11 en HEAD con follow-imports=skip. No es mypy verde global
  ni acredita imports estrictos; no se añadieron supresiones.
- CI remoto aún no ejecutado. Workflow configura PostgreSQL aislado y navegador mock+API real.
  CI será autoritativo sólo para los gates que ejecute. No se corrió una suite universal local.

## Auditoría R3: afirmaciones y refutaciones

| Afirmación | Evidencia / intento de refutación | Resultado y riesgo residual |
|---|---|---|
| Snapshot conserva identidad por componente | Igual nombre/estación; FK UNIQUE task_id; prueba SQLite FK-on y PG | Corregido orden de inserción tarea antes de snapshot; PASS tras fallo PG reproducido |
| Correcciones compensan reservas sin duplicarlas | Reducción, replay, dos enmiendas y cancelación; costo/reserva netos | PASS neto cero al cancelar; movimientos ADDITION distintos |
| Composición efectiva respeta alcance | Anidamiento local distinto y componente convertido en combo | Sol cerró tras pruebas focales; aceptación falla cerrado |
| Cantidad/costo son exactos y congelados | Exponentes extremos, overflow Numeric, costo10 por consumo1, historial | Sol cerró fixes Decimal, límite de clave y snapshot canónico |
| Replay es estable ante cambios posteriores | Archivar componente después de guardar; versión2 antes de replayv1 | Sol cerró ambos tras reproducción y regresiones service/HTTP PASS; mantiene reautorización |
| Editor ofrece componentes del alcance sin permisos adicionales | Cambiar CENTRO/NORTE; rol recipes.manage sin pos.operate | Cerrado: filtro por scope y prueba recipes.manage sin permiso POS PASS |
| Offline conserva snapshots | Gateway actual sólo sincroniza caja | BDD-SC-501 diferido por acuerdo explícito; fuera de esta entrega |

## Reparación focal R0 de fixtures

Cinco fixtures basales (DiDi, Rappi, Uber, Facturapi y quality_ratchet) recibieron únicamente
una primera línea de provenance y hash exacto en el registro canónico. Cuerpos verificados
idénticos; no cambian detectores, patrones ni pruebas. Credenciales son sintéticas y se usan
sobre mocks/SQLite. Nuevos fixtures de navegador/API tienen provenance y hash revisados;
una edición invalida su hash. Sol validó esta reparación separadamente de la funcionalidad.

## Cierre de alcance y publicación

El usuario acordó dejar pedidos offline por separado y retomarlos después de probar esta entrega.
BDD-SC-501 y la parte offline de TDD-TC-248 conservan su contrato futuro sin declararse aprobados.
PRD242 queda Scaffold para reflejar esa cobertura parcial; PRD237–241 quedan Probado con evidencia
local. Sol cerró el alcance online sin hallazgos accionables abiertos tras la revalidación del mismo
ciclo. CI remoto, commit, merge y push se verifican durante la publicación autorizada.

Los comandos de replay conservan autorización vigente; devuelven el resultado histórico exacto
incluso tras archivar componentes o guardar una versión posterior. El selector filtra componentes
corporativos/locales sin exigir pos.operate; cambio de sucursal reinicia la revisión. Las regresiones
SQLite/HTTP, mypy fuerte, build y mock final de alcance pasaron. No se desplegó ni migró producción.
