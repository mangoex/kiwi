# CRM-MOBILE-002 — acceso con teléfono y contraseña

R3: autenticación, datos sensibles, migración. Sustituye el mecanismo habitual de CRM-MOBILE-001.
Causa observada en código: gate false y proveedor obligatorio; la UI permitía intentar el flujo
tras fallar /profile y mezclaba fallos de configuración/almacenamiento en un único mensaje.
No se ha inspeccionado configuración productiva en este paquete.

1. [x] Contrato PRD281/282, SDD69 ADR046, BDD740..744, TDD153 y matriz.
2. [x] RED: tres pruebas fallaron por default false y rutas inexistentes, antes del cambio.
3. [x] Credenciales, throttle persistente, migración0099, API y UI.
4. [x] Pruebas focales, PG/SQLite, QA y auditoría R3 independiente. CI se acredita en el PR.
5. [ ] Publicación Git; activación/migración productiva separada.

Se preservan los cambios previos de docs/10-operacion-easypanel.md, su entrada de hash y tmp/.
Rollback: volver al lector anterior manteniendo tablas nuevas; downgrade0099 rechaza credenciales
existentes. Backup antes de migración productiva. No se generan contraseñas a clientes históricos.
Recuperación sin sesión: no se publica un reset inseguro basado sólo en teléfono/cumpleaños.

## Evidencia y afirmaciones

Evidencia local:
- Backend: 33 casos de password, perfil y límites públicos; PostgreSQL/migración: 11 casos sin skips.
  Regresión adicional: OTP productivo sin Redis falla cerrado sin afectar contraseña; RED confirmó
  llamada indebida al proveedor antes del ajuste focal en main. GREEN: 19 casos de contraseñas/límites,
  Ruff y mypy main; Sol confirmó cierre del hallazgo en el mismo ciclo de revisión.
- Arquitectura (trazabilidad, gates CI y capacidad Alembic): 34 casos; semántica frontend: 6 casos.
- Ruff y mypy focal; typecheck del monorepo; builds mobile/admin. Admin conserva aviso de chunk grande.
- Browser real contra API sintética sin SMS: registro/perfil/pedido/reingreso en 320/390/1280 px,
  CRM en 1366 px y seguimiento de pedidos completo. Capturas en output/playwright/crm-password-journey/.
- Sol independiente con contexto fresco: sin hallazgos bloqueantes; ejecutó 18 pruebas focales
  y diff-check. No certifica producción ni recuperación asistida.
- Política de repositorio: excepciones exactas por hash para cuatro fixtures de contraseñas
  sintéticas y un falso positivo de autocomplete HTML en CustomerProfile; motivo visible en cada archivo.

| Afirmación R3 | Intento de refutación / evidencia | Resultado y límite |
| --- | --- | --- |
| Conocer un teléfono no expone CRM previo | Registro con teléfono histórico y lectura/edición del perfil | Cliente nuevo separado, datos anteriores intactos; duplicidad deliberada hasta vinculación asistida |
| Rotar credenciales invalida sesiones previas | Dos rotaciones PG simultáneas, cookie vieja y contraseña anterior | Una gana, otra rechazada; cookie anterior inválida |
| OTP no evita la contraseña | Retos de acceso/cambio iniciados antes de establecer contraseña | Rechazo tras guardia bajo bloqueo; compatibilidad OTP sólo para identidades sin contraseña |
| OTP productivo conserva límites compartidos | Twilio configurado sin Redis y proveedor que falla si se invoca | Rutas OTP devuelven 503 antes del proveedor; contraseñas mantienen disponibilidad SQL |
| Límites persisten entre procesos | Nuevo cliente HTTP y 16 conexiones PG simultáneas | Diez aceptadas/seis limitadas; claves HMAC sin PII; no acredita carga productiva |
| Migración preserva historia | Upgrade/downgrade SQLite y PG con identidad/sesión antiguas | Datos intactos y downgrade bloqueado con credenciales |
| Una falla no permite avanzar al menú | GET profile 503 en navegador, reintento y login inválido/válido | Formulario bloqueado hasta recuperar disponibilidad; ninguna configuración productiva inspeccionada |

Activación productiva separada: backup, aplicar Alembic hasta 0099_mobile_password_access y
desplegar backend/frontend juntos. Si RESTAURANTOS_MOBILE_CUSTOMER_ACCESS_ENABLED estaba definido
explícitamente como false, debe habilitarse; el nuevo default sólo aplica cuando no se define.
Los pedidos conservan RESTAURANTOS_PUBLIC_ORDER_INTENTS_ENABLED y sus requisitos previos.
Canary autorizado: cuenta sintética nueva, reingreso, perfil, cambio de contraseña y sesión anterior
rechazada; observar códigos HTTP y auditoría por IDs, sin registrar credenciales. No ejecutado aquí.
Preguntas operativas y señales se mantienen en SDD69; CI, Git y producción se reportan por separado.
