# POS-AI-001 — handoff de implementación a Terra

## Objetivo y riesgo

Implementar `PRD-FR-228` conforme a `SDD-ADR-032`, `BDD-FEAT-093` y `TDD-TS-096`. Riesgo `R3` por
PII y porque el borrador alimenta un pedido, aunque este paquete no agrega integración externa,
persistencia, migración, despliegue ni comando de dominio.

## Alcance obligatorio

1. Crear primero pruebas RED focales para el intérprete puro y una prueba semántica de integración.
2. Implementar un módulo TypeScript puro, determinista y sin dependencias para normalizar texto,
   detectar nombre/teléfono/modalidad/cantidad y resolver productos por catálogo efectivo.
3. Agregar el botón accesible **Captura asistida** junto a la sucursal del encabezado del POS.
4. Agregar modal con textarea, dictado progresivo opcional, vista previa y estados resuelto/ambiguo/no
   encontrado. Ninguna ausencia de API de voz bloquea la captura escrita.
5. Aplicar sólo valores inequívocos al estado React existente. Reutilizar el lookup telefónico y la
   personalización canónica; no duplicar checkout ni escribir directo en pedidos.
6. No enviar ni persistir frase, audio, nombre o teléfono; no agregar proveedor, secreto, endpoint,
   dependencia o migración.
7. Mantener español de México, navegación por teclado, foco del modal, labels y mensajes legibles.

## Invariantes fail-closed

- El intérprete no calcula ni acepta precio, inventario, sucursal o permisos.
- Sólo productos activos/disponibles ya cargados en la sucursal pueden resolverse.
- Una coincidencia ambigua no se aplica; una instrucción no configurada no se convierte en texto
  libre silencioso.
- Abrir/cancelar no cambia carrito, cliente, modalidad ni checkout.
- Aplicar no llama `/orders`, `/payments`, aceptación, fulfillment, reserva ni KDS.
- El checkout vigente sigue siendo la única autoridad y conserva sus claves idempotentes.

## Tareas y evidencia solicitada

- `POS-AI-001-T1`: pruebas unitarias del intérprete (`TDD-TC-183/184`).
- `POS-AI-001-T2`: botón, modal, preview, fallback de voz y aplicación (`TDD-TC-185`).
- `POS-AI-001-T3`: prueba semántica de no-escritura y regresión checkout (`TDD-TC-186`).
- `POS-AI-001-T4`: ejecutar pruebas focales, `pnpm --filter @restaurantos/pos-web typecheck` y
  `git diff --check`; reportar límites sin editar trabajo ajeno.

Sol realizará auditoría independiente R3, revisión de diff, pruebas de arquitectura/trazabilidad,
gates frontend aplicables y correcciones antes del cierre. Publicación y despliegue quedan fuera.
