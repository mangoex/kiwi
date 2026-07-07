# TDD - Sincronizacion minima nube-gateway

## TDD-TS-023 Sync Command Minimal

Casos:

- recibir comando con `idempotency_key`,
- rechazar comando sin campos obligatorios,
- asignar checkpoint monotono por sucursal,
- crear evento de confirmacion,
- registrar auditoria de sincronizacion,
- reintentar la misma clave idempotente sin duplicar,
- listar eventos posteriores a un checkpoint.

## TDD-TC-014 Reintento idempotente de comando local

Given la API central recibio un comando local  
And devolvio checkpoint y evento de confirmacion  
When el gateway reintenta el mismo comando con la misma `idempotency_key`  
Then la API devuelve el mismo checkpoint  
And no crea otro comando confirmado  
And no crea otro evento.
