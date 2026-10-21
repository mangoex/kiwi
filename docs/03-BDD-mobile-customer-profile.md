# BDD — Acceso y perfil móvil

## BDD-FEAT-153 CRM-MOBILE-001

```gherkin
@PRD-FR-281 @PRD-FR-282
Feature: Consultar y pedir con identidad propia

  @BDD-SC-740
  Scenario: Alta mínima con cumpleaños parcial
    Given un visitante sin sesión móvil
    When crea su cuenta con teléfono y contraseña y registra nombre y cumpleaños sin año
    Then puede consultar el menú y el CRM conserva día y mes sin inventar año

  @BDD-SC-741
  Scenario: Acceso y aislamiento
    Given una contraseña incorrecta, una sesión vencida o un límite agotado
    When intenta acceder o editar un perfil ajeno
    Then no obtiene sesión ni datos personales
    And una sesión móvil no autoriza endpoints de empleados

  @BDD-SC-742
  Scenario: No reclamar CRM por teléfono capturado
    Given un teléfono con coincidencias históricas en la organización
    When se registra una nueva cuenta con contraseña
    Then obtiene un perfil propio vacío sin revelar ni modificar las coincidencias
    And si ya hay una cuenta móvil el registro no reemplaza sus credenciales

  @BDD-SC-743
  Scenario: Delivery y consumo histórico
    Given un perfil móvil completo y carrito
    When elige delivery sin correo o domicilio completo
    Then se rechaza sin perder el carrito ni crear una orden
    When completa esos datos y la intención es aceptada
    Then el pedido se vincula al cliente y conserva los snapshots al editar el perfil

  @BDD-SC-744
  Scenario: Editar perfil y teléfono
    Given un cliente con sesión
    When edita cumpleaños, correo y domicilio propios
    Then el CRM recibe los cambios válidos
    And cambiar teléfono o contraseña requiere la contraseña actual sin tomar otra identidad
    And revoca las sesiones anteriores y conserva el historial
    And un servicio indisponible impide mostrar el formulario como si estuviera operativo
```
