"""Additive credential and throttle schema, shared with migration 0099."""

import sqlalchemy as sa


def password_tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table]:
    credentials = sa.Table(
        "mobile_customer_credentials", metadata,
        sa.Column("identity_id", sa.String(36),
                  sa.ForeignKey("mobile_customer_identities.id"), primary_key=True),
        sa.Column("password_salt", sa.String(32), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    attempts = sa.Table(
        "mobile_auth_attempts", metadata,
        sa.Column("bucket_key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    return credentials, attempts
