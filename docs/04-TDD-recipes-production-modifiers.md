# TDD - Recetas, producción y snapshots de consumo

## TDD-TS-042 Recetas avanzadas y lotes

Casos:

- migrar recetas existentes a tipo venta con merma cero;
- crear nueva versión sin modificar la anterior;
- calcular cantidad bruta `neta / (1 - merma)` con Decimal;
- rechazar merma menor a cero o igual/mayor a uno;
- detectar ciclos directos e indirectos entre elaborados;
- calcular costo teórico por sucursal desde costo promedio vigente;
- conservar desglose y fecha del cálculo;
- crear snapshot de consumo al aceptar pedido;
- mantener snapshot al activar otra versión;
- confirmar lote idempotente y consumir componentes una sola vez;
- crear salida de elaborado con costo real del lote;
- vender elaborado sin explotar nuevamente su receta de producción;
- rechazar producción sin existencia física suficiente;
- aplicar y revertir migración conservando recetas y movimientos previos.

## TDD-TC-035 Elaborado sin doble consumo

Given se produce un lote de 10 kg de aderezo usando aceite y condimentos
When se vende un producto que consume 0.1 kg de aderezo
Then el lote contiene movimientos PRODUCTION_INPUT y PRODUCTION_OUTPUT
And la venta contiene consumo de aderezo
And no contiene un segundo consumo de aceite ni condimentos.

## TDD-TS-043 Modificadores efectivos

Casos:

- validar mínimo, máximo y grupo obligatorio antes de persistir el pedido;
- rechazar opciones ajenas al producto, inactivas o deshabilitadas en sucursal;
- calcular precio adicional en backend por cantidad de línea;
- quitar, agregar, sustituir y cambiar cantidades con Decimal;
- evitar cantidades finales negativas;
- conservar instrucción libre sin efecto automático de inventario;
- congelar opciones, texto, precios y componentes finales en línea y snapshot;
- reservar, liberar y consumir exactamente el snapshot modificado;
- mostrar en KDS los textos congelados;
- comprobar que cambios de catálogo posteriores no alteran pedidos existentes;
- migrar y revertir catálogos sin modificar órdenes anteriores.

## TDD-TC-036 Sin ingrediente y extra

Given una hamburguesa consume 100 g de aguacate
And Sin aguacate elimina 100 g
And Aguacate extra agrega 50 g y cuesta 20 pesos
When se venden dos hamburguesas con Aguacate extra
Then el total adicional es 40 pesos
And reserva y consumo contienen 300 g de aguacate
When se vende con Sin aguacate
Then el snapshot no consume aguacate.

## TDD-TC-192 Alta administrativa de opción con precio exacto

Given el administrador captura 22.00 MXN para una nueva opción ordinaria
When confirma el formulario
Then la UI convierte el importe a 2200 centavos sin `float` ni redondeo
And espera `mutateAsync` antes de cerrar y refrescar el catálogo
When la API rechaza la escritura
Then el formulario conserva la captura y presenta el error.

## TDD-TC-182 Edición y retiro histórico seguro

Given existe una venta con un modificador ordinario congelado
When el administrador edita la opción y después la elimina
Then ventas futuras usan la edición y posteriormente rechazan la opción archivada
And la venta original conserva grupo, opción, cantidad, precio y costo
When intenta eliminar la única opción de un grupo con mínimo uno
Then recibe `modifier_group_cardinality_conflict` sin archivar la opción
And tampoco puede editar el mínimo por encima de las opciones activas.
When una sucursal deshabilita una opción central
Then POS no la ofrece pero la vista administrativa central sí la conserva con el precio corporativo.
When una organización intenta agregar una opción a un grupo ajeno
Then recibe `modifier_group_not_found` sin escritura.
When intenta recrear un nombre archivado
Then recibe un conflicto de nombre estable y nunca `database_unavailable`.

## TDD-TS-117 Producto compuesto seleccionable

Suite focal de contrato administrativo, dominio de pedidos, migración y frontend. Debe cubrir lectura
central separada de la proyección POS, guardado atómico versionado, replay idempotente, conflicto de
versión, aislamiento organizacional, validación de relaciones, incluidos, precio exacto, receta
efectiva y conservación histórica. PostgreSQL verifica dos writers y SQLite verifica upgrade,
downgrade protegido, compatibilidad de bundle `v1` a `v2` y rollback de una configuración inválida.

## TDD-TC-267 Configuración administrativa autoritativa

Guardar un árbol válido incrementa una sola versión y produce auditoría; repetir misma clave/actor/
payload devuelve el resultado original. Otra carga con la misma clave o una versión obsoleta falla
sin alterar grupos, opciones ni versión. La lectura no contiene comentarios ni ingredientes
adicionales canónicos y exige rol de alcance organización más `catalog.manage`; el mismo permiso en
un rol de sucursal recibe denegación estable. Cada escritor heredado incrementa la misma versión y
una validación fallida revierte ese incremento. Opciones que no sean objetos y cardinalidades que
excedan el entero persistible se rechazan con error de negocio, nunca con 500.

## TDD-TC-268 Relaciones de producto seguras

Aceptar sólo productos corporativos activos de la misma organización y estación, con receta efectiva,
sin autorreferencia, combo o grupos seleccionables. Cada contraparte inválida revierte el comando
completo. Una opción ordinaria no puede conservar `component_product_id` y la clonación heredada
rechaza grupos que lo contengan. El gate PostgreSQL cruza
los dos comandos para demostrar que el bloqueo compartido sólo permite producto seleccionable o
combo fijo, nunca ambos, incluso cuando un writer referencia al producto C y el otro intenta
convertir C en combo fijo.

## TDD-TC-269 Precio incluido y snapshot

Con `included_selections=1`, dos selecciones ordenadas y cantidad de línea dos, la primera congela
precio aplicado cero y la segunda cobra exactamente dos veces su precio adicional. Cambiar luego
precios, nombres o recetas no altera la orden ni su snapshot. Altas, ediciones y overrides de
sucursal rechazan valores negativos, y las restricciones de base de datos sostienen la misma regla.

## TDD-TC-270 Consumo y experiencia integrada

La receta del componente se multiplica por cantidad de componente y línea, se agrega al snapshot y
gobierna reserva/liberación/consumo. La pestaña Producto compuesto muestra y edita grupos y productos
sin abrir el catálogo POS, conserva el borrador ante error/conflicto, explica incluidos en lenguaje
operativo y ofrece controles accesibles por teclado. El bundle `ord-off-catalog/v2` transporta los
campos nuevos; el hidratador también acepta `v1` e inserta ceros/nulos seguros.
