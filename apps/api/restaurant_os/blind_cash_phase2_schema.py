"""CORTE-CIEGO-001 Phases 2..6 additive schema tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session


def tables(metadata: sa.MetaData) -> tuple[sa.Table, ...]:
    denominations = sa.Table(
        "blind_cash_denominations",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("denomination_cents", sa.Integer, nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updated_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "denomination_cents", name="uq_blind_cash_denom_org_cents"
        ),
        sa.CheckConstraint("denomination_cents > 0", name="ck_blind_cash_denom_positive"),
        sa.CheckConstraint("kind IN ('bill', 'coin')", name="ck_blind_cash_denom_kind"),
    )

    declarations = sa.Table(
        "user_cash_cut_declarations",
        metadata,
        sa.Column(
            "cash_cut_id",
            sa.String(36),
            sa.ForeignKey("user_cash_cuts.id"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("responsible_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("capturer_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_substitution", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("substitution_reason", sa.String(500), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("counted_cash_cents", sa.Integer, nullable=False),
        sa.Column("denominations_snapshot", sa.JSON, nullable=False),
        sa.Column("payment_methods_snapshot", sa.JSON, nullable=False),
        sa.Column("draft_history", sa.JSON, nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("custody_delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("custody_receiver_user_id", sa.String(36), nullable=True),
        sa.Column("custody_notes", sa.String(500), nullable=True),
        sa.Column("retained_fund_cents", sa.Integer, nullable=True),
        sa.Column("custody_movement_id", sa.String(36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('DRAFT', 'CONFIRMED')", name="ck_cut_decl_state"),
        sa.CheckConstraint("counted_cash_cents >= 0", name="ck_cut_decl_cash_nonneg"),
        sa.CheckConstraint("revision >= 1", name="ck_cut_decl_revision"),
    )

    reconciliations = sa.Table(
        "user_cash_cut_method_reconciliations",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cash_cut_id", sa.String(36), sa.ForeignKey("user_cash_cuts.id"), nullable=False),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("payment_method", sa.String(32), nullable=False),
        sa.Column("declared_cents", sa.Integer, nullable=True),
        sa.Column("expected_cents", sa.Integer, nullable=True),
        sa.Column("difference_cents", sa.Integer, nullable=True),
        sa.Column("reconciliation_status", sa.String(32), nullable=False),
        sa.Column("pending_reason", sa.String(500), nullable=True),
        sa.Column("source_references", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "cash_cut_id", "payment_method", name="uq_cut_method_reconcil_cut_method"
        ),
        sa.CheckConstraint(
            "reconciliation_status IN ('RECONCILED', 'PENDING_EXTERNAL')",
            name="ck_cut_method_reconcil_status",
        ),
    )

    error_reports = sa.Table(
        "user_cash_cut_error_reports",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cash_cut_id", sa.String(36), sa.ForeignKey("user_cash_cuts.id"), nullable=False),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("reporter_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("evidence_refs", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("trim(reason) != ''", name="ck_cut_error_report_reason"),
    )

    owner_alerts = sa.Table(
        "owner_alerts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("dataset", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("delivery_status", sa.String(32), nullable=False),
        sa.Column("delivery_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_delivery_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by_user_id", sa.String(36), nullable=True),
        sa.UniqueConstraint("organization_id", "dedupe_key", name="uq_owner_alerts_org_dedupe"),
        sa.CheckConstraint(
            "delivery_status IN ('PENDING', 'SENT', 'FAILED_RETRYING', 'ACKNOWLEDGED')",
            name="ck_owner_alerts_delivery_status",
        ),
    )

    alert_recipients = sa.Table(
        "owner_alert_recipients",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "branch_id",
            "user_id",
            "alert_type",
            "channel",
            name="uq_owner_alert_recipient_scope",
        ),
    )

    control_events = sa.Table(
        "operational_control_events",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("control_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("supervisor_user_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("sequence_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    return (
        denominations,
        declarations,
        reconciliations,
        error_reports,
        owner_alerts,
        alert_recipients,
        control_events,
    )


def ensure_phase2_tables(session: Session) -> None:
    """Ensure Phase 2..6 additive tables exist in isolated test schemas."""
    if session.info.get("_cc_phase2_tables_ready"):
        return
    from restaurant_os import models

    conn = session.connection()
    inspector = sa.inspect(conn)
    for table in (
        models.blind_cash_denominations,
        models.user_cash_cut_declarations,
        models.user_cash_cut_method_reconciliations,
        models.user_cash_cut_error_reports,
        models.owner_alerts,
        models.owner_alert_recipients,
        models.operational_control_events,
    ):
        if not inspector.has_table(table.name):
            table.create(conn, checkfirst=True)
    session.info["_cc_phase2_tables_ready"] = True
