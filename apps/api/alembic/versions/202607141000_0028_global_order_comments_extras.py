"""global order comments and universal ingredient extras

Revision ID: 0028_global_order_comments_extras
Revises: 0027_catalog_cleanup
Create Date: 2026-07-14 10:00:00.000000
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0028_global_order_comments_extras"
down_revision: str | None = "0027_catalog_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> str:
    return str(uuid4())


def _normalized_comment(value: object) -> str:
    compact = " ".join(str(value or "").strip().split())
    decomposed = unicodedata.normalize("NFKD", compact)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_accents.casefold()


def _tables() -> dict[str, sa.TableClause]:
    return {
        "organizations": sa.table("organizations", sa.column("id")),
        "legacy_options": sa.table(
            "modifier_options",
            sa.column("id"),
            sa.column("group_id"),
            sa.column("name"),
            sa.column("effect_type"),
            sa.column("display_order"),
            sa.column("status"),
        ),
        "legacy_groups": sa.table(
            "modifier_groups",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("product_id"),
        ),
        "variations": sa.table(
            "ingredient_variations",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("status"),
            sa.column("portion_quantity"),
            sa.column("sale_price_cents"),
            sa.column("station"),
            sa.column("display_order"),
        ),
        "status_backups": sa.table(
            "ingredient_variation_0028_status_backups",
            sa.column("variation_id"),
            sa.column("previous_status"),
        ),
        "assignments": sa.table(
            "ingredient_variation_products",
            sa.column("variation_id"),
            sa.column("allow_add"),
            sa.column("allow_remove"),
            sa.column("add_quantity"),
            sa.column("add_price_delta_cents"),
            sa.column("add_option_id"),
            sa.column("status"),
        ),
        "options": sa.table(
            "modifier_options",
            sa.column("id"),
            sa.column("station"),
            sa.column("display_order"),
        ),
        "presets": sa.table(
            "order_comment_presets",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("text"),
            sa.column("text_normalized"),
            sa.column("display_order"),
            sa.column("status"),
            sa.column("created_by"),
            sa.column("updated_by"),
            sa.column("created_at"),
            sa.column("updated_at"),
        ),
        "relations": sa.table(
            "order_comment_products",
            sa.column("id"),
            sa.column("comment_preset_id"),
            sa.column("product_id"),
            sa.column("status"),
            sa.column("actor_user_id"),
            sa.column("created_at"),
            sa.column("updated_at"),
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
        "ingredient_variation_0028_status_backups",
        sa.Column(
            "variation_id",
            sa.String(36),
            sa.ForeignKey("ingredient_variations.id"),
            primary_key=True,
        ),
        sa.Column("previous_status", sa.String(32), nullable=False),
    )
    op.create_table(
        "order_comment_presets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("text", sa.String(120), nullable=False),
        sa.Column("text_normalized", sa.String(120), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "text_normalized", name="uq_order_comment_preset_org_normalized"
        ),
    )
    op.create_table(
        "order_comment_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "comment_preset_id",
            sa.String(36),
            sa.ForeignKey("order_comment_presets.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "comment_preset_id", "product_id", name="uq_order_comment_product_pair"
        ),
    )

    op.add_column(
        "ingredient_variations",
        sa.Column("portion_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    )
    op.add_column(
        "ingredient_variations",
        sa.Column("sale_price_cents", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("ingredient_variations", sa.Column("station", sa.String(32), nullable=True))
    op.add_column(
        "ingredient_variations",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )

    connection = op.get_bind()
    tables = _tables()
    now = datetime.now(timezone.utc)

    # Convert the old product-specific preset options into one corporate identity
    # plus an explicit many-to-many relation.  The old motor is intentionally left
    # untouched so historical orders and legacy read paths remain readable.
    preset_ids: dict[tuple[str, str], str] = {}
    preset_counts: dict[str, int] = {}
    preset_rows = connection.execute(
        sa.select(
            tables["legacy_groups"].c.organization_id,
            tables["legacy_groups"].c.product_id,
            tables["legacy_options"].c.name,
            tables["legacy_options"].c.display_order,
            tables["legacy_options"].c.status,
        )
        .select_from(
            tables["legacy_options"].join(
                tables["legacy_groups"],
                tables["legacy_options"].c.group_id == tables["legacy_groups"].c.id,
            )
        )
        .where(tables["legacy_options"].c.effect_type == "preset_instruction")
        .order_by(tables["legacy_groups"].c.organization_id, tables["legacy_options"].c.name)
    ).mappings()
    for row in preset_rows:
        organization_id = str(row["organization_id"])
        visible_text = " ".join(str(row["name"] or "").strip().split())
        normalized = _normalized_comment(visible_text)
        if not visible_text or not normalized:
            continue
        key = (organization_id, normalized)
        preset_id = preset_ids.get(key)
        if preset_id is None:
            preset_id = _id()
            preset_ids[key] = preset_id
            preset_counts[organization_id] = preset_counts.get(organization_id, 0) + 1
            connection.execute(
                tables["presets"].insert().values(
                    id=preset_id,
                    organization_id=organization_id,
                    text=visible_text[:120],
                    text_normalized=normalized[:120],
                    display_order=int(row["display_order"] or 0),
                    status="active" if row["status"] == "active" else "archived",
                    created_by=None,
                    updated_by=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        elif row["status"] == "active":
            connection.execute(
                tables["presets"].update()
                .where(tables["presets"].c.id == preset_id)
                .values(status="active", updated_at=now)
            )

        existing_relation = connection.execute(
            sa.select(tables["relations"].c.id, tables["relations"].c.status).where(
                tables["relations"].c.comment_preset_id == preset_id,
                tables["relations"].c.product_id == row["product_id"],
            )
        ).mappings().first()
        relation_status = "active" if row["status"] == "active" else "archived"
        if existing_relation:
            if relation_status == "active":
                connection.execute(
                    tables["relations"].update()
                    .where(tables["relations"].c.id == existing_relation["id"])
                    .values(status="active", updated_at=now)
                )
        else:
            connection.execute(
                tables["relations"].insert().values(
                    id=_id(),
                    comment_preset_id=preset_id,
                    product_id=row["product_id"],
                    status=relation_status,
                    actor_user_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )

    # Consolidate only a single, fully consistent ADD configuration.  A missing
    # value, remove assignment, or disagreement is deliberately non-publishable.
    review_counts: dict[str, int] = {}
    active_counts: dict[str, int] = {}
    variation_rows = connection.execute(sa.select(tables["variations"])).mappings()
    for variation in variation_rows:
        organization_id = str(variation["organization_id"])
        assignments = list(
            connection.execute(
                sa.select(
                    tables["assignments"].c.allow_add,
                    tables["assignments"].c.allow_remove,
                    tables["assignments"].c.add_quantity,
                    tables["assignments"].c.add_price_delta_cents,
                    tables["assignments"].c.add_option_id,
                    tables["assignments"].c.status,
                    tables["options"].c.station,
                    tables["options"].c.display_order,
                )
                .select_from(
                    tables["assignments"].outerjoin(
                        tables["options"],
                        tables["assignments"].c.add_option_id == tables["options"].c.id,
                    )
                )
                .where(
                    tables["assignments"].c.variation_id == variation["id"],
                    tables["assignments"].c.status == "active",
                )
            ).mappings()
        )
        add_assignments = [row for row in assignments if row["allow_add"]]
        candidates = [
            (
                str(row["add_quantity"]),
                int(row["add_price_delta_cents"] or 0),
                row["station"],
                int(row["display_order"] or 0),
            )
            for row in add_assignments
            if row["add_option_id"] and row["station"]
        ]
        contradictory = (
            not add_assignments
            or len(candidates) != len(add_assignments)
            or any(row["allow_remove"] for row in assignments)
            or len(set(candidates)) != 1
        )
        next_status = (
            "needs_review"
            if contradictory
            else variation["status"] if variation["status"] in {"active", "archived"} else "active"
        )
        if next_status != variation["status"]:
            connection.execute(
                tables["status_backups"].insert().values(
                    variation_id=variation["id"],
                    previous_status=variation["status"],
                )
            )
        if contradictory:
            review_counts[organization_id] = review_counts.get(organization_id, 0) + 1
            connection.execute(
                tables["variations"].update()
                .where(tables["variations"].c.id == variation["id"])
                .values(
                    portion_quantity="0",
                    sale_price_cents=0,
                    station=None,
                    display_order=0,
                    status="needs_review",
                )
            )
            continue
        quantity, price, station, display_order = candidates[0]
        active_counts[organization_id] = active_counts.get(organization_id, 0) + 1
        connection.execute(
            tables["variations"].update()
            .where(tables["variations"].c.id == variation["id"])
            .values(
                portion_quantity=quantity,
                sale_price_cents=price,
                station=station,
                display_order=display_order,
                status=next_status,
            )
        )

    affected_organizations = sorted(
        set(preset_counts) | set(active_counts) | set(review_counts)
    )
    for organization_id in affected_organizations:
        connection.execute(
            tables["audit"].insert().values(
                id=_id(),
                organization_id=organization_id,
                branch_id=None,
                actor_user_id=None,
                action="catalog.global_comments_extras_migrated",
                entity_type="migration",
                entity_id=revision,
                payload={
                    "comment_presets": preset_counts.get(organization_id, 0),
                    "ingredient_variations_active": active_counts.get(organization_id, 0),
                    "ingredient_variations_needs_review": review_counts.get(organization_id, 0),
                },
                correlation_id=None,
                created_at=now,
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    tables = _tables()
    for backup in connection.execute(sa.select(tables["status_backups"])).mappings():
        connection.execute(
            tables["variations"].update()
            .where(tables["variations"].c.id == backup["variation_id"])
            .values(status=backup["previous_status"])
        )
    op.drop_table("order_comment_products")
    op.drop_table("order_comment_presets")
    op.drop_table("ingredient_variation_0028_status_backups")
    with op.batch_alter_table("ingredient_variations") as batch_op:
        batch_op.drop_column("display_order")
        batch_op.drop_column("station")
        batch_op.drop_column("sale_price_cents")
        batch_op.drop_column("portion_quantity")
