# TDD - Checador de personal

## TDD-TS-074 Registro y reporte de asistencia

Pruebas de migración y dominio:

- `0032_attendance_clock` agrega códigos nullable de seis posiciones a registros heredados de
  Usuarios y Repartidores, crea el registro central de códigos y la tabla append-only de checadas;
- la reserva central única por organización acepta registros heredados sin código, exige código en
  altas nuevas y evita atómicamente duplicados entre ambos catálogos;
- el downgrade funciona sin checadas ni códigos y se bloquea cuando destruiría identidad o historial;
- alta y edición exigen `^[A-Z0-9]{6}$`, normalizan minúsculas y exigen `admin.manage`;
- editar el propio Usuario administrador desde el formulario completo conserva su asignación de
  rol cuando no cambia, acepta agregar el código y no modifica la contraseña si llega vacía;
- el registro exige `pos.operate`, sucursal activa y una sola persona activa por código;
- fecha y secuencia se calculan en backend con UTC y la zona IANA de la sucursal;
- primera, segunda y tercera checada producen `single`, entrada/salida y rechazo respectivamente;
- el reporte exige `branch.staff.read`, respeta alcance y filtra por código, día, mes y sucursal;
- día y mes simultáneos o formatos inválidos fallan sin ampliar el resultado;
- auditoría no contiene código ni nombre del empleado.

Pruebas frontend:

- el menú coloca Checador entre Pedidos y Administración;
- el diálogo muestra reloj, un único input de clave, carga, error y confirmación sin navegar;
- Usuarios y Repartidores muestran y editan Código de empleado con `maxLength=6`, patrón
  alfanumérico y error visible antes de enviar;
- Administración contiene la tarjeta y ruta protegida del reporte;
- los filtros limpian día o mes al elegir el otro y conservan el alcance de sucursal;
- las filas muestran texto y color azul para `single`, verde para `entry` y rojo para `exit`.

## TDD-TC-070 Jornada completa y reporte autorizado

Given un Usuario y un Repartidor activos con códigos alfanuméricos únicos de seis caracteres y sucursales configuradas
When cada uno registra una primera y segunda checada desde un POS autorizado
Then existen cuatro filas inmutables con hora UTC, día local y secuencia correctos
And el reporte presenta Entrada verde y Salida roja para cada persona
And filtros de código, día, mes y sucursal devuelven sólo filas autorizadas
And claves con formato inválido, duplicadas, inactivas y terceras checadas no crean registros.
