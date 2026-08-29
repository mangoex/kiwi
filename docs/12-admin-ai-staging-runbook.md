# AIA-002A — runbook de staging del asistente Admin

Este documento prepara una habilitación controlada; no autoriza credenciales, configuración,
migración, despliegue ni llamadas reales al proveedor.

## Precondiciones

- Artefacto identificado por commit y CI verde en Python, frontend, trazabilidad y PostgreSQL
  `aia001_ci`.
- Migración 0055 ensayada vacía y con bloqueo de downgrade cuando existe historia.
- Cuenta QA con `catalog.manage`, sucursal de prueba y catálogo enteramente sintético.
- Secreto de OpenRouter almacenado en el gestor del entorno, nunca en Git, navegador o ticket.
- Operador, ventana, presupuesto, criterio de aborto y responsable de rollback definidos.

El recorrido visual reproducible está en `tests/browser/test_admin_ai_assistant.mjs`; requiere un
servidor Admin local, un runtime Playwright disponible mediante `AIA002_PLAYWRIGHT_IMPORT` y,
opcionalmente, `AIA002_CHROME_PATH`. No forma parte del gate CI hasta que el repositorio adopte una
dependencia de navegador gobernada.

## Configuración

El primer despliegue conserva `RESTAURANTOS_ADMIN_AI_ASSISTANT_ENABLED=false`. Para el canary se
provisionan por separado `RESTAURANTOS_OPENROUTER_API_KEY`,
`RESTAURANTOS_ADMIN_AI_OPENROUTER_MODEL` y
`RESTAURANTOS_ADMIN_AI_OPENROUTER_TIMEOUT_SECONDS`; `RESTAURANTOS_OPENROUTER_BASE_URL` sólo cambia
si se aprueba otro endpoint compatible. No se imprimen ni copian valores reales a la evidencia.

## Secuencia de canary

1. Desplegar el artefacto con flag apagado y comprobar que una consulta devuelve orientación local
   `DRAFT`, sin `change_set` aplicable.
2. Ejecutar 0055 como acción separada y comprobar head, tabla y health del API.
3. Proveer el secreto; habilitar el flag sólo para la ventana controlada de staging.
4. Enviar una solicitud sintética sin PII para actualizar un producto QA identificable; confirmar
   `READY_FOR_REVIEW`, fuentes allowlist y ausencia de escritura anticipada.
5. Rechazar una propuesta y comprobar estado terminal/auditoría. Generar otra, aceptar una sola vez y
   repetir la misma clave para comprobar replay; otra clave debe producir conflicto.
6. Verificar `admin_ai_proposal` y `admin_ai_review` por IDs técnicos y resultado. Confirmar que no
   contienen prompt, transcript, secreto ni idempotency key.
7. Revisar catálogo, auditoría, latencia, errores del proveedor y consumo/costo del canary; apagar el
   flag al terminar la ventana.

## Abortos y rollback

Se aborta ante salida fuera de allowlist, escritura sin aceptación, permisos/alcance incorrectos,
duplicidad, prompt o secreto en logs, latencia sostenida mayor al timeout, errores 5xx repetidos o
imposibilidad de correlacionar propuesta y auditoría. El rollback inmediato es apagar el flag; se
conservan artefacto, tabla e historia. No se ejecuta downgrade 0055 cuando existen propuestas: la
migración lo bloquea deliberadamente. Una reversión de código y una limpieza de datos requieren
planes y autorizaciones independientes.

## Límites antes de uso amplio

El gate local usa proveedor y datos sintéticos; falta evidencia de CI y OpenRouter real. El MVP no
incluye cuota propia por usuario ni presupuesto automático, por lo que staging debe limitarse a un
operador y una ventana corta. Uso general o producción requiere límites de costo/volumen, alertas,
canary aprobado y evidencia productiva separada.
