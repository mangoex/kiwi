# TDD - Frontend de administración operativa por sucursal en el POS

## TDD-TS-051 Frontend de administración por sucursal

Casos vigentes:

- sesión canónica, rechazo de cuentas sin pos.operate, GET sólo de hidratación y selección validada
  exclusivamente mediante `POST /auth/branch-selections`;
- política compartida de tarjetas, guardas y destinos internos autorizados;
- disponibilidad local en las páginas canónicas con branch_id explícito;
- modificadores autenticados y alcance de sucursal sin confiar en localStorage.

La verificación de navegación, comandos y regreso se consolida en TDD-TS-052.

## TDD-TC-044 El frontend respeta la sesión canónica

Given una sesión validada por backend
When abre administración desde POS o Admin
Then menús y guardas usan capacidades efectivas y destino predefinido
And las peticiones dependientes de sucursal incluyen la sucursal validada.
