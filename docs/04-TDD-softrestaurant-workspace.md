# TDD — SR-WORKSPACE-001

Estado: estrategia y casos implementados; evidencia local consolidada en el cierre del plan.
Las pruebas de baseline se complementan con previews, recibos, carreras reales y recorridos UI. Una implementación comienza con
RED dirigido del caso cuyo comportamiento cambia; sin tests permanentemente fallidos ni exclusiones
para obtener verde. Datos numéricos de referencia son constantes reproducibles, nunca tolerancias
float. Pruebas usan SQLite aislado; PostgreSQL real es obligatorio al cambiar persistencia,
bloqueo, SQL o concurrencia. CI sólo acredita las suites que realmente ejecuta.

## TDD-TS-123 Nota completa, autoridad Python y recuperación

Frontera y dominio Python, editor compartido en Admin/POS y recorrido crítico de recepción/caja.
Archivos actuales de baseline: `apps/api/tests/test_branch_purchases_and_courtesies.py`,
`apps/api/tests/test_platform_api.py`, `tests/frontend/test_pos_purchases_and_reprint.mjs`.
Pruebas nuevas: `test_purchase_workspace.py`, `test_workspace_compound_copy.py`,
`test_purchase_workspace_postgres.py`, `test_purchase_workspace_migration.py`, contrato HTTP,
`test_purchase_workspace.mjs` y `test_purchase_workspace_e2e.mjs`. El E2E usa administrador
sintético autorizado; no certifica una matriz completa de roles ni sustituye los guards de API.

## TDD-TC-280 Recepción multilínea real y compensación

Extender el test llamado multilínea para enviar tres partidas del mismo insumo y dos presentaciones:
rendimientos 10, 5 y 10; cantidades 2, 1 y 0.5; precios 250.00, 19.99 y 0.29; descuentos 1.00,
0.29 y 0.00; impuestos 40.00, 3.15 y 0.02. Esperar cantidades base 20, 5 y 5, subtotal 520.135000,
descuento 1.290000, impuesto 43.170000, total 562.015000 y costo recibido 518.845000. Confirmar debe incrementar
saldo físico en 30 unidades base, dejar tres recepciones y cero retiros si no usa caja. Replay
mantiene efectos; cancelar preserva recepciones, agrega compensaciones y restaura saldo físico.

Fixture `test_three_line_cash_receipt_has_exact_prior_weighted_cost_and_compensation` con
10 unidades a costo 2.00: recibir lo anterior produce
40 unidades y promedio redondeado a seis decimales 13.471125. Con efectivo validar retiro único
56202 centavos, replay y compensación; no fabricar tres retiros. La prueba actual de efectivo
continúa cubriendo caja requerida y retiro/depósito de una compra.

## TDD-TC-281 Atomicidad y fallos de recepción

Partidas válidas seguidas de presentación inexistente deben fallar sin documento/líneas, inventario,
costo ni caja. Repetir con descuento superior al subtotal, cantidad/rendimiento inválidos, proveedor
inactivo y stock físico negativo al confirmar. Inyectar fallo entre recepciones y entre retiro/commit
para demostrar rollback completo. Reservas no sustituyen saldo físico para promedio.
Baseline de este paso cubre presentación inválida en última fila; los demás contraejemplos deben
ejecutarse al intervenir sus contratos.

## TDD-TC-282 Creación recuperable y confirmación independiente

Perder respuesta después del commit y reenviar misma clave/actor/payload: mismo ID, una evidencia de
comando, documento, auditoría y líneas. Otra carga/actor/alcance con clave ocupada: conflicto sin
efectos ni filtración. Dos writers concurrentes PostgreSQL: un ganador durable, sin 500 por unique.
Reautorizar replay tras revocar permiso. Clave de crear nunca confirma ni collide con confirmar;
confirmación propia se repite sin duplicar ledger/costo/retiro. No sortear unique de folio.
Migración aditiva conserva documentos/historia y rollback no elimina comandos o ledger.

## TDD-TC-283 Alcance y flujo de editor

En ambas apps agregar/editar/quitar tres filas, revisar proveedor/presentación, conservar captura
ante fallo y mostrar detalle persistido. Cambio sucursal/organización limpia contexto tras aviso;
cache separado y respuesta tardía ajena descartada. Servidor rechaza IDs ajenos aunque UI los envíe.
Permiso de compras no concede retiro ni edición histórica de precio. Fecha documental preserva día;
contrato HTTP/schema y método de pago se prueban sin atribuir cuentas por pagar a `other`.
E2E real nota -> confirmación -> kardex/costo/caja -> cancelación; QA visual en tamaños afectados.

## TDD-TC-284 Decimal y paridad de previews

Preview y writer llaman la misma función; verificar constantes de TC-280, borde 0.145 permanece 0.145000,
importes/cantidades/costos seis y retiro final en centavos, descuento igual subtotal, cero válido y límites persistibles. Rechazar
NaN/Infinity, payload no objeto, campos desconocidos, colecciones/cuerpos excesivos y dimensión no
autorizada. Resultado externo sólo cadenas decimales; no usar `float` en Python ni aritmética
JS de dinero/conversiones/merma. Precio/usable_content y precio/base_unit_yield se distinguen y
no se sustituyen sin validación explícita. Bruta neta=9/merma=0.1 da 10 bajo fórmula canónica.

## TDD-TC-285 Pureza y vigencia

Comparar antes/después documento, movimientos, caja, costo, recetas/versiones, historial y auditoría
de mutación al pedir cada preview. Ningún cambio. Captura/versionado de UI descarta respuesta obsoleta;
backend reautoriza y recalcula al guardar/confirmar ante relaciones cambiadas. Sin red/error no hay
totales simulados ni nueva escritura. No se usan helpers con commit para preview.
Inyectar fallo SQL con un marcador sensible en cada frontera nueva: HTTP 503 de código/mensaje
constantes y ausencia del marcador tanto en la respuesta como en logs de aplicación.

## TDD-TS-124 Relaciones de catálogo y copia de compuestos

Pruebas Python/API de relaciones, funciones de cálculo, escritor versionado y UI contextual.
Reutiliza TDD-TS-040/117 para invariantes existentes, sin duplicar dominio ni relajar restricciones.
Cambio de persistencia/concurrencia exige PostgreSQL; cambios de bundle/migración dual activan
SQLite/gateway y compatibilidad de lectores, únicamente cuando el diff los afecte.

## TDD-TC-286 Proveedor, unidades y ausencia de defaults silenciosos

Proveedor ausente/inexistente/inactivo/ajeno con cero, uno y varios proveedores disponibles:
error estable, sin sustitución ni historial parcial. Unidad base corresponde al insumo; unidades
incompatibles sin equivalencia no pasan. Empaque pieza/caja con contenido autorizado sí puede
representar masa/volumen, sin inferir del nombre. Rendimiento/contenido faltante o no positivo falla;
precio/impuesto cero permitido se preserva. Precio informativo no muta promedio contable.

## TDD-TC-287 Alta contextual y permisos

Crear presentación desde compra con permiso correcto, releer su alcance y regresar sin perder
partidas. Cancelar alta no cambia captura. Denegar permiso, sucursal/organización ajenas e intento
de precio histórico reservado. Alta crea catálogo/historial autorizado pero ninguna recepción/caja.
Labels de precio, equivalencia, costo informativo y promedio coinciden con las fuentes Python.

## TDD-TC-288 Incluidos, consumos y separación de conceptos

Reutilizar casos de TDD-TC-269/270: incluidos por orden, extras en centavos, mínimos/máximos,
componentes/restricciones y snapshots inmutables. Preview de selección no crea pedido/reserva.
Comentario no consume; insumo adicional y componente usan su contrato; combo fijo se escribe por
su comando separado. No ampliar máximo cero ni nested compounds. Revisar bundles sólo si cambian.

## TDD-TC-289 Copia completa atómica y versionada

Copiar grupos/opciones con IDs del destino y dependencias válidas conserva orden, cantidades,
cardinalidades, incluidos/recargos; excluye precio base/receta/combo/disponibilidad. Una última opción
inválida revierte todo. Versiones de origen/destino obsoletas, dos writers, clave con carga distinta
y replay son contraejemplos obligatorios. No comparte grupos mutables ni altera pedidos históricos.
PostgreSQL demuestra bloqueo con writers hermanos; no sustituirlo por SQLite.
