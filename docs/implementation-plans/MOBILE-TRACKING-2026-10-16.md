# Seguimiento público del menú móvil

Riesgo R3: consulta externa y aislamiento de información por organización/sucursal.
Base dd413a4; referencia de diseño pos-saas/main 9235cea. Se preserva la edición previa de
docs/10-operacion-easypanel.md; no pertenece a este paquete.

Secuencia: PRD-FR-227 → SDD §67 → BDD-SC-715..719 → TDD-TS-149 → matriz → RED → implementación
→ verificaciones focales y recorrido local → auditoría independiente. Se reutilizan intención,
accepted_order_id, pedidos y eventos existentes; la auditoría detectó falta de índice para la
consulta repetida, por lo que 0097 agrega sólo un índice de eventos. No hay proveedor nuevo. Reversión por
código conserva historia; no toca pagos, inventario ni autoridad del gateway.

Preguntas operativas: ¿cuándo se confirmó por última vez el estado? Timestamp de servidor y hora
de consulta separados en la tarjeta. ¿por qué dejó de actualizarse? Error estable visible,
Retry-After y métrica public_order_tracking con resultado acotado. ¿se filtran referencias ajenas?
DTO mínimo y joins de organización/sucursal con pruebas adversariales; sin registrar referencia,
dirección, nombre, teléfono ni IP en las métricas del flujo.

## Evidencia local del cierre

- RED: la primera prueba API falló por ausencia de `display_status`; la prueba semántica móvil
  falló porque todavía no existía el módulo de seguimiento. Fallos esperados antes de implementar.
- GREEN: 8 pruebas nuevas de API y 9 de trazabilidad aprobaron juntas (17); las 26 pruebas del
  contrato público anterior aprobaron en la ejecución focal inicial. Las 6 pruebas semánticas
  nuevas y las 14 del flujo móvil anterior aprobaron.
- Migración: 2 roundtrips reales, PostgreSQL local aislado y SQLite, de 0096 a 0097 y regreso,
  verificando columnas del índice y conservación de filas. Ninguna base productiva fue utilizada.
- Navegador contra API real efímera: pedidos para recoger en 390/1280 px y domicilio en 390 px;
  aceptación, preparación, listo, salida, entrega, recarga, cambio de sucursal y ocultación local.
  Checkout real con persistencia disponible y con fallo de almacenamiento, sin errores de página.
  Capturas en `output/playwright/public-tracking/`; revisión visual de READY y almacenamiento
  fallido sin recortes ni mensajes contradictorios.
- Typecheck y build móvil, Ruff y mypy dirigidos aprobados. Para mypy se usaron SQLAlchemy 2.1.4
  y stubs exactos del lock en un directorio aislado, sin modificar el entorno compartido.
- Política del repositorio, análisis monotónico del diff incluyendo archivos nuevos y
  `git diff --check` aprobados. El paquete actualiza el hash sintético ya existente de CI;
  el ajuste local del hash del documento operativo previo se excluye junto con ese documento.
  No se agregaron silenciamientos ni se modificaron fragmentos de credenciales sintéticas.
- Auditoría R3 independiente, con contexto fresco: sin hallazgos bloqueantes. Reejecutó por su
  cuenta las 8 pruebas API, 6 semánticas, política e integridad del diff. La misma revisión detectó
  y verificó las correcciones de índice, copia del modal, almacenamiento y `Retry-After`.

## Afirmaciones R3 y límites

| Afirmación | Evidencia e intento de refutación | Resultado y riesgo residual |
| --- | --- | --- |
| La consulta no escribe ni revela pedidos de otra sucursal/organización. | Interceptor SQL rechaza DML/DDL; pruebas de vínculos incoherentes, referencias inválidas, DTO estricto y headers. | Aprobado localmente; la referencia PI es una capacidad y debe mantenerse privada. |
| La actualización no solapa solicitudes ni evita el cooldown. | Respuestas diferidas, cancelación, pestaña oculta y recreación del poller durante `Retry-After`. | Aprobado; sin Redis las cuotas son por proceso, como documenta SDD. |
| El historial permite proyectar el estado sin explorar toda la tabla de eventos. | Auditoría reprodujo el scan y verificó el índice con EXPLAIN; roundtrips reales en ambos dialectos. | Aprobado en fixtures; capacidad y bloqueo durante creación del índice requieren validación productiva. |
| La tarjeta conserva contexto sin depender de almacenamiento disponible. | Checkout real, recarga, storage bloqueado, cambio de sucursal y modal compartiendo el mismo estado. | Aprobado; al fallar storage sólo se conserva durante la sesión. DELIVERED detiene consultas: una devolución posterior se descubre al recargar. |

CI incluye los nuevos gates PostgreSQL y navegador, pero no se ejecutó CI remoto ni la suite
completa local. Tampoco se verificó comportamiento productivo. Al cierre de la implementación
todavía no se había hecho commit ni push. La autorización posterior cubre su publicación y merge;
despliegue, migración productiva y modificación de datos reales mantienen autorización separada.

## Publicación y reversión pendientes

La verificación previa a publicación reprodujo una expectativa obsoleta de head 0095 en la suite
de capacidad Alembic. Se ajustó a 0097 junto con las aserciones de conservación de revisión de
las suites PostgreSQL fiscal, offline, intenciones y XML; no se alteraron sus guardas ni fixtures.
CI también reprodujo un fixture de sesión administrativa sin `active_branch.timezone`, requerido
por el contrato vigente. Se agregó sólo ese dato sintético; la prueba completa del provider pasó
localmente conservando las validaciones de autoridad, contexto y navegación. El mismo dato se
completa en el fixture compartido de navegador, respetando zonas explícitas por sucursal.

Publicar el código y esperar CI verde antes de release. Bajo autorización productiva separada,
respaldar la base y elegir una ventana para crear el índice: puede bloquear escrituras mientras
se construye y su duración depende del volumen histórico. Desde `/app/apps/api`, comprobar
`python -m alembic current -v` y `python -m alembic heads`; el punto de partida esperado es
`0096_driver_cash_settlements`. Aplicar `python -m alembic upgrade 0097_public_tracking_event_index`
y comprobar revisión e índice antes del canary de un pedido sintético por modalidad.

El canary debe comprobar aislamiento, estado visible y errores/latencia sin registrar referencias
ni datos personales. Revertir el frontend/API restaura el contrato anterior; el índice es aditivo
y puede permanecer. Si se autoriza retirarlo, ejecutar
`python -m alembic downgrade 0096_driver_cash_settlements` elimina únicamente el índice 0097. No deshacer la migración 0096 ni
alterar pagos o liquidaciones históricas.
