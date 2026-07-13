# BDD - Importación de catálogos heredados por sucursal

## BDD-FEAT-053 Migración trazable de Constitución

```gherkin
@PRD-FR-190 @PRD-FR-191 @PRD-FR-197 @import @branch
Feature: Importar datos heredados sin mezclar sucursales ni duplicar reintentos

  @BDD-SC-144
  Scenario: Un lote identifica sucursal y fuentes
    Given un administrador corporativo y la sucursal Constitución
    When inicia un lote con manifiesto y checksum por archivo
    Then el lote conserva origen, sucursal, actor y conteos
    And repetir el mismo manifiesto no crea otro lote ni otro destino

  @BDD-SC-145
  Scenario: Productos sin estación quedan en revisión
    Given una fila válida de PRODUCTOS con precio e impuestos consistentes
    But el archivo no contiene estación de producción
    When se importa la fila
    Then se conserva el producto con alcance Constitución y estado needs_review
    And el producto es visible en administración pero no es vendible en POS

  @BDD-SC-146
  Scenario: Insumos no alteran existencias ni costo promedio
    Given una fila de INSUMOS con unidad y costos heredados
    When se materializa el insumo para Constitución
    Then se crea o vincula el catálogo del insumo y se conserva el costo como referencia del lote
    And no se crea movimiento, saldo inicial, recepción ni costo promedio contable

  @BDD-SC-147
  Scenario: Presentación incompleta permanece pendiente
    Given una fila de PRESENTACIONES sin proveedor
    When se importa la fila
    Then queda needs_review vinculada al insumo cuando sea posible
    And no se crea purchase_presentation con un proveedor ficticio

  @BDD-SC-148
  Scenario: Archivo de recetas sin componentes se rechaza con evidencia
    Given un archivo RECETAS cuyas columnas y filas son las de PRODUCTOS
    When se valida la fuente
    Then sus filas quedan needs_review con razón missing_recipe_components
    And no se crea una receta vacía

  @BDD-SC-149
  Scenario: Clientes se aíslan y consultan por página
    Given clientes heredados de Constitución
    When un actor autorizado consulta el directorio con búsqueda, limit y offset
    Then sólo recibe clientes centrales o de su sucursal autorizada
    And la respuesta contiene total, limit, offset e items sin consultas por cliente

  @BDD-SC-150
  Scenario: Otra sucursal no recibe datos exclusivos
    Given un producto, insumo o cliente importado con alcance Constitución
    When un Supervisor de otra sucursal consulta su catálogo
    Then el registro no aparece aunque conozca su identificador

  @BDD-SC-151
  Scenario: Ajustes respetan autoridad y alcance
    Given un registro importado que requiere revisión
    When el administrador corporativo completa su configuración o el Supervisor ajusta un registro propio permitido
    Then el backend vuelve a validar permiso y sucursal
    And registra auditoría con valores anteriores y nuevos
```
