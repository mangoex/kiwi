# TDD de políticas D05/D06

## TDD-TS-143 Referencia de políticas versionadas

### TDD-TC-388 Demanda completa y cero real

BDD-SC-685: referencia Decimal de completitud/calendario, promedio semanal, datos censurados,
días cerrados y demanda cero; adapter futuro debe probar intervalo UTC/local y DST reales.
### TDD-TC-389 Pendientes temporales y empaque

BDD-SC-686: referencia de necesidad, demanda restante al corte, reservas, mínimo/objetivo,
capacidad residual a ETA, posición diaria y lotes/MOQ/excesos; la integración
I03 debe probar residual neto C02, versiones y fingerprint bajo autorización sin efectos.
### TDD-TC-390 Costeo y distribución conservativa

BDD-SC-687: r=0/1/0.5/unknown, impuesto/flete/descuentos, Decimal estricto, centavos residuales y
micro-unidades. Referencia no certifica elegibilidad fiscal ni importación de CFDI.
### TDD-TC-391 Compensación atribuida

BDD-SC-688: delta positivo/negativo, cantidad remanente cero/total/parcial, atribución inválida;
referencia conserva suma y no realiza SQL. C02 debe comprobar plan autorizado, locks, saldo,
historia inmutable, replay, rollback y UI de revisión antes de declarar ese comportamiento listo.

Evidencia ejecutable: tests/architecture/test_procurement_policy_reference.py y
`docs/implementation-plans/AUD-2026-10-13/policy_reference.py`. Las políticas se implementan por
capas según dependencias del plan; suites API/PG/E2E y auditoría independiente siguen siendo gates
para sus efectos. El modelo actual inventory_ai con demanda constante no queda certificado por
estas pruebas y debe sustituirse dentro de I03.
