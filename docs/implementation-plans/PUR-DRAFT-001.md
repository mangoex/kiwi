# PUR-DRAFT-001 — Borradores de compra inspeccionables y editables

Fecha: 2026-10-27. Riesgo R3 por persistencia e inventario/dinero futuro. Este paquete no autoriza
deploy, migración, configuración ni datos productivos.

## Resultado e invariantes

Permitir ver todas las partidas, editar sólo una compra `draft` de la sucursal autorizada y retirarla
de pendientes mediante cancelación auditada. Ver, editar y descartar no crean inventario, costo, caja
ni compensaciones. No existe borrado físico; confirmar/cancelar conservan su autoridad actual.

## Secuencia

1. Contrato y RED: esquema de update, pruebas API/versiones/replay/ausencia de efectos y semántica UI.
2. Persistencia: versión aditiva y recibos idempotentes; downgrade bloqueado con historia de edición.
3. Dominio/API: PUT atómico bajo lock; confirmación y descarte cotejan la versión revisada.
4. UI: Ver para lectura; Editar/Confirmar/Eliminar para manager; editor compartido hidratado.
5. Gates focales, migración aislada, QA visual y auditoría Sol independiente.

## Afirmaciones R3 a refutar

- Una edición/replay aumenta versión una sola vez: contar versión, auditoría, recibos y líneas.
- Editar o descartar no produce efectos: comparar movimientos, costo y caja antes/después.
- Edición contra confirmación/cancelación tiene un único orden serial: barreras PostgreSQL y estado final.
- Respuesta perdida no crea una intención nueva: repetir misma key/body y conflictar key reutilizada.

CI, PostgreSQL aislado disponible, navegador, despliegue, migración y producción se reportan por
separado; ningún gate omitido se presenta como aprobado.
