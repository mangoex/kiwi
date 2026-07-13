# TDD - Capacidad de identificadores de revisión Alembic

## TDD-TS-049 Capacidad de identificadores de revisión

Casos:

- la migración puente define un revision ID de máximo 32 caracteres,
- el parent de la migración puente es `0013_pos_cash_rbac_permissions`,
- la revisión `0014_legacy_caja_role_permissions` apunta a la migración puente,
- la rama PostgreSQL del upgrade amplía `version_num` a `VARCHAR(128)`,
- la rama PostgreSQL del downgrade reduce `version_num` a `VARCHAR(32)`,
- el DDL PostgreSQL de upgrade y downgrade se genera con `op.alter_column` y `sa.String(length=N)`, de modo que la longitud aparece como literal en el SQL y no contiene placeholders (`:length`, `%(length)s`, `$1`, `?`),
- la prueba de upgrade verifica `op.alter_column("alembic_version", "version_num", existing_type=sa.String(length=32), type_=sa.String(length=128))` y compila la operación completa con Alembic y el dialecto PostgreSQL para confirmar `ALTER TABLE ... TYPE VARCHAR(128);`,
- la prueba de downgrade verifica `sa.String(length=128)` → `sa.String(length=32)` y compila la operación completa a `ALTER TABLE ... TYPE VARCHAR(32);`,
- la prueba negativa del guard verifica que `downgrade()` aborta con `RuntimeError` cuando la revisión actual supera 32 caracteres y que en ese caso no se invoca `op.alter_column`,
- SQLite puede avanzar y retroceder sin invocar `op.alter_column` (no-op),
- un `upgrade` desde `0013_pos_cash_rbac_permissions` llega al head `0023_physical_counts`,
- ninguna revisión del repositorio supera 128 caracteres,
- la cadena de revisiones es lineal, sin ramas ni múltiples heads.

## TDD-TC-042 La migración puente amplía la capacidad y mantiene la cadena

Given el directorio `apps/api/alembic/versions`
When la prueba de arquitectura inspecciona los revision IDs y la cadena
Then comprueba que la migración puente `0013a_expand_version_num` tiene parent `0013_pos_cash_rbac_permissions`
And comprueba que `0014_legacy_caja_role_permissions` tiene parent `0013a_expand_version_num`
And comprueba que el bridge ID cabe en 32 caracteres
And comprueba que ninguna revisión supera 128 caracteres
And comprueba que existe una sola head `0023_physical_counts`
And comprueba que el DDL PostgreSQL de upgrade produce `VARCHAR(128)` literal sin placeholders
And comprueba que el DDL PostgreSQL de downgrade produce `VARCHAR(32)` literal sin placeholders
And comprueba que el guard impide reducir la columna si la revisión actual no cabe
And comprueba que SQLite no invoca `op.alter_column`.
