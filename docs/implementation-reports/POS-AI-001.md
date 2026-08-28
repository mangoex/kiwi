# POS-AI-001 — captura asistida local de pedidos

## Resultado

Se implementó el borrador asistido definido por `PRD-FR-228` y `SDD-ADR-032`. El encabezado del POS
muestra **Captura asistida** junto a la sucursal; el modal permite texto, preview y aplicación al
estado editable. El dictado progresivo `es-MX` queda desactivado por defecto y sólo aparece con
`VITE_POS_ASSISTED_DICTATION_ENABLED=true` más soporte del navegador. El intérprete local normaliza nombre, teléfono, modalidad,
cantidad, producto e instrucción sin proveedor externo ni persistencia.

El producto se resuelve sólo contra la proyección efectiva ya filtrada de la sucursal. Antes de
aplicar, el POS consulta los modificadores efectivos de ese producto. Una instrucción como **Sin
cebolla** se agrega como comentario configurado; una opción comercial se conserva como modificador y
el cotizador Python sigue recalculando. Si faltan cardinalidades obligatorias, el flujo abre la
personalización canónica con la instrucción reconocida preseleccionada. Ambigüedad, indisponibilidad,
instrucción no configurada o error de lectura bloquean la aplicación.

Aplicar limpia primero cualquier identidad/domicilio anterior cuando el borrador contiene otro
teléfono. La búsqueda vigente selecciona automáticamente sólo una coincidencia exacta; cero o varias
quedan para decisión humana. Cancelar no modifica el estado. El asistente no invoca creación de
pedido, pago, aceptación, reserva, KDS ni fulfillment.

## Implementación y tareas

- `POS-AI-001-T1`: intérprete puro y pruebas RED/GREEN de frase, cantidad, teléfono, modalidad,
  catálogo, ambigüedad e instrucción.
- `POS-AI-001-T2`: botón con icono, modal, dictado real default-off, preview y aplicación segura.
- `POS-AI-001-T3`: prueba semántica de privacidad/no escritura e integración con comentarios,
  personalización, cliente y carrito.
- `POS-AI-001-T4`: auditoría Sol, regresiones focales, typecheck, build y diff check.

## Evidencia local

- RED de Terra: las dos pruebas POS-AI-001 fallaron antes de existir módulo y control.
- `node tests/frontend/test_pos_assisted_order_capture.mjs`: verde.
- `node tests/frontend/test_pos_assisted_order_semantic.mjs`: verde.
- `node tests/frontend/test_pos_global_comments_extras.mjs`: verde.
- `node tests/frontend/test_pos_checkout_idempotency.mjs`: verde.
- `node tests/frontend/test_pos_order_edit_restore.mjs`: verde.
- `tsc --noEmit -p apps/pos-web/tsconfig.json`: verde.
- build Vite POS: 1,591 módulos, exit 0; conserva advertencia no bloqueante de chunk mayor a 500 kB.
- `git diff --check`: verde.
- Revisión focal de arquitectura ejecutando sus funciones puras: flujo telefónico 7/7, UX POS 9/9,
  variaciones frontend 6/6 y trazabilidad nueva 7/8 gates verdes.

## Límites y riesgo residual

- `pytest` no está instalado en el runtime Python disponible. La ejecución equivalente de funciones
  puras confirmó que el único fallo global de trazabilidad es preexistente: `BDD-SC-200..204` están
  duplicados entre documentos ajenos a POS-AI-001. Los IDs nuevos 406..412 y 183..186 son únicos,
  están relacionados y no quedan huérfanos.
- La QA visual automatizada no se completó: la skill Playwright verificó `npx`, pero la resolución de
  `@playwright/cli` no produjo salida y se canceló. No se declara validación de breakpoints, foco real
  ni apariencia en navegador.
- El intérprete inicial resuelve una línea inequívoca por frase. Pedidos multi-producto, modelos
  externos, aprendizaje, telemetría de contenido y operación offline específica quedan fuera.
- La interpretación escrita no requiere API ni Python. Si se habilita el dictado del navegador, su
  fabricante puede procesar audio fuera de la aplicación; requiere decisión operativa y aviso de
  privacidad separados.
- Publicación Git: commit funcional `46c3ec9`, merge `74cf55a` y push verificado a `origin/main` el
  2026-08-28. El workflow CI sólo tiene disparadores `pull_request` y `workflow_dispatch`, por lo que
  este push directo no produjo por sí solo una corrida CI.
- No hubo operación directa en Easypanel, despliegue confirmado, migración, configuración ni acceso a
  datos productivos.
