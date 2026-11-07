"""Copilot Engine with Dynamic Tool Calling for Kiwi RestaurantOS.

Orchestrates multi-tool execution with Gemini / OpenRouter models.
Deterministic database reads combined with natural language synthesis.
Side-by-side compatible with GrokBot without modifying GrokBot boundaries.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from restaurant_os.config import get_settings
from restaurant_os.copilot_tools import (
    COPILOT_TOOL_DEFINITIONS,
    dispatch_copilot_tool,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres el Asistente Ejecutivo y Operativo de Kiwi RestaurantOS para Mazatlán y todas sus sucursales.
Tu función es responder al dueño y a los encargados con datos autoritarios en tiempo real sobre inventarios, umbrales, cajas y ventas.

REGLAS OBLIGATORIAS:
1. NUNCA inventes números o límites de memoria. SIEMPRE usa las herramientas disponibles:
   - Para umbrales de insumos (mínimos, máximos, unidades, existencias): usa 'get_inventory_stock_and_thresholds'.
   - Para cajas abiertas, cajeros, fondo inicial o cortes: usa 'get_cash_status'.
   - Para ventas, ticket promedio y canales (POS, Uber Eats, Rappi, DiDi): usa 'get_sales_performance'.
   - Para recetas y costeo de platillos: usa 'get_recipes_list'.
   - Para compras sugeridas y proveedores: usa 'get_suggested_purchases'.
2. Formato: Presenta los datos en tablas Markdown claras y elegantes (con columnas claras como Insumo, Mínimo, Máximo, Unidad).
3. Aclara siempre la distinción de negocio si preguntan por productos vs insumos (los umbrales son de insumos de inventario, no de productos de venta).
4. Proactividad: Al final de la tabla, agrega observaciones de valor operativo si detectas alguna anomalía (ej. insumos con mínimo igual a máximo, stock en cero, o insumos sin existencia).
5. Responde en español mexicano natural, profesional, conciso y directo.
"""


def call_llm_with_tools(
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    timeout_seconds: float = 25.0,
) -> dict[str, Any]:
    """Call OpenAI/OpenRouter compatible chat endpoint with tools."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.2,
    }

    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kiwirestaurante.com",
            "X-Title": "Kiwi RestaurantOS Copilot",
        },
        method="POST",
    )

    with urlopen(req, timeout=timeout_seconds) as resp:
        return json.loads(resp.read().decode("utf-8"))


def execute_copilot_chat(
    session: Session,
    organization_id: str,
    prompt: str,
    branch_name_or_id: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    actor_id: str = "copilot-admin",
) -> dict[str, Any]:
    """Execute conversational turn with automatic Tool Calling and fallback."""
    settings = get_settings()

    api_key = settings.openrouter_api_key
    base_url = settings.openrouter_base_url
    model = settings.admin_ai_openrouter_model or "google/gemini-2.5-flash"

    # Assemble messages
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Ingest short conversation history
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    user_content = prompt
    if branch_name_or_id:
        user_content = f"[Sucursal seleccionada: {branch_name_or_id}]\n{prompt}"

    messages.append({"role": "user", "content": user_content})

    # If no API key configured, run local tool execution as fallback
    if not api_key:
        return _execute_local_deterministic_fallback(
            session=session,
            organization_id=organization_id,
            prompt=prompt,
            branch_name_or_id=branch_name_or_id,
        )

    try:
        response = call_llm_with_tools(
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=messages,
            tools=COPILOT_TOOL_DEFINITIONS,
            timeout_seconds=settings.admin_ai_openrouter_timeout_seconds or 20.0,
        )

        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls", [])

        # If LLM didn't call tools, return its text
        if not tool_calls:
            return {
                "answer": message.get("content") or "No se obtuvo respuesta del modelo.",
                "tools_used": [],
                "data": None,
            }

        # Handle tool calls
        messages.append(message)
        tools_executed = []
        raw_tool_data = {}

        for tc in tool_calls:
            fn = tc.get("function", {})
            fn_name = fn.get("name")
            raw_args = fn.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                args = {}

            # Inject selected branch if omitted
            if branch_name_or_id and not args.get("branch_name_or_id"):
                args["branch_name_or_id"] = branch_name_or_id

            logger.info("Executing copilot tool %s with args %s", fn_name, args)
            tool_result = dispatch_copilot_tool(
                session=session,
                organization_id=organization_id,
                tool_name=fn_name,
                arguments=args,
                actor_id=actor_id,
            )

            tools_executed.append(fn_name)
            raw_tool_data[fn_name] = tool_result

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": fn_name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        # Second turn: LLM synthesizes tool outputs into answer
        second_resp = call_llm_with_tools(
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=messages,
            tools=COPILOT_TOOL_DEFINITIONS,
            timeout_seconds=settings.admin_ai_openrouter_timeout_seconds or 20.0,
        )

        final_choice = second_resp.get("choices", [{}])[0]
        final_text = (
            final_choice.get("message", {}).get("content")
            or "Información obtenida correctamente."
        )

        return {
            "answer": final_text,
            "tools_used": tools_executed,
            "data": raw_tool_data,
        }

    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Copilot provider error (%s), using local fallback", exc)
        return _execute_local_deterministic_fallback(
            session=session,
            organization_id=organization_id,
            prompt=prompt,
            branch_name_or_id=branch_name_or_id,
        )


def _execute_local_deterministic_fallback(
    session: Session,
    organization_id: str,
    prompt: str,
    branch_name_or_id: str | None,
) -> dict[str, Any]:
    """Deterministic fallback when external LLM is offline or unconfigured."""
    p_lower = prompt.lower()

    if any(k in p_lower for k in ("umbral", "minimo", "maximo", "limite")):
        res = dispatch_copilot_tool(
            session=session,
            organization_id=organization_id,
            tool_name="get_inventory_stock_and_thresholds",
            arguments={"branch_name_or_id": branch_name_or_id},
        )
        items = res.get("items", [])
        if not items:
            return {
                "answer": f"No se encontraron umbrales configurados para {res.get('branch_name', 'la sucursal')}.",
                "tools_used": ["get_inventory_stock_and_thresholds"],
                "data": res,
            }

        table_rows = [
            f"| {it['insumo']} | {it['minimo']:g} | {it['maximo']:g} | {it['unidad']} | {it['existencia_actual']:g} |"
            for it in items
        ]
        text = (
            f"**{res.get('branch_name')}** tiene **{len(items)} umbrales configurados**:\n\n"
            "| Insumo | Mínimo | Máximo | Unidad | Existencia |\n"
            "| :--- | :--- | :--- | :--- | :--- |\n"
            + "\n".join(table_rows)
            + "\n\n*Datos verificados directamente de la base de datos de inventario.*"
        )
        return {
            "answer": text,
            "tools_used": ["get_inventory_stock_and_thresholds"],
            "data": res,
        }

    elif any(k in p_lower for k in ("caja", "corte", "fondo", "arqueo", "abierta")):
        res = dispatch_copilot_tool(
            session=session,
            organization_id=organization_id,
            tool_name="get_cash_status",
            arguments={"branch_name_or_id": branch_name_or_id},
        )
        open_regs = res.get("open_registers", [])
        if not open_regs:
            answer = f"No hay cajas abiertas actualmente en {res.get('branch_name', 'el sistema')}."
        else:
            rows = [
                f"• **{r['caja']}** ({r['sucursal']}): Cajero: {r['cajero']}, Fondo: {r['fondo_inicial']} (Abierta {r['hora_apertura']})"
                for r in open_regs
            ]
            answer = f"Hay **{len(open_regs)} caja(s) abierta(s)**:\n" + "\n".join(rows)

        return {
            "answer": answer,
            "tools_used": ["get_cash_status"],
            "data": res,
        }

    else:
        # Default sales performance
        res = dispatch_copilot_tool(
            session=session,
            organization_id=organization_id,
            tool_name="get_sales_performance",
            arguments={"branch_name_or_id": branch_name_or_id, "days": 1},
        )
        answer = (
            f"Resumen de ventas de hoy ({res.get('branch_name')}):\n"
            f"• Ventas Totales: **{res.get('ventas_totales')}**\n"
            f"• Pedidos: **{res.get('total_pedidos')}**\n"
            f"• Ticket Promedio: **{res.get('ticket_promedio')}**"
        )
        return {
            "answer": answer,
            "tools_used": ["get_sales_performance"],
            "data": res,
        }
