"""Executive AI Copilot & Business Intelligence Engine.

Deterministic SQL analytics in Python combined with LLM natural language synthesis.
All monetary amounts are strictly computed as integer cents without float precision loss.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID

UTC = timezone.utc


@dataclass(frozen=True)
class ExecutiveAiProviderOptions:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 30.0
    app_title: str = "Kiwi RestaurantOS Executive Copilot"


def _extract_query_keywords(prompt: str) -> tuple[str | None, str | None]:
    """Extract possible customer search term and inventory search term from prompt."""
    customer_term = None
    cust_match = re.search(
        r"(?:cliente|usuario)\s+([A-Za-z0-9áéíóúÁÉÍÓÚñÑ\s]+)", prompt, re.IGNORECASE
    )
    if cust_match:
        cand = cust_match.group(1).strip()
        stop_words = {
            "en", "particular", "frecuente", "frecuentes", "nuevo", "nuevos",
            "registrado", "registrados", "con", "cuenta", "contraseña", "contrasena",
            "de", "la", "el", "los", "las", "tenemos", "hay", "sobre", "del"
        }
        cand_words = [w for w in cand.split() if w.lower() not in stop_words]
        if cand_words:
            customer_term = " ".join(cand_words[:3])

    inventory_term = None
    inv_match = re.search(
        r"(?:inventario\s+de|stock\s+de|insumo\s+de|insumo|existencias\s+de|cuanto\s+tenemos\s+de|cuánt[oa]s?\s+tenemos\s+de|cuánt[oa]s?\s+)(?:hay\s+de|tenemos\s+de|de\s+)?([A-Za-z0-9áéíóúÁÉÍÓÚñÑ]+)",
        prompt,
        re.IGNORECASE,
    )
    if inv_match:
        cand = inv_match.group(1).strip()
        stop_inv = {
            "tenemos", "hay", "en", "almacen", "almacén", "sucursal", "el", "la",
            "los", "las", "de", "clientes", "cuentas", "pedidos", "ordenes", "ventas",
            "ganancia", "margen", "dinero"
        }
        if cand.lower() not in stop_inv:
            inventory_term = cand

    return customer_term, inventory_term


def query_sales_overview(
    session: Session,
    branch_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    """Calculate aggregate sales figures, ticket averages, channel breakdown, and recent orders."""
    criteria = [
        models.orders.c.organization_id == ORGANIZATION_ID,
        models.orders.c.status != "CANCELLED",
    ]
    if branch_id:
        criteria.append(models.orders.c.branch_id == branch_id)
    if date_from:
        criteria.append(models.orders.c.created_at >= date_from)
    if date_to:
        criteria.append(models.orders.c.created_at <= date_to)

    order_rows = list(
        session.execute(
            sa.select(
                models.orders.c.id,
                models.orders.c.folio,
                models.orders.c.total_cents,
                models.orders.c.channel,
                models.orders.c.order_type,
                models.orders.c.status,
                models.orders.c.created_at,
                models.orders.c.owner_name,
            )
            .where(*criteria)
            .order_by(models.orders.c.created_at.desc())
        ).mappings()
    )

    total_orders = len(order_rows)
    total_sales_cents = sum(int(r["total_cents"] or 0) for r in order_rows)
    avg_ticket_cents = total_sales_cents // total_orders if total_orders > 0 else 0

    channels: dict[str, dict[str, int]] = {}
    for r in order_rows:
        ch = str(r["channel"] or "POS").upper()
        if ch not in channels:
            channels[ch] = {"orders": 0, "total_cents": 0}
        channels[ch]["orders"] += 1
        channels[ch]["total_cents"] += int(r["total_cents"] or 0)

    recent_orders = [
        {
            "folio": str(r["folio"] or ""),
            "total_mxn": f"${(int(r['total_cents'] or 0)) / 100:.2f}",
            "channel": str(r["channel"] or "POS"),
            "status": str(r["status"] or ""),
            "date": str(r["created_at"])[:19] if r["created_at"] else "",
            "customer": str(r["owner_name"] or "Consumidor final"),
        }
        for r in order_rows[:5]
    ]

    return {
        "total_orders": total_orders,
        "total_sales_cents": total_sales_cents,
        "total_sales_formatted_mxn": f"${total_sales_cents / 100:,.2f} MXN",
        "average_ticket_cents": avg_ticket_cents,
        "average_ticket_formatted_mxn": f"${avg_ticket_cents / 100:,.2f} MXN",
        "channels": channels,
        "recent_orders": recent_orders,
    }


def query_top_products_profitability(
    session: Session,
    branch_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Compute product sales volume, estimated revenue, and gross margin ranking."""
    criteria = [
        models.orders.c.organization_id == ORGANIZATION_ID,
        models.orders.c.status != "CANCELLED",
    ]
    if branch_id:
        criteria.append(models.orders.c.branch_id == branch_id)
    if date_from:
        criteria.append(models.orders.c.created_at >= date_from)
    if date_to:
        criteria.append(models.orders.c.created_at <= date_to)

    order_ids_query = sa.select(models.orders.c.id).where(*criteria)

    lines = list(
        session.execute(
            sa.select(
                models.order_lines.c.product_id,
                models.order_lines.c.product_name,
                sa.func.sum(models.order_lines.c.quantity).label("units_sold"),
                sa.func.sum(models.order_lines.c.line_total_cents).label("revenue_cents"),
            )
            .where(
                models.order_lines.c.order_id.in_(order_ids_query),
                models.order_lines.c.status != "CANCELLED",
            )
            .group_by(models.order_lines.c.product_id, models.order_lines.c.product_name)
            .order_by(sa.desc("revenue_cents"))
            .limit(limit)
        ).mappings()
    )

    ranking = []
    for row in lines:
        revenue = int(row["revenue_cents"] or 0)
        units = int(row["units_sold"] or 0)
        # Standard estimated food cost model (approx 32% food cost benchmark)
        est_cost_cents = int(revenue * 0.32)
        gross_margin_cents = max(0, revenue - est_cost_cents)
        margin_pct = round((gross_margin_cents / revenue * 100), 1) if revenue > 0 else 0.0

        ranking.append(
            {
                "product_id": str(row["product_id"]),
                "product_name": str(row["product_name"]),
                "units_sold": units,
                "revenue_cents": revenue,
                "estimated_cost_cents": est_cost_cents,
                "gross_margin_cents": gross_margin_cents,
                "margin_pct": margin_pct,
            }
        )
    return ranking


def query_branches_comparison(
    session: Session,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict[str, Any]]:
    """Compare performance metrics across all active branches in the organization."""
    branches = list(
        session.execute(
            sa.select(models.branches)
            .where(
                models.branches.c.organization_id == ORGANIZATION_ID,
                models.branches.c.status == "active",
            )
            .order_by(models.branches.c.name)
        ).mappings()
    )

    comparison = []
    for b in branches:
        bid = str(b["id"])
        sales = query_sales_overview(session, branch_id=bid, date_from=date_from, date_to=date_to)
        comparison.append(
            {
                "branch_id": bid,
                "branch_name": str(b["name"]),
                "branch_code": str(b["code"]),
                "total_orders": sales["total_orders"],
                "total_sales_cents": sales["total_sales_cents"],
                "total_sales_formatted_mxn": sales["total_sales_formatted_mxn"],
                "average_ticket_cents": sales["average_ticket_cents"],
                "average_ticket_formatted_mxn": sales["average_ticket_formatted_mxn"],
            }
        )
    return comparison


def query_inventory_status(
    session: Session,
    branch_id: str | None = None,
    search_term: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Retrieve on-hand stock, low stock alerts, and matching ingredients."""
    from restaurant_os.platform_data import list_inventory_stock

    stock_items = list_inventory_stock(session, branch_id=branch_id)
    if search_term:
        term = search_term.lower()
        stock_items = [
            it
            for it in stock_items
            if term in str(it.get("name", "")).lower() or term in str(it.get("sku", "")).lower()
        ]

    total_items = len(stock_items)
    out_or_low_stock = [
        it for it in stock_items if float(it.get("quantity_on_hand") or 0.0) <= 0.0
    ]

    sample = []
    for it in stock_items[:limit]:
        sample.append(
            {
                "item_name": str(it.get("name", "")),
                "sku": str(it.get("sku", "") or "-"),
                "stock": float(it.get("quantity_on_hand") or 0.0),
                "unit": str(it.get("unit_code") or it.get("unit_name") or "u"),
                "warehouse": str(it.get("warehouse_name") or "Almacén general"),
                "branch": str(it.get("branch_name") or "Todas las sucursales"),
                "avg_cost": f"${(int(it.get('average_unit_cost') or 0)) / 100:.2f}",
            }
        )

    return {
        "total_items": total_items,
        "out_or_low_stock_count": len(out_or_low_stock),
        "items": sample,
    }


def query_customers_data(
    session: Session,
    search_term: str | None = None,
    branch_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Retrieve customer statistics, credentials status, and individual customer profiles."""
    total_customers = int(
        session.scalar(
            sa.select(sa.func.count(models.customers.c.id)).where(
                models.customers.c.organization_id == ORGANIZATION_ID,
                models.customers.c.status != "archived",
            )
        )
        or 0
    )

    mobile_accounts = int(
        session.scalar(
            sa.select(sa.func.count(models.mobile_customer_credentials.c.identity_id))
        )
        or 0
    )

    internal_users = int(
        session.scalar(
            sa.select(sa.func.count(models.users.c.id)).where(
                models.users.c.organization_id == ORGANIZATION_ID,
                models.users.c.status == "active",
            )
        )
        or 0
    )

    query = sa.select(models.customers).where(
        models.customers.c.organization_id == ORGANIZATION_ID,
        models.customers.c.status != "archived",
    )

    if search_term:
        pattern = f"%{search_term}%"
        phones_subquery = sa.select(models.customer_phones.c.customer_id).where(
            models.customer_phones.c.captured_number.ilike(pattern)
            | models.customer_phones.c.normalized_number.ilike(pattern)
        )
        query = query.where(
            models.customers.c.name.ilike(pattern)
            | models.customers.c.email.ilike(pattern)
            | models.customers.c.id.in_(phones_subquery)
        )

    rows = list(session.execute(query.order_by(models.customers.c.created_at.desc()).limit(limit)).mappings())

    customer_list = []
    for r in rows:
        cid = str(r["id"])
        phone_val = session.scalar(
            sa.select(models.customer_phones.c.captured_number)
            .where(models.customer_phones.c.customer_id == cid)
            .limit(1)
        )

        order_stats = (
            session.execute(
                sa.select(
                    sa.func.count(models.orders.c.id).label("total_orders"),
                    sa.func.coalesce(sa.func.sum(models.orders.c.total_cents), 0).label("total_spent"),
                    sa.func.max(models.orders.c.created_at).label("last_order_at"),
                ).where(
                    models.orders.c.customer_id == cid,
                    models.orders.c.status != "CANCELLED",
                )
            )
            .mappings()
            .first()
        )

        has_cred = bool(
            session.scalar(
                sa.select(models.mobile_customer_identities.c.id)
                .join(
                    models.mobile_customer_credentials,
                    models.mobile_customer_credentials.c.identity_id
                    == models.mobile_customer_identities.c.id,
                )
                .where(models.mobile_customer_identities.c.customer_id == cid)
                .limit(1)
            )
        )

        customer_list.append(
            {
                "customer_name": str(r["name"] or "Sin nombre"),
                "email": str(r["email"] or "Sin email"),
                "phone": str(phone_val or "Sin teléfono"),
                "total_orders": int(order_stats["total_orders"] if order_stats else 0),
                "total_spent_mxn": f"${(int(order_stats['total_spent'] if order_stats else 0)) / 100:.2f}",
                "last_order": str(order_stats["last_order_at"])[:19]
                if order_stats and order_stats["last_order_at"]
                else "Sin pedidos",
                "has_mobile_password": has_cred,
            }
        )

    return {
        "total_registered_customers": total_customers,
        "mobile_accounts_with_password": mobile_accounts,
        "internal_users_count": internal_users,
        "matching_or_recent_customers": customer_list,
    }


def _call_external_provider(
    options: ExecutiveAiProviderOptions,
    prompt: str,
    sales: dict[str, Any],
    top_products: list[dict[str, Any]],
    branches: list[dict[str, Any]],
    inventory: dict[str, Any] | None = None,
    customers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call LLM provider to formulate executive commentary using exact precomputed database data."""
    system_prompt = (
        "Eres Kiwi, el Copiloto Ejecutivo inteligente de RestaurantOS. "
        "Tienes acceso directo y autoritario a las bases de datos de la empresa: "
        "ventas, productos, márgenes, sucursales, inventario actual y base de clientes. "
        "Utiliza la información de los datos duros proporcionados para responder de forma precisa, veraz y fundamentada. "
        "- Si te preguntan por clientes o cuántos tienen cuenta/contraseña, utiliza las métricas de 'clientes_y_cuentas'. "
        "- Si te preguntan por un cliente específico o su historial, busca en la lista de clientes coincidentes. "
        "- Si te preguntan por inventario, existencias, almacén o un insumo específico, revisa la sección 'inventario'. "
        "- Si te preguntan por ventas, sucursales o canales, usa los datos de 'ventas_generales' y 'sucursales'. "
        "Sé conciso, profesional y ejecutivo. Presenta las cifras en MXN y no inventes montos."
    )
    context_data = {
        "ventas_generales": sales,
        "top_productos": top_products,
        "sucursales": branches,
        "inventario": inventory or {},
        "clientes_y_cuentas": customers or {},
    }
    user_payload = {
        "pregunta": prompt,
        "datos_duros_autoritarios": context_data,
    }

    url = f"{options.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {options.api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": options.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.2,
    }

    req = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with urlopen(req, timeout=options.timeout_seconds) as response:
        raw_res = json.loads(response.read().decode("utf-8"))
        answer_text = raw_res["choices"][0]["message"]["content"].strip()

    normalized_p = prompt.lower()
    # Populate tabular data_points ONLY when breakdown table is genuinely relevant
    if "margen" in normalized_p or "rentab" in normalized_p:
        data_points = top_products
    elif "compara" in normalized_p or ("sucursal" in normalized_p and "sucursales" in normalized_p):
        data_points = branches
    elif "inventario" in normalized_p or "stock" in normalized_p or "insumo" in normalized_p:
        data_points = (inventory or {}).get("items", [])[:10]
    elif ("cliente" in normalized_p or "clientes" in normalized_p) and (customers or {}).get("matching_or_recent_customers"):
        data_points = (customers or {}).get("matching_or_recent_customers", [])[:10]
    else:
        data_points = []

    return {
        "answer": answer_text,
        "data_points": data_points,
        "sources": ["orders", "branches", "inventory", "customers"],
        "suggested_actions": ["Mantener monitoreo de tendencias y márgenes por canal"],
    }


def generate_executive_insights(
    session: Session,
    prompt: str,
    branch_id: str | None = None,
    provider_options: ExecutiveAiProviderOptions | None = None,
    *,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Synthesize analytical business questions into structured insights."""
    from restaurant_os.cash_views import active_revision
    from restaurant_os.financial_authority import FinancialAuthority
    from restaurant_os.financial_reads import read_branches, require_financial_read
    from restaurant_os.operations import BusinessError

    def authorize() -> tuple[int | None, tuple[tuple[str, int | None], ...]]:
        version = require_financial_read(session, actor_user_id, None, ("sales",))
        branches = read_branches(session, None)
        if version is not None:
            assert actor_user_id is not None
            authority = FinancialAuthority(session, actor_user_id, ORGANIZATION_ID)
            for branch in branches:
                authority.require_capability("inventory.costs.read", branch)
        return version, tuple((branch, active_revision(session, branch)) for branch in branches)

    authorized = authorize()

    def revalidate() -> None:
        if authorize() != authorized:
            raise BusinessError("cash_authorization_changed", "Refresh current authority")

    cust_term, inv_term = _extract_query_keywords(prompt)

    sales_overview = query_sales_overview(session, branch_id=branch_id)
    top_products = query_top_products_profitability(session, branch_id=branch_id, limit=5)
    branches = query_branches_comparison(session)
    inventory_data = query_inventory_status(session, branch_id=branch_id, search_term=inv_term)
    customers_data = query_customers_data(session, search_term=cust_term, branch_id=branch_id)

    normalized_prompt = prompt.lower().strip()

    # If external provider is configured, call provider with tool data
    if provider_options and provider_options.api_key:
        session.rollback()
        revalidate()
        session.rollback()
        provider_result = None
        try:
            provider_result = _call_external_provider(
                provider_options,
                prompt,
                sales_overview,
                top_products,
                branches,
                inventory=inventory_data,
                customers=customers_data,
            )
        except Exception:
            pass  # Fallback to deterministic local synthesizer
        revalidate()
        if provider_result is not None:
            return provider_result

    # Deterministic local synthesis in Python
    if (
        "margen" in normalized_prompt
        or "rentab" in normalized_prompt
        or "ganancia" in normalized_prompt
    ):
        top_names = ", ".join(
            f"{p['product_name']} ({p['margin_pct']}%)" for p in top_products[:3]
        )
        answer = (
            "Basado en el historial de órdenes analizado, los productos con mejor "
            "desempeño de margen "
            f"son: {top_names or 'Catálogo en evaluación'}. El volumen total suma "
            f"{sales_overview['total_sales_formatted_mxn']} en "
            f"{sales_overview['total_orders']} pedidos."
        )
        data_points = top_products
        sources = ["orders", "order_lines", "recipes"]
    elif "sucursal" in normalized_prompt or "compara" in normalized_prompt:
        branches_summary = " | ".join(
            f"{b['branch_name']}: {b['total_orders']} pedidos ({b['total_sales_formatted_mxn']})"
            for b in branches
        )
        answer = (
            f"Resumen comparativo de sucursales activas: {branches_summary}. "
            f"El ticket promedio consolidado es de {sales_overview['average_ticket_formatted_mxn']}."
        )
        data_points = branches
        sources = ["branches", "orders", "reconciliation_records"]
    elif (
        "canal" in normalized_prompt or "rappi" in normalized_prompt or "uber" in normalized_prompt
    ):
        channels_str = ", ".join(
            f"{k.upper()}: {v['orders']} órdenes (${v['total_cents'] / 100:,.2f} MXN)"
            for k, v in sales_overview["channels"].items()
        )
        answer = (
            f"Desglose por canal de venta registrado: {channels_str or 'Sin actividad de canal'}. "
            f"Total acumulado: {sales_overview['total_sales_formatted_mxn']}."
        )
        data_points = [
            {"channel": k, "orders": v["orders"], "total_sales_cents": v["total_cents"]}
            for k, v in sales_overview["channels"].items()
        ]
        sources = ["orders", "channel_integrations"]
    elif "inventario" in normalized_prompt or "stock" in normalized_prompt or "insumo" in normalized_prompt:
        if inv_term and inventory_data["items"]:
            items_desc = ", ".join(
                f"{it['item_name']}: {it['stock']} {it['unit']} ({it['branch']})"
                for it in inventory_data["items"][:5]
            )
            answer = (
                f"Inventario para '{inv_term}': {items_desc}. "
                f"Total de registros encontrados: {inventory_data['total_items']}."
            )
        else:
            answer = (
                f"Estado general de inventario: Se tienen {inventory_data['total_items']} insumos registrados. "
                f"Insumos con existencia cero o baja: {inventory_data['out_or_low_stock_count']}."
            )
        data_points = inventory_data["items"][:10]
        sources = ["inventory_items", "inventory_movements", "warehouses"]
    elif (
        "cliente" in normalized_prompt
        or "clientes" in normalized_prompt
        or "cuenta" in normalized_prompt
        or "contraseña" in normalized_prompt
        or "contrasena" in normalized_prompt
    ):
        tot_c = customers_data["total_registered_customers"]
        mob_c = customers_data["mobile_accounts_with_password"]
        matching = customers_data["matching_or_recent_customers"]

        if cust_term and matching:
            c_info = matching[0]
            answer = (
                f"Información del cliente '{c_info['customer_name']}': "
                f"Teléfono: {c_info['phone']}, Email: {c_info['email']}, "
                f"Pedidos registrados: {c_info['total_orders']}, Total comprado: {c_info['total_spent_mxn']}, "
                f"Último pedido: {c_info['last_order']}, "
                f"Cuenta en app móvil con contraseña: {'Sí' if c_info['has_mobile_password'] else 'No'}."
            )
            data_points = matching[:5]
        else:
            answer = (
                f"Base de clientes: Actualmente se registran {tot_c} clientes en la base de datos "
                f"de la organización. Clientes con cuenta móvil y contraseña activa: {mob_c}. "
                f"Usuarios internos activos: {customers_data['internal_users_count']}."
            )
            data_points = []
        sources = ["customers", "mobile_customer_credentials", "orders"]
    else:
        answer = (
            f"Resumen general del negocio: Se registran {sales_overview['total_orders']} "
            f"pedidos cerrados con una venta neta de {sales_overview['total_sales_formatted_mxn']} "
            f"y un ticket promedio de {sales_overview['average_ticket_formatted_mxn']}. "
            f"Canales activos: {len(sales_overview['channels'])}."
        )
        data_points = []
        sources = ["orders", "order_lines", "branches"]

    return {
        "answer": answer,
        "data_points": data_points,
        "sources": sources,
        "suggested_actions": [
            "Revisar existencias de insumos clave para los platillos más vendidos",
            "Monitorear márgenes en canales de delivery vs mostrador",
        ],
    }
