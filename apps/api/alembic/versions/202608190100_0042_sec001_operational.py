"""add SEC-001 operational credentials and print attempts

Revision ID: 0042_sec001_operational
Revises: 0042_recipe_reports
"""

from alembic import op
import sqlalchemy as sa

revision = "0042_sec001_operational"
down_revision = "0042_recipe_reports"
branch_labels = None
depends_on = None

KDS_PERMISSION_ID = "018f6f73-2d0a-74f0-8f1c-000000000928"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description, created_at) "
            "VALUES (:id, 'kds.tasks.operate', 'Operar tareas KDS de la sucursal.', "
            "'2026-08-19 01:00:00+00:00') ON CONFLICT (code) DO NOTHING"
        ).bindparams(id=KDS_PERMISSION_ID)
    )
    op.create_index(
        "uq_branches_organization_id_id",
        "branches",
        ["organization_id", "id"],
        unique=True,
    )
    op.create_table(
        "device_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_version", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("capability IN ('kds.operate', 'gateway.sync', 'print.agent')", name="ck_device_credential_capability"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_device_credential_token_hash"),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["branches.organization_id", "branches.id"],
            name="fk_device_credentials_organization_branch",
        ),
    )
    op.create_table(
        "print_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("print_job_id", sa.String(36), sa.ForeignKey("print_jobs.id"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("claimed_by_device_id", sa.String(36)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("ack_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acked_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.UniqueConstraint("print_job_id", "idempotency_key", name="uq_print_attempt_key"),
        sa.CheckConstraint("status IN ('QUEUED', 'CLAIMED', 'PRINTED', 'FAILED')", name="ck_print_attempt_status"),
        sa.CheckConstraint(
            "(status = 'QUEUED' AND claimed_by_device_id IS NULL AND claimed_at IS NULL "
            "AND ack_hash IS NULL AND acked_at IS NULL AND failed_at IS NULL AND error_code IS NULL) OR "
            "(status = 'CLAIMED' AND claimed_by_device_id IS NOT NULL AND claimed_at IS NOT NULL "
            "AND ack_hash IS NULL AND acked_at IS NULL AND failed_at IS NULL AND error_code IS NULL) OR "
            "(status = 'PRINTED' AND claimed_by_device_id IS NOT NULL AND claimed_at IS NOT NULL "
            "AND ack_hash IS NOT NULL AND acked_at IS NOT NULL AND failed_at IS NULL AND error_code IS NULL) OR "
            "(status = 'FAILED' AND claimed_by_device_id IS NOT NULL AND claimed_at IS NOT NULL "
            "AND failed_at IS NOT NULL AND error_code IS NOT NULL AND ack_hash IS NULL AND acked_at IS NULL)",
            name="ck_print_attempt_state_fields",
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_print_attempt_request_hash"),
        sa.CheckConstraint("ack_hash IS NULL OR length(ack_hash) = 64", name="ck_print_attempt_ack_hash"),
        sa.CheckConstraint("error_code IS NULL OR (length(error_code) BETWEEN 1 AND 64)", name="ck_print_attempt_error_code"),
    )
    op.create_index(
        "ix_print_attempts_pull_scope",
        "print_attempts",
        ["organization_id", "branch_id", "status", "created_at", "id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM print_attempts LIMIT 1")).first() or bind.execute(sa.text("SELECT 1 FROM device_credentials LIMIT 1")).first():
        raise RuntimeError("SEC-001 device or print history blocks downgrade")
    if bind.execute(
        sa.text(
            "SELECT 1 FROM role_permissions WHERE permission_id = "
            "(SELECT id FROM permissions WHERE code = 'kds.tasks.operate') LIMIT 1"
        )
    ).first():
        raise RuntimeError("SEC-001 KDS permission grants block downgrade")
    op.drop_table("print_attempts")
    op.drop_table("device_credentials")
    op.drop_index("uq_branches_organization_id_id", table_name="branches")
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'kds.tasks.operate'"))
