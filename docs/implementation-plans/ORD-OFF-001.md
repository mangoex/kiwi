# ORD-OFF-001 — pedidos offline

R3; usuario retoma el incremento mientras despliega ADMIN-RETRO-001 por separado. Rama
codex/offline-orders, base09d641a. No despliegue/provisión productiva. Preservar operations.py y
los tres archivos mobile con trabajo previo; no incluir output/ ni .playwright-cli/.

Autoridad: PRD180–189/242, SDD47 y ADR035, BDD001/002/501 y extensiones del incremento,
TDD-TS-004/TDD-TC-002/003/248. Protocolo cash existente se conserva.

Secuencia: raíz especificación y contratos; Terra dominio/contexto/transacciones; Terra gateway y
reconciliación; Terra POS/KDS y recuperación; Sol auditoría independiente del mismo ciclo.
Primero RED focal de identidad/snapshot/atomicidad; después recorrido SQLite→PostgreSQL, dos cajas,
confirmación perdida, reinicio, catálogo modificado, grants expirados/revocados, conflicto y bundle
manipulado. Gate de empaquetado gateway, typecheck/build, navegador desconectado y CI aplicable.

Implementación en validación; no está aprobada para release. Registrar aquí evidencia R3 de afirmación, refutación,
resultado y riesgo residual; el estado de matriz no se promueve por arquitectura propuesta.

Evidencia local parcial (no equivale a autorización de release):

- Dominio/contexto y combos: 26 pruebas focales correctas. ContextVar por comando, snapshots
  congelados y rollback externo; no acredita por sí solo el transporte central.
- Gateway: outbox transaccional probado con fallo de dominio, reinicio, reintentos concurrentes de
  dos cajas, ACK perdido, ACK de otro comando y conflicto que bloquea sólo descendientes. El
  reintento conserva el sobre firmado y usa espera creciente persistida de 5 a 300 segundos.
- Recorrido local real: combo, cobro, dos tareas KDS, entrega y cierre de pedido correctos con FK
  SQLite activas. La prueba detectó y corrigió serialización UTC de fechas SQLite sin zona.
- Integridad documental: 8 pruebas correctas. Gateway cash anterior: 17 correctas y 6 omitidas
  por comprobaciones POSIX no ejecutables en Windows.
- Empaquetado: se detectó que el wheel API omitía restaurant_os.domain; se incluye el árbol
  restaurant_os completo. Ambos wheels construidos e instalados fuera del checkout; importación
  de CLI, servicio gateway y dominio correcta (dependencias Python del entorno disponibles).
- PostgreSQL real: dos reconciliaciones concurrentes de un sobre producen un pedido, dos tareas
  y el mismo recibo; conserva 15900 centavos aunque el precio central cambió a 999. La prueba
  también verifica revocación del actor y bloqueo de downgrade con historia. Regresión RED→GREEN
  de constraints de inbox. Otro caso demuestra con lock_timeout SQLSTATE55P03 que la primera
  adquisición de lease espera al escritor online que ya posee la sucursal: 2 pruebas PG correctas.
  Regresiones PostgreSQL de combos con nueva revisión: 3 correctas.
- HTTP central: lease, bootstrap, grant mínimo, reconciliación y replay con sesiones nuevas por
  petición. La auditoría descubrió commit ausente del grant; corregido y persistencia verificada
  desde otra sesión. HTTP/crypto/conflictos/fencing/provisión: 13 pruebas correctas en el corte.
- Navegador Chromium con gateway HTTP real y servidor estático detenido: POS y KDS recargan sus
  shells; un combo cobra 15900 centavos una sola vez y ambas tareas llegan a COMPLETED. Se verifica
  detalle por API local y estado PENDING_SYNC; nube central intencionalmente no disponible.
  No es evidencia de conciliación productiva ni de hardware de impresión.
- Cadena Alembic SQLite: 12 pruebas correctas. Outbox/transporte/API local/TLS: 8 correctas.
- Cierre focal Sol: commit de grant, recibos causales, reloj futuro, constraints/downgrade y
  fencing de rutas hermanas revisados sin nuevo defecto P0/P1. Detectó incompatibilidad de helper
  en prueba de reloj (4 valores frente a 5), corregida en el caller; gate dirigido registrado
  después de esa corrección. Fencing/conflictos/contexto/provisión/reinicio: 14 pruebas correctas.
- Integridad de repositorio: actualizado únicamente el hash de la entrada sintética existente de
  CI tras añadir base aislada y gate navegador; no se ampliaron excepciones ni silenciamientos.

Decisión confirmada por el usuario: bloquear el cierre mientras haya pedidos/cobros pendientes.
Implementado bloqueo canónico y alias, incluso con lease caducado; 4 regresiones RED→GREEN,
21 pruebas focales de caja correctas y 1 omitida por variable PostgreSQL en ese comando. El gate
omitido se ejecutó luego con PostgreSQL real: carrera cobro/cierre correcta (1 prueba). Un replay
de cierre ya confirmado sigue recuperable después de adquirir otro lease, con autorización vigente.

Renovación y devolución/recuperación explícitas implementadas. Corte local posterior:
54 pruebas nuevas de dominio, gateway, lifecycle y reconciliación correctas, incluidas las dos
de PostgreSQL real; 8 de trazabilidad correctas. Ruff API/tests/gateway, mypy de los 11 módulos
nuevos y typecheck frontend correctos. Recorrido Chromium con gateway HTTP real repetido
tras los cambios de lifecycle: cobro único y dos tareas KDS completadas.

Afirmación: renovar conserva pedidos abiertos y bloquea escritores con bundle viejo.
Evidencia/refutación: test_gateway_catalog_refresh parametrizado, cambio de precio 15900 a 9999,
fallo inyectado después de publicar catálogo y antes del bundle, reinicio y reintento con
servicio anterior. Resultado: ambas variantes pasan; pedido/snapshots/movimientos previos
idénticos, nuevo pedido a 9999. Riesgo residual: la prueba de excepción no simula pérdida eléctrica.

Afirmación: devolver autoridad congela admisión entre procesos y permite recuperar ACK perdido.
Evidencia/refutación: lifecycle barriers/CLI/HTTP; cola pendiente, segundo writer, caída antes
de firmar, manifiesto omitido/alterado, replay y nueva época. Resultado: rechazo durable o
recibo idéntico; una nueva época conserva historia y reinicia sólo su secuencia firmada.
Riesgo residual: la firma atesta completitud local; la nube no puede detectar un sufijo nunca
enviado por un gateway comprometido. Límite de confianza explícito en SDD47.5.

Correcciones de auditoría: se eliminan enlaces de autorización de actores omitidos conservando
identidades históricas; se sincroniza archivo y directorio POSIX antes de activar la renovación.
13 pruebas focales correctas, incluyendo omisión completa de actor y fallo de fsync con
recuperación. Windows carece de directory fsync portable: riesgo eléctrico explícito en SDD47.5.
PostgreSQL lifecycle adicional: 1 prueba correcta; release/recovery esperan al lock de sucursal
(SQLSTATE55P03), no cambian estado prematuramente y rechazan la época anterior. Arquitectura
y trazabilidad: 20 pruebas correctas.

Auditoría Sol cerrada: verificó las tres observaciones, ejecutó 7 pruebas y Ruff focal; sin
hallazgos P0/P1 pendientes. Riesgos residuales anteriores explícitos.

Pendiente de cierre: CI de PR60, cuya ejecución es la evidencia autoritativa de integración.
Publicación de rama para ejecutar CI;
no hay despliegue, migración productiva ni provisión de sucursales autorizados en este paquete.


Regresiones detectadas por CI: la comprobación semántica de cotización se adaptó al transporte
operativo; las credenciales sintéticas y claves de fixture usan permisos 0600 POSIX. El fence
central asumía la organización predeterminada: ahora toma la organización de la sucursal bajo
lock. RED reproducido fuera del tenant predeterminado; 34 pruebas focales de fencing/SEC001
correctas después del ajuste. Estos cambios conservan las comprobaciones de seguridad.

Revisión Sol del ajuste multiorganización: 13 pruebas focales correctas y ningún P0/P1;
el lookup bloquea la sucursal persistida antes del lease. Reconciliación/concurrencia PostgreSQL
repetida tras el ajuste: 2 pruebas correctas, incluido bloqueo de primera adquisición.

Aislamiento de PCO004: la prueba histórica reinicia exclusivamente el schema de la base local
pco004_* validada, sin intentar atravesar el downgrade productivo prohibido de 0058. Secuencia
PostgreSQL cobro/cierre seguida de roundtrip 0038: 1 + 1 pruebas correctas; guard de migración
productiva intacto. CI previo cerró 897 correctas, 12 omitidas y sólo estos dos fallos corregidos;
el siguiente CI del PR verifica el conjunto final.
