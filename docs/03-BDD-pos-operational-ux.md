# BDD - POS operativo en español, clientes y domicilios

## BDD-FEAT-055 Experiencia operativa del POS en español

```gherkin
@PRD-FR-019 @PRD-FR-020 @PRD-FR-024 @PRD-FR-031 @PRD-FR-032 @PRD-FR-034 @PRD-FR-070 @PRD-FR-195 @PRD-NFR-018 @pos @ux
Feature: El POS es operativa y visualmente íntegro en español con búsqueda y domicilios funcionales

  @BDD-SC-156
  Scenario: Todo el POS visible está en español y no muestra controles muertos
    Given un cajero o supervisor que abre el Punto de Venta
    When la interfaz carga
    Then todas las etiquetas visibles están en español de México
    And no se muestran botones sin implementación como Tables, Discount ni Save Bill
    And no se muestra Voucher sin comportamiento real

  @BDD-SC-157
  Scenario: Buscar cliente por teléfono devuelve coincidencias exactas de la sucursal
    Given un cajero en el checkout del POS
    When completa un teléfono mexicano válido
    Then se realiza una búsqueda remota y paginada en la sucursal canónica
    And la búsqueda usa el teléfono normalizado como criterio exacto
    And las coincidencias telefónicas múltiples no se fusionan

  @BDD-SC-158
  Scenario: Seleccionar cliente conserva la selección aunque cambie la búsqueda
    Given un cajero que ha seleccionado un cliente en el checkout
    When cambia el texto de búsqueda o se limpian los resultados
    Then el cliente seleccionado se conserva en el pedido
    And el domicilio seleccionado se mantiene

  @BDD-SC-159
  Scenario: Un cliente importado muestra su domicilio heredado sólo como referencia pendiente
    Given un cliente importado con legacy_address_reference
    When el cajero lo selecciona en el checkout
    Then se muestra el texto heredado como domicilio por confirmar
    And no se convierte automáticamente en un domicilio operativo
    And no se divide automáticamente en calle, número ni colonia

  @BDD-SC-160
  Scenario: Agregar un domicilio desde el checkout lo guarda y lo selecciona sin cerrar la venta
    Given un cajero con un cliente seleccionado y un carrito activo
    When agrega un domicilio estructurado desde el checkout
    Then el domicilio se guarda mediante POST /customers/{id}/addresses
    And se selecciona automáticamente como domicilio de entrega
    And el carrito, tipo de pedido y total se conservan

  @BDD-SC-161
  Scenario: Un pedido a domicilio exige cliente y domicilio activo perteneciente a ese cliente
    Given un cajero que intenta cobrar un pedido a domicilio
    When no hay cliente seleccionado o no hay domicilio activo
    Then el botón Cobrar está deshabilitado
    And se explica debajo qué falta
    When se selecciona un domicilio de otro cliente
    Then el backend rechaza con error de validación

  @BDD-SC-162
  Scenario: Inventario muestra existencia teórica de la sucursal canónica
    Given un supervisor o cajero que abre la pantalla de Inventario
    When la pantalla carga usando session.active_branch.id
    Then se consulta únicamente /inventory/stock con el branch_id canónico
    And se distingue existencia positiva, cero y negativa
    And no se aplica un umbral arbitrario de stock bajo

  @BDD-SC-231
  Scenario: El POS prioriza menú, productos y complementos sin desplazar la cuenta
    Given un cajero que abre el Punto de Venta
    When la interfaz carga en escritorio
    Then las categorías del menú se muestran en una franja horizontal superior
    And los accesos a productos aparecen inmediatamente debajo
    And los complementos del producto seleccionado aparecen debajo del catálogo
    And la cuenta permanece fija a la derecha con total y acción Pagar
```
