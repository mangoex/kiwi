# TDD - Variaciones preestablecidas del POS

## TDD-TS-057 Variaciones preestablecidas seguras y efectivas

Casos:

- crear fuerza `preset_instruction`, precio cero, cantidades cero, artículos nulos, sin inventario y
  `kitchen_text` normalizado;
- se rechaza duplicado por producto ignorando mayúsculas y espacios, y se auditan alta, edición,
  archivo/reactivación y excepción de sucursal;
- un grupo avanzado homónimo no se reutiliza ni se muta; un grupo seguro sólo de presets sí puede
  reutilizarse, y `display_order` malformado se rechaza de forma explícita en POST y PUT;
- administrador, supervisor y cajero reciben sólo las operaciones que permiten sus permisos y la
  sucursal activa canónica;
- `available`, `unavailable` e `inherit` afectan sólo la sucursal autorizada;
- pedido con varias notas conserva una línea, snapshot y total/consumo base; texto malicioso no
  sustituye un preset y `instruction` libre sigue funcionando;
- el read model/API KDS y payload de print kitchen incluyen `selected_modifiers` y sus
  `kitchen_text`; la pantalla KDS real queda fuera de alcance;
- rutas corporativa y de sucursal, visibilidad de tarjeta y POS usan `fetchApi`, sesión canónica y
  botones `aria-pressed` para presets sin alterar el checkout POS-CUST-001.

## TDD-TC-050 La nota preestablecida no puede mutar el dominio de venta

Given una nota activa y dos sucursales con permisos distintos
When se crea un pedido con dos notas y un texto controlado por cliente
Then el backend usa los textos congelados de las opciones, conserva precio e inventario base y
expone las notas a KDS e impresión
And el frontend sólo permite que el cajero las seleccione con controles táctiles accesibles,
cierra el modal tras un reintento vacío y oculta la tarjeta de sucursal sin catalog.branch.manage
And las rutas administrativas niegan el acceso o el alcance no autorizado.
