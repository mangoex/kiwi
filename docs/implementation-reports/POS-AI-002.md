# POS-AI-002 — pedido asistido estricto con OpenRouter

## Resultado

Se reemplazó el intérprete local permisivo por `POST /api/v1/orders/assisted-draft`. El backend
autentica al Cajero, valida la sucursal, redacta nombre/teléfono, solicita salida JSON estructurada a
OpenRouter y reconcilia cada producto contra el catálogo. Los modificadores y las preguntas se derivan
de grupos efectivos; el modelo no controla precios, opciones, clientes ni creación del pedido.

El encabezado muestra sólo el icono de persona con nombre accesible. El modal ahora usa jerarquía
tipográfica, conversación, estados de carga/error, preguntas con botones canónicos y una acción final
bloqueada hasta satisfacer todos los mínimos.

## Evidencia local

- `12 passed`: adaptador, redacción, fallo cerrado, configuración y semántica del POS.
- Ruff focal: `All checks passed!`.
- TypeScript POS: `tsc --noEmit` verde.
- Vite POS: build verde; conserva advertencia preexistente de chunk principal mayor a 500 kB.
- Dictado: disponible por capacidad del navegador y permiso del Cajero, sin variable de Easypanel.
- `git diff --check`: verde.
- Integridad global de trazabilidad: 18 pruebas pasaron y una falló por cinco IDs BDD duplicados
  preexistentes ajenos a POS-AI-002 (`BDD-SC-200..204`). Los IDs nuevos `413..418` no aparecen en el
  reporte de duplicados.

## Límites y release

No se llamó OpenRouter porque no existe clave configurada. La revisión visual automatizada quedó
inconclusa: Playwright no alcanzó localhost desde su navegador aislado aunque el host respondió HTTP
200; debe repetirse como smoke posterior al redeploy. No hay migración. Configuración Easypanel y
redeploy requieren autorización productiva separada.
