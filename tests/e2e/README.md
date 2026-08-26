# Cashier sales E2E

This harness exercises seven synthetic cashier sessions against the local POS and an isolated
PostgreSQL database. Each cashier records eight accounts totaling MXN 20,000, closes the shift
operationally, and leaves the final user cash cut to an authorized administrator.

## Safety boundary

- Use only `127.0.0.1:55432/kiwi_cashier_e2e`.
- Never pass `DATABASE_URL` or a production/staging database.
- `cashier_sales_postgres_fixture.py` truncates all business tables in that exact database.
- Store manifests, browser results, screenshots, and reports under `.e2e/`; that directory is
  ignored because manifests contain synthetic login credentials.
- The fixture uses synthetic data and must not be interpreted as production-readiness evidence.

## Execution order

1. Create the isolated database and migrate it to Alembic `head`.
2. Run `cashier_sales_postgres_fixture.py` to seed seven branches, cashiers, cost states, and the
   deterministic account matrix.
3. Start the API and compiled Admin/POS assets on `http://127.0.0.1:8765`.
4. Run `cashier_sales_mcp.mjs` once per branch index (`0` through `6`). Pass `--runtime` pointing to
   an isolated Node runtime containing `@playwright/mcp` and `@modelcontextprotocol/sdk`.
5. Run `cashier_sales_cross_branch.py` to execute a fresh cross-branch denial.
6. Run `cashier_sales_postgres_finalize.py` to create and finalize the seven cash cuts.
7. Run `cashier_sales_postgres_audit.py` with all seven browser result files. The audit fails closed
   on duplicate branches, altered account matrices, PostgreSQL totals, non-exact recipe costs,
   missing closures/cuts, or an uncorrelated cross-branch denial.

## Declared limitation

The finalizer can add test-only `cash.user_cut.read/create` authority after the synthetic fixture
truncates migration-seeded RBAC rows. This validates the cash-cut behavior but does not validate the
canonical production RBAC seed. Production readiness requires a separate run that preserves and
exercises migration-seeded permissions.
