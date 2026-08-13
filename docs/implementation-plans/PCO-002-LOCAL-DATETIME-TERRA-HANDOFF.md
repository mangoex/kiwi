# PCO-002 — handoff Terra: vigencia local de conceptos

## Hallazgo productivo

El canary PCO-003 del 2026-08-12 publicó un concepto a las 17:12 de `America/Mazatlan`, pero el
formulario precargó `2026-08-13T00:12` mediante `toISOString().slice(0, 16)`. El control
`datetime-local` reinterpretó esos componentes UTC como hora local y el backend recibió un instante
siete horas futuro. El concepto fue correctamente excluido de la lectura efectiva. El concepto QA se
archivó sin crear movimientos; su historia se conserva.

## Alcance autorizado

- Extraer a `cashConceptState.ts` un helper puro para construir `YYYY-MM-DDTHH:mm` con componentes
  locales del `Date` recibido.
- Usarlo en el estado inicial de creación, después de guardar y al iniciar una nueva versión.
- Conservar `new Date(form.valid_from).toISOString()` como única conversión local a UTC del payload.
- Añadir prueba ejecutable con `TZ=America/Mazatlan`, incluida una hora cuyo día local difiere del UTC.
- No cambiar backend, contratos, migraciones, permisos, idempotencia ni reglas de efectividad.

## Gates

- `node tests/frontend/test_admin_cash_concepts.mjs` con Node soportado.
- Typecheck y build de `@restaurantos/admin-web`.
- Trazabilidad y `git diff --check`.
- Sin commit, push, merge, deploy ni nuevas escrituras productivas por Terra.
