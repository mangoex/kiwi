# POS-AI-002 — plan de pedido asistido estricto

Riesgo `R3` por integración externa y tratamiento transitorio de PII. No incluye migración,
persistencia nueva, modificación de precios, creación de pedidos ni despliegue productivo.

## Contrato e invariantes

- OpenRouter sólo se invoca desde backend y permanece apagado sin bandera y secreto.
- Nombre y teléfono identificados se redactan antes de la frontera externa y nunca se registran.
- El modelo sólo propone producto/cantidad; Python valida IDs, disponibilidad y cardinalidades.
- Cada grupo obligatorio incompleto produce una pregunta con opciones efectivas de sucursal.
- El POS no agrega el borrador hasta resolver todos los mínimos y nunca sustituye al checkout.

## Tareas

- `POS-AI-002-T1`: actualizar PRD, ADR, BDD, TDD, matriz y runbook de Easypanel.
- `POS-AI-002-T2`: implementar adaptador OpenRouter, redacción, esquema estricto y endpoint autenticado.
- `POS-AI-002-T3`: rediseñar icono y diálogo; aplicar únicamente opciones canónicas completas.
- `POS-AI-002-T4`: pruebas focales, lint, typecheck, build, revisión visual y auditoría de diff.

## Release

Commit/push pueden formar parte del paquete autorizado. Configurar el secreto y hacer redeploy son
operaciones productivas separadas. Sin clave real no se ejecuta prueba contra el proveedor.
