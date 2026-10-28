# PUR-DRAFT-001 — Borradores de compra inspeccionables y editables

Fecha: 2026-10-27. Riesgo R3 por persistencia e inventario/dinero futuro. Este paquete no autoriza
deploy, migración, configuración ni datos productivos.

## Resultado e invariantes

Permitir ver todas las partidas, editar sólo una compra `draft` de la sucursal autorizada y retirarla
de pendientes mediante cancelación auditada. Ver, editar y descartar no crean inventario, costo, caja
ni compensaciones. No existe borrado físico; confirmar/cancelar conservan su autoridad actual.

## Secuencia

1. Contrato y RED: esquema de update, pruebas API/versiones/replay/ausencia de efectos y semántica UI.
2. Persistencia: versión aditiva y recibos idempotentes; downgrade bloqueado con historia de edición.
3. Dominio/API: PUT atómico bajo lock; confirmación y descarte cotejan la versión revisada.
4. UI: Ver para lectura; Editar/Confirmar/Eliminar para manager; editor compartido hidratado.
5. Gates focales, migración aislada, QA visual y auditoría Sol independiente.

## Afirmaciones R3 a refutar

- Una edición/replay aumenta versión una sola vez: contar versión, auditoría, recibos y líneas.
- Editar o descartar no produce efectos: comparar movimientos, costo y caja antes/después.
- Edición contra confirmación/cancelación tiene un único orden serial: barreras PostgreSQL y estado final.
- Respuesta perdida no crea una intención nueva: repetir misma key/body y conflictar key reutilizada.

CI, PostgreSQL aislado disponible, navegador, despliegue, migración y producción se reportan por
separado; ningún gate omitido se presenta como aprobado.

## Remediación de validación — 2026-10-28

Paquete R3 autorizado para implementar el plan de solución: separar la variable de fila SQL del
diccionario opcional en sugerencias (R1); revisar cuatro fixtures sintéticos y renovar sólo sus
excepciones exactas; reproducir y corregir el orden de locks crear/editar; validar en PostgreSQL
aislado, SQLite, E2E, QA visual y CI. PRD/BDD y matriz conservan contratos e IDs: se activan SDD por
el orden de locks y TDD-TC-476 por la regresión. No cambia esquema ni requiere nueva migración.

Preguntas operativas: ¿crear/editar el mismo folio termina en conflicto de negocio sin 503?,
¿un replay conserva una sola edición/recibo/auditoría?, ¿el perdedor deja efectos parciales?
Resultados estructurados de comandos y conteos transaccionales de la regresión responden estas
preguntas; no se agregan payloads o claves a logs. La auditoría Sol final tendrá contexto fresco.
La evidencia GREEN y los límites de publicación se reportan en el cierre y en el PR; CI conserva
la evidencia completa de sus gates.

### Evidencia adversarial y revisión

- Afirmación: crear y editar no deben formar un ciclo identidad/presentación. La regresión forzó
  ambas intercalaciones en PostgreSQL 16 aislado; antes del fix obtuvo `DeadlockDetected` cuando
  creación ganó la identidad (1 failed, 1 passed). El fix establece identidad antes de presentaciones
  en ambas rutas. La prueba exige un único ganador, conflicto de negocio y ausencia de efectos.
- Afirmación: el perdedor y el replay no duplican historia. La misma regresión compara cabeceras,
  partidas, versiones, recibos, auditoría, inventario, costo, precio vigente y caja; el replay de la
  intención ganadora debe preservar el snapshot. La evidencia de ejecución se registra en el cierre.
- E2E detectó una carrera del fixture: confirmar por API antes de cargar la fila draft provocaba un
  timeout buscando Eliminar. Se espera primero esa acción y se exige el POST discard rechazado con
  `409 purchase_state_conflict`, seguido de la acción Cancelar actualizada (TDD-TC-477).
- Auditoría Sol independiente y continuación sobre el delta E2E: sin hallazgos bloqueantes. Se
  revisaron guardas de autorización/replay, normalización, rutas hermanas, atomicidad y excepciones
  sintéticas. No sustituye los resultados ejecutables pendientes de cierre.
- Política: tres hashes se renovaron tras revisar credenciales/tokens de fixtures; se agregó
  procedencia y excepción exacta a `test_corte_ciego_phase2_through_6.py` por la contraseña local
  del actor sintético de step-up. No se cambió el scanner, ni se excluyeron rutas completas.
- CI detectó diez errores de inferencia con SQLAlchemy 2.1.4 (versión fijada), ausentes en el
  entorno local previo 2.0.52. Se anotan colecciones de escalares y se leen filas de sujetos de
  revisión por mappings tipados; no cambian permisos, fórmulas, consultas ni efectos. Se crea un
  entorno QA aislado desde el lock Windows para verificar paridad, sin alterar dependencias.
- CI detectó una expectativa de branding obsoleta en `test_admin_retro.mjs`: se comprueba Mimenu
  Admin/Utensils, ya introducido por `35e3396`, conservando el resto de verificaciones. El E2E
  espera mostrar el turno renovado antes de iniciar otra confirmación tras un rechazo definitivo.

La ejecución completa de semánticas descubrió expectativas anteriores al Copiloto, componentes
elegibles y branding Mimenu. Se conservan autoridad Python, restricciones de profundidad y contraste
AA; se reconcilian los apartados SDD/TDD desactualizados con PRD-FR-260/262 y los cambios existentes.
Ruff identificó líneas largas previas en `executive_ai`; el formateo conserva exactamente su AST.

La afirmación de aislamiento del Copiloto fue refutada: el browser mostró el resultado de Centro
después de seleccionar Norte. Se remonta el componente por actor/sucursal y aborta la petición al
salir; la regresión cubre respuesta cargada y diferida. Preguntas operativas: ¿qué sucursal se
consultó? El payload conserva `branch_id`; ¿puede una respuesta anterior alterar la vista nueva?
La regresión de navegador y la cancelación del request verifican esa frontera, sin registrar
prompts ni respuestas financieras. La auditoría independiente revisa también este delta.

Riesgo residual: el test cubre crear/editar la misma identidad y presentación, no todas las posibles
intercalaciones del sistema. No hay migración nueva, escrituras históricas ni efectos que compensar
por esta corrección; revertir código reintroduciría el deadlock. La migración 0104 se valida sólo en
bases aisladas. No se acredita despliegue, migración o canary productivo.

### Remediación del backend completo de CI

La ejecución 40721663770 sobre `3cfc628` terminó con 86 fallos, 2895 aprobadas y 8 omitidas.
El frontend completo de ese mismo commit pasó. El paquete continúa hasta validar las causas
compartidas del backend; ese resultado no acredita un cierre.

- Gobernanza/actor: la apertura con contexto retenía actor antes de pedir gobernanza; selección
  usaba el orden inverso. La corrección adopta gobernanza exclusiva antes de actor/perfil y antes
  de guardas financieras fiscales que luego validan workspace. No se conserva una transacción
  durante I/O al PAC. Riesgo residual: serialización organizacional de esas transacciones.
- Los observadores de carreras reconocen advisory locks además de locks de fila, manteniendo la
  obligación de observar espera real y ausencia de efectos. El holder de cierre de caja adquiere
  gobernanza antes de sucursal; prueba exclusión antes del turno, no exclusivamente espera en sucursal.
- La descarga fiscal fuerza revocación después del commit de auditoría y antes de entregar bytes:
  la reautorización debe denegar. Una respuesta auditada no concede autoridad posterior.
- Se conserva PRD-FR-262: editar grupos ordinarios de un componente es válido; agregar otra
  profundidad sigue fallando atómicamente. La carrera fijo/elegible usa un componente real, no
  una instrucción ordinaria. Las actualizaciones del fixture conservan IDs de grupos/opciones.
- Fixtures HTTP usan tokens humanos firmados, sin depender de headers de desarrollo. Gastos crea
  todas las tablas de autoridad; no se relaja la guarda de esquema incompleto. Las invocaciones
  directas del endpoint de gastos incluyen `Response`, como la firma HTTP actual exige.
- Crear tablas PostgreSQL sobre los metadatos compartidos suprimía la FK SQLite de intención
  aceptada. Se reprodujo antes/después y se copian metadatos en los fixtures, conservando restricciones.
- Expectativas de head pasan a 0104; migración 0076 conserva checks estructurales y exige rechazo
  del perfil actual, seguido de perfil válido en 0077. Carreras de impresión usan esquema vigente.
- Se regeneran cuatro JSON Schema con las dependencias fijadas: la diferencia es el patrón
  autogenerado de Decimal; no cambian modelos, tipos ni validadores. Se conserva igualdad exacta
  entre schema publicado y runtime. Auditoría corporativa exige también diferencias y motivo.
- Se conecta la semántica de componentes POS a CI y se alinea la altura de opciones con la UI
  vigente; no se omite ninguna prueba ni se aumenta ningún timeout para obtener verde.

Preguntas operativas: ¿una selección espera hasta el commit del comando?, ¿hay deadlocks al abrir
caja o consultar un documento fiscal?, ¿una revocación impide entregar datos ya materializados?
Las barreras, `pg_stat_activity`, resultados de comandos y conteos/auditorías retenidos responden
estas preguntas sin registrar secretos ni contenido fiscal. Una auditoría Sol final con contexto
fresco detectó un ascenso compartido/exclusivo todavía posible en el dependency HTTP fiscal y en
`list_invoices`. Se anticipa el modo final desde esas entradas. La regresión PostgreSQL reprodujo
`DeadlockDetected` en HTTP y servicio directo (2 RED), seguida de 5/5 GREEN en listado, detalle,
PDF/XML y listado directo. El auditor revisó el fix aplicado sin nuevos bloqueantes.

Evidencia local adicional del paquete: 11 pruebas de workspace, 3 de revocación fiscal, 2 de
cierre/movimientos de caja, 5 de gastos y la carrera fijo/elegible aprobadas en PostgreSQL aislado.
La guarda 0066 se invoca directamente sobre snapshots de pedidos actuales y conserva contenido/head;
no acredita la cadena CLI head→0065. La carrera de retry de impresión tuvo un timeout de preparación
al migrar head bajo carga; se repitió aislada y pasó sin cambiar el timeout. Mypy de 150 fuentes,
Ruff completo, 39 regresiones finales fiscales/trazabilidad y diff-check verdes. CI completo del
nuevo commit sigue siendo el gate de cierre; no se acredita producción.

CI de `86c83aa` detectó contaminación residual en el fixture de existencias para agentes, que
parametriza SQLite/PostgreSQL en un archivo sin sufijo `_postgres`. La secuencia local de ese
módulo seguida de las tres guardas de metadatos y la FK de intención pública reprodujo cuatro
fallos y siete aprobadas. Se aplica también allí la copia de metadatos; no cambia runtime ni
restricciones. La ejecución completa de CI sigue siendo necesaria para cerrar el paquete.
La repetición de esa misma secuencia pasó 11/11, junto con Ruff, política del repositorio y
`git diff --check`. Se conserva el fallo real de FK en la fase RED, sin relajar su expectativa.
