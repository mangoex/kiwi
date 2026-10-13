# BDD - Compras corporativas distribuidas

## BDD-FEAT-135 Orden central con recepción por almacén

```gherkin
@PRD-FR-274 @purchases @inventory @R3
Feature: Comprar corporativamente y recibir en cada sucursal

  @BDD-SC-669
  Scenario: Crear y aprobar sin afectar inventario ni caja
    Given un actor con permiso corporativo elige una razón social y proveedor
    And distribuye exactamente cada partida entre almacenes de sucursales de esa razón social
    When crea y aprueba la orden
    Then la orden queda aprobada con sus snapshots y asignaciones
    And no se crea inventario costo historial local ni movimiento de caja
    And catálogo inactivo local ajeno o total fuera de Numeric(18,6) rechaza sin crear orden

  @BDD-SC-670
  Scenario: Recibir parcialmente en un destino
    Given una orden aprobada asigna diez unidades base al almacén de Centro
    When Centro recibe cuatro con una clave idempotente
    Then se crea una recepción y movimiento por cuatro sólo en Centro
    And se actualizan costo promedio e historial local de Centro
    And la orden queda parcialmente recibida con seis pendientes

  @BDD-SC-671
  Scenario: Completar recepciones distribuidas
    Given una orden parcialmente recibida conserva saldos en dos destinos
    When cada almacén confirma exactamente sus cantidades restantes
    Then cada movimiento conserva su sucursal y almacén
    And la orden queda recibida sin mezclar costos entre destinos
    And la suma base y costo de destinos coincide exactamente con los targets congelados de la partida
    And cuatro destinos de un costo mínimo nunca generan costo ni promedio negativo

  @BDD-SC-672
  Scenario: Reintento y carrera no duplican recepción
    Given una asignación tiene cantidad pendiente
    When se repite la misma clave o dos recepciones compiten por más de lo pendiente
    Then el replay devuelve el mismo resultado
    And como máximo una intención confirma dentro del saldo
    And no existe movimiento costo o auditoría duplicada
    And misma clave con URL de otra orden falla conflicto sin devolver el recurso anterior
    And campos desconocidos y versión booleana fallan antes de confirmar un comando
    And una respuesta perdida o recarga conserva la misma clave y cuerpo congelados por actor
    And un intento incierto impide iniciar otra mutación hasta recuperar su resultado

  @BDD-SC-673
  Scenario: Alcance y destino inválidos fallan sin efectos
    Given una orden pertenece a una organización y razón social
    When un rol local o una sucursal almacén proveedor o presentación ajenos intentan operar
    Then la API rechaza con código estable
    And no expone ni modifica datos fuera del alcance autorizado
    But un actor organizacional con sólo lectura consulta órdenes proveedores y presentaciones
    And no ve ni puede ejecutar acciones de mutación
    And un comprador local no ve historial de precios originado en otra sucursal

  @BDD-SC-676
  Scenario: Una parcial menor que la precisión base no deja saldo imposible
    Given una asignación usa la cantidad base mínima representable
    When se intenta recibir una fracción que agotaría la cantidad base pero no la comercial
    Then la API rechaza con corporate_purchase_quantity_below_base_precision antes de efectos
    But recibir la asignación comercial completa continúa permitido

  @BDD-SC-674
  Scenario: Cancelar sólo un borrador sin recepciones
    Given una orden corporativa continúa en borrador
    When un actor corporativo la cancela con motivo
    Then conserva orden líneas asignaciones y auditoría y queda cancelada
    But una orden aprobada o con recepción no se borra ni cancela como borrador
    And un plan legacy inconsistente bloquea aprobación o recepción sin recalcular historia

  @BDD-SC-675
  Scenario: Compras corporativas y de sucursal son acciones distintas
    Given el usuario abre Compras desde Administración
    Then elige Compra corporativa o Compra de sucursal
    And la corporativa no muestra caja turno ni una sucursal global de cabecera
    And la de sucursal identifica el contexto activo y conserva las reglas de efectivo
    And recibir muestra insumo SKU presentación y unidades con cantidad explícita y confirmación
    And borrar la cantidad no recibe automáticamente todo el pendiente
    And el POS sólo enlaza a Administración sin duplicar el editor corporativo
```
