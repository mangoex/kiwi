"""Frozen EXP-001 table definition, also used by migration 0076. Do not mutate v1."""

import sqlalchemy as sa


def tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table, sa.Table]:
    concepts = sa.Table(
        "expense_concepts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(600), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_expense_concept_code"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_expense_concept_status"),
        sa.CheckConstraint("version > 0", name="ck_expense_concept_version"),
    )
    documents = sa.Table(
        "expense_documents",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column(
            "concept_id", sa.String(36), sa.ForeignKey("expense_concepts.id"), nullable=False
        ),
        sa.Column("concept_snapshot", sa.JSON(), nullable=False),
        sa.Column("folio", sa.String(64), nullable=False, unique=True),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("total_cents", sa.BigInteger(), nullable=False),
        sa.Column("tax_cents", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_method", sa.String(16), nullable=False),
        sa.Column("reference", sa.String(120), nullable=False),
        sa.Column("notes", sa.String(600), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "cash_movement_id", sa.String(36), sa.ForeignKey("cash_movements.id"), unique=True
        ),
        sa.Column(
            "compensation_movement_id",
            sa.String(36),
            sa.ForeignKey("cash_movements.id"),
            unique=True,
        ),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.String(600)),
        sa.CheckConstraint(
            "total_cents > 0 AND total_cents <= 2147483647", name="ck_expense_amount"
        ),
        sa.CheckConstraint(
            "tax_cents IS NULL OR (tax_cents >= 0 AND tax_cents <= total_cents)",
            name="ck_expense_tax",
        ),
        sa.CheckConstraint("currency = 'MXN'", name="ck_expense_currency"),
        sa.CheckConstraint(
            "payment_method IN ('cash','transfer','card','other')", name="ck_expense_method"
        ),
        sa.CheckConstraint("status IN ('draft','confirmed','cancelled')", name="ck_expense_status"),
        sa.CheckConstraint("version > 0", name="ck_expense_version"),
        sa.CheckConstraint(
            "payment_method = 'cash' OR "
            "(cash_movement_id IS NULL AND compensation_movement_id IS NULL)",
            name="ck_expense_cash_links",
        ),
        sa.Index("ix_expense_branch_confirmed", "organization_id", "branch_id", "confirmed_at"),
        sa.Index("ix_expense_branch_cancelled", "organization_id", "branch_id", "cancelled_at"),
        sa.Index("ix_expense_concept", "organization_id", "concept_id"),
        sa.Index("ix_expense_branch_created", "organization_id", "branch_id", "created_at", "id"),
    )
    commands = sa.Table(
        "expense_commands",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id")),
        sa.Column("command_type", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_expense_command_key"),
    )
    return concepts, documents, commands
