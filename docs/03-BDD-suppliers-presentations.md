# BDD - Proveedores y presentaciones de compra

## BDD-FEAT-036 Proveedores centrales y conversiones por presentación

```gherkin
@PRD-FR-091 @PRD-FR-092 @suppliers
Feature: Administrar proveedores y contactos operativos

  @BDD-SC-075
  Scenario: Registrar proveedor con contactos distintos
    Given el administrador opera el catálogo central
    When registra un proveedor y contactos para pedidos, facturación y cobranza
    Then conserva cada contacto por separado
    And puede marcar responsables principales por función
    And registra auditoría de las altas

  @BDD-SC-076
  Scenario: Habilitar proveedor en una sucursal
    Given existe un proveedor central
    When el administrador lo habilita para una sucursal con tiempo de entrega particular
    Then otras sucursales no heredan silenciosamente esa condición particular

  @BDD-SC-704
  Scenario: Consultar el expediente completo de un proveedor en el panel lateral
    Given el administrador abrió el detalle de un proveedor del catálogo
    When el contenido supera la altura disponible de la pantalla
    Then puede recorrer verticalmente todo el expediente dentro del panel
    And conserva visibles el encabezado y las acciones de cierre o guardado
    And puede expandir o contraer las secciones aun en modo de consulta
    And los campos tienen etiquetas separadas y se adaptan a una columna en móvil
    And conserva los días de crédito registrados aunque su valor sea cero
    And distingue los proveedores activos, inactivos y suspendidos en el listado y el detalle
    And no muestra facturas, saldos, vencimientos ni proyecciones de demostración
    And distingue información financiera no disponible de una deuda igual a cero
    And un error de consulta ofrece reintento sin presentarse como un catálogo vacío
```

## BDD-FEAT-037 Presentaciones y precio informativo

```gherkin
@PRD-FR-061 @PRD-FR-062 @PRD-FR-093 @PRD-FR-094 @purchasing
Feature: Convertir presentaciones de compra a unidad base

  @BDD-SC-077
  Scenario: Registrar bolsa de azúcar de diez kilogramos
    Given azúcar usa kilogramo como unidad base
    When se registra una bolsa con contenido aprovechable de 10 kg y precio base neto de 280 pesos
    Then la presentación informa 28 pesos por kilogramo
    And conserva el precio como baseline corporativo en su historial
    And no genera movimiento ni cambia costo promedio de inventario
    When una recepción de la sucursal A confirma otro precio
    Then conserva ese precio e historial efectivo sólo para A
    And la sucursal B mantiene su propio historial o el baseline corporativo

  @BDD-SC-078
  Scenario: Rechazar conversión inválida
    Given existe un artículo medido en masa
    When se intenta usar una unidad base incompatible sin equivalencia autorizada
    Then el sistema rechaza la presentación

  @BDD-SC-739
  Scenario: Corregir proveedor y unidad comercial de una presentación heredada
    Given una presentación central pertenece a PROVEEDOR GENERAL y tiene compras con snapshot
    When el administrador selecciona proveedor activo y unidad comercial de la organización
    Then guarda las nuevas referencias con control de versión y auditoría antes y después
    And conserva insumo, unidad base, código, compras, conteos, historial y costos de inventario
    And una compra pendiente conserva su proveedor y conversión originales al confirmarse
    And una edición desactualizada se rechaza sin efectos
    And cambiar sólo el proveedor no modifica magnitudes ni recalcula el costo guardado
    And una discrepancia heredada de contenido se señala y requiere corrección explícita
    And el preview de edición coincide con el costo que se guardará
    And los campos intactos conservan precisión interna y la captura manual admite dos decimales
```
