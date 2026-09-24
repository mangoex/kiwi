# BDD - Grupos y subgrupos integrados

## BDD-FEAT-111 ADMIN-CAT-005 estación integrada de grupos y subgrupos

```gherkin
@PRD-FR-213 @PRD-FR-229 @catalog @admin @pos @ux
Feature: Administrar y consumir grupos y subgrupos con el lenguaje operativo del restaurante

  @BDD-SC-511
  Scenario: Administrar grupo, subgrupos y cobertura sin cambiar de catálogo
    Given un administrador corporativo con `catalog.manage`
    When abre Grupos y subgrupos
    Then selecciona el grupo en una lista maestra
    And edita nombre, orden y estado del grupo en el panel de detalle
    And crea o edita cada subgrupo capturando únicamente su nombre visible
    And Python genera o conserva código, orden, relación y estado técnicos
    And ve los productos del grupo con su asignación explícita o su estado incompleto

  @BDD-SC-512
  Scenario: Conservar compatibilidad con un grupo sin subgrupos
    Given un grupo no tiene selector previo configurado
    When el administrador consulta su detalle
    Then la estación indica que los subgrupos son opcionales
    And permite crear el primer subgrupo por nombre sin configurar un nivel técnico
    And POS sigue mostrando directamente sus productos mientras el selector no esté activo

  @BDD-SC-516
  Scenario: Publicar subgrupos con una sola acción visible
    Given el grupo tiene subgrupos y todos sus productos activos cuentan con asignación válida
    When el administrador elige Mostrar subgrupos en POS
    Then Python activa el selector canónico después de validar la cobertura
    And la interfaz no presenta en paralelo nombre del nivel, código interno ni estado del nivel
    When el administrador elige Ocultar subgrupos del POS
    Then Python conserva subgrupos y asignaciones y cambia únicamente el estado del selector

  @BDD-SC-513
  Scenario: Asignar desde Productos un subgrupo persistido por Python
    Given un producto pertenece a un grupo con subgrupos canónicos
    When el administrador selecciona un subgrupo y guarda el producto
    Then el navegador actualiza el producto mediante la API existente
    And solicita al backend la asignación explícita `producto-grupo-valor`
    And no conserva catálogos de subgrupos simulados en memoria del navegador
    And un error de asignación queda visible sin presentar la operación completa como exitosa

  @BDD-SC-514
  Scenario: Capturar un pedido con lenguaje Grupo y Subgrupo
    Given un grupo del POS tiene un selector previo activo
    When el cajero abre el grupo
    Then la etapa siguiente se presenta como Subgrupos
    And elegir un subgrupo filtra productos concretos sin agregar una línea al carrito
    And cambiar grupo o subgrupo conserva carrito y búsqueda conforme al contrato vigente
```
