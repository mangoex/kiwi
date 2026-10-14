"""Append-only private supplier evidence and import command results."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.sql.schema import SchemaItem


def tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table, sa.Table]:
    def common() -> list[SchemaItem]:
        return [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("branch_id", sa.String(36), nullable=False),
            sa.Column("actor_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ]

    def scoped(prefix: str) -> list[SchemaItem]:
        return [
            sa.ForeignKeyConstraint(
                ["organization_id", "branch_id"],
                ["branches.organization_id", "branches.id"],
                name=f"fk_{prefix}_branch",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "actor_user_id"],
                ["users.organization_id", "users.id"],
                name=f"fk_{prefix}_actor",
            ),
            sa.UniqueConstraint("id", "organization_id", "branch_id", name=f"uq_{prefix}_scope"),
        ]

    def evidence(prefix: str) -> list[SchemaItem]:
        return [
            sa.Column("original_sha256", sa.String(64), nullable=False),
            sa.Column("original_size", sa.Integer(), nullable=False),
            sa.Column("original_ciphertext", sa.Text(), nullable=False),
            sa.CheckConstraint("length(original_sha256) = 64", name=f"ck_{prefix}_hash"),
            sa.CheckConstraint("original_size BETWEEN 1 AND 1048576", name=f"ck_{prefix}_size"),
            sa.CheckConstraint(
                "length(original_ciphertext) BETWEEN 1 AND 1572864", name=f"ck_{prefix}_cipher"
            ),
        ]

    imports = sa.Table(
        "supplier_document_imports",
        metadata,
        *common(),
        *evidence("supplier_import"),
        sa.Column("legal_entity_id", sa.String(36), nullable=False),
        sa.Column("declared_uuid", sa.String(36), nullable=False),
        sa.Column("capture_profile", sa.String(48), nullable=False),
        sa.Column("fiscal_validation", sa.String(16), nullable=False),
        *scoped("supplier_import"),
        sa.ForeignKeyConstraint(
            ["organization_id", "legal_entity_id"],
            ["legal_entities.organization_id", "legal_entities.id"],
            name="fk_supplier_import_entity",
        ),
        sa.UniqueConstraint(
            "organization_id", "declared_uuid", name="uq_supplier_import_declared_uuid"
        ),
        sa.CheckConstraint(
            "length(declared_uuid) = 36 AND declared_uuid = upper(declared_uuid)",
            name="ck_supplier_import_uuid",
        ),
        sa.CheckConstraint(
            "capture_profile = 'cfdi4_tfd11_identity_v1'", name="ck_supplier_import_profile"
        ),
        sa.CheckConstraint(
            "fiscal_validation = 'unverified'", name="ck_supplier_import_unverified"
        ),
    )
    conflicts = sa.Table(
        "supplier_document_import_conflicts",
        metadata,
        *common(),
        *evidence("supplier_conflict"),
        sa.Column("import_id", sa.String(36), nullable=False),
        *scoped("supplier_conflict"),
        sa.ForeignKeyConstraint(
            ["import_id", "organization_id", "branch_id"],
            [
                "supplier_document_imports.id",
                "supplier_document_imports.organization_id",
                "supplier_document_imports.branch_id",
            ],
            name="fk_supplier_conflict_original",
        ),
        sa.UniqueConstraint("import_id", "original_sha256", name="uq_supplier_conflict_hash"),
        sa.UniqueConstraint(
            "id",
            "import_id",
            "organization_id",
            "branch_id",
            name="uq_supplier_conflict_command_scope",
        ),
    )
    commands = sa.Table(
        "supplier_document_import_commands",
        metadata,
        *common(),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("import_id", sa.String(36), nullable=False),
        sa.Column("conflict_id", sa.String(36), nullable=True),
        sa.Column("result_kind", sa.String(16), nullable=False),
        *scoped("supplier_import_command"),
        sa.ForeignKeyConstraint(
            ["import_id", "organization_id", "branch_id"],
            [
                "supplier_document_imports.id",
                "supplier_document_imports.organization_id",
                "supplier_document_imports.branch_id",
            ],
            name="fk_supplier_import_command_original",
        ),
        sa.ForeignKeyConstraint(
            ["conflict_id", "import_id", "organization_id", "branch_id"],
            [
                "supplier_document_import_conflicts.id",
                "supplier_document_import_conflicts.import_id",
                "supplier_document_import_conflicts.organization_id",
                "supplier_document_import_conflicts.branch_id",
            ],
            name="fk_supplier_import_command_conflict",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "idempotency_key",
            name="uq_supplier_import_command_key",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 128", name="ck_supplier_import_command_key"
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_supplier_import_command_hash"),
        sa.CheckConstraint(
            "result_kind IN ('imported','duplicate','conflict')",
            name="ck_supplier_import_command_result",
        ),
        sa.CheckConstraint(
            "(result_kind = 'conflict' AND conflict_id IS NOT NULL) OR "
            "(result_kind != 'conflict' AND conflict_id IS NULL)",
            name="ck_supplier_import_command_link",
        ),
    )
    return imports, conflicts, commands
