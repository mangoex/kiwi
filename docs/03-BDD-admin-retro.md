# BDD — Administración retro y hallazgos del sistema de referencia

## BDD-FEAT-108 Escritorio administrativo claro

```gherkin
@PRD-FR-237 @admin @retro
Feature: Administrar con apariencia retro monocromática

  @BDD-SC-489
  Scenario: Recorrer catálogos con el escritorio retro
    Given un usuario autenticado con permisos administrativos y sucursal seleccionada
    When abre Productos, Insumos, Presentaciones, Proveedores, Recetas y Almacenes
    Then conserva rutas, permisos y sucursal canónica
    And ve navegación clara, tablas y barras de herramientas en blanco, gris y negro
    And sus formularios y diálogos mantienen etiquetas, foco y estados textuales

  @BDD-SC-490
  Scenario: Conservar operabilidad en pantallas estrechas y con teclado
    Given la administración se presenta a 390, 768 o 1440 píxeles
    When el usuario navega con Tab y abre un formulario
    Then todas las acciones y campos permanecen accesibles
    And el foco es visible y los mensajes de carga, error y vacío son legibles
    And una tabla ancha se desplaza dentro de su contenedor sin desbordar la página

  @BDD-SC-491
  Scenario: Aislar el tema del resto de aplicaciones
    Given el tema administrativo está activo
    When se abren POS, KDS o el sitio móvil
    Then esas aplicaciones conservan sus estilos y comportamiento existentes
```

## BDD-FEAT-110 Combos fijos versionados

```gherkin
@PRD-FR-010 @PRD-FR-242 @production @inventory
Feature: Administrar y operar una oferta compuesta fija

  @BDD-SC-498
  Scenario: Versionar una composición válida sin alterar el pasado
    Given un administrador autorizado y productos activos del alcance
    When guarda un combo con cantidades enteras positivas de productos y versión esperada
    Then conserva una composición auditable y su precio propio canónico
    And rechaza productos ajenos, duplicados, cantidades fraccionarias o inválidas y combos anidados
    And una versión obsoleta o replay incompatible no crea una composición adicional
    And ante conflicto el editor conserva el borrador y permite revisar la composición vigente
    And sólo tras esa revisión explícita puede reintentar con la nueva versión esperada

  @BDD-SC-499
  Scenario: Aceptar y preparar un combo de cocina y bebidas
    Given un combo fijo con hamburguesa y bebida y recetas efectivas vigentes
    When acepta dos unidades del combo con un comando idempotente
    Then cobra dos veces el precio del combo sin sumar los precios de sus componentes
    And congela composición y recetas y reserva una sola vez las cantidades exactas
    And cocina y bebidas reciben sus respectivas tareas conforme a BDD-SC-004
    And empaque espera que ambas estaciones terminen

  @BDD-SC-500
  Scenario: Conservar consumo histórico ante edición y cancelación
    Given un combo aceptado cuya composición o recetas cambiaron posteriormente
    When se edita o cancela el pedido antes o después de producción
    Then aplica las transiciones y compensaciones canónicas sobre sus snapshots
    And no reescribe importes históricos ni duplica reservas, consumo o liberaciones

  # Incremento posterior acordado: fuera de ADMIN-RETRO-001; no implementado ni aprobado.
  @BDD-SC-501
  Scenario: Conservar un combo durante operación local y sincronización
    Given una sucursal operativa en SQLite con el catálogo efectivo sincronizado
    When acepta y prepara un combo y repite su sincronización con PostgreSQL
    Then conserva identidad, precio, snapshots y transiciones del pedido
    And no duplica tareas, reservas, consumo ni cobros
```

## BDD-FEAT-109 Capacidades administrativas derivadas de pantallas

```gherkin
@PRD-FR-238 @admin
Feature: Prioridades administrativas independientes

  @BDD-SC-492
  Scenario: Consultar e imprimir con órdenes distintos
    Given categorías activas y un administrador autorizado
    When guarda una prioridad de consulta y otra de impresión
    Then la consulta administrativa y la impresión del catálogo usan sus respectivos órdenes
    And POS conserva sus grupos y orden comercial
    And una versión obsoleta, un ID ajeno, omitido o repetido se rechaza sin cambiar órdenes

@PRD-FR-239 @recipes
Feature: Versionar recetas en lote

  @BDD-SC-493
  Scenario: Revisar y aplicar una composición a varios productos
    Given productos autorizados y componentes válidos en el mismo alcance
    When solicita vista previa
    Then ve diferencias y versiones esperadas sin crear recetas ni movimientos
    When confirma la misma captura revisada con Idempotency-Key
    Then se crean todas las versiones nuevas y un resultado auditable en una transacción
    And los históricos, pedidos, reservas y costos contables permanecen intactos

  @BDD-SC-494
  Scenario: Evitar aplicación parcial, obsoleta o duplicada
    Given un lote revisado
    When cambia una versión destino o se inyecta un fallo durante la escritura
    Then ninguna receta del lote queda aplicada parcialmente
    Given un lote ya aplicado
    When el mismo actor autorizado repite la misma clave y captura
    Then recibe el mismo resultado sin versiones adicionales
    When reutiliza la clave con otro contenido o actor
    Then se rechaza el comando sin escrituras

@PRD-FR-240 @inventory
Feature: Consultar umbrales sin modificar existencias

  @BDD-SC-495
  Scenario: Configurar umbrales y comparar stock canónico
    Given un administrador con catalog.manage y alcance autorizado
    When configura mínimo y máximo válidos en unidad base para un insumo de la sucursal
    Then la consulta compara la existencia teórica canónica con esos umbrales usando Decimal
    And la igualdad pertenece a En rango y la falta de configuración a Sin umbrales
    And un umbral retirado deja intactos ledger, reservas y costo promedio
    And otra sucursal mantiene su configuración independiente

  @BDD-SC-496
  Scenario: Rechazar configuración inválida o concurrente
    Given una configuración de umbrales vigente
    When recibe valores no finitos, negativos, máximo menor al mínimo o una versión obsoleta
    Then conserva la configuración anterior y responde un error explícito
    And un actor sin permiso o de otra sucursal no puede leer ni modificar datos ajenos

@PRD-FR-241 @recipes
Feature: Encontrar usos directos efectivos de un insumo

  @BDD-SC-497
  Scenario: Consultar recetas que realmente usan el insumo en el alcance
    Given un producto con receta central y una local que la sustituye
    When un usuario autorizado consulta los usos del insumo en esa sucursal
    Then sólo ve usos de la versión local efectiva y otras recetas efectivas autorizadas
    And puede abrir el producto y versión correspondientes
    And no recibe históricos, costos ni dependencias indirectas
    And ausencia de usos y error de consulta se presentan como estados diferentes
```
