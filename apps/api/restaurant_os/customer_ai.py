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


def get_customer_upsell_recommendations(
    session: Session,
    customer_id: str | None = None,
    current_product_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compute personalized upsell and cross-selling suggestions based on cart co-occurrences and customer history."""
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

    # 1. Cart-Based Co-Occurrences (Products frequently ordered together with items currently in the cart)
    if current_ids:
        try:
            # Find products that appeared in the same order as any current_product_id
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
                    .limit(6)
                ).mappings()
            )

            for row in co_occurrences:
                pid = str(row["product_id"])
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
                        if len(recommendations) >= 3:
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

    # 3. Intelligent Pairing Logic (Beverage if missing, Bakery/Food if beverage only)
    if len(recommendations) < 4:
        # Check if cart has beverages
        all_active_products = list(
            session.execute(
                sa.select(models.products).where(
                    models.products.c.organization_id == ORGANIZATION_ID,
                    models.products.c.status == "active",
                ).limit(20)
            ).mappings()
        )

        # Check cart names
        cart_product_names = [str(p["name"]).lower() for p in all_active_products if str(p["id"]) in current_ids]
        has_drink = any(
            any(w in name for w in ("jugo", "café", "cafe", "maccha", "matcha", "smoothie", "agua", "extracto"))
            for name in cart_product_names
        )

        # If no drink in cart, recommend popular drink
        if not has_drink:
            for prod in all_active_products:
                pid = str(prod["id"])
                pname = str(prod["name"]).lower()
                if pid not in seen_ids and any(w in pname for w in ("jugo", "café", "cafe", "maccha", "matcha", "smoothie", "agua", "extracto")):
                    recommendations.append({
                        "product_id": pid,
                        "product_name": str(prod["name"]),
                        "price_cents": _get_price(pid),
                        "reason": "Acompaña tu comida con una bebida refrescante",
                        "confidence_score": 0.88,
                    })
                    seen_ids.add(pid)
                    if len(recommendations) >= 4:
                        break

        # Fill remaining with general active products
        for prod in all_active_products:
            pid = str(prod["id"])
            if pid not in seen_ids:
                recommendations.append({
                    "product_id": pid,
                    "product_name": str(prod["name"]),
                    "price_cents": _get_price(pid),
                    "reason": "Recomendación popular de la casa",
                    "confidence_score": 0.80,
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
    fourteen_days_ago = now - timedelta(days=14)

    vip_customers = []
    churn_risk_customers = []
    new_customers = []

    for cust in customers_list:
        cid = str(cust["id"])
        c_name = str(cust["name"])
        c_email = str(cust["email"] or "")
        created_at = cust["created_at"]
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        # Phone lookup
        phone_row = session.execute(
            sa.select(models.customer_phones.c.normalized_number)
            .where(
                models.customer_phones.c.customer_id == cid,
                models.customer_phones.c.status == "active",
            )
            .order_by(models.customer_phones.c.is_primary.desc())
            .limit(1)
        ).scalar()
        c_phone = str(phone_row or "")

        # Aggregate order stats for this customer
        order_stats = session.execute(
            sa.select(
                sa.func.count(models.orders.c.id).label("total_orders"),
                sa.func.sum(models.orders.c.total_cents).label("total_spent_cents"),
                sa.func.max(models.orders.c.created_at).label("last_order_at"),
            ).where(
                models.orders.c.customer_id == cid,
                models.orders.c.status != "cancelled",
            )
        ).mappings().one()

        total_orders = int(order_stats["total_orders"] or 0)
        total_spent_cents = int(order_stats["total_spent_cents"] or 0)
        last_order_at = order_stats["last_order_at"]
        if last_order_at and last_order_at.tzinfo is None:
            last_order_at = last_order_at.replace(tzinfo=UTC)

        customer_summary = {
            "customer_id": cid,
            "name": c_name,
            "phone": c_phone,
            "email": c_email,
            "total_orders": total_orders,
            "total_spent_cents": total_spent_cents,
            "last_order_date": last_order_at.isoformat() if last_order_at else None,
            "days_since_last_order": (now - last_order_at).days if last_order_at else None,
        }

        # Segmentation criteria
        if total_orders >= 3 or total_spent_cents >= 50000:
            vip_customers.append(customer_summary)
        
        if last_order_at and last_order_at < thirty_days_ago:
            churn_risk_customers.append(customer_summary)
        
        if created_at and created_at >= fourteen_days_ago and total_orders <= 1:
            new_customers.append(customer_summary)

    return {
        "vip_customers": vip_customers,
        "churn_risk_customers": churn_risk_customers,
        "new_customers": new_customers,
        "summary": {
            "total_customers": len(customers_list),
            "vip_count": len(vip_customers),
            "churn_risk_count": len(churn_risk_customers),
            "new_count": len(new_customers),
        },
    }


def generate_churn_recovery_message(
    customer_name: str,
    favorite_product_name: str = "tus platillos favoritos",
    discount_code: str | None = None,
) -> str:
    """Generate friendly, personalized WhatsApp copy for churn recovery campaigns."""
    promo_part = f" como cortesía usa el código *{discount_code}* para un descuento especial" if discount_code else ""
    return (
        f"¡Hola {customer_name}! 👋 En Kiwi te extrañamos mucho. "
        f"Queremos invitarte a disfrutar nuevamente de {favorite_product_name}{promo_part}. "
        f"¿Te gustaría que te preparemos tu pedido hoy? ✨"
    )
