# BDD — modificadores compartidos por productos

## BDD-FEAT-128 Configurar una vez y aplicar a varios productos

```gherkin
@PRD-FR-262 @modifiers @catalog @admin @r3
Feature: Administrar modificadores compartidos por alcance de productos

  @BDD-SC-592
  Scenario: Crear una configuración compartida para productos seleccionados
    Given un Administrador corporativo con catalog.manage
    When crea un set, selecciona productos activos por categoría y guarda grupos y opciones
    Then el backend persiste árbol y alcance de forma versionada e idempotente
    And los mismos IDs de opción aparecen en ventas nuevas de cada producto relacionado
    And un producto que nunca fue relacionado no recibe opciones de ese set

  @BDD-SC-593
  Scenario: Editar una vez para todos los productos relacionados
    Given un set vigente relacionado con varias ensaladas
    When cambia el precio o la instrucción y confirma la versión esperada
    Then todas las ensaladas relacionadas usan el cambio en ventas nuevas
    And una versión obsoleta o una clave reutilizada con otro cuerpo falla sin escritura parcial

  @BDD-SC-594
  Scenario: Reemplazar el alcance sin alterar historia
    Given una venta aceptada congeló una opción compartida
    When el Administrador retira un producto y agrega otro al set
    Then el producto retirado ya no ofrece la opción y el nuevo sí
    And la venta y su snapshot histórico permanecen idénticos

  @BDD-SC-595
  Scenario: Mantener separadas las autoridades de catálogo
    When el Administrador edita un set compartido
    Then no puede agregar un producto componente seleccionable
    And comentarios, ingredientes adicionales, combo fijo y composición propia no son modificados

  @BDD-SC-596
  Scenario: Seleccionar alcance por categoría y producto
    Given existen categorías con productos activos
    When abre Modificadores desde Catálogo y Menú
    Then puede expandir categorías y marcar productos individuales o todos los de una categoría
    And ve el alcance a la izquierda y la creación o configuración de modificadores a la derecha
    And si intenta crear sin nombre o productos la interfaz explica qué falta sin enviar el comando
    And la interfaz comunica selección vacía, parcial o completa y conserva el borrador ante error

  @BDD-SC-597
  Scenario: Usar una sola superficie administrativa
    Given un producto recibe uno o más sets compartidos
    When abre el detalle del producto
    Then no ve una sección Modificadores / Producto compuesto ni un editor local
    And administra los modificadores exclusivamente desde Catálogo y Menú > Modificadores
    And la compatibilidad de dominio existente no crea una segunda superficie visible

  @BDD-SC-598
  Scenario: Cobrar desde la primera selección sin inclusión implícita
    Given el Administrador agrega un grupo nuevo con máximo uno y una opción de 15 pesos
    When guarda la configuración sin declarar selecciones incluidas
    Then el grupo persiste con cero selecciones incluidas
    And la POS comunica un recargo de 15 pesos para esa opción
    And cotización, pedido y pago conservan el total base más 15 pesos
    But si el Administrador declara explícitamente una selección incluida
    Then la POS comunica que no hay recargo y Python congela precio aplicado cero
  @BDD-SC-614
  Scenario: Conservar paquetes offline legados sin omitir modificadores compartidos
    Given un paquete firmado v1, v2 o v3 con grupos ligados a productos
    When el gateway actualizado lo hidrata o renueva su esquema local
    Then conserva las filas históricas y puede cotizar, cobrar y producir con el catálogo congelado
    But si el catálogo a exportar contiene una asignación compartida activa a un set activo
    Then rechaza la emisión antes de firmar o instalar un catálogo incompleto
    And informa offline_shared_modifiers_unsupported sin omitir requisitos ni recargos
```
