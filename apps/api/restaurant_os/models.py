import sqlalchemy as sa

metadata = sa.MetaData()


organizations = sa.Table(
    "organizations",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

legal_entities = sa.Table(
    "legal_entities",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("name", sa.String(180), nullable=False),
    sa.Column("tax_id", sa.String(32), nullable=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

branches = sa.Table(
    "branches",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("legal_entity_id", sa.String(36), sa.ForeignKey("legal_entities.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("code", sa.String(32), nullable=False),
    sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Chihuahua"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_branches_organization_code"),
)

warehouses = sa.Table(
    "warehouses",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column(
        "branch_id",
        sa.String(36),
        sa.ForeignKey("branches.id"),
        nullable=False,
        unique=True,
    ),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

roles = sa.Table(
    "roles",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("scope", sa.String(32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),
)

permissions = sa.Table(
    "permissions",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("code", sa.String(120), nullable=False, unique=True),
    sa.Column("description", sa.String(240), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("email", sa.String(180), nullable=False, unique=True),
    sa.Column("display_name", sa.String(160), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="invited"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

role_permissions = sa.Table(
    "role_permissions",
    metadata,
    sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), primary_key=True),
    sa.Column("permission_id", sa.String(36), sa.ForeignKey("permissions.id"), primary_key=True),
)

user_roles = sa.Table(
    "user_roles",
    metadata,
    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), primary_key=True),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
)

audit_events = sa.Table(
    "audit_events",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
    sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("action", sa.String(120), nullable=False),
    sa.Column("entity_type", sa.String(120), nullable=False),
    sa.Column("entity_id", sa.String(36), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("correlation_id", sa.String(36), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
