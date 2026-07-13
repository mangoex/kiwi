# TDD - Capacidad de identificadores de revisión Alembic

## TDD-TS-049 Capacidad de identificadores de revisión

Casos:

- la migración puente define un revision ID de máximo 32 caracteres,
- el parent de la migración puente es `0013_pos_cash_rbac_permissions`,
- la revisión `0014_legacy_caja_role_permissions` apunta a la migración puente,
- la rama PostgreSQL del upgrade amplía `version_num` a `VARCHAR(128)`,
- la rama PostgreSQL del downgrade reduce `version_num` a `VARCHAR(32)`,
- SQLite puede avanzar y retroceder sin alterar la columna,
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
And comprueba que existe una sola head `0023_physical_counts`.
