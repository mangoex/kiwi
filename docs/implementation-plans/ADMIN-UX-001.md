# Plan de Implementación: Mejoras de UI/UX en Catálogos Admin (ADMIN-UX-001)

> Estado 2026-09-23: parcialmente superado. Las tareas de Insumos pueden conservarse como mejoras
> visuales R2. El guardado de Productos, receta, navegación de secciones y verificación POS pasan a
> `ADMIN-PROD-001`, porque la revisión encontró brechas de contrato y persistencia R3 que este plan
> asumía inexistentes. `UX-003` a `UX-006` no deben implementarse de forma aislada contra el contrato
> actual.

Este documento detalla el plan de implementación para refinar el diseño Master-Detail de los catálogos de Insumos y Productos en la aplicación web de administración (`admin-web`), acercando la experiencia al modelo mental de Soft Restaurant pero con estándares modernos SaaS.

## 1. Contexto y Objetivos

- **Problema:** El cliente requiere que el sistema sea familiar a la vista y operación de su software anterior (Soft Restaurant), pero sin heredar las malas prácticas de UX de los años 90 (ventanas flotantes MDI, checkboxes aglomerados, mala visualización de KPIs financieros).
- **Objetivo:** Refinar el diseño Master-Detail existente (implementado en commits recientes) agregando indicadores visuales claros (KPIs de costeo), modales rápidos `[+]` in-line para evitar pérdida de contexto, y controles táctiles modernos (Toggles en vez de checkboxes).
- **Riesgo:** R2 (Refactor de UI con impacto en comportamiento observable). No se cambian modelos de dominio backend ni persistencia. Los cálculos siguen siendo deterministas en Python.

## 2. Especificaciones Técnicas y Funcionales (UX)

- **UX-001 (Insumos - Tarjetas de Costeo):** Mostrar el "Costo Promedio" y "Último Costo" usando componentes visuales tipo `Card` o `Badge` (Read-only) para diferenciarlos de los inputs editables.
- **UX-002 (Insumos/Productos - Creación In-line):** Integrar un botón `[+]` adyacente a selectores (Ej: Categoría, Unidad) que despliegue un modal rápido sin cambiar de ruta, manteniendo el estado del formulario principal intacto.
- **UX-003 (Productos - Toggles de Servicio):** Reemplazar los checkboxes genéricos para los canales de venta (Comedor, Domicilio, Rápido) con `Icon Toggles` o `Switch` modernos (Ej: iconos iluminados al estar activos).
- **UX-004 (Recetas - KPI de Salud Financiera):** En la pestaña de receta, agregar una barra de resumen flotante (Sticky Summary) que muestre el "Costo de Receta" y "Margen de Utilidad". Aplicar colores semánticos (verde = >66% margen, rojo = <33% margen, amarillo = intermedio).
- **UX-005 (Recetas - Autocompletado):** En la grilla de ingredientes de la receta, la búsqueda de insumos debe ser in-line (typeahead/dropdown) en lugar de requerir una ventana de búsqueda separada.
- **UX-006 (Productos - Navegación entre configuraciones; sustituido por ADMIN-PROD-001):**
  Presentar secciones como pestañas cápsula accesibles; las flechas desplazan el contenedor sin
  paginar el estado ni cambiar la sección activa. El contrato definitivo está en SDD §48.

## 3. Plan de Pruebas (TDD / BDD)

- **BDD:** Se actualizará `docs/03-BDD-admin-saas-catalog.md` con un nuevo escenario (`BDD-SC-515`) que describa la experiencia de captura rápida y visibilidad de KPIs.
- **TDD:** Las pruebas semánticas Node verifican que los badges de costo existen, los toggles cambian de estado y el modal in-line no borra el formulario padre (`tests/frontend/test_admin_ux_improvements.mjs`); la navegación accesible de las siete configuraciones se cubre de forma focal en `tests/frontend/test_product_capsule_tabs.mjs`.

## 4. Tareas (Ruta Crítica)

1. **[Fase Roja]** Actualizar BDD y TDD (Tests fallando).
2. **[Fase Verde]** Modificar `ItemsList.tsx` y `InsumosWindow.css` (UX-001, UX-002).
3. **[Fase Verde]** Modificar `ProductsList.tsx` (UX-003, UX-004, UX-005).
4. **[Auditoría]** Correr Linter, TS Typecheck, y Tests Semánticos.

---
**NOTA:** Los cálculos matemáticos (ej. costo teórico total, utilidad) se mantienen en el backend según las directivas SBD; el frontend solo formatea y colorea los datos provistos por la API o calcula la representación visual basada en los datos en crudo.
