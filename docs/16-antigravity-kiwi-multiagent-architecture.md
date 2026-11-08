# 05. Arquitectura Multi-Agente y Manual Operativo de Bots (Kiwi — RestaurantOS)

**Organización:** Kiwi Restaurante (`018f6f73-2d0a-74f0-8f1c-000000000001`)  
**Entorno en Producción Enlazado:** `https://kiwipos.mimenu.onl`  
**Usuario de Servicio Activo:** Miguel Gonzalez (`mangoex@gmail.com`) — Administrador Corporativo / Dueño  
**Estándar de Gobernanza:** `GROKBOT-001` (`/api/v1/agent-tools/*` + API REST Platform + Puente de Dominio `kiwi_agent_cli.py`)  
**Orquestación de Modelos:** Híbrida **Argon (`inherit`) + Flash (`flash`)** bajo patrones Google ADK y Antigravity Subagents.

---

## 1. Diagnóstico de la Integración Original vs. Nueva Arquitectura en Antigravity

Durante la auditoría forense del repositorio `mangoex/kiwi` se identificaron las tres causas técnicas por las cuales el copiloto interno no igualaba la capacidad operativa de agentes externos:

1. **Un solo turno de herramientas en el Copiloto Interno:** [`copilot_engine.py`](https://github.com/mangoex/kiwi/blob/main/apps/api/restaurant_os/copilot_engine.py) ejecutaba una sola ronda de llamada a herramientas (`tools=COPILOT_TOOL_DEFINITIONS`) seguida inmediatamente de una llamada de síntesis sin herramientas (`tools=None`), impidiendo flujos multi-paso (ej. *revisar inventario $\rightarrow$ detectar faltantes bajo umbral $\rightarrow$ consultar presentaciones de proveedor $\rightarrow$ programar orden de compra*).
2. **Desconexión de herramientas de escritura en el Copiloto y MCP:** [`copilot_tools.py`](https://github.com/mangoex/kiwi/blob/main/apps/api/restaurant_os/copilot_tools.py) declaraba `propose_recipe` pero omitía su manejador en `dispatch_copilot_tool`, y [`mcp_server.py`](https://github.com/mangoex/kiwi/blob/main/apps/api/restaurant_os/mcp_server.py) únicamente exponía las 16 herramientas de lectura (`READ_TOOL_SPECS`).
3. **Frontera Gobernada Completa en `agent_tools.py`:** El módulo [`agent_tools.py`](https://github.com/mangoex/kiwi/blob/main/apps/api/restaurant_os/agent_tools.py) sí implementa la totalidad de las **16 herramientas de lectura** y las **4 herramientas de escritura gobernada** con autenticación por perfil técnico, control de capacidades (`BASELINE_CAPABILITIES`), alcance por sucursal, `Idempotency-Key` obligatoria y auditoría inmutable en `audit_events`.

---

## 2. Topología de los 4 Agentes y Eficiencia de Modelos (Argon + Fallback a Flash)

Se implementó el patrón **Coordinator / Dispatcher** jerárquico donde el usuario interactúa **exclusivamente** con el Administrador (`kiwi-administrador`), quien coordina a los 3 especialistas privados:

```
                       ┌────────────────────────────────────┐
                       │              USUARIO               │
                       └─────────────────┬──────────────────┘
                                         │ (Único canal de conversación)
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │      kiwi-administrador (Argon -> Fallback Flash)    │
              │  Perfil: administrator                               │
              │  Modelo: inherit (Argon/Pro) con fallback a Flash    │
              │  Lecturas: Ventas, Cajas Abiertas, Cortes, Pagos,    │
              │            Gastos, Conciliación Diaria, Catálogo     │
              │  Escrituras: Propuestas de Catálogo                  │
              └───────┬──────────────────┬───────────────────┬───────┘
                      │                  │                   │
       ┌──────────────┘                  │                   └──────────────┐
       ▼                                 ▼                                  ▼
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│    kiwi-inventarios     │   │      kiwi-cocinero      │   │      kiwi-compras       │
│  Perfil: inventory      │   │  Perfil: kitchen        │   │  Perfil: purchasing     │
│  Modelo: flash          │   │  Modelo: flash          │   │  Modelo: flash          │
│  - Stock y umbrales     │   │  - Catálogo y recetas   │   │  - Proveedores          │
│  - Alertas <= min_qty   │   │  - Registro/versionado  │   │  - Presentaciones/costos│
│  - Movimientos (kardex) │   │    de recetas           │   │  - Borradores de compra │
│  - Alta de insumos      │   │    (propose/apply)      │   │  - Rutina auto-umbral   │
└─────────────────────────┘   └─────────────────────────┘   └─────────────────────────┘
```

### Regla de Enrutamiento y Resiliencia de Modelos
- **Nivel 1 (`inherit` / Argon con Fallback a `flash`):** Asignado a `kiwi-administrador`. Utiliza Argon (`inherit` / `pro`) de manera preferente para sintetizar decisiones ejecutivas y cruzar métricas financieras complejas. **Mecanismo de Resiliencia:** Si la cuota de Argon se agota o se presenta error por límite de cuota/rate limit, el agente conmuta inmediatamente a `Model: 'flash'`, manteniendo la operación del restaurante ininterrumpida 24/7.
- **Nivel 2 (`flash`):** Asignado de forma permanente a `kiwi-inventarios`, `kiwi-cocinero` y `kiwi-compras` para consultas estructuradas, verificaciones de umbral (`check-thresholds`), versionado de recetas (`apply-recipe`) y programación de órdenes de compra (`auto-replenish-thresholds`), reduciendo latencia y costo por token.

---

## 3. Matriz de Capacidades y Endpoints Gobernados (`GROKBOT-001`)

| Perfil Técnico | Agente Antigravity | Capacidades Autorizadas | Operaciones Soportadas |
| :--- | :--- | :--- | :--- |
| `administrator` | `kiwi-administrador` | `agent.context.read`, `agent.catalog.read`, `agent.sales.read`, `agent.cash_cuts.read`, `agent.operating_expenses.read`, `agent.payment_methods.read`, `agent.cash_reconciliation.read`, `agent.cash_personal_data.read`, `agent.catalog.propose` | `open-registers`, `sales-summary`, `payments-by-method`, `expenses-summary`, `cash-cuts`, `daily-reconciliation`, `catalog-items`, `propose-catalog`, `audit-log` |
| `inventory` | `kiwi-inventarios` | `agent.context.read`, `agent.inventory.read`, `agent.recipes.read`, `agent.inventory_item.propose` | `inventory-items`, `inventory-stock`, `check-thresholds`, `inventory-movements`, `propose-inventory-item` |
| `kitchen` | `kiwi-cocinero` | `agent.context.read`, `agent.catalog.read`, `agent.inventory.read`, `agent.recipes.read`, `agent.recipe.propose` | `catalog-items`, `recipes`, `propose-recipe`, `apply-recipe` |
| `purchasing` | `kiwi-compras` | `agent.context.read`, `agent.inventory.read`, `agent.suppliers.read`, `agent.purchases.read`, `agent.purchase_needs.read`, `agent.purchase_draft.create` | `suppliers`, `purchase-presentations`, `purchase-history`, `purchase-needs`, `purchase-drafts`, `create-purchase-draft`, `auto-replenish-thresholds` |

---

## 4. Rutina Automática de Revisión de Umbral y Pedido (`auto-replenish-thresholds`)

La rutina automatizada implementa el flujo completo solicitado:

1. **Inspección de Existencias (`kiwi-inventarios`):** Consulta `inventory_cost_states` y `inventory_stock_thresholds` para la sucursal activa e identifica todos los insumos cuya existencia actual cumple:
   $$\text{available\_quantity} \le \text{min\_quantity}$$
2. **Cálculo de Déficit a Stock Máximo:** Para cada insumo en alerta, calcula el déficit en unidades base para restablecer el inventario hasta su nivel óptimo (`max_quantity`):
   $$\text{deficit\_base} = \text{max\_quantity} - \text{available\_quantity}$$
3. **Selección de Presentación Comercial (`kiwi-compras`):** Cruza cada insumo con `purchase_presentations` activas, priorizando la presentación marcada como `preferred = true` y menor `cost_per_base_unit`, calculando el número entero de empaques comerciales requeridos:
   $$\text{paquetes} = \left\lceil \frac{\text{deficit\_base}}{\text{usable\_content}} \right\rceil$$
4. **Programación Idempotente de Órdenes de Compra (`DRAFT`):** Agrupa las líneas por `supplier_id` e invoca `POST /api/v1/agent-tools/purchase-drafts` (`create_purchase_draft`) con llave de idempotencia determinista `auto-replenish-{branch_id}-{supplier_id}-{YYYY-MM-DD}`, generando los documentos en `purchase_documents` (`status = 'draft'`) sin alterar efectivo ni kardex físico hasta la recepción humana en sucursal.

---

## 5. Topología Real Verificada en Producción (`kiwipos.mimenu.onl`)

### 5.1 Sucursales Activas en Culiacán, Sinaloa

| Código | Sucursal | UUID | Dirección / Referencia | Umbrales Activos |
| :---: | :--- | :--- | :--- | :---: |
| `SUC04` | **Chapultepec** | `b63c117d-85cf-4c83-8eba-c6321ff37a15` | Calle Josefa Ortiz de Domínguez 598 | **14 insumos** |
| `SUC01` | **Centro** | `a64252bf-9297-42a9-b2e2-ec30a2771ca1` | Álvaro Obregón Norte 698 | 0 |
| `SUC02` | **Guadalupe** | `5aeea33c-d247-4962-99af-ae4c9d9ca42e` | Culiacán, Sin. | 0 |
| `SUC03` | **Insurgentes** | `3a4bb054-7905-43f0-ba4d-bb647773f360` | Blvd. De los Insurgentes Sur 1205 | 0 |
| `SUC05` | **Cinepolis** | `8679ba6a-65a8-43e3-bcb7-6ce186b5ce98` | Blvd. Pedro Infante 1546-5 | 0 |
| `SUC06` | **La Primavera** | `6bf77697-8270-4cbc-b5a5-b389ba26e3af` | Calle Industrial 6 #37 | 0 |
| `SUC07` | **Constitución** | `dd271572-a918-4608-a19c-a2c284a4b8dc` | Álvaro Obregón Sur 576-B | 0 |

### 5.2 Catálogo Exacto de los 14 Umbrales de Chapultepec

| # | Insumo | Unidad | Mínimo | Máximo | Estado Actual en Sistema |
|---|---|:---:|:---:|:---:|:---:|
| 1 | **ACEITUNA NEGRA** | KILO | 1.00 | 3.00 | `below_minimum` (0.00 existencias) |
| 2 | **ADEREZO ARANDANO** | LITRO | 1.00 | 3.00 | `below_minimum` (0.00 existencias) |
| 3 | **ADEREZO BALSAMICO** | LITRO | 1.00 | 1.00 | `below_minimum` (0.00 existencias) |
| 4 | **ADEREZO CHIPOTLE** | LITRO | 1.00 | 3.00 | `below_minimum` (0.00 existencias) |
| 5 | **ADEREZO CILANTRO** | LITRO | 1.00 | 3.00 | `below_minimum` (0.00 existencias) |
| 6 | **ADEREZO KYOTO** | LITRO | 1.00 | 3.00 | `below_minimum` (0.00 existencias) |
| 7 | **ADEREZO RANCH** | LITRO | 1.00 | 3.00 | `below_minimum` (0.00 existencias) |
| 8 | **ADEREZO VINAGRETA** | LITRO | 1.00 | 3.00 | `below_minimum` (0.00 existencias) |
| 9 | **AGUACATE** | KILO | 3.00 | 5.00 | `below_minimum` (0.00 existencias) |
| 10 | **AGUA JAMAICA** | PZA | 3.00 | 10.00 | `below_minimum` (0.00 existencias) |
| 11 | **AGUA MIRENAL** | PZA | 10.00 | 24.00 | `below_minimum` (0.00 existencias) |
| 12 | **AGUA SIN SED** | PZA | 5.00 | 24.00 | `below_minimum` (0.00 existencias) |
| 13 | **TORTILLAS INTEGRAL** | PZA | 2.00 | 8.00 | `below_minimum` (0.00 existencias) |
| 14 | **YOGURTH** | LITRO | 1.00 | 2.00 | `below_minimum` (0.00 existencias) |

---

## 6. Habilidades Instaladas y Guía de Invocación CLI

### 6.1 Habilidades Modulares Antigravity
1. **`kiwi-operations-team`**: Orquestación gobernada de los 4 bots combinando Argon y Flash.
2. **`agent-creator`**: Diseño y arquitectura multi-agente ADK.
3. **`skill-creator`**: Empaquetado y mantenimiento de habilidades modulares.

### 6.2 Comandos de Consulta Operativa en Vivo
```bash
# Consultar cajas abiertas en Chapultepec
python3 /home/antigravity/kiwi-agents/kiwi_agent_cli.py --profile administrator --branch-id "Chapultepec" open-registers

# Consultar ventas recientes de Chapultepec
python3 /home/antigravity/kiwi-agents/kiwi_agent_cli.py --profile administrator --branch-id "Chapultepec" sales-summary

# Auditar los 14 umbrales de inventario en Chapultepec
python3 /home/antigravity/kiwi-agents/kiwi_agent_cli.py --profile inventory --branch-id "Chapultepec" check-thresholds

# Generar borradores de compra para reabastecer faltantes bajo umbral
python3 /home/antigravity/kiwi-agents/kiwi_agent_cli.py --profile purchasing --branch-id "Chapultepec" auto-replenish-thresholds
```
