# BDD - Administracion de usuarios y roles

## BDD-FEAT-029 Usuarios y roles operativos

```gherkin
@PRD-FR-005 @PRD-FR-007 @security @admin @phase1
Feature: Gestion basica de usuarios y roles

  @BDD-SC-043
  Scenario: Crear rol operativo
    Given existe la organizacion Kiwi Restaurante
    When el administrador crea un rol con nombre y alcance
    Then el sistema conserva el rol
    And evita duplicar otro rol con el mismo nombre
    And registra auditoria del alta

  @BDD-SC-044
  Scenario: Invitar usuario operativo
    Given existe la organizacion Kiwi Restaurante
    When el administrador registra nombre y correo del usuario
    Then el sistema crea el usuario en estado invitado
    And evita duplicar el mismo correo
    And registra auditoria del alta

  @BDD-SC-045
  Scenario: Asignar rol a usuario
    Given existe un usuario invitado
    And existe un rol operativo
    When el administrador asigna el rol al usuario
    Then el sistema conserva la relacion usuario-rol
    And permite alcance corporativo o de sucursal
    And registra auditoria de la asignacion
```
