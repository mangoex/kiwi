# AIA-002A — endurecimiento local y paquete de staging

Fecha: 2026-08-29. Riesgo: R3. Worktree: `/private/tmp/kiwi-admin-ai-assistant`.

## Resultado

AIA-001 quedó endurecido localmente para revisión: el gate de trazabilidad ya no tiene IDs BDD
duplicados, CI provisiona una base PostgreSQL `aia001_ci`, la concurrencia de aceptación y la
migración tienen pruebas opt-in, creación/revisión producen observabilidad redactada y el recorrido
real de UI fue validado con datos y API sintéticos en escritorio y móvil. El runbook mantiene la
habilitación default-off y separa despliegue, migración, credencial y canary.

## Evidencia visual

- `assets/AIA-002A-desktop-review.png`
- `assets/AIA-002A-desktop-applied.png`
- `assets/AIA-002A-mobile-review.png`
- `assets/AIA-002A-mobile-applied.png`

El flujo comprobó trigger accesible, avatar de perfil conservado, consulta, deep link, comparación
actual/propuesto, aceptación y encabezado `Idempotency-Key`. En 1440x1000 y 390x844 no hubo overlay,
errores de consola ni `pageerror`.

## Evidencia ejecutada

- Ruff focal y `compileall`: verdes.
- Pytest de servicio, HTTP, configuración, migraciones, arquitectura, CI y trazabilidad:
  `70 passed, 3 skipped`; los tres skips son únicamente PostgreSQL opt-in.
- Node `v24.19.0`: TypeScript estricto y build Admin verdes, 1609 módulos transformados.
- Contrato semántico Admin AI: verde.
- Chrome sintético: dos recorridos completos, cuatro capturas, cero errores de página/consola.
  El recorrido reproducible vive en `tests/browser/test_admin_ai_assistant.mjs`.
- El build conserva el warning conocido del chunk principal de 612.82 kB.

## Límites vigentes

- Esta máquina no ofrece servidor PostgreSQL; los casos opt-in quedan omitidos localmente y deben
  ejecutarse en CI antes de integración.
- No hubo proveedor real, credencial, CI remoto, commit, push, merge, despliegue, migración externa
  ni canary. Ninguna de esas capas se declara pasada.
- Las capturas usan datos y respuestas sintéticos; demuestran el recorrido de navegador, no el
  comportamiento de OpenRouter ni de staging.
- Falta una cuota/costo propia del asistente antes de habilitarlo para uso amplio.
