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

### TDD-TC-466 Extracción multimodal y documental hacia el borrador de compra (`PUR-AI-CAPTURE-001`)

BDD-SC-795 / BDD-SC-705: validar en `apps/api/tests/test_purchase_ai_capture.py` y
`tests/frontend/test_purchase_workspace.mjs`:

- autorización de sucursal activa y `purchases.manage` (`401`/`403` ante actor inactivo, sin permiso o sucursal ajena);
- extracción determinista de XML CFDI 3.3/4.0 (emisor, folio, fecha, conceptos, impuestos y rechazo de DTD/XXE);
- extracción de PDF textual y lista en papel / ticket en texto libre o con tuberías, normalizando cantidades y precios a dos decimales (`PRD-NFR-012`);
- extracción multimodal de imagen (`image/png`, `image/jpeg`, `image/webp`) y PDF escaneado mediante adaptador OpenRouter con JSON Schema estricto, verificación de firmas mágicas, límite de tamaño y fallo cerrado (`purchase_ai_provider_unavailable`) cuando no hay proveedor configurado;
- conciliación contra proveedores y presentaciones activas de la sucursal (`matched`, `cross_supplier`, `unmatched`), preservando líneas no conciliadas para selección manual y limpiando metadatos de IA en `purchasePayload`;
- ausencia total de efectos secundarios en `purchase_documents`, `inventory_movements`, `inventory_cost_states` y `cash_movements` durante la extracción.
