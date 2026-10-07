# MODIFIER-EDITOR-002 — reparación del editor de producto

R3: edición de configuraciones con recargos y consumo. PRD-FR-096 explicita la lectura limitada de
identidades de insumos; PRD-FR-095/245 mantienen su alcance. Se extienden SDD §48.7,
BDD-SC-591 y TDD-TC-308 para cubrir las regresiones existentes.

1. Reproducir bloqueo de opciones ordinarias y cantidades Decimal en Chrome; rechazos negativos en API.
2. Exponer candidatos mínimos del catálogo autorizado y campos de efectos existentes sin fórmulas nuevas.
3. Preservar referencias, indicador de inventario y texto; limpiar incompatibilidades sólo al cambiar tipo.
4. Verificar guardado/relectura, permisos, versión, replay, rollback, typecheck, QA visual y auditoría Sol.

Preguntas operativas: ¿por qué guardar está deshabilitado? (mensaje junto al botón);
¿qué actor/versión aplicó el cambio y un reintento lo duplicó? (comando y auditoría canónicos);
¿un error dejó datos parciales? (pruebas de rollback/versionado). No se agrega telemetría redundante.

No hay migraciones ni dependencias nuevas. Publicación, despliegue y datos productivos quedan fuera
de esta reparación local. La evidencia y refutación se completan tras los gates focales.

## Evidencia local y cierre

RED: Chrome rechazó la afirmación de que el nombre de una opción `add` era editable; dos casos
API demostraron que cantidades negativas devolvían 200 y persistían una versión. La cantidad
Decimal `1.000000` estaba excluida por la expresión regular del editor.

GREEN: `test_compound_product_admin.mjs` completó creación, edición, guardado, limpieza al cambiar
a instrucción, bloqueo de fracciones/negativos y QA sin recorte de controles a 1440/1100 px.
Se inspeccionaron ambas capturas en `output/playwright/modifier-editor-002-ingredients-*.png`.
Las tres pruebas semánticas de modificadores, typecheck/build Admin, mypy del módulo y Ruff de
API/tests pasaron. Trazabilidad: 9 passed. Política de repositorio y `git diff --check`: verdes;
sólo se renovaron los hashes exactos de dos fixtures sintéticos ya autorizados.

API focal: 11 passed en configuración/compuestos/escritores heredados; 1 passed para el actor de
catálogo sin lectura de inventario; 4 passed para cantidades negativas e indicadores de tipo
inválido (los dos casos negativos repiten cobertura de la ejecución inicial). Incluyen relectura
de los cinco efectos ordinarios, replay, conflicto de versión, aislamiento de sucursal y rollback.

Afirmación: editar nombre/recargo no cambia silenciosamente consumo o cocina.
Evidencia: UI y API conservan `inventory_effect=false`, cantidades y `SERVIR APARTE` al renombrar.
Refutación: se guardaron y releyeron los cinco efectos, y se cambió explícitamente uno a instrucción.
Resultado: se preservan campos ordinarios y la instrucción limpia referencias/cantidades en la UI.
Riesgo residual: no se inspeccionaron configuraciones ni pedidos productivos.

Afirmación: la edición sigue autorizada y no amplía la consulta de existencias/costos.
Evidencia: actor corporativo con sólo `catalog.manage` obtiene candidatos mínimos y recibe 403 en
`/inventory/items`; un actor de sucursal sigue recibiendo 403 en configuración.
Refutación: se archivó un insumo y se intentó leer inventario sin ese permiso.
Resultado: se excluyó el insumo y el DTO contiene sólo ID/nombre/SKU/unidad.
Riesgo residual: lista sin paginación, igual que los candidatos de productos existentes.

Afirmación: cantidades negativas o indicadores no booleanos no escriben datos parciales.
Evidencia/refutación: ambos campos negativos y `inventory_effect` con string/entero se rechazaron;
la relectura mantuvo versión cero y grupos vacíos. Resultado: cuatro regresiones verdes.
Riesgo residual: PostgreSQL no se ejecutó en este equipo, sin servicio/URL local configurada.

La auditoría Sol independiente confirmó los bloqueos y cerró sin hallazgos accionables tras
acotar el PRD y aclarar referencias de insumos. No cambian cálculo Python, bloqueos, versión,
idempotencia, esquema ni históricos. CI, PostgreSQL, publicación, despliegue y canary productivo
permanecen pendientes; el build sólo advierte el tamaño del bundle existente.
