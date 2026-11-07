# RestaurantOS — Agent Instructions, Operational Team & Memory

The repository-root [`AGENTS.md`](../AGENTS.md) is the sole canonical process authority for
software engineering in RestaurantOS. Do not restate, broaden, or override its documentation,
verification, release, or authorization rules here.

---

## 1. Habilidades (Skills) Activas del Proyecto

1. **Desarrollo e Ingeniería (`restaurantos_dev`):**
   - Ubicación: [`skills/restaurantos_dev/SKILL.md`](skills/restaurantos_dev/SKILL.md)
   - Uso: Cuando la tarea requiere modificar el código fuente de RestaurantOS (PRD, SDD, BDD, TDD, migraciones y verificación proporcional).

2. **Operación Multi-Agente Gobernada (`kiwi-operations-team`):**
   - Ubicación: [`skills/kiwi-operations-team/SKILL.md`](skills/kiwi-operations-team/SKILL.md)
   - Puente CLI: [`skills/kiwi-operations-team/scripts/kiwi_agent_cli.py`](skills/kiwi-operations-team/scripts/kiwi_agent_cli.py)
   - Uso: Cuando el usuario solicita consultar o ejecutar operaciones del restaurante (ventas, cortes de caja, inventarios, conteos físicos, umbrales, recetas o borradores de compras).

---

## 2. Equipo de 4 Agentes Operativos (`.agents/agents/`)

| Agente | Archivo de Definición | Perfil Técnico | Modelo | Rol Operativo |
| :--- | :--- | :--- | :--- | :--- |
| **`kiwi-administrador`** | [`agents/kiwi-administrador/agent.md`](agents/kiwi-administrador/agent.md) | `administrator` | `inherit` (Argon/Pro) | Orquestador principal e interlocutor único con el dueño. Consulta P&L, ventas, cajas abiertas, cortes de caja, gastos y coordina a los otros 3 especialistas. |
| **`kiwi-inventarios`** | [`agents/kiwi-inventarios/agent.md`](agents/kiwi-inventarios/agent.md) | `inventory` | `flash` | Especialista de almacén. Consulta existencias, conteos físicos, kardex y semáforo de umbrales (`check-thresholds`). |
| **`kiwi-cocinero`** | [`agents/kiwi-cocinero/agent.md`](agents/kiwi-cocinero/agent.md) | `kitchen` | `flash` | Especialista de cocina y recetarios. Consulta productos POS y registra/versiona recetas (`apply-recipe`). |
| **`kiwi-compras`** | [`agents/kiwi-compras/agent.md`](agents/kiwi-compras/agent.md) | `purchasing` | `flash` | Especialista de abastecimiento. Consulta proveedores, presentaciones y programa órdenes de compra en borrador (`auto-replenish-thresholds`). |

---

## 3. Memoria Operativa y Recursos Externos (Lectura Obligatoria)

Al iniciar cualquier tarea operativa o de análisis sobre sucursales, inventarios, ventas o el tablero web, **lee siempre primero**:

- **Memoria Operativa Canónica:** [`MEMORY.md`](MEMORY.md)
  - Contiene la URL productiva (`https://kiwipos.mimenu.onl`), los UUIDs de las **7 sucursales** en Culiacán, el estado del **Inventario Físico aprobado de Chapultepec** (`7988e017`), el repositorio del **Tablero Ejecutivo conectado a Vercel** (`mangoex/kiwi-dashboard`) y el índice de documentos en **Google Drive** (`1VvOyaRqaFAI3jgtjmIsw0E8vWH81ATpX`).
