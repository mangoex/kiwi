---
name: kiwi-operations-team
description: Orquestación multi-agente gobernada para RestaurantOS (Kiwi). Coordina los 4 perfiles técnicos (kiwi-administrador, kiwi-inventarios, kiwi-cocinero, kiwi-compras) combinando modelos Argon (inherit) y Flash para consultar ventas, cajas abiertas, cortes de caja, inventario, umbrales, recetas y proveedores, así como registrar recetas versionadas y programar compras automáticas por umbral.
---

# Kiwi Operations Team (`kiwi-operations-team`)

Habilidad operativa oficial para interactuar con **RestaurantOS (Kiwi)** mediante la arquitectura multi-agente gobernada (`GROKBOT-001` / `/api/v1/agent-tools/*` + puente de dominio `scripts/kiwi_agent_cli.py`).

## 1. Topología de Agentes y Modelos (Argon + Flash)

El sistema implementa el patrón **Coordinator / Dispatcher** con aislamiento estricto de credenciales y capacidades por perfil:

| Subagente | Perfil Técnico | Modelo Recomendado | Responsabilidad Operativa |
| :--- | :--- | :--- | :--- |
| **`kiwi-administrador`** | `administrator` | `inherit` (Argon/Pro) | Único interlocutor con el usuario. Consulta ventas (`sales-summary`), cajas abiertas (`open-registers`), cortes de caja (`cash-cuts`), pagos por método (`payments-by-method`), gastos (`expenses-summary`), conciliación diaria (`daily-reconciliation`), propone catálogo (`propose-catalog`) y delega a especialistas. |
| **`kiwi-inventarios`** | `inventory` | `flash` | Consulta catálogo de insumos (`inventory-items`), existencias y umbrales (`inventory-stock`), detecta insumos en o bajo el mínimo (`check-thresholds`), consulta kardex (`inventory-movements`) y propone insumos (`propose-inventory-item`). |
| **`kiwi-cocinero`** | `kitchen` | `flash` | Consulta productos (`catalog-items`), recetas activas (`recipes`) y registra/versiona recetas (`propose-recipe` y `apply-recipe`). |
| **`kiwi-compras`** | `purchasing` | `flash` | Consulta proveedores (`suppliers`), presentaciones comerciales (`purchase-presentations`), necesidades (`purchase-needs`), borradores (`purchase-drafts`), programa órdenes de compra (`create-purchase-draft`) y ejecuta la rutina automática de reabastecimiento por umbral (`auto-replenish-thresholds`). |

## 2. Puente Ejecutivo Canónico (`kiwi_agent_cli.py`)

Todos los agentes ejecutan sus lecturas y escrituras gobernadas mediante:

```bash
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile <perfil> [--branch-id <sucursal>] <comando> [opciones]
```

## 3. Comandos Principales por Caso de Uso

### A. Consultas Administrativas (`--profile administrator`)
```bash
# Cajas abiertas en vivo y ventas acumuladas por turno
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile administrator open-registers

# Resumen de ventas confirmadas y top productos
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile administrator sales-summary

# Ventas desglosadas por método de pago
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile administrator payments-by-method

# Gastos operativos confirmados y cortes de caja finalizados
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile administrator expenses-summary
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile administrator cash-cuts
```

### B. Revisión de Inventario y Umbrales (`--profile inventory`)
```bash
# Existencias actuales vs. min_quantity y max_quantity
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile inventory inventory-stock

# Detectar únicamente insumos que llegaron o bajaron del umbral mínimo
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile inventory check-thresholds
```

### C. Consulta y Registro de Recetas (`--profile kitchen`)
```bash
# Listar recetas activas con sus componentes
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile kitchen recipes

# Registrar y activar una nueva versión de receta con Idempotency-Key
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile kitchen apply-recipe \
  --product-id "<product_uuid>" \
  --yield-quantity "1" \
  --yield-unit-id "<unit_uuid>" \
  --components-json '[...]' \
  --idempotency-key "<idempotency_key>"
```

### D. Programación de Compras y Rutina Automática de Umbral (`--profile purchasing`)
```bash
# Rutina completa: revisa inventario <= min_quantity, calcula paquetes hasta max_quantity y programa órdenes DRAFT por proveedor
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile purchasing auto-replenish-thresholds

# Consultar órdenes de compra en borrador programadas en el sistema
python3 .agents/skills/kiwi-operations-team/scripts/kiwi_agent_cli.py --profile purchasing purchase-drafts
```
