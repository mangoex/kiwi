# BDD - Frontend de administración operativa por sucursal en el POS

## BDD-FEAT-051 Centro administrativo de sucursal dentro del POS

```gherkin
@PRD-FR-005 @PRD-FR-008 @PRD-FR-017 @PRD-FR-018 @PRD-FR-019 @pos @branch @frontend
Feature: El Supervisor administra su sucursal dentro del POS sin entrar al admin corporativo

  @BDD-SC-125
  Scenario: La sesión canónica reemplaza los permisos guardados localmente
    Given un Supervisor que abre el POS con un token válido
    When el frontend llama a GET /api/v1/auth/session
    Then obtiene usuario, roles, permisos, alcance y active_branch desde PostgreSQL
    And no confía en el objeto user de localStorage ni en is_superadmin
    And el active_branch.id reemplaza cualquier branch_id local para scope branch

  @BDD-SC-126
  Scenario: Supervisor ve Administración dentro del POS
    Given un Supervisor con permiso branch.admin.access
    When el POS carga la sesión canónica
    Then el menú Administración es visible
    And las tarjetas de productos, insumos, sucursal activa y personal son navegables dentro del layout POS

  @BDD-SC-127
  Scenario: Cajero no ve ni abre Administración
    Given un Cajero sin branch.admin.access
    When el POS carga la sesión canónica
    Then el menú Administración no es visible
    And si escribe /pos/administration directamente recibe acceso denegado o redirección a /pos/pos

  @BDD-SC-128
  Scenario: Ninguna tarjeta abandona el layout POS
    Given un Supervisor en el centro de administración
    When selecciona cualquier tarjeta habilitada
    Then la navegación usa Link o useNavigate dentro de PosLayout
    And no hay enlaces a /admin ni window.location hacia módulos corporativos

  @BDD-SC-129
  Scenario: La disponibilidad local hereda, cambia y vuelve a heredar
    Given un Supervisor con catalog.branch.manage en su sucursal
    When consulta los productos del catálogo
    Then ve la disponibilidad efectiva y la fuente (central o excepción local)
    When marca un producto como no disponible
    Then se actualiza sólo branch_product_availability de su sucursal
    When vuelve a heredar
    Then se elimina la excepción local y la disponibilidad vuelve al valor central

  @BDD-SC-130
  Scenario: El personal de sucursal es sólo lectura
    Given un Supervisor con branch.staff.read
    When consulta el personal de su sucursal
    Then ve nombre, correo, estado y roles informativos
    And no hay botones para crear, editar ni eliminar usuarios
    Y la administración de cuentas corresponde al administrador corporativo

  @BDD-SC-131
  Scenario: La configuración usa la sucursal canónica
    Given un Supervisor con scope branch
    When abre la configuración del POS
    Then la sucursal mostrada es el active_branch de la sesión canónica
    And no hay selector de sucursal
    Y el identificador de caja conserva su configuración local

  @BDD-SC-132
  Scenario: Los modificadores envían Bearer mediante fetchApi
    Given un Supervisor operando el POS
    When selecciona un producto con modificadores
    Then la petición de modificadores usa fetchApi con Authorization Bearer
    Y no usa un fetch directo sin cabecera de autenticación
```
