# BDD de la frontera XML de proveedor

```gherkin
@PRD-FR-102 @PRD-FR-107
Feature: Extracción XML acotada antes de validación fiscal
  @BDD-SC-689
  Scenario: Un XML no confiable no activa entidades ni devuelve resultados parciales
    Given bytes XML originales de proveedor sin autorización de efectos contables
    When la frontera sintáctica recibe DTD entidades PI compresión o estructura excesiva
    Then rechaza con un código estable sin payload ni acceso a red o archivos
    And motor incompatible exige revisión sin fallback
    But XML benigno dentro de límites produce un árbol para validación posterior
    And el resultado no acredita validez fiscal ni recibe stock ni genera deuda

  @BDD-SC-690
  Scenario: Captura identidad declarada sin atribuir validación fiscal
    Given CFDI 4.0 con Timbre 1.1 y receptor explícito de un consumidor autorizado
    When captura identidad declarada y hash de bytes originales
    Then entrega DTO congelado y fiscal_validation unverified
    And UUID equivalente se normaliza sin alterar el hash original
    But receptor ajeno versión incompatible o identidad ambigua rechaza sin exponer RFC

  @BDD-SC-691
  Scenario: Capturar original privado conserva idempotencia y duplicados
    Given actor autorizado y receptor cargado de branch real
    When captura XML crudo acotado con key estable
    Then persiste un original cifrado y comando unverified sin efectos contables
    And replay exacto conserva el resultado sin duplicar filas
    But nuevo key con UUID existente rechaza duplicado
    And bytes distintos para UUID existente conservan conflicto privado sin reemplazar original
    And recuperación con Idempotency-Key y cuerpo vacío reautoriza el recurso sin capturar de nuevo
    But errores SQL o cuerpo de recuperación inválido no reflejan key XML contexto ni parámetros

  @BDD-SC-692
  Scenario: Descargar original exige autoridad actual y confirma auditoría
    Given evidencia privada de branch autorizada incluso después de cierre
    When actor actual con purchases.read solicita el original
    Then entrega bytes originales como attachment sin-cache después de auditoría
    But actor revocado otra branch o crypto alterado no obtiene bytes

  @BDD-SC-693
  Scenario: Cambiar contexto durante carga impide persistencia anterior
    Given carga preautorizada en A sin locks durante red
    And actor anónimo no provoca lectura del cuerpo
    And XML mayor a 1MiB o carga mayor a cinco segundos se rechaza sin efectos
    When selección o revocación cambia autoridad antes del commit
    Then dominio reautoriza y rechaza sin original comando stock deuda ni pago nuevos

  @BDD-SC-694
  Scenario: Migración conserva evidencia y rechaza downgrade con historia
    Given esquema previo con historia original sin modificación
    When migra a captura documental
    Then tablas nuevas están vacías y restricciones impiden referencias de otra organización
    But downgrade con cualquier evidencia o comando se bloquea sin pérdida
```
