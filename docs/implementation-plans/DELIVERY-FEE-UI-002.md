# DELIVERY-FEE-UI-002 — contexto corporativo y panel del pedido

Riesgo R1. Alcance autorizado: presentación local de Admin y POS. Se conserva el catálogo
de tarifas, las selecciones, permisos, comandos y cálculo del servidor. No requiere PRD, SDD,
migración ni cambios de configuración productiva. Incluye la propuesta administrativa previa
todavía sin publicar.

Secuencia: distinguir contexto corporativo de sucursal operativa en el encabezado; compactar
productos y acciones del pedido; convertir envío en desplegable sin importe duplicado; comprobar
recorridos existentes y geometría en escritorio/móvil. Autoridad observable y cobertura en
BDD-SC-630/745/748/752 y TDD-TC-348/439/440/442.

Evidencia local: RED causal de encabezado corporativo y desplegable ausentes. La primera medición
de 1366x768 dejó 225 px para productos; quitar la segunda línea del cargo recuperó el mínimo de
240 px con cotización lista. La prueba espera el total exacto 19800 y confirmación habilitada
antes de medir, evitando capturar una cotización anterior mientras React recotiza las tres líneas.
Browser con API/SQLite sintética confirma selección, retiro, recarga, restauración,
gratuidad y regreso al cobro; apertura por teclado sin reducir la lista y confirmación visible.
El recorrido API conserva cobro 12300 y reporte 2800 = 2414 + 386 centavos.

Build/typecheck de Admin y POS, semánticas afectadas, browser de encabezados 1440x900/1024x768,
trazabilidad (9 pruebas), política del repositorio y diff-check verdes. Capturas locales en
`output/playwright/delivery-fee/`: catálogo, reglas, editor, pedido compacto y opciones de envío.
Los nombres, tarifas adicionales y mínimo de $500 son fixtures; no son cambios productivos.

Revisión focal R1: handlers, condiciones de deshabilitado y valores monetarios siguen ligados
al contrato anterior; no se añade estado persistente al desplegable. Se mantienen semántica
nativa, etiquetas y foco visibles; errores de tarifas quedan visibles incluso al cerrarlo.
CI remoto, publicación Git y despliegue no ejecutados en este incremento de UI. Las advertencias
de tamaño de bundles permanecen; no se cambian dependencias ni se declara validación productiva.
