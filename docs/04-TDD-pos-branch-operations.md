# TDD - Administración única desde POS

## TDD-TS-052 Acceso canónico y navegación administrativa

- `tests/frontend/test_admin_access.mjs`: política real de rutas, lectura/escritura,
  destinos internos, sucursal y perfiles parciales sin inferir autoridad de localStorage.
- `apps/api/tests/test_admin_unification.py`: capacidades compatibles con autorización,
  denegaciones 403 y disponibilidad explícita en dos sucursales, SQLite aislado.
- `apps/api/tests/test_admin_unification_postgres.py`: los mismos contratos en PostgreSQL
  desechable configurado en CI; la ausencia local de la variable se informa como omitida.
- `tests/architecture/test_pos_branch_operations.py`: ausencia de páginas duplicadas alcanzables,
  política compartida, guardas, disponibilidad y trazabilidad BDD-SC-136 a BDD-SC-143.
- Navegador: cuatro perfiles, rutas directas, regreso con captura, sucursal rechazada,
  caducidad, pérdida de permiso y cambio de cuenta; comandos sólo en base aislada.
- Typecheck/build de Admin y POS; lint/tipos Python focales; auditoría R3 independiente.

## TDD-TC-045 El acceso POS no amplía autoridad administrativa

Given una cuenta de sucursal o consulta con permisos parciales
When abre funciones desde POS o directamente desde Admin
Then utiliza una política compartida y las mismas páginas y comandos
And no monta datos ni acciones fuera de sus capacidades efectivas
And conserva sucursal, captura y rechazos canónicos sin depender de nombres de rol.
