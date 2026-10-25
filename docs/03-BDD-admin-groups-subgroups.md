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
    Then el navegador envía una sola intención de configuración al backend
    And Python valida y persiste producto, precio y asignación explícita `producto-grupo-valor`
    And todas las escrituras se confirman en una sola transacción
    And no conserva catálogos de subgrupos simulados en memoria del navegador
    And un error de asignación queda visible sin conservar una escritura parcial ni presentar éxito

  @BDD-SC-514
  Scenario: Capturar un pedido con lenguaje Grupo y Subgrupo
    Given un grupo del POS tiene un selector previo activo
    When el cajero abre el grupo
    Then la etapa siguiente se presenta como Subgrupos
    And elegir un subgrupo filtra productos concretos sin agregar una línea al carrito
    And cambiar grupo o subgrupo conserva carrito y búsqueda conforme al contrato vigente

  @BDD-SC-802
  Scenario: Explicar un subgrupo vacío y comenzar un producto en su contexto
    Given un grupo contiene un subgrupo activo sin productos asignados
    When el administrador revisa Grupos y subgrupos
    Then ve el conteo cero y la advertencia de que ese subgrupo no aparecerá en POS
    When elige Crear producto en ese subgrupo
    Then Productos abre un borrador nuevo con grupo y subgrupo canónicos preseleccionados
    And guardar continúa sujeto a precio, estación, estado y validación transaccional del backend

  @BDD-SC-803
  Scenario: Eliminar configuración incorrecta sin borrar productos implícitamente
    Given un administrador corporativo con `catalog.manage`
    And un grupo contiene una configuración incorrecta de subgrupos
    When intenta eliminar un subgrupo con productos asignados
    Then el comando se rechaza sin mutación parcial y exige reasignar primero
    When oculta del POS la configuración y confirma eliminar todos los subgrupos
    Then Python elimina atómicamente asignaciones, valores y selector técnico
    And conserva los productos concretos del grupo
    When intenta eliminar el grupo mientras todavía contiene productos
    Then el comando se rechaza con un error estable
    But un grupo vacío puede eliminarse con confirmación y auditoría
```
