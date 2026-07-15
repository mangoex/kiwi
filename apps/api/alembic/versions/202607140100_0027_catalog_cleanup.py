"""catalog cleanup and organization-wide visibility

Revision ID: 0027_catalog_cleanup
Revises: 0026_ingredient_variations
Create Date: 2026-07-14 01:00:00.000000
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0027_catalog_cleanup"
down_revision: str | None = "0026_ingredient_variations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEADING_IMPORT_QUOTES = "'´‘’"
ASCII_NUMERIC_SKU = re.compile(r"^[0-9]+$")
DRINK_CATEGORIES = {
    "AGUAS",
    "BEBIDAS",
    "EXTRA JUGOS",
    "EXTRA LICUADOS",
    "JUGOS",
    "LICUADOS",
    "SMOOTHIES Y EXTRACTOS",
}
PACKING_CATEGORIES = {"SERVICIOS A DOMICILIO"}
DRINK_WORDS = {
    "AGUA",
    "BEBIDA",
    "BEBIDAS",
    "CAFE",
    "CAFÉ",
    "EXTRACTO",
    "EXTRACTOS",
    "JUGO",
    "JUGOS",
    "LICUADO",
    "LICUADOS",
    "MATCHA",
    "REFRESCO",
    "SMOOTHIE",
    "SMOOTHIES",
    "TE",
    "TÉ",
}
PACKING_WORDS = {
    "BAG",
    "BOLSA",
    "BOLSAS",
    "CONTENEDOR",
    "CONTENEDORES",
    "CUBIERTO",
    "CUBIERTOS",
    "EMPAQUE",
    "EMPAQUES",
    "SERVILLETA",
    "SERVILLETAS",
}
PACKAGING_ITEM_CATEGORIES = {"PLASTICOS Y DESECHABLES", "PLÁSTICOS Y DESECHABLES"}


def _id() -> str:
    return str(uuid4())


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _product_sku(value: Any) -> str:
    return str(value or "").strip().lstrip(LEADING_IMPORT_QUOTES).strip()


def _numeric(value: Any) -> bool:
    return bool(ASCII_NUMERIC_SKU.fullmatch(str(value or "")))


def _uppercase(value: Any) -> bool:
    normalized = str(value or "").strip()
    return bool(normalized) and normalized == normalized.upper()


def _category(value: Any) -> str:
    return str(value or "").strip().upper()


def _station(name: Any, category_name: Any) -> str:
    normalized_name = str(name or "").strip().upper()
    normalized_category = _category(category_name)
    words = set(re.findall(r"[A-ZÁÉÍÓÚÜÑ]+", normalized_name))
    if normalized_category in PACKING_CATEGORIES or words & PACKING_WORDS:
        return "packing"
    if normalized_category in DRINK_CATEGORIES or words & DRINK_WORDS:
        return "drinks"
    return "kitchen"


def _tables() -> dict[str, sa.TableClause]:
    return {
        "categories": sa.table(
            "product_categories",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("name"),
            sa.column("display_order"),
            sa.column("status"),
            sa.column("created_at"),
            sa.column("updated_at"),
        ),
        "products": sa.table(
            "products",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("category_id"),
            sa.column("name"),
            sa.column("sku"),
            sa.column("station"),
            sa.column("status"),
            sa.column("catalog_scope"),
            sa.column("source_branch_id"),
            sa.column("created_at"),
            sa.column("updated_at"),
        ),
        "items": sa.table(
            "inventory_items",
            sa.column("id"),
            sa.column("sku"),
            sa.column("item_type"),
            sa.column("category_name"),
            sa.column("catalog_scope"),
            sa.column("source_branch_id"),
            sa.column("status"),
            sa.column("updated_at"),
        ),
        "availability": sa.table(
            "branch_product_availability",
            sa.column("branch_id"),
            sa.column("product_id"),
            sa.column("is_available"),
            sa.column("updated_at"),
        ),
        "records": sa.table(
            "legacy_import_records",
            sa.column("id"),
            sa.column("batch_id"),
            sa.column("entity_type"),
            sa.column("normalized_payload", sa.JSON()),
            sa.column("status"),
            sa.column("reason_code"),
            sa.column("target_entity_id"),
            sa.column("updated_at"),
        ),
        "batches": sa.table(
            "legacy_import_batches",
            sa.column("id"),
            sa.column("status"),
            sa.column("summary", sa.JSON()),
            sa.column("updated_at"),
        ),
        "cleanup_records": sa.table(
            "catalog_cleanup_records",
            sa.column("id"),
            sa.column("revision"),
            sa.column("entity_type"),
            sa.column("entity_id"),
            sa.column("action"),
            sa.column("original_payload", sa.JSON()),
            sa.column("applied_payload", sa.JSON()),
            sa.column("created_at"),
        ),
        "cleanup_runs": sa.table(
            "catalog_cleanup_runs",
            sa.column("id"),
            sa.column("revision"),
            sa.column("status"),
            sa.column("summary", sa.JSON()),
            sa.column("created_at"),
        ),
        "audit": sa.table(
            "audit_events",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("branch_id"),
            sa.column("actor_user_id"),
            sa.column("action"),
            sa.column("entity_type"),
            sa.column("entity_id"),
            sa.column("payload", sa.JSON()),
            sa.column("correlation_id"),
            sa.column("created_at"),
        ),
    }


def upgrade() -> None:
    op.create_table(
        "catalog_cleanup_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.String(80), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "catalog_cleanup_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("original_payload", sa.JSON(), nullable=False),
        sa.Column("applied_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "revision",
            "entity_type",
            "entity_id",
            name="uq_catalog_cleanup_record_entity",
        ),
    )

    connection = op.get_bind()
    tables = _tables()
    now = datetime.now(timezone.utc)
    summary: Counter[str] = Counter()
    run_id = _id()

    def record(
        entity_type: str,
        entity_id: str,
        action: str,
        original: dict[str, Any],
        applied: dict[str, Any],
    ) -> None:
        connection.execute(
            tables["cleanup_records"]
            .insert()
            .values(
                id=_id(),
                revision=revision,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                original_payload=original,
                applied_payload=applied,
                created_at=now,
            )
        )

    categories = list(connection.execute(sa.select(tables["categories"])).mappings())
    products = list(connection.execute(sa.select(tables["products"])).mappings())
    category_by_id = {str(row["id"]): row for row in categories}
    canonical_categories = {
        str(row["name"]).strip(): row
        for row in categories
        if _uppercase(row["name"])
    }

    candidates: dict[str, list[Any]] = defaultdict(list)
    invalid_product_ids: set[str] = set()
    for product in products:
        normalized_sku = _product_sku(product["sku"])
        if _numeric(normalized_sku) and _uppercase(product["name"]):
            candidates[normalized_sku].append(product)
        else:
            invalid_product_ids.add(str(product["id"]))

    winners: dict[str, Any] = {}
    duplicate_product_ids: set[str] = set()
    for normalized_sku, rows in candidates.items():
        ordered = sorted(
            rows,
            key=lambda row: (
                str(row["sku"]).strip() != normalized_sku,
                row["catalog_scope"] != "organization",
                _iso(row["created_at"]) or "",
                str(row["id"]),
            ),
        )
        winners[normalized_sku] = ordered[0]
        duplicate_product_ids.update(str(row["id"]) for row in ordered[1:])

    archived_product_ids = invalid_product_ids | duplicate_product_ids
    for product in products:
        product_id = str(product["id"])
        if product_id not in archived_product_ids:
            continue
        reason = (
            "normalized_sku_conflict" if product_id in duplicate_product_ids else "legacy_identity"
        )
        original = {
            "sku": product["sku"],
            "category_id": product["category_id"],
            "station": product["station"],
            "status": product["status"],
            "catalog_scope": product["catalog_scope"],
            "source_branch_id": product["source_branch_id"],
            "updated_at": _iso(product["updated_at"]),
        }
        applied = {"sku": f"ARCHIVED-{product_id}"[:64], "status": "archived", "reason": reason}
        record("product", product_id, "archived", original, applied)
        connection.execute(
            tables["products"]
            .update()
            .where(tables["products"].c.id == product_id)
            .values(sku=applied["sku"], status="archived", updated_at=now)
        )
        summary["products_archived"] += 1
        if reason == "normalized_sku_conflict":
            summary["product_duplicates_archived"] += 1

    category_targets: dict[str, str] = {}
    for product in winners.values():
        source_category = category_by_id[str(product["category_id"])]
        source_category_id = str(source_category["id"])
        canonical_name = _category(source_category["name"])
        target = canonical_categories.get(canonical_name)
        if target is None:
            category_id = _id()
            created = {
                "id": category_id,
                "organization_id": source_category["organization_id"],
                "name": canonical_name[:120],
                "display_order": source_category["display_order"],
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            connection.execute(tables["categories"].insert().values(**created))
            record("product_category_created", category_id, "created", {}, {"name": canonical_name})
            target = created
            canonical_categories[canonical_name] = target
            summary["categories_created"] += 1
        category_targets[source_category_id] = str(target["id"])

    retained_product_ids: set[str] = set()
    retained_product_values: dict[str, dict[str, Any]] = {}
    for normalized_sku, product in winners.items():
        product_id = str(product["id"])
        source_category = category_by_id[str(product["category_id"])]
        category_name = _category(source_category["name"])
        applied = {
            "sku": normalized_sku,
            "category_id": category_targets[str(product["category_id"])],
            "station": _station(product["name"], category_name),
            "status": "active",
            "catalog_scope": "organization",
            "source_branch_id": None,
        }
        original = {
            "sku": product["sku"],
            "category_id": product["category_id"],
            "station": product["station"],
            "status": product["status"],
            "catalog_scope": product["catalog_scope"],
            "source_branch_id": product["source_branch_id"],
            "updated_at": _iso(product["updated_at"]),
        }
        record("product", product_id, "normalized", original, applied)
        connection.execute(
            tables["products"]
            .update()
            .where(tables["products"].c.id == product_id)
            .values(**applied, updated_at=now)
        )
        retained_product_ids.add(product_id)
        retained_product_values[product_id] = applied
        summary["products_normalized"] += 1
        summary[f"products_station_{applied['station']}"] += 1

    for category_row in categories:
        category_id = str(category_row["id"])
        target_status = "active" if _uppercase(category_row["name"]) else "archived"
        if category_row["status"] == target_status:
            continue
        original = {
            "status": category_row["status"],
            "updated_at": _iso(category_row["updated_at"]),
        }
        applied = {"status": target_status}
        record("product_category", category_id, "normalized", original, applied)
        connection.execute(
            tables["categories"]
            .update()
            .where(tables["categories"].c.id == category_id)
            .values(status=target_status, updated_at=now)
        )
        summary[
            "categories_archived" if target_status == "archived" else "categories_activated"
        ] += 1

    items = list(connection.execute(sa.select(tables["items"])).mappings())
    for item in items:
        item_id = str(item["id"])
        original = {
            "item_type": item["item_type"],
            "category_name": item["category_name"],
            "catalog_scope": item["catalog_scope"],
            "source_branch_id": item["source_branch_id"],
            "status": item["status"],
            "updated_at": _iso(item["updated_at"]),
        }
        if not _numeric(str(item["sku"] or "").strip()):
            applied = {"status": "archived"}
            action = "archived"
            summary["inventory_items_archived"] += 1
        else:
            category_name = _category(item["category_name"]) or None
            item_type = (
                "packaging"
                if category_name in PACKAGING_ITEM_CATEGORIES
                else str(item["item_type"] or "ingredient").strip().lower()
            )
            applied = {
                "item_type": item_type,
                "category_name": category_name,
                "catalog_scope": "organization",
                "source_branch_id": None,
                "status": "active",
            }
            action = "normalized"
            summary["inventory_items_normalized"] += 1
            if item_type == "packaging":
                summary["inventory_items_packaging"] += 1
        changed = any(original.get(key) != value for key, value in applied.items())
        if changed:
            record("inventory_item", item_id, action, original, applied)
            connection.execute(
                tables["items"]
                .update()
                .where(tables["items"].c.id == item_id)
                .values(**applied, updated_at=now)
            )

    if retained_product_ids:
        availability_rows = list(
            connection.execute(
                sa.select(tables["availability"]).where(
                    tables["availability"].c.product_id.in_(retained_product_ids)
                )
            ).mappings()
        )
        for row in availability_rows:
            entity_id = f"{row['branch_id']}:{row['product_id']}"
            record(
                "branch_product_availability",
                entity_id,
                "removed",
                {
                    "branch_id": row["branch_id"],
                    "product_id": row["product_id"],
                    "is_available": bool(row["is_available"]),
                    "updated_at": _iso(row["updated_at"]),
                },
                {},
            )
        connection.execute(
            tables["availability"]
            .delete()
            .where(tables["availability"].c.product_id.in_(retained_product_ids))
        )
        summary["availability_overrides_removed"] += len(availability_rows)

    product_record_rows = list(
        connection.execute(
            sa.select(tables["records"]).where(tables["records"].c.entity_type == "product")
        ).mappings()
    )
    for import_record in product_record_rows:
        target_id = str(import_record["target_entity_id"] or "")
        if target_id not in retained_product_ids and target_id not in archived_product_ids:
            continue
        normalized_payload = dict(import_record["normalized_payload"] or {})
        original = {
            "normalized_payload": normalized_payload,
            "status": import_record["status"],
            "reason_code": import_record["reason_code"],
            "updated_at": _iso(import_record["updated_at"]),
        }
        if target_id in retained_product_ids:
            product_values = retained_product_values[target_id]
            normalized_payload.update(
                {
                    "sku": product_values["sku"],
                    "station": product_values["station"],
                    "catalog_scope": "organization",
                }
            )
            applied = {
                "normalized_payload": normalized_payload,
                "status": "imported",
                "reason_code": None,
            }
            summary["import_product_records_resolved"] += 1
        else:
            applied = {
                "normalized_payload": normalized_payload,
                "status": "rejected",
                "reason_code": "legacy_product_identity",
            }
            summary["import_product_records_rejected"] += 1
        record("legacy_import_record", str(import_record["id"]), "resolved", original, applied)
        connection.execute(
            tables["records"]
            .update()
            .where(tables["records"].c.id == import_record["id"])
            .values(**applied, updated_at=now)
        )

    batch_rows = list(connection.execute(sa.select(tables["batches"])).mappings())
    for batch in batch_rows:
        status_rows = connection.execute(
            sa.select(tables["records"].c.status, sa.func.count(tables["records"].c.id))
            .where(tables["records"].c.batch_id == batch["id"])
            .group_by(tables["records"].c.status)
        ).all()
        batch_summary = {str(status): int(count) for status, count in status_rows}
        batch_status = (
            "review"
            if batch_summary.get("needs_review", 0) or batch_summary.get("rejected", 0)
            else "completed"
        )
        if batch["summary"] == batch_summary and batch["status"] == batch_status:
            continue
        original = {
            "status": batch["status"],
            "summary": batch["summary"],
            "updated_at": _iso(batch["updated_at"]),
        }
        applied = {"status": batch_status, "summary": batch_summary}
        record("legacy_import_batch", str(batch["id"]), "recomputed", original, applied)
        connection.execute(
            tables["batches"]
            .update()
            .where(tables["batches"].c.id == batch["id"])
            .values(**applied, updated_at=now)
        )
        summary["import_batches_recomputed"] += 1

    final_summary = dict(sorted(summary.items()))
    connection.execute(
        tables["cleanup_runs"]
        .insert()
        .values(
            id=run_id,
            revision=revision,
            status="completed",
            summary=final_summary,
            created_at=now,
        )
    )
    organization_id = connection.execute(
        sa.text("SELECT id FROM organizations ORDER BY id LIMIT 1")
    ).scalar_one_or_none()
    if organization_id:
        connection.execute(
            tables["audit"]
            .insert()
            .values(
                id=_id(),
                organization_id=organization_id,
                branch_id=None,
                actor_user_id=None,
                action="catalog.cleanup.applied",
                entity_type="catalog_cleanup_run",
                entity_id=run_id,
                payload={"revision": revision, "summary": final_summary},
                correlation_id=run_id,
                created_at=now,
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    tables = _tables()
    records = list(
        connection.execute(
            sa.select(tables["cleanup_records"]).where(
                tables["cleanup_records"].c.revision == revision
            )
        ).mappings()
    )

    for row in records:
        original = dict(row["original_payload"] or {})
        entity_type = row["entity_type"]
        if entity_type == "legacy_import_record":
            connection.execute(
                tables["records"]
                .update()
                .where(tables["records"].c.id == row["entity_id"])
                .values(
                    normalized_payload=original["normalized_payload"],
                    status=original["status"],
                    reason_code=original["reason_code"],
                    updated_at=_datetime(original["updated_at"]),
                )
            )
        elif entity_type == "legacy_import_batch":
            connection.execute(
                tables["batches"]
                .update()
                .where(tables["batches"].c.id == row["entity_id"])
                .values(
                    status=original["status"],
                    summary=original["summary"],
                    updated_at=_datetime(original["updated_at"]),
                )
            )

    product_records = [row for row in records if row["entity_type"] == "product"]
    for row in product_records:
        connection.execute(
            tables["products"]
            .update()
            .where(tables["products"].c.id == row["entity_id"])
            .values(sku=f"ROLLBACK-{row['entity_id']}"[:64])
        )
    for row in product_records:
        original = dict(row["original_payload"])
        connection.execute(
            tables["products"]
            .update()
            .where(tables["products"].c.id == row["entity_id"])
            .values(
                sku=original["sku"],
                category_id=original["category_id"],
                station=original["station"],
                status=original["status"],
                catalog_scope=original["catalog_scope"],
                source_branch_id=original["source_branch_id"],
                updated_at=_datetime(original["updated_at"]),
            )
        )

    for row in records:
        original = dict(row["original_payload"] or {})
        if row["entity_type"] == "inventory_item":
            connection.execute(
                tables["items"]
                .update()
                .where(tables["items"].c.id == row["entity_id"])
                .values(
                    item_type=original["item_type"],
                    category_name=original["category_name"],
                    catalog_scope=original["catalog_scope"],
                    source_branch_id=original["source_branch_id"],
                    status=original["status"],
                    updated_at=_datetime(original["updated_at"]),
                )
            )
        elif row["entity_type"] == "product_category":
            connection.execute(
                tables["categories"]
                .update()
                .where(tables["categories"].c.id == row["entity_id"])
                .values(
                    status=original["status"],
                    updated_at=_datetime(original["updated_at"]),
                )
            )
        elif row["entity_type"] == "branch_product_availability":
            connection.execute(
                tables["availability"]
                .delete()
                .where(
                    tables["availability"].c.branch_id == original["branch_id"],
                    tables["availability"].c.product_id == original["product_id"],
                )
            )
            connection.execute(
                tables["availability"]
                .insert()
                .values(
                    branch_id=original["branch_id"],
                    product_id=original["product_id"],
                    is_available=original["is_available"],
                    updated_at=_datetime(original["updated_at"]),
                )
            )

    created_category_ids = [
        row["entity_id"] for row in records if row["entity_type"] == "product_category_created"
    ]
    if created_category_ids:
        connection.execute(
            tables["categories"].delete().where(tables["categories"].c.id.in_(created_category_ids))
        )

    run_ids = list(
        connection.execute(
            sa.select(tables["cleanup_runs"].c.id).where(
                tables["cleanup_runs"].c.revision == revision
            )
        ).scalars()
    )
    if run_ids:
        connection.execute(
            tables["audit"]
            .delete()
            .where(
                tables["audit"].c.action == "catalog.cleanup.applied",
                tables["audit"].c.entity_id.in_(run_ids),
            )
        )
    op.drop_table("catalog_cleanup_records")
    op.drop_table("catalog_cleanup_runs")
