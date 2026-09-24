# ADMIN-PROD-001 — Plan de implementación del flujo confiable de productos

## 1. Objetivo y límites

Entregar un recorrido administrativo familiar para usuarios de SoftRestaurant, pero respaldado por
contratos verificables: borrador claro, captura esencial, guardado atómico, receta real y comprobación
contra POS. El paquete no inventa semántica para impuestos, canales, monedero, comisiones u otros
campos que todavía carecen de autoridad canónica.

La iniciativa se clasifica **R3** por persistencia de catálogo, precio versionado, receta, migración,
concurrencia y visibilidad operativa. La elaboración de este paquete documental es R0 y no cambia
runtime. Implementación, publicación, migración y despliegue son gates distintos.

Dentro de alcance:

- comando transaccional e idempotente de producto + precio + subgrupo;
- payload estricto y estación canónica;
- control de concurrencia por versión observada;
- borrador, validación y secciones accesibles;
- receta efectiva sin datos demostrativos;
- vista previa POS de sólo lectura;
- migración aditiva para evidencia del comando;
- auditoría, observabilidad y compatibilidad temporal de endpoints.

Fuera de alcance:

- decidir o persistir IVA/exención/no facturable;
- precios y disponibilidad por canal;
- fidelización, cargos, comisiones, precio abierto o conteo de comensales;
- almacenamiento de imágenes administrado;
- cambiar recetas dentro del guardado general;
- desplegar, migrar o editar datos productivos.

## 2. Autoridades y trazabilidad

- Producto: `PRD-FR-243`, `PRD-FR-244`.
- Diseño: SDD §48 y `SDD-ADR-036` propuesta.
- Comportamiento: `BDD-FEAT-113`, `BDD-SC-517..524`; se corrige `BDD-SC-513`.
- Verificación: `TDD-TS-115`, `TDD-TS-116`, `TDD-TC-258..264`.
- Relacionados: `PRD-FR-010`, `PRD-FR-011`, `PRD-FR-015`, `PRD-FR-213`, `PRD-FR-237`.

## 3. Criterios de aceptación del incremento

1. Un guardado válido produce exactamente una configuración canónica reconsultable.
2. Cualquier fallo revierte producto, precio, subgrupo, comando y auditoría de éxito.
3. Un replay idéntico no duplica efectos; una clave reutilizada con otra intención falla.
4. Dos ediciones concurrentes no se pisan silenciosamente.
5. Ningún control editable puede ser ignorado por la API.
6. La UI nunca envía etiquetas de estación ni genera SKU o precios de ejemplo.
7. La receta muestra datos del endpoint canónico o un estado vacío.
8. La comprobación POS usa la proyección real y no muta pedido, carrito o disponibilidad.
9. Teclado, foco, zoom 200% y ancho estrecho conservan acciones, borrador y sección activa.
10. PostgreSQL, migración, CI, QA visual y auditoría independiente quedan verdes antes de release.

## 4. Secuencia y tareas

### Gate 0 — decisión

- [x] Aprobar `SDD-ADR-036` o registrar una alternativa.
- [x] Resolver si la clave seguirá siendo manual en el MVP; esta especificación adopta captura manual
  numérica y elimina generación aleatoria del navegador.
- [x] Confirmar que los campos `OPEN-ADMIN-PROD-001..004` quedan ocultos/no editables hasta un
  incremento propio.

### Fase 1 — RED de contrato y dominio

- [x] Crear contrato estricto `admin-product-configuration-v1` en `packages/contracts`.
- [x] Crear `apps/api/tests/test_admin_product_flow.py` con TDD-TC-258, 260 y 261.
- [ ] Crear gate PostgreSQL para TDD-TC-259 e inyección de fallos.
- [x] Crear prueba de migración upgrade/downgrade/upgrade y una sola head.
- [x] Registrar RED sólo cuando cada prueba falle por la brecha descrita en TDD §RED esperado.

### Fase 2 — comando Python mínimo

- [x] Agregar migración `catalog_product_configuration_commands` sin backfill destructivo.
- [x] Separar helpers internos de `commit` para que la orquestación controle la transacción.
- [x] Implementar create/update con permiso, scope, payload estricto, hash, replay y auditoría.
- [x] Usar `category_id` y `subgroup_option_value_id`; validar cobertura y relaciones cruzadas.
- [x] Versionar precio sólo cuando cambie y exigir `expected_updated_at` al editar.
- [x] Añadir `pos-preview` reutilizando la proyección canónica, sin duplicar reglas en el controlador.
- [x] Mantener temporalmente endpoints legacy y observar su uso; no ignorar propiedades nuevas.

### Fase 3 — GREEN frontend

- [x] Reemplazar el guardado encadenado por una sola mutación con `Idempotency-Key` estable por
  intento y reutilizable después de timeout.
- [x] Mapear etiquetas a `kitchen|drinks|packing` y mostrar errores de dominio traducidos.
- [x] Eliminar SKU aleatorio, precios/canales/monedero de ejemplo y fila que parece persistida.
- [x] Presentar `Borrador sin guardar`, validación resumida y guard de cambios pendientes.
- [x] Restaurar las siete pestañas familiares y su paginación visual accesible sin cambiar por sí
  misma la sección activa.
- [x] Eliminar `sampleDagNodes`; cargar receta efectiva y permisos reales.
- [x] Implementar `Ver en POS` con sucursal explícita, elegibilidad y motivos accionables.
- [x] Ocultar o marcar como no disponibles los campos abiertos, sin enviarlos al backend.
- [x] Mantener Grupo y Subgrupo dentro del borrador mediante altas rápidas contextuales, seleccionar
  la entidad recién creada y eliminar el aviso interno de persistencia que no aporta al operador.

### Fase 4 — integración y robustez

- [ ] Ejecutar contrato API/UI y recuperación de timeout con la misma clave.
- [x] Probar un fallo entre precio y subgrupo y comprobar ausencia de parciales; quedan pendientes las
  restantes fronteras y la paridad PostgreSQL.
- [ ] Probar carrera PostgreSQL con dos sesiones reales.
- [ ] Confirmar que receta, composición y disponibilidad no cambian al guardar datos generales.
- [ ] Ejecutar revisión focal de autorización, payload estricto, logs redactados y respuestas de error.
- [ ] Ejecutar QA visual en estados vacío, borrador, error, guardado, sin receta y no elegible.

### Fase 5 — auditoría y release

- [x] Ejecutar comandos focales de TDD-TS-115/116 y `git diff --check`.
- [ ] Ejecutar suite aplicable en CI, build Admin y migración PostgreSQL.
- [ ] Solicitar auditoría Sol independiente con contexto fresco y resolver hallazgos.
- [ ] Preparar rollback de aplicación y migración sin borrar evidencia de comandos.
- [ ] Commit/PR/merge/push sólo con autorización aplicable.
- [ ] Despliegue, migración productiva y canary requieren autorización separada.

## 5. Matriz de pruebas por riesgo

| Riesgo | Intento de refutación | Evidencia exigida |
|---|---|---|
| Producto parcial | Fallar después de producto, precio y antes de subgrupo | Cero filas/efectos y error estable |
| Precio histórico corrupto | Guardar igual, cambiar, reintentar y competir | Una versión abierta; historia exacta |
| Replay duplicado | Perder respuesta y repetir clave/hash | Mismo resultado y conteos invariantes |
| Conflicto oculto | Dos ediciones con igual versión observada | Un ganador y un conflicto sin escritura |
| Cruce de alcance | Categoría/subgrupo/actor de otra organización | Denegación sin filtrar existencia |
| Campo descartado | Propiedad desconocida en payload | Rechazo de contrato, nunca 2xx |
| Receta ficticia | Producto nuevo, sin receta y con receta | Vacío real o DTO real; cero fixtures UI |
| Falsa presencia POS | Inactivo, sin precio, sin subgrupo, no disponible | Motivo canónico y cero mutaciones |
| Regresión accesible | Teclado, 200% zoom, ancho estrecho, error | Acción y foco preservados |

## 6. Afirmaciones R3 que debe cerrar la auditoría

### Afirmación A — no hay escritura parcial

- **Evidencia requerida:** transacción única e inyección de fallo en cada frontera.
- **Refutación:** provocar excepción antes de auditoría y antes del resultado del comando.
- **Resultado esperado:** ninguna fila nueva o modificada.
- **Riesgo residual:** commits ocultos dentro de helpers legacy; revisar toda la cadena llamada.

### Afirmación B — replay no duplica efectos

- **Evidencia requerida:** mismo hash/clave en secuencia y concurrencia PostgreSQL.
- **Refutación:** perder respuesta, reintentar y enviar payload distinto.
- **Resultado esperado:** recuperación exacta o conflicto estable.
- **Riesgo residual:** índices o aislamiento diferentes en SQLite; no extrapolar concurrencia.

### Afirmación C — la UI representa sólo estado canónico

- **Evidencia requerida:** refetch/response persistida, payload estricto y ausencia de fixtures.
- **Refutación:** timeout, 422, 403 y error de receta/proyección.
- **Resultado esperado:** borrador conservado, error visible y cero éxito falso.
- **Riesgo residual:** caché del cliente; invalidar claves y probar recarga.

### Afirmación D — la vista POS no concede autoridad

- **Evidencia requerida:** endpoint de lectura reutiliza proyección y autorización.
- **Refutación:** sucursal no autorizada y producto no elegible.
- **Resultado esperado:** denegación o motivo redactado, sin cambios en dominio.
- **Riesgo residual:** navegación entre aplicaciones; no transportar sesión por URL.

## 7. Entregables

- contrato y migración;
- dominio/API y pruebas Python/PostgreSQL;
- editor y pruebas semánticas;
- QA visual aprobada;
- matriz actualizada con evidencia real;
- reporte de implementación únicamente al cierre;
- runbook de migración/canary sólo cuando se autorice release.
