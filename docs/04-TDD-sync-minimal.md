# TDD - Sincronizacion minima nube-gateway

## TDD-TS-023 Sync Command Minimal

Casos:

- recibir comando con `idempotency_key`,
- rechazar comando sin campos obligatorios,
- asignar checkpoint monotono por sucursal,
- crear evento de confirmacion,
- registrar auditoria de sincronizacion,
- reintentar la misma clave idempotente sin duplicar,
- listar eventos posteriores a un checkpoint,
- conservar orden ascendente al descargar eventos,
- consultar estado de sincronizacion de sucursal.

## TDD-TC-014 Reintento idempotente de comando local

Given la API central recibio un comando local  
And devolvio checkpoint y evento de confirmacion  
When el gateway reintenta el mismo comando con la misma `idempotency_key`  
Then la API devuelve el mismo checkpoint  
And no crea otro comando confirmado  
And no crea otro evento.

## TDD-TC-015 Descarga de eventos pendientes

Given existen eventos con checkpoints 1 y 2
When el gateway solicita eventos despues del checkpoint 1
Then la API devuelve solo el evento con checkpoint 2.

## TDD-TC-016 Estado de sincronizacion

Given existen comandos confirmados para la Sucursal Piloto
When el operador consulta el estado de sincronizacion
Then la API muestra ultimo checkpoint, total de comandos y total de eventos.
