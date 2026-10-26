# BDD de asistencia de compras y extracción

```gherkin
@PRD-FR-275 @PRD-FR-249
Feature: Asistencia con alcance autorizado y datos fieles
  @BDD-SC-677
  Scenario: Leer sugerencias y merma sólo dentro de la sucursal autorizada
    Given un actor con permisos actuales y una sucursal activa
    When solicita sugerencias o merma de esa sucursal
    Then cada consulta respeta organización y sucursal y catálogo local
    But un actor inactivo sin permiso o una sucursal ajena falla antes de leer datos

  @BDD-SC-678
  Scenario: Extraer una factura sin inventar importes ni partidas
    Given texto con Producto | 1 | $19.99
    When un actor autorizado solicita extracción
    Then devuelve cantidad decimal exacta y precio de 1999 centavos para revisión humana
    And una entrada vacía o ilegible no genera partidas proveedor ni folio ficticios
    And líneas con cantidad negativa o precio inválido requieren revisión explícita
    And la extracción no genera inventario caja cuentas por pagar ni emisión fiscal

  @BDD-SC-795
  Scenario: Autocompletar el borrador de nota de compra desde foto PDF XML o lista en papel
    Given una cuenta autorizada con permiso de compras abre Registrar nota de compra en su sucursal activa
    When sube una imagen PDF o XML de factura o pega una lista en papel con conceptos cantidades y precios
    Then el sistema extrae cabecera y partidas en Decimal exacto a dos decimales y concilia proveedor y presentaciones del catálogo de la sucursal
    And prellena el borrador editable marcando las partidas conciliadas de otro proveedor o sin conciliar para revisión humana
    And las partidas sin presentación conciliada conservan la descripción e importes extraídos hasta que el usuario seleccione la presentación
    And la extracción no guarda ni confirma la compra ni mueve inventario o caja hasta que el actor revise y ejecute Guardar borrador o Confirmar recepción
```
