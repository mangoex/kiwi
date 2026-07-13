# TDD - Identificación telefónica de clientes en el POS

## TDD-TS-056 Flujo telefónico de cliente durante el checkout

Casos:

- el checkout no consulta clientes con un teléfono mexicano incompleto o inválido,
- la consulta usa `phone`, `branch_id` canónico y `limit`, nunca `q`,
- coincidencias telefónicas múltiples conservan nombres e identidades separadas,
- un resultado vacío habilita el formulario de alta con nombre y teléfono,
- el alta usa `POST /customers`, conserva auditoría y selecciona la respuesta,
- la selección del tipo de pedido permanece visible dentro del modal,
- un cliente seleccionado muestra sólo domicilios activos con alias y dirección,
- el alta de domicilio conserva el carrito y selecciona la nueva dirección,
- la importación no materializa `CLAVE` como teléfono,
- ningún dato personal se imprime en logs o pruebas estructurales.

## TDD-TC-049 Buscar, registrar y asignar domicilio por teléfono

Given un POS con sucursal canónica y un carrito activo
When la prueba ejercita un teléfono existente y otro inexistente
Then verifica nombres separados para coincidencias exactas
And verifica el alta con teléfono primario cuando no hay coincidencias
And verifica que el nuevo cliente queda seleccionado
And verifica que A domicilio muestra, crea y selecciona domicilios activos
And verifica que una clave heredada no se usa como teléfono.
