# BDD — CAT-CLASS-001 (implementación local; canary pendiente)

## BDD-FEAT-114 Clasificación comercial independiente

```gherkin
@PRD-FR-246 @PRD-FR-247
Feature: Clasificar sin cambiar la operación

  @BDD-SC-531
  Scenario: Clasificar grupo y conservar estación
    Given un administrador corporativo autorizado y un grupo CERVEZAS
    When asigna Bebidas y el subgrupo ARTESANALES contiene una IPA
    Then POS presenta Bebidas, Cervezas, Artesanales y la IPA
    And cada producto conserva su estación, precio, receta y disponibilidad
    And un alimento preparado en barra permanece en Alimentos por su grupo
    And un grupo con estaciones mixtas aparece en una sola clasificación

  @BDD-SC-532
  Scenario: Crear desde ambas pantallas sin duplicar autoridad
    Given el modo explícito está activo
    When crea un grupo desde Grupos y subgrupos o desde el alta rápida de Productos
    Then exige clasificación válida y confirma los mismos datos persistidos
    And Productos muestra la clasificación heredada de sólo lectura
    And cancelar o fallar conserva el borrador sin anunciar éxito
    And cambiar grupo invalida un subgrupo incompatible sin cambiar la estación

  @BDD-SC-533
  Scenario: Rechazar acceso fuera de alcance y payload inválido
    Given un actor de sucursal con catalog.manage o un actor de otra organización
    When intenta leer configuración administrativa, escribir o repetir un comando corporativo
    Then no obtiene datos ni realiza cambios ni auditoría de éxito
    And códigos desconocidos, campos heredados manipulados y versiones inválidas se rechazan
    And los consumidores operativos mantienen sólo su catálogo autorizado
    And GET de categorías sin sucursal exige autoridad corporativa antes de devolver configuración
    And GET con sucursal no incluye versión de escritura ni metadata administrativa

  @BDD-SC-534
  Scenario: Reintentar, competir y fallar durante el guardado
    Given dos comandos parten de la misma versión
    When compiten por clasificar el mismo grupo
    Then sólo uno confirma y el otro conserva su borrador con conflicto explícito
    And repetir una clave idéntica devuelve el resultado sin duplicar auditoría
    And reutilizar la clave con otro contenido falla sin escribir
    And un fallo entre actualización y auditoría revierte toda la transacción
    And ningún escritor heredado puede omitir versión y autorización

  @BDD-SC-535
  Scenario: Migrar sin adivinar y bloquear activación incompleta
    Given grupos existentes mixtos, vacíos, inactivos y con estaciones antiguas
    When se aplica la migración aditiva
    Then todos quedan pendientes de asignación explícita sin cambiar la operación legacy
    And un mapping reanudado no duplica comandos ni sobrescribe versiones cambiadas
    And no activa con grupos activos pendientes o sucursales sin capacidad y acuse
    And un grupo archivado pendiente requiere clasificación al reactivarse

  @BDD-SC-536
  Scenario: Conservar operación offline y generación coherente
    Given un gateway nuevo con un catálogo legacy válido
    When recibe un bundle v1 o v2 sigue operando en modo legacy
    And un gateway antiguo no recibe un bundle v3
    When instala un v3 válido con grupos, subgrupos y clasificación explícita
    Then POS online y offline ofrecen la misma jerarquía para el mismo catálogo
    And fallos de firma, alcance, integridad o instalación conservan el último catálogo válido
    And nunca mezcla clasificación nueva con grupos o productos de otra generación
    And rechaza generaciones anteriores aunque su firma sea válida, incluso después de reiniciar
    And una generación igual con otro hash o modo se rechaza
    And volver a legacy requiere una reversión explícita con generación superior
    And desconectar una sucursal después de preparar deja adopción pendiente hasta acuse de instalación explícita
    And no declara la organización activada por un acuse de capacidad o de catálogo legacy
    And un cambio de grupos o sucursales durante preparación obliga a revalidar antes de publicar

  @BDD-SC-537
  Scenario: Reclasificar o revertir sin perder ventas ni historia
    Given pedidos aceptados, carrito abierto y catálogo explícito activado
    When se reclasifica un grupo o se emite una generación de reversión legacy
    Then no cambia dinero, inventario, recetas, estación, impresión ni snapshots de pedidos
    And conserva búsqueda, favoritos y carrito y revalida al aceptar conforme al contrato vigente
    And no oculta productos vendibles ni amplía permisos ni disponibilidad
    And no recalcula reportes históricos ni borra auditoría
    And la reversión informa qué nodos desconectados aún no la adoptaron
```
