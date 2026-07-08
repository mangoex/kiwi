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

user_credentials = sa.Table(
    "user_credentials",
    metadata,
    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("password_hash", sa.String(96), nullable=False),
    sa.Column("password_salt", sa.String(32), nullable=False),
    sa.Column("password_algorithm", sa.String(32), nullable=False),
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

product_categories = sa.Table(
    "product_categories",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "name", name="uq_product_categories_org_name"),
)

products = sa.Table(
    "products",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("category_id", sa.String(36), sa.ForeignKey("product_categories.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("sku", sa.String(64), nullable=False),
    sa.Column("description", sa.String(360), nullable=True),
    sa.Column("station", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "sku", name="uq_products_org_sku"),
)

price_versions = sa.Table(
    "price_versions",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
    sa.Column("price_cents", sa.Integer(), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
    sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
    sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

branch_product_availability = sa.Table(
    "branch_product_availability",
    metadata,
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
    sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
    sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

inventory_units = sa.Table(
    "inventory_units",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("code", sa.String(24), nullable=False),
    sa.Column("name", sa.String(80), nullable=False),
    sa.Column("precision_scale", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_inventory_units_org_code"),
)

inventory_items = sa.Table(
    "inventory_items",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("sku", sa.String(64), nullable=False),
    sa.Column("base_unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("item_type", sa.String(32), nullable=False, server_default="ingredient"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "sku", name="uq_inventory_items_org_sku"),
)

recipes = sa.Table(
    "recipes",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("yield_quantity", sa.Integer(), nullable=False),
    sa.Column("yield_unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("product_id", "version", name="uq_recipes_product_version"),
)

recipe_components = sa.Table(
    "recipe_components",
    metadata,
    sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), primary_key=True),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), primary_key=True),
    sa.Column("quantity_base_units", sa.Integer(), nullable=False),
)

inventory_movements = sa.Table(
    "inventory_movements",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
    sa.Column("movement_type", sa.String(48), nullable=False),
    sa.Column("quantity_delta", sa.Integer(), nullable=False),
    sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("reason", sa.String(240), nullable=False),
    sa.Column("source_type", sa.String(80), nullable=True),
    sa.Column("source_id", sa.String(36), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

cash_shifts = sa.Table(
    "cash_shifts",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("register_code", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("opening_cash_cents", sa.Integer(), nullable=False),
    sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

orders = sa.Table(
    "orders",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=False),
    sa.Column("folio", sa.String(64), nullable=False),
    sa.Column("channel", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("total_cents", sa.Integer(), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("branch_id", "folio", name="uq_orders_branch_folio"),
)

order_lines = sa.Table(
    "order_lines",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
    sa.Column("product_name", sa.String(160), nullable=False),
    sa.Column("quantity", sa.Integer(), nullable=False),
    sa.Column("unit_price_cents", sa.Integer(), nullable=False),
    sa.Column("line_total_cents", sa.Integer(), nullable=False),
    sa.Column("station", sa.String(32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

order_events = sa.Table(
    "order_events",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("event_type", sa.String(80), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

production_tasks = sa.Table(
    "production_tasks",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("order_line_id", sa.String(36), sa.ForeignKey("order_lines.id"), nullable=False),
    sa.Column("station", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("product_name", sa.String(160), nullable=False),
    sa.Column("quantity", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
)

payments = sa.Table(
    "payments",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=False),
    sa.Column("method", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("amount_cents", sa.Integer(), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

cash_shift_cuts = sa.Table(
    "cash_shift_cuts",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column(
        "cash_shift_id",
        sa.String(36),
        sa.ForeignKey("cash_shifts.id"),
        nullable=False,
        unique=True,
    ),
    sa.Column("sales_total_cents", sa.Integer(), nullable=False),
    sa.Column("payment_total_cents", sa.Integer(), nullable=False),
    sa.Column("cash_payment_total_cents", sa.Integer(), nullable=False),
    sa.Column("opening_cash_cents", sa.Integer(), nullable=False),
    sa.Column("expected_cash_cents", sa.Integer(), nullable=False),
    sa.Column("counted_cash_cents", sa.Integer(), nullable=False),
    sa.Column("difference_cents", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

print_jobs = sa.Table(
    "print_jobs",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("job_type", sa.String(32), nullable=False),
    sa.Column("target", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("last_error", sa.String(240), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
)

sync_commands = sa.Table(
    "sync_commands",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("source_device_id", sa.String(36), nullable=False),
    sa.Column("command_id", sa.String(36), nullable=False),
    sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
    sa.Column("command_type", sa.String(120), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("checkpoint", sa.Integer(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
)

sync_events = sa.Table(
    "sync_events",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("sync_command_id", sa.String(36), sa.ForeignKey("sync_commands.id"), nullable=False),
    sa.Column("event_type", sa.String(120), nullable=False),
    sa.Column("checkpoint", sa.Integer(), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
)
