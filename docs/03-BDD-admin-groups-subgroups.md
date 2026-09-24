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
    And consulta y edita los subgrupos canónicos del grupo en la misma estación
    And ve los productos del grupo con su asignación explícita o su estado incompleto

  @BDD-SC-512
  Scenario: Conservar compatibilidad con un grupo sin subgrupos
    Given un grupo no tiene selector previo configurado
    When el administrador consulta su detalle
    Then la estación indica que los subgrupos son opcionales
    And permite habilitarlos sin crear una jerarquía paralela
    And POS sigue mostrando directamente sus productos mientras el selector no esté activo

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
