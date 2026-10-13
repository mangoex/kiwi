# BDD de asistencia de compras y extracción

```gherkin
@PRD-FR-275
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
```
