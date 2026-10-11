# TDD-TS-139 Integración, autoridad y recuperación de agentes GrokBot

La implementación se desarrollará con adaptadores de proveedor inyectables y fixtures sintéticos.
La red real de GrokBot, secretos, migración y canary productivos no forman parte de las pruebas
locales y requieren autorización separada.

## TDD-TC-358 Contrato OpenAPI y validación de frontera

Valida sintaxis OpenAPI 3.1, operación/operationId únicos, esquemas estrictos, límites, cursores,
errores estables, `Idempotency-Key` obligatorio en todos los comandos y ausencia de rutas de
confirmación/recepción/pago/cancelación de compras o movimientos de inventario.

## TDD-TC-359 Autenticación de servicio, rotación y revocación

Con reloj determinista verifica client credentials, audiencia, expiración corta, hash/referencia de
secreto, versión de autorización y separación de las cuatro identidades. Rechaza bearer humano,
credencial de dispositivo, `X-Actor-User-Id`, token vencido, integración/identidad pausada y token
anterior después de rotación o revocación. Verifica que la frontera construya `AgentPrincipal` y
nunca un usuario humano ficticio o una sesión reutilizable.

## TDD-TC-360 Matriz de capacidades y aislamiento de sucursal

Prueba cada perfil contra todas las lecturas y comandos permitidos/denegados. Incluye organización
ajena, branch omitida o ambigua, branch fuera de allowlist y expansión de capacidad solicitada en el
body. Las consultas paginadas sólo contienen campos allowlist y excluyen PII, caja, pagos, nómina,
auditoría cruda y datos cross-branch.

## TDD-TC-361 Propuestas de catálogo, insumo y receta sin escritura anticipada

Con servicios canónicos espiados verifica que los tres comandos creen una sola propuesta
`READY_FOR_REVIEW` con origen, identidad, branch, fingerprint y expiración. Antes de aceptación no
cambian producto, insumo, receta activa, existencia ni movimientos. IDs, unidades, componentes,
versión obsoleta, acción múltiple o campo no permitido fallan sin propuesta aplicable. La migración
y el modelo exigen exactamente un creador humano o agente y preservan sin reescritura las propuestas
humanas históricas.
El oráculo confirma paridad exacta con los campos allowlist actuales de `product.create`,
`product.update`, `inventory_item.create` y `recipe.version`; v1 rechaza recetas de producción en vez
de reinterpretarlas como receta de venta. Producto e insumo exigen scope corporativo y el test falla
si el servicio usa `BRANCH_ID`, deriva una sucursal por omisión o crea disponibilidad parcial.

## TDD-TC-362 Borrador de compra sin efectos financieros ni inventario

Verifica que el bot de Compras cree únicamente `DRAFT` con proveedor/presentación/sucursal válidos.
Confirma ausencia de recepción, costo promedio, movimiento, cuenta por pagar y retiro de caja. Las
rutas Agent Tools no pueden invocar confirmación, cancelación, pago o recepción, incluso si el token
incluye una capacidad inventada. El borrador conserva creador agente mediante la referencia tipada y
el constraint XOR; confirmar o cancelar conserva actor humano y nunca fabrica `created_by`.

## TDD-TC-363 Idempotencia, carreras y fallo parcial

En PostgreSQL aislado ejecuta dos comandos concurrentes con misma identidad y key: mismo hash produce
una referencia, distinto hash produce conflicto y nunca dos entidades. Inyecta fallo antes y después
del commit para demostrar cero escritura parcial o una operación recuperable. El replay reautoriza
identidad, versión y branch y no entrega resultado después de revocación.

## TDD-TC-364 Firma, reintento y redacción de callbacks

Con reloj y transporte inyectados valida HMAC sobre key ID/timestamp/event ID/body, rotación
current/next separada de client credentials, ventana de replay, event ID estable, backoff acotado y
terminalidad. Prueba URL inicial y redirección hacia loopback, RFC1918, link-local, metadata, host
interno, self-call y DNS rebinding; ninguna abre conexión. Demuestra que el callback no ejecuta
dominio y que callback, logs, métricas y trazas omiten secreto, token, idempotency key, cuerpos
completos, PII, texto libre, recetas, costos y existencias.
Inyecta crash antes y después del commit de una transición: propuesta/compra y evento outbox aparecen
juntos o ninguno; después del commit el worker recupera el mismo event ID sin reaplicar dominio.

## TDD-TC-365 Hub, Agentes y estados operativos

La prueba semántica de Admin verifica tarjeta GrokBot default-off, salud y bitácora redactada en
Integraciones; cuatro identidades separadas en Agentes; confirmación de creación/rotación; secreto
visible una sola vez; capacidades y sucursales efectivas; estados desconectado, conectado, degradado,
drenando y pausado. El test de rollback exige que drenando rechace comandos nuevos, permita sólo
consulta propia preexistente y que pausado o revocado nieguen toda consulta. TypeScript estricto y
build Admin se activan cuando exista implementación de UI.
También demuestra que los flags de API y Admin están apagados por defecto, que no existen rutas ni
tarjeta configurables en ese estado, que rotar exige confirmación y descarte explícito del secreto, y
que dos ediciones con la misma `expected_authorization_version` no producen lost update.

## TDD-TC-366 Retención cifrada y minimización

Con payloads sintéticos verifica que la política habilitada conserve el original cifrado y restrinja
su lectura a la autoridad de auditoría, mientras el monitor usa sólo resumen redactado. Política
deshabilitada no persiste cuerpo. Ningún caso guarda transcript de WhatsApp y la expiración elimina
el payload mediante un proceso auditable sin borrar el command log.

## TDD-TC-367 Trazabilidad y gates de entrega R3

Ejecuta trazabilidad documental y `git diff --check`. Cuando se implemente runtime agrega Ruff,
mypy focal, pruebas API/dominio, migración ida/vuelta SQLite y PostgreSQL, contrato/E2E con relay
simulado, typecheck/build Admin y auditoría independiente. CI ejecuta la suite completa aplicable.
Configuración, migración, secretos, red real, despliegue y canary siguen siendo gates separados.

## TDD-TC-368 Orquestador único y delegación técnica

La prueba contractual simula un solo Administrador Kiwi con cuatro herramientas especialistas. Cada
herramienta obtiene o usa exclusivamente la identidad técnica allowlist de su perfil y Kiwi ignora o
rechaza cualquier perfil, capacidad, organización o sucursal que el orquestador intente afirmar en
el cuerpo. Una credencial de un especialista no accede a herramientas de otro; la bitácora conserva
la identidad ejecutora sin multiplicar conversaciones visibles para el usuario.

## TDD-TC-369 Ventas agregadas minimizadas

Construye snapshots sintéticos confirmados en una sucursal, con varias monedas, servicio, líneas y una
corrección posterior, y comprueba el rechazo de otra sucursal. Verifica que `administrator` con
`agent.sales.read` sólo consulta la sucursal allowlist y periodos UTC de hasta treinta y un días; los
totales se derivan de snapshots inmutables,
las correcciones permanecen separadas y los productos se agregan sin folio, pedido, pago, caja o PII.
El agregado se ejecuta en SQL sin materializar todos los snapshots, consolida renombres por
`product_id` y aplica `top_limit` por moneda. Los otros tres perfiles, periodos inválidos y sucursales
fuera de alcance fallan cerrados.

## TDD-TC-370 Límite distribuido y configuración fail-closed

Verifica límites global/identidad con señal HMAC, respuesta `429` y `Retry-After`, y `503` cuando el
limitador falla. Configuración productiva con Agent Tools habilitado rechaza ausencia de Redis o del
secreto HMAC dedicado; ningún bucket, log o respuesta conserva Authorization en claro. El script
atómico rechaza primero una identidad agotada sin incrementar el bucket global. La autenticación
pretoken usa namespace y señal de red separados, por lo que un `client_id` conocido con secreto
inválido no agota la identidad ni las herramientas. Las pruebas capturan eventos redactados
`agent.request.accepted|denied` con operación, sucursal, resultado y motivo estable.
