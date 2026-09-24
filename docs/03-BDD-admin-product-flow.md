# BDD - Configuración confiable de productos

## BDD-FEAT-113 ADMIN-PROD-001 alta, edición y verificación de productos

```gherkin
@PRD-FR-243 @PRD-FR-244 @catalog @admin @r3
Feature: Configurar productos sin guardados parciales ni datos simulados

  @BDD-SC-517
  Scenario: Crear producto y subgrupo como una sola intención
    Given un Administrador corporativo autenticado con `catalog.manage`
    And existe un grupo con selector de subgrupos activo y cobertura incompleta
    When captura nombre en mayúsculas, clave numérica única, grupo, subgrupo activo, precio positivo y estación canónica
    And guarda con una `Idempotency-Key`
    Then Python crea producto, precio vigente, asignación de subgrupo, auditoría y resultado del comando en una sola transacción
    And la respuesta contiene únicamente valores persistidos y la versión observada
    And el borrador es sustituido por el producto confirmado

  @BDD-SC-518
  Scenario: Fallar sin producto parcial cuando el subgrupo no es válido
    Given un Administrador captura un producto para un grupo con subgrupos activos
    When envía un subgrupo inactivo, inexistente o perteneciente a otro grupo
    Then el backend responde con un código de dominio estable
    And no crea ni modifica producto, precio, asignación, disponibilidad o auditoría de éxito
    And la interfaz conserva el borrador y muestra el error sin anunciar guardado

  @BDD-SC-519
  Scenario: Reintentar y competir sin duplicar ni sobrescribir
    Given una intención de configuración fue confirmada pero su respuesta se perdió
    When se repite la misma clave con el mismo contenido
    Then devuelve el mismo producto y no duplica precio, asignación ni auditoría
    When se reutiliza la clave con contenido diferente
    Then responde `idempotency_key_conflict` sin escribir
    When dos ediciones parten del mismo `expected_updated_at`
    Then sólo una puede confirmar y la otra responde `product_configuration_version_conflict`

  @BDD-SC-520
  Scenario: Capturar únicamente datos con persistencia canónica
    Given el editor carga un producto nuevo o existente
    Then cada control editable corresponde a un campo aceptado y devuelto por el contrato vigente
    And una etiqueta visible de estación se traduce a `kitchen`, `drinks` o `packing`
    And no aparecen importes, canales, monedero, comisiones o códigos inventados como defaults locales
    And campos aún no gobernados no se envían ni se confirman como guardados

  @BDD-SC-521
  Scenario: Consultar una receta real o un estado vacío verificable
    Given existe un producto persistido
    When el administrador abre Receta
    Then la interfaz consulta la receta efectiva del alcance autorizado
    And muestra su versión y procedencia cuando existe
    But si no existe muestra un estado vacío y no ingredientes, costos o márgenes de demostración
    And sólo ofrece editar cuando el actor conserva `recipes.manage`

  @BDD-SC-522
  Scenario: Verificar el producto contra la proyección real del POS
    Given el producto fue guardado y el administrador seleccionó una sucursal autorizada
    When solicita Ver en POS
    Then el backend evalúa el producto mediante la proyección canónica de esa sucursal
    And devuelve el grupo, subgrupo y elegibilidad reales
    And si no es vendible muestra un motivo estable y accionable
    And la navegación no crea pedido, no agrega carrito y no cambia disponibilidad

  @BDD-SC-523
  Scenario: Conservar un borrador distinguible y navegación accesible
    Given el administrador inicia un producto nuevo
    Then la lista lo identifica como Borrador sin guardar y no como registro confirmado
    And no le asigna una clave aleatoria en el navegador
    When recorre las secciones con teclado, flechas, indicadores de página o vista estrecha
    Then la sección activa permanece visible, enfocada y asociada a su panel
    And cambiar la página visual de pestañas no cambia por sí mismo el contenido activo
    And salir con cambios pendientes solicita confirmación

  @BDD-SC-525
  Scenario: Seleccionar otro producto muestra su detalle principal
    Given el administrador consulta o edita un producto de la lista maestra
    When selecciona otro producto y, si aplica, confirma descartar el borrador anterior
    Then la edición anterior termina antes de cambiar la selección
    And Principal / Varios muestra nombre, clave, grupo, precio, estación y estado del producto seleccionado
    But si rechaza descartar los cambios conserva el producto y el borrador actuales

  @BDD-SC-526
  Scenario: Crear grupos y subgrupos sin perder el alta de producto
    Given el administrador captura un producto nuevo o edita uno existente
    When abre el alta rápida de Grupo desde el botón más
    Then permanece en Productos y conserva todos los campos del borrador
    And al guardar el grupo canónico éste queda seleccionado en el producto
    When abre el alta rápida de Subgrupo con un grupo seleccionado
    Then el diálogo muestra y conserva fijo ese grupo como contexto
    And al guardar el subgrupo canónico éste queda seleccionado en el producto
    But si cancela, cierra o la API rechaza el alta, el borrador del producto no cambia

  @BDD-SC-524
  Scenario: Diferenciar catálogo corporativo y contexto de sucursal
    Given el Administrador abre Productos sin una sucursal seleccionada
    Then puede configurar los datos corporativos autorizados
    And la interfaz no afirma que una sucursal o almacén estén seleccionados
    But Ver en POS y la receta efectiva local permanecen deshabilitados con una explicación
    When selecciona una sucursal autorizada
    Then sólo la vista previa y el alcance local de receta usan ese contexto
```
