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
