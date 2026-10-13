# TDD de asistencia de compras

## TDD-TS-141 Frontera de compras asistidas

### TDD-TC-380 Autorización y alcance de asistencia

BDD-SC-677: actor sin grants/inactivo, sucursal inválida/ajena,
  lectura de historial de otra sucursal y catálogo local. Negativos sin datos ni efectos;
  positivo con grants persistidos, no permisos autoasignados por token.
### TDD-TC-381 Fidelidad decimal y extracción incompleta

BDD-SC-678: vacío, ilegible, $19.99, medio centavo, cantidad decimal,
  negativos, overflow, formatos ambiguos y datos faltantes. Comparar centavos exactos y
  cantidades como Decimal/string; nunca tolerancia flotante ni partidas artificiales.

Evidencia focal: `test_inventory_ai_remediation.py`, `test_inventory_ai.py`.
La demanda I03 y el período de merma I04 requieren pruebas adicionales antes de declarar el módulo completo.
