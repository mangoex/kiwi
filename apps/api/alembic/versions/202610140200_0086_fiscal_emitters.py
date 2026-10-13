"""Explicit issuer identities and encrypted append-only configuration revisions."""

import sqlalchemy as sa
from alembic import op
from restaurant_os.fiscal_emitter_schema import LEGAL_ENTITY_INDEX, tables

revision = "0086_fiscal_emitters"
down_revision = "0085_fiscal_permissions"
branch_labels = depends_on = None


def _tables():
    metadata = sa.MetaData()
    sa.Table("organizations", metadata, sa.Column("id", sa.String(36), primary_key=True))
    sa.Table(
        "legal_entities",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
    )
    sa.Table("users", metadata, sa.Column("id", sa.String(36), primary_key=True))
    return tables(metadata)


def upgrade() -> None:
    bind = op.get_bind()
    op.create_index(LEGAL_ENTITY_INDEX, "legal_entities", ["organization_id", "id"], unique=True)
    identities, versions = _tables()
    identities.create(bind)
    versions.create(bind)
    with op.batch_alter_table("cfdi_invoices") as batch:
        batch.add_column(sa.Column("emitter_configuration_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("emitter_configuration_version", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_cfdi_emitter_configuration_revision",
            "fiscal_emitter_configuration_versions",
            ["emitter_configuration_id", "emitter_configuration_version"],
            ["configuration_id", "version"],
        )
        batch.create_check_constraint(
            "ck_cfdi_emitter_reference_complete",
            "(emitter_configuration_id IS NULL AND emitter_configuration_version IS NULL) OR "
            "(emitter_configuration_id IS NOT NULL AND emitter_configuration_version IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if (
        any(
            bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()
            for table in (
                "fiscal_emitter_configuration_versions",
                "fiscal_emitter_configurations",
            )
        )
        or bind.execute(
            sa.text(
                "SELECT 1 FROM cfdi_invoices WHERE emitter_configuration_id IS NOT NULL LIMIT 1"
            )
        ).first()
    ):
        raise RuntimeError(
            "0086 downgrade blocked: fiscal issuer configuration or document history exists"
        )
    with op.batch_alter_table("cfdi_invoices") as batch:
        batch.drop_constraint("fk_cfdi_emitter_configuration_revision", type_="foreignkey")
        batch.drop_constraint("ck_cfdi_emitter_reference_complete", type_="check")
        batch.drop_column("emitter_configuration_version")
        batch.drop_column("emitter_configuration_id")
    identities, versions = _tables()
    versions.drop(bind)
    identities.drop(bind)
    op.drop_index(LEGAL_ENTITY_INDEX, table_name="legal_entities")
