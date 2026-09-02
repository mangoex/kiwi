"""Customer AI, CRM Segmentation, and Upsell Recommendations for RestaurantOS.

Predictive cross-selling, customer segmentation (VIP, At-Risk/Churn, New),
and personalized WhatsApp recovery messages. All money values in exact cents.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID

UTC = timezone.utc


def _is_beverage(name: str) -> bool:
    n = name.lower()
    return any(
        w in n
        for w in (
            "jugo",
            "café",
            "cafe",
            "maccha",
            "matcha",
            "smoothie",
            "agua",
            "extracto",
            "licuado",
            "bebida",
            "drink",
            "té",
            "te",
            "latte",
            "soda",
            "infusion",
            "infusión",
            "frappé",
            "frappe",
        )
    )


def get_customer_upsell_recommendations(
    session: Session,
    customer_id: str | None = None,
    current_product_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compute personalized upsell and cross-selling suggestions based on cart co-occurrences and cross-category pairing."""
    current_ids = set(current_product_ids or [])
    recommendations: list[dict[str, Any]] = []
    seen_ids = set(current_ids)

    # Helper to get price for a product
    def _get_price(product_id: str) -> int:
        price_row = session.execute(
            sa.select(models.price_versions.c.price_cents)
            .where(
                models.price_versions.c.product_id == product_id,
                models.price_versions.c.valid_to.is_(None),
            )
            .order_by(models.price_versions.c.created_at.desc())
            .limit(1)
        ).scalar()
        return int(price_row or 8500)

    # Fetch all active catalog products
    all_active_products = list(
        session.execute(
            sa.select(models.products).where(
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.status == "active",
            )
        ).mappings()
    )

    # Detect what is currently in the cart
    cart_prods = [
        p for p in all_active_products
        if str(p["id"]) in current_ids or str(p.get("sku", "")) in current_ids
    ]
    has_beverage = any(_is_beverage(str(p["name"])) for p in cart_prods)
    has_food = any(not _is_beverage(str(p["name"])) for p in cart_prods)

    # 1. Historical Co-Occurrences in same orders (Products frequently bought together)
    if current_ids:
        try:
            l1 = models.order_lines.alias("l1")
            l2 = models.order_lines.alias("l2")
            o = models.orders

            co_occurrences = list(
                session.execute(
                    sa.select(
                        l2.c.product_id,
                        l2.c.product_name,
                        sa.func.count(sa.distinct(l2.c.order_id)).label("pair_count"),
                    )
                    .select_from(
                        l1.join(
                            l2,
                            sa.and_(
                                l1.c.order_id == l2.c.order_id,
                                l1.c.product_id != l2.c.product_id,
                            ),
                        ).join(o, l1.c.order_id == o.c.id)
                    )
                    .where(
                        o.organization_id == ORGANIZATION_ID,
                        o.status != "cancelled",
                        l1.c.product_id.in_(list(current_ids)),
                    )
                    .group_by(l2.c.product_id, l2.c.product_name)
                    .order_by(sa.desc("pair_count"))
                    .limit(10)
                ).mappings()
            )

            # If cart has only beverage, prefer food co-occurrences; if cart has only food, prefer beverage co-occurrences
            for row in co_occurrences:
                pid = str(row["product_id"])
                pname = str(row["product_name"])
                is_bev = _is_beverage(pname)

                # Skip same-category repetition if single-category cart
                if has_beverage and not has_food and is_bev:
                    continue
                if has_food and not has_beverage and not is_bev:
                    continue

                if pid not in seen_ids:
                    prod = session.execute(
                        sa.select(models.products).where(
                            models.products.c.id == pid,
                            models.products.c.status == "active",
                        )
                    ).mappings().one_or_none()
                    if prod:
                        recommendations.append({
                            "product_id": pid,
                            "product_name": str(prod["name"]),
                            "price_cents": _get_price(pid),
                            "reason": f"Frecuentemente pedido junto ({row['pair_count']} clientes)",
                            "confidence_score": 0.92,
                        })
                        seen_ids.add(pid)
                        if len(recommendations) >= 2:
                            break
        except Exception:
            pass

    # 2. Customer Personal History (if customer_id provided)
    if customer_id and len(recommendations) < 4:
        past_products = list(
            session.execute(
                sa.select(
                    models.order_lines.c.product_id,
                    models.order_lines.c.product_name,
                    sa.func.count(models.order_lines.c.id).label("times_ordered"),
                )
                .select_from(
                    models.order_lines.join(
                        models.orders,
                        models.order_lines.c.order_id == models.orders.c.id,
                    )
                )
                .where(
                    models.orders.c.organization_id == ORGANIZATION_ID,
                    models.orders.c.customer_id == customer_id,
                    models.orders.c.status != "cancelled",
                )
                .group_by(models.order_lines.c.product_id, models.order_lines.c.product_name)
                .order_by(sa.desc("times_ordered"))
            ).mappings()
        )

        for pp in past_products:
            pid = str(pp["product_id"])
            if pid not in seen_ids:
                prod = session.execute(
                    sa.select(models.products).where(
                        models.products.c.id == pid,
                        models.products.c.status == "active",
                    )
                ).mappings().one_or_none()
                if prod:
                    recommendations.append({
                        "product_id": pid,
                        "product_name": str(prod["name"]),
                        "price_cents": _get_price(pid),
                        "reason": f"Favorito habitual del cliente (pedido {pp['times_ordered']} veces)",
                        "confidence_score": 0.95,
                    })
                    seen_ids.add(pid)
                    if len(recommendations) >= 4:
                        break

    # 3. Dynamic Cross-Category Pairing (Food if beverage-only; Beverage if food-only)
    if len(recommendations) < 4:
        # Case A: Cart has ONLY beverages -> Recommend FOOD / BAKERY / SANDOS
        if has_beverage and not has_food:
            food_candidates = [
                p for p in all_active_products
                if str(p["id"]) not in seen_ids and not _is_beverage(str(p["name"]))
            ]
            for prod in food_candidates:
                pid = str(prod["id"])
                recommendations.append({
                    "product_id": pid,
                    "product_name": str(prod["name"]),
                    "price_cents": _get_price(pid),
                    "reason": "Combina perfecto con tu bebida ⭐",
                    "confidence_score": 0.90,
                })
                seen_ids.add(pid)
                if len(recommendations) >= 4:
                    break

        # Case B: Cart has ONLY food (or no beverages) -> Recommend BEVERAGES / JUICES / SMOOTHIES
        elif not has_beverage:
            drink_candidates = [
                p for p in all_active_products
                if str(p["id"]) not in seen_ids and _is_beverage(str(p["name"]))
            ]
            for prod in drink_candidates:
                pid = str(prod["id"])
                recommendations.append({
                    "product_id": pid,
                    "product_name": str(prod["name"]),
                    "price_cents": _get_price(pid),
                    "reason": "¿Acompañas con una bebida fresca? 🥤",
                    "confidence_score": 0.90,
                })
                seen_ids.add(pid)
                if len(recommendations) >= 4:
                    break

        # Case C: General House Favorites for remaining slots
        for prod in all_active_products:
            pid = str(prod["id"])
            if pid not in seen_ids:
                is_bev = _is_beverage(str(prod["name"]))
                reason = "Favorito de nuestros clientes ⭐"
                if is_bev and not has_beverage:
                    reason = "¿Acompañas con una bebida fresca? 🥤"
                elif not is_bev and has_beverage:
                    reason = "Combina perfecto con tu bebida ⭐"

                recommendations.append({
                    "product_id": pid,
                    "product_name": str(prod["name"]),
                    "price_cents": _get_price(pid),
                    "reason": reason,
                    "confidence_score": 0.85,
                })
                seen_ids.add(pid)
                if len(recommendations) >= 4:
                    break

    return recommendations


def get_crm_segments_and_churn_risk(
    session: Session,
    branch_id: str | None = None,
) -> dict[str, Any]:
    """Segment customers into VIPs, Churn Risk (>30 days inactive), and New customers with metrics."""
    criteria = [models.customers.c.organization_id == ORGANIZATION_ID]
    if branch_id:
        criteria.append(models.customers.c.origin_branch_id == branch_id)

    customers_list = list(
        session.execute(
            sa.select(models.customers).where(*criteria)
        ).mappings()
    )

    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)

    vips: list[dict[str, Any]] = []
    churn_risk: list[dict[str, Any]] = []
    new_customers: list[dict[str, Any]] = []

    for cust in customers_list:
        cid = str(cust["id"])

        # Aggregate total orders and total spend in exact cents
        orders = list(
            session.execute(
                sa.select(
                    models.orders.c.id,
                    models.orders.c.total_cents,
                    models.orders.c.created_at,
                ).where(
                    models.orders.c.customer_id == cid,
                    models.orders.c.status != "cancelled",
                )
            ).mappings()
        )

        total_orders = len(orders)
        total_spend_cents = sum(int(o["total_cents"] or 0) for o in orders)

        last_order_dt: datetime | None = None
        if orders:
            order_dates = [o["created_at"] for o in orders if o["created_at"]]
            if order_dates:
                last_order_dt = max(order_dates)

        days_inactive = (now - last_order_dt).days if last_order_dt else 999

        customer_summary = {
            "id": cid,
            "name": f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip() or "Cliente Frecuente",
            "phone": cust.get("phone") or "",
            "total_orders": total_orders,
            "total_spend_cents": total_spend_cents,
            "last_order_date": last_order_dt.isoformat() if last_order_dt else None,
            "days_inactive": days_inactive,
        }

        # Segmentation Rules:
        # VIP: >= 3 orders or spend >= $500.00 MXN (50,000 cents)
        if total_orders >= 3 or total_spend_cents >= 50000:
            vips.append(customer_summary)
        # Churn Risk: > 30 days inactive with at least 1 past order
        if days_inactive >= 30 and total_orders > 0:
            churn_risk.append(customer_summary)
        # New: 1 order within last 14 days
        if total_orders <= 1 and days_inactive <= 14:
            new_customers.append(customer_summary)

    # Sort each list
    vips.sort(key=lambda x: x["total_spend_cents"], reverse=True)
    churn_risk.sort(key=lambda x: x["days_inactive"], reverse=True)
    new_customers.sort(key=lambda x: x["last_order_date"] or "", reverse=True)

    return {
        "summary": {
            "total_customers": len(customers_list),
            "vip_count": len(vips),
            "churn_risk_count": len(churn_risk),
            "new_count": len(new_customers),
        },
        "vips": vips[:15],
        "vip_customers": vips[:15],
        "churn_risk": churn_risk[:15],
        "churn_risk_customers": churn_risk[:15],
        "new_customers": new_customers[:15],
    }


def generate_churn_recovery_message(
    session: Session | None = None,
    customer_id: str | None = None,
    customer_name: str | None = None,
    favorite_product_name: str | None = None,
    discount_code: str | None = "VUELVE10",
) -> str:
    """Generate a personalized WhatsApp re-engagement message highlighting customer favorites."""
    name = customer_name
    fav_product = favorite_product_name
    code = discount_code or "VUELVE10"

    if session and customer_id and not name:
        cust = session.execute(
            sa.select(models.customers).where(models.customers.c.id == customer_id)
        ).mappings().one_or_none()
        if cust:
            name = cust.get("first_name") or "amigo"

        fav_row = session.execute(
            sa.select(
                models.order_lines.c.product_name,
                sa.func.count(models.order_lines.c.id).label("cnt"),
            )
            .select_from(
                models.order_lines.join(
                    models.orders,
                    models.order_lines.c.order_id == models.orders.c.id,
                )
            )
            .where(
                models.orders.c.customer_id == customer_id,
                models.orders.c.status != "cancelled",
            )
            .group_by(models.order_lines.c.product_name)
            .order_by(sa.desc("cnt"))
            .limit(1)
        ).mappings().one_or_none()
        if fav_row:
            fav_product = fav_row["product_name"]

    name = name or "amigo"
    fav_product = fav_product or "tu favorito de siempre"

    return (
        f"¡Hola {name}! 👋 En Kiwi te extrañamos. Hace tiempo que no disfrutamos de prepararte {fav_product}. 🥑✨ "
        f"Hoy te regalamos 10% de descuento con el código {code} en tu próxima visita o pedido directo. ¿Te lo preparamos?"
    )
