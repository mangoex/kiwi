# TDD — modificadores compartidos por productos

## TDD-TS-133 Persistencia, motor POS y alcance administrativo

### TDD-TC-309 Configuración compartida efectiva y precio autoritativo

Una prueba API crea un set para dos productos, guarda una opción con recargo, consulta ambos
catálogos POS y confirma que comparten el mismo `option_id`. Acepta una venta y verifica que Python
aplica el precio y congela el snapshot. Un tercer producto nunca asignado responde correctamente sin
heredar esa opción. Editar el set cambia ventas nuevas pero no el snapshot previo.

### TDD-TC-310 Alcance exacto, concurrencia e idempotencia

La prueba reemplaza `product_ids`, comprueba alta/baja efectiva, auditoría y versión incremental.
Conjunto vacío, producto inválido/no corporativo/otra estación, versión obsoleta y clave reutilizada
con cuerpo distinto fallan sin mutación parcial. Ambos órdenes set↔combo fijo y
set↔`product_component` se rechazan incluso con un set todavía vacío.

### TDD-TC-311 Separación de autoridades

Pruebas negativas rechazan `product_component` en sets compartidos y comprueban que grupos legados,
comentarios, extras y composición permanecen intactos. El CRUD legado no puede editar un grupo cuyo
propietario es un set.

### TDD-TC-312 Administrador central como superficie única

Pruebas frontend semánticas exigen tarjeta/ruta **Modificadores**, selector por categoría/producto,
estados mixtos, escritura mediante endpoints del set y editor sin producto componente. Productos no
publica tab, resumen, enlace ni monta `ModifierManager`; la ruta central es la única superficie. La prueba
Chrome fuerza `401`, relogin y remontaje para creación y alcance, y exige el mismo cuerpo y clave.

### TDD-TC-313 Migración reversible protegida

SQLite ejecuta upgrade desde `0074`, conserva grupos por producto, permite el modelo compartido y
revierte sólo sin datos compartidos. Con sets/grupos/asignaciones existentes, downgrade cierra con
error antes de perder historia. PostgreSQL valida DDL, locks y constraints en CI.

## Gates

1. RED focal API y frontend por ausencia de endpoints/ruta compartida.
2. GREEN API dirigida, prueba semántica Admin, typecheck/build y migración SQLite.
3. Regresiones focales de configuración por producto, precio/snapshot y comentarios/extras.
4. `git diff --check`, trazabilidad y auditoría Sol independiente.
5. PostgreSQL y CI son gates de release; migración, despliegue y canary productivos quedan fuera.
