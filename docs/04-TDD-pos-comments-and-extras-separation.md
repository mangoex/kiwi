# TDD - Separación de comentarios e ingredientes adicionales

## TDD-TS-059 Contrato add-only y comentarios sin dominio

Casos:

- preview, bulk apply y update individual de adicionales exigen add-only, cantidades Decimal
  exactas y cargo explícito; `allow_remove=true` devuelve `ingredient_extra_add_only`;
- el read model y la ejecución ocultan/rechazan exclusivamente remove heredado de
  `ingredient_variations`, conservando remove de otros módulos e históricos/KDS/impresión;
- comentario `preset_instruction` conserva precio, receta, inventario, costo, reservas y consumo;
- adicional exacto cubre snapshot, costo promedio, reserva, consumo, sin cargo y cargo explícito;
- reactivación y branch override sólo habilitan acciones add activas, con alcance, permisos,
  idempotencia y auditoría existentes;
- rutas y menús corporativos/sucursal, guards de Cajero, POS con secciones accesibles separadas y
  conversión MXN BigInt se verifican sin usar localStorage como autoridad;
- una sola head Alembic `0026_ingredient_variations`, sin archivo de migración nuevo o cambio
  destructivo en 0026.

## TDD-TC-052 Comentario y adicional nunca comparten efecto por texto

Given Sin lechuga como preset_instruction y Porción extra de aguacate como adicional add
When se crean ventas nuevas y se intenta enviar una opción remove heredada manualmente
Then el comentario sólo congela kitchen_text, el adicional ejecuta inventario/costo explícito y el
remove heredado falla sin mutar datos históricos
And administración, sucursal y POS muestran los dos conceptos en superficies separadas.
