# TDD - Captura asistida de pedidos en POS

## TDD-TS-096 Intérprete local y aplicación segura del borrador

La suite focal usa frases y teléfonos sintéticos. Cubre:

- normalización de acentos, mayúsculas, relleno conversacional, cantidades y teléfono mexicano;
- mapeo explícito `para recoger|para llevar -> takeout` y `a domicilio -> delivery`;
- resolución única contra productos disponibles de la sucursal, sin precio ni ID inventado;
- ambigüedad, producto ausente e instrucción no configurada como estados no resueltos;
- vista previa editable antes de aplicar y cancelación sin mutar el estado del POS;
- aplicación sólo al carrito, titular y modalidad; no llama `POST /orders`, pagos, aceptación ni
  fulfillment;
- búsqueda telefónica exacta: auto-selección sólo con una coincidencia, flujo humano con cero o
  múltiples;
- soporte progresivo del dictado y fallback textual cuando `SpeechRecognition` no existe;
- ausencia de proveedor, secreto, persistencia o logging de frase, audio, nombre y teléfono;
- integración con el cotizador/checkout existente, que continúa siendo la autoridad de precios,
  disponibilidad, snapshots e idempotencia.

## TDD-TC-183 Interpretar y aplicar el ejemplo de aceptación

Given Baguette BBQ disponible y Sin cebolla configurado para ese producto
When se interpreta la frase sintética de BDD-SC-406
Then el borrador resuelve cliente, teléfono, takeout y una línea inequívoca
And aplicar llena el carrito sin emitir comandos de pedido o pago.

## TDD-TC-184 Rechazar ambigüedad y catálogo inválido

Given productos homónimos, productos no disponibles o instrucciones sin opción efectiva
When se intenta resolver y aplicar el borrador
Then los elementos permanecen no resueltos, se explican en español y no generan IDs ni líneas.

## TDD-TC-185 Conservar control humano y privacidad

Given un estado de venta previo y una frase con PII sintética
When se cancela, falla el dictado o la búsqueda telefónica devuelve cero o múltiples resultados
Then el estado previo permanece intacto, el operador decide el siguiente paso y no existe salida a
proveedores, logs o almacenamiento persistente.

## TDD-TC-186 Integración POS y regresión del checkout

Given un borrador aplicado y revisado
When el Cajero continúa por el checkout existente
Then cotización, validaciones, caja, idempotencia y creación autoritativa conservan sus contratos
And la captura asistida no puede declarar éxito ni folio.
