# BDD — pedidos offline ORD-OFF-001

Complementa BDD-SC-001/002/501; conserva las reglas de precio, producción, pagos y compensaciones.

```gherkin
@PRD-FR-180 @PRD-FR-182 @PRD-FR-184 @PRD-FR-187 @PRD-FR-242 @offline @critical
Feature: Operar pedidos locales con evidencia durable
  @BDD-SC-502
  Scenario: Dos cajas crean pedidos sin nube
    Given un gateway con catálogo vigente y turnos abiertos autorizados
    When dos cajas crean pedidos y una repite su comando tras perder la respuesta
    Then cada intención conserva un solo pedido y folio único
    And sus líneas, tareas, reservas y outbox se confirman atómicamente
    And el POS muestra pendiente de sincronización

  @BDD-SC-503
  Scenario: Preparar, cobrar y entregar un combo local
    Given un combo local aceptado con componentes de cocina y bebidas
    When cada estación completa sus tareas y el cajero registra el cobro autorizado
    Then sólo las recetas congeladas determinan el consumo exacto
    And empaque y entrega conservan las guardas canónicas
    And pagos, auditoría e impresión conservan identidad sin duplicarse

  @BDD-SC-504
  Scenario: Reconectar después de modificar el catálogo central
    Given pedidos locales aceptados con un bundle emitido por la nube
    And la nube cambió precios o recetas después de esa aceptación
    When reconcilia los comandos locales y pierde una confirmación
    Then el reintento conserva identidad, folio, precio y snapshots originales
    And la nube no usa catálogo cliente ni duplica efectos operativos

  @BDD-SC-505
  Scenario: Reiniciar con un comando en vuelo
    Given una escritura local confirmada y un comando pendiente o en sincronización
    When reinicia el gateway y recupera la conexión
    Then conserva el resultado local y reintenta con la misma identidad
    And un fallo antes del commit local no deja efectos parciales

  @BDD-SC-506
  Scenario: Mantener conflictos y orden causal por pedido
    Given una secuencia local cuyo predecesor no fue confirmado
    When la nube rechaza por turno cerrado, permiso revocado o estado divergente
    Then el conflicto queda visible y sus descendientes no se aplican
    And otros pedidos independientes pueden sincronizarse
    And no se compensan ni alteran saldos automáticamente

  @BDD-SC-507
  Scenario: Rechazar autorización o catálogo no confiables
    Given un grant vencido, ajeno o sin capability o un bundle alterado o vencido
    When intenta aceptar un comando local
    Then rechaza antes de escribir pedido, pago, tarea o outbox
    And nunca expone credenciales ni datos de otra sucursal

  @BDD-SC-508
  Scenario: Recargar la interfaz y recuperar una escritura ambigua
    Given un POS o KDS preparado para operar localmente
    When pierde internet, recarga y una respuesta de escritura se pierde
    Then conserva recursos y autorización local aún vigente
    And consulta o reintenta el mismo comando en el gateway
    And no crea una escritura alternativa en la nube

  @BDD-SC-509
  Scenario: Bloquear cierre hasta confirmar toda la operación local
    Given un gateway que conserva autoridad y pedidos o cobros pendientes o en conflicto
    When el cajero intenta cerrar la caja desde nube
    Then el turno permanece abierto sin snapshot de cierre
    And caducar el lease no habilita el cierre
    When el gateway congela nuevas escrituras y devuelve autoridad con todos sus comandos confirmados
    Then el cierre puede continuar con sus permisos y guardas canónicas

  @BDD-SC-510
  Scenario: Renovar y recuperar autoridad sin perder historia
    Given un gateway con pedidos abiertos y comandos confirmados
    When congela escrituras y renueva su catálogo autorizado
    Then conserva pedidos, cobros, snapshots y auditoría
    And los comandos nuevos requieren el bundle y grant nuevos
    When devuelve autoridad y pierde el acuse central
    Then un reinicio conserva el bloqueo de nuevas aceptaciones
    And reintentar el mismo handoff devuelve el mismo recibo
    And una recuperación explícita aumenta la época e invalida la autoridad anterior
```
