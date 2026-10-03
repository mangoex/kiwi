# BDD - Ajustes de usabilidad en compras y POS

## BDD-FEAT-124 Compra por proveedor y excepción urgente

```gherkin
@PRD-FR-249 @PRD-FR-251 @purchases @inventory @r3
Feature: Identificar productos del proveedor y registrar una urgencia trazable

  @BDD-SC-574
  Scenario: Mostrar productos y presentaciones relacionadas con el proveedor
    Given un proveedor seleccionado y presentaciones activas autorizadas
    When el usuario agrega una partida
    Then el selector agrupa por identidad de insumo y etiqueta nombre más SKU
    And muestra sus presentaciones del proveedor
    And no ofrece relaciones de otro proveedor mientras la excepción está apagada

  @BDD-SC-575
  Scenario: Registrar una compra urgente con presentación de otro proveedor
    Given que el proveedor real no tiene registrada la presentación necesaria
    When el usuario activa Compra excepcional, escribe un motivo y selecciona una presentación canónica ajena
    Then Python valida y calcula la compra con el insumo y conversión congelados
    And el documento conserva proveedor real, proveedor de catálogo, motivo y marca de excepción
    And confirmar no cambia precio, historial ni relación de la presentación ajena
    But sin casilla o sin motivo se rechaza sin efectos
```

## BDD-FEAT-126 Jerarquía cromática del catálogo POS

```gherkin
@PRD-FR-260 @pos @visual @r1
Feature: Distinguir clasificaciones y contenido con una paleta coherente

  @BDD-SC-578
  Scenario: Mostrar colores sólidos en el menú superior
    Given los cinco grupos canónicos del catálogo POS
    When se presenta el menú superior
    Then cada grupo conserva un color sólido estable con icono y etiqueta legibles
    And el grupo activo mantiene aria-pressed y una indicación adicional al color

  @BDD-SC-579
  Scenario: Heredar la variante pastel del grupo seleccionado
    Given que el usuario selecciona Todo, Alimentos, Bebidas, Otros o Favoritos
    When consulta grupos, subgrupos o productos en el centro
    Then el centro usa la variante pastel correspondiente al grupo superior activo
    And no cambia clasificación, selección, favoritos, precio ni carrito
```

## BDD-FEAT-125 Apariencia del catálogo POS

```gherkin
@PRD-FR-259 @pos @admin @r3
Feature: Controlar los visuales centrales del catálogo por sucursal

  @BDD-SC-576
  Scenario: Ocultar visuales centrales y aumentar legibilidad
    Given un usuario con admin.manage en una sucursal
    When desactiva Mostrar iconos e imágenes en grupos y productos
    Then la preferencia se persiste y audita en esa sucursal
    And grupos, subgrupos y productos centrales omiten sus visuales y muestran texto mayor
    And los iconos del menú superior permanecen visibles

  @BDD-SC-577
  Scenario: Conservar valor compatible y autoridad
    Given una sucursal sin una preferencia histórica
    Then la sesión muestra visuales por omisión
    And un gateway SQLite existente incorpora la columna al renovar su bundle
    When un actor sin admin.manage intenta cambiarla
    Then se rechaza sin modificar la sucursal ni emitir éxito
```
