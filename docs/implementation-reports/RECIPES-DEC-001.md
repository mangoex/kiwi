# RECIPES-DEC-001 — Dos decimales en el editor de recetas

Riesgo R3 por captura de cantidades y guardado de recetas. Alcance: editor canónico compartido
por Productos y Recetas; no cambia cálculo Python, API, persistencia ni historial. Autoridad:
PRD-NFR-012, SDD-ADR-010, BDD-SC-720..722 y TDD-TS-150 / TDD-TC-420..421.

## Evidencia local

- RED: `node tests/frontend/test_recipe_product_flow.mjs` falla porque falta el formateador
  de dos decimales (`undefined` en lugar de `function`). GREEN con la implementación.
- Semántica y formato: `test_recipe_product_flow.mjs`, `test_pco007_recipe.mjs`,
  `test_product_capsule_tabs.mjs`, `test_admin_productos_master_detail.mjs` y
  `test_admin_product_flow.mjs` aprobados.
- Typecheck admin y build de producción aprobados. Vite conserva el aviso de bundle mayor de 500 kB.
- `python -m pytest tests/architecture/test_traceability.py -q`: 9 aprobadas usando `.venv`.
- Browser sintético y QA visual aprobados en 390, 768 y 1440 px; screenshots locales en
  `output/playwright/recipe-product-flow-{width}.png`, con costo `45.59` y unitario `40.58`.
- `git diff --check` aprobado.

## Revisión R3 independiente y refutaciones

Auditoría con contexto fresco requerida por AGENTS.md: sin hallazgos accionables. Revisión de
corrección, fronteras de captura y conservación del contrato de escritura.

| Afirmación | Evidencia e intento de refutación | Resultado y riesgo residual |
| --- | --- | --- |
| Mostrar dos decimales no cuantiza comandos | Browser carga rendimiento `1.123456`, neto `0.123456` y merma `12.5678 %`; enfoca y guarda sin cambios; después modifica sólo merma. Inspecciona POST/PUT exactos. | Se conservan los valores originales no editados. Fixture sintético: no certifica escritura productiva. |
| Captura inválida no alcanza preview ni PUT | Ingresar y dejar `12.345` en rendimiento, neto y merma; esperar más que el debounce e inspeccionar requests y contador de guardados. Probar signo negativo; recuperar con captura válida y coma decimal. | Error visible, botón bloqueado y cero solicitudes nuevas mientras es inválido; mutationFn agrega guarda defensiva. Backend conserva sus validaciones. |
| El formato respeta HALF_UP sin float | Casos `45.586562`, `1.005`, negativos, cero y acarreo sobre `999999999999.999999`; implementación con cadenas y BigInt. | Formato exacto aprobado, independiente de cálculos de dominio. |
| UI y reintentos conservan las fronteras existentes | Inspección de whitelist de payload, mapeos de carga/IA y `usePythonPreview`; browser comprueba versión esperada, sucursal, clave y bloqueo tras conflicto. Blur modifica sólo metadatos de UI. | Sin campos de UI en PUT ni cambio de permisos, idempotencia o escritor. La revisión de IA es estática; no se invocó proveedor externo. |

## Preguntas operativas y señales existentes

- ¿Qué impide guardar? Error junto al campo y `aria-invalid` para precisión; alerta existente para
  error del servidor o conflicto de versión. No se agregan logs de contenido de recetas.
- ¿El costo corresponde a la captura actual? Identidad de `usePythonPreview`, cancelación de
  solicitudes anteriores y costo pendiente durante captura inválida o espera del cálculo.
- ¿Se confirmó la nueva versión? Mensaje de éxito sólo tras PUT confirmado y errores existentes
  que conservan el borrador; la receta efectiva sigue gobernada por versión e idempotencia.

## Límites y publicación

No se requieren migraciones ni pruebas PostgreSQL/SQLite: no cambian esquema, fórmulas, bloqueo,
SQL o dialecto. La QA local representa el riesgo de UI; no se realizaron cambios ni canary sobre
datos productivos. Reversión mediante revert del código de presentación, sin compensar historial.
Suite completa local omitida conforme GOV-TEST-001; CI pendiente de publicación del PR. Se conserva
el gate existente para las suites que configura. Despliegue no realizado. Las demás interfaces siguen
pendientes de adoptar esta regla.
