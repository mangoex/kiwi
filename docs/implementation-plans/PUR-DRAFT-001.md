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

Riesgo residual: el test cubre crear/editar la misma identidad y presentación, no todas las posibles
intercalaciones del sistema. No hay migración nueva, escrituras históricas ni efectos que compensar
por esta corrección; revertir código reintroduciría el deadlock. La migración 0104 se valida sólo en
bases aisladas. No se acredita despliegue, migración o canary productivo.
