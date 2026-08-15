# PCO-005B — cierre de release y evidencia para auditoría Sol

Fecha de cierre: 2026-08-15. Riesgo del cambio: R3.

## Integración y CI

- PR #29 integró PCO-005B: feature `031ee55`, corrección `b5144f7` y merge a `main` `08bfdff`.
- El CI de PR quedó verde y el CI de `main` quedó verde. En CI, PostgreSQL aislado ejecutó `7 passed`;
  la suite Python completa reportó `393 passed, 12 skipped`.
- Ruff, Docker, frontend, typecheck y los builds de frontend quedaron verdes. El job Python mantiene
  PostgreSQL 16 efímero y usa exclusivamente `PCO005B_TEST_POSTGRES_URL`; no usa `DATABASE_URL`.

## Evidencia productiva del 2026-08-15

- El build de EasyPanel para PR #29 fue exitoso. `/health/live` y `/health/ready` respondieron 200,
  con PostgreSQL y Redis en estado `ok`.
- Antes de migrar, la UI mostró `UndefinedTable: order_corrections`; `alembic current` confirmó
  `0039_order_reopen_requests`.
- Se ejecutó `alembic upgrade head`; después, `alembic current` confirmó
  `0040_order_corrections (head)`.
- Al recargar, cuentas y cola cargaron sin error y la UI mostró el texto PCO-005B.
- Después de actualizar únicamente `RESTAURANTOS_GIT_COMMIT` y hacer redeploy, `/health/version`
  reportó exactamente `08bfdff815a2fb9ca2b13ee8858dce915a1e1c61`; `/health/ready` siguió en `ok`
  con PostgreSQL y Redis.

## Límites

- No se probó una corrección `APPLIED` en producción: no había una solicitud `APPROVED` y no se
  mutaron pedidos.
