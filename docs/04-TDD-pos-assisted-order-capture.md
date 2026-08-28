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
- dictado visible por capacidad `SpeechRecognition`, iniciado sólo por acción y permiso del Cajero,
  sin variable de build/runtime, y fallback textual cuando falta capacidad o permiso;
- ausencia de proveedor, secreto, persistencia o logging de frase, nombre y teléfono; el posible
  procesamiento de audio por el fabricante del navegador se declara como configuración autorizada;
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
When se cancela, el dictado no está autorizado/disponible o la búsqueda telefónica devuelve cero o múltiples resultados
Then el estado previo permanece intacto, el operador decide el siguiente paso y no existe salida a
proveedores, logs o almacenamiento persistente.

## TDD-TC-186 Integración POS y regresión del checkout

Given un borrador aplicado y revisado
When el Cajero continúa por el checkout existente
Then cotización, validaciones, caja, idempotencia y creación autoritativa conservan sus contratos
And la captura asistida no puede declarar éxito ni folio.

## TDD-TS-097 Adaptador OpenRouter y diálogo estricto

La suite focal cubre redacción previa de PII, esquema JSON estricto, reconciliación de IDs con catálogo
efectivo, preguntas deterministas por cardinalidad, fallo cerrado y semántica accesible del diálogo.
Las pruebas del proveedor usan un transporte simulado y datos sintéticos; nunca consumen una clave real.

## TDD-TC-187 Redactar PII antes de la frontera externa

Given una frase sintética con nombre y teléfono
When el servicio prepara la solicitud OpenRouter
Then extrae ambos localmente y el payload externo contiene marcadores, no los valores originales.

## TDD-TC-188 Reconciliar salida estructurada y cardinalidades

Given una respuesta estructurada con un producto canónico
When Python carga sus grupos efectivos
Then conserva únicamente IDs válidos y devuelve preguntas para cada mínimo incompleto.

## TDD-TC-189 Fallar cerrado ante proveedor o salida inválida

Given clave ausente, timeout, error HTTP, JSON inválido o product_id desconocido
When se solicita un borrador
Then no se devuelve una línea aplicable ni se modifica el estado de venta.

## TDD-TC-190 Completar preguntas sólo con opciones canónicas

Given preguntas de tamaño, pan o aderezo
When el Cajero elige opciones del diálogo
Then se respetan mínimos y máximos y el carrito recibe los option_id efectivos sin texto libre inventado.

## TDD-TC-191 Verificar presentación y accesibilidad del diálogo

Given el encabezado y el modal del POS
Then el acceso visible contiene sólo el icono de persona con nombre accesible y área táctil mínima
And el diálogo usa jerarquía tipográfica, estados de conversación, foco visible y acciones inequívocas.
