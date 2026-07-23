from __future__ import annotations

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

business_units = sa.Table(
    "business_units",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("legal_entity_id", sa.String(36), sa.ForeignKey("legal_entities.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("code", sa.String(32), nullable=False),
    sa.Column("unit_type", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_business_units_organization_code"),
)

branches = sa.Table(
    "branches",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("legal_entity_id", sa.String(36), sa.ForeignKey("legal_entities.id"), nullable=False),
    sa.Column(
        "business_unit_id", sa.String(36), sa.ForeignKey("business_units.id"), nullable=False
    ),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("code", sa.String(32), nullable=False),
    sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Chihuahua"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_branches_organization_code"),
)

drivers = sa.Table(
    "drivers",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("license_number", sa.String(80), nullable=False),
    sa.Column("motorcycle_plate", sa.String(32), nullable=False),
    sa.Column("phone", sa.String(32), nullable=False),
    sa.Column("address", sa.String(500), nullable=False),
    sa.Column("emergency_contact_name", sa.String(160), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
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
    sa.Column("image_url", sa.String(512), nullable=True),
    sa.Column("catalog_scope", sa.String(24), nullable=False, server_default="organization"),
    sa.Column("source_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "sku", name="uq_products_org_sku"),
)

modifier_groups = sa.Table(
    "modifier_groups",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("minimum_selections", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("maximum_selections", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("station", sa.String(32), nullable=True),
    sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("product_id", "name", name="uq_modifier_group_product_name"),
)

modifier_options = sa.Table(
    "modifier_options",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("group_id", sa.String(36), sa.ForeignKey("modifier_groups.id"), nullable=False),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("effect_type", sa.String(24), nullable=False),
    sa.Column("price_delta_cents", sa.Integer(), nullable=False, server_default="0"),
    sa.Column(
        "affected_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=True
    ),
    sa.Column(
        "replacement_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=True
    ),
    sa.Column("remove_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("add_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("inventory_effect", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("kitchen_text", sa.String(240), nullable=False),
    sa.Column("station", sa.String(32), nullable=True),
    sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("group_id", "name", name="uq_modifier_option_group_name"),
)

branch_modifier_options = sa.Table(
    "branch_modifier_options",
    metadata,
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
    sa.Column("option_id", sa.String(36), sa.ForeignKey("modifier_options.id"), primary_key=True),
    sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("price_delta_cents", sa.Integer(), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

ingredient_variations = sa.Table(
    "ingredient_variations",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column(
        "inventory_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False
    ),
    sa.Column("add_label", sa.String(120), nullable=False),
    sa.Column("remove_label", sa.String(120), nullable=False),
    sa.Column("portion_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("sale_price_cents", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("station", sa.String(32), nullable=True),
    sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "organization_id", "inventory_item_id", name="uq_ingredient_variation_org_item"
    ),
)

order_comment_presets = sa.Table(
    "order_comment_presets",
    metadata,
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

order_comment_products = sa.Table(
    "order_comment_products",
    metadata,
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

ingredient_variation_products = sa.Table(
    "ingredient_variation_products",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "variation_id", sa.String(36), sa.ForeignKey("ingredient_variations.id"), nullable=False
    ),
    sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
    sa.Column("allow_add", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("allow_remove", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("add_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("remove_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("charge_additional", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("add_price_delta_cents", sa.Integer(), nullable=False, server_default="0"),
    sa.Column(
        "add_option_id",
        sa.String(36),
        sa.ForeignKey("modifier_options.id"),
        nullable=True,
        unique=True,
    ),
    sa.Column(
        "remove_option_id",
        sa.String(36),
        sa.ForeignKey("modifier_options.id"),
        nullable=True,
        unique=True,
    ),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("variation_id", "product_id", name="uq_ingredient_variation_product"),
    sa.CheckConstraint("allow_add = 1 OR allow_remove = 1", name="ck_ingredient_variation_actions"),
    sa.CheckConstraint(
        "allow_add = 0 OR add_quantity > 0", name="ck_ingredient_variation_add_quantity"
    ),
    sa.CheckConstraint("remove_quantity >= 0", name="ck_ingredient_variation_remove_quantity"),
    sa.CheckConstraint(
        "charge_additional = 0 OR (allow_add = 1 AND add_price_delta_cents > 0)",
        name="ck_ingredient_variation_charge",
    ),
    sa.CheckConstraint(
        "charge_additional = 1 OR add_price_delta_cents = 0",
        name="ck_ingredient_variation_free_price",
    ),
)

ingredient_variation_commands = sa.Table(
    "ingredient_variation_commands",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column(
        "variation_id", sa.String(36), sa.ForeignKey("ingredient_variations.id"), nullable=False
    ),
    sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("idempotency_key", sa.String(180), nullable=False, unique=True),
    sa.Column("request_hash", sa.String(64), nullable=False),
    sa.Column("result", sa.JSON(), nullable=True),
    sa.Column("status", sa.String(24), nullable=False, server_default="processing"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
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
    sa.Column("dimension", sa.String(24), nullable=False, server_default="discrete"),
    sa.Column("precision_scale", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_inventory_units_org_code"),
)

suppliers = sa.Table(
    "suppliers",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("code", sa.String(32), nullable=False),
    sa.Column("commercial_name", sa.String(180), nullable=False),
    sa.Column("legal_name", sa.String(180), nullable=True),
    sa.Column("tax_id", sa.String(16), nullable=True),
    sa.Column("tax_regime", sa.String(12), nullable=True),
    sa.Column("fiscal_address", sa.String(500), nullable=True),
    sa.Column("fiscal_postal_code", sa.String(12), nullable=True),
    sa.Column("municipality", sa.String(100), nullable=True),
    sa.Column("state", sa.String(100), nullable=True),
    sa.Column("country", sa.String(2), nullable=False, server_default="MX"),
    sa.Column("billing_email", sa.String(180), nullable=True),
    sa.Column("credit_days", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("credit_limit", sa.Numeric(18, 2), nullable=True),
    sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
    sa.Column("minimum_amount", sa.Numeric(18, 2), nullable=True),
    sa.Column("usual_lead_time_days", sa.Integer(), nullable=True),
    sa.Column("delivery_days", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("payment_methods", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("accounting_reference", sa.String(120), nullable=True),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_suppliers_organization_code"),
)

supplier_contacts = sa.Table(
    "supplier_contacts",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("position_area", sa.String(120), nullable=True),
    sa.Column("phone", sa.String(32), nullable=True),
    sa.Column("whatsapp", sa.String(32), nullable=True),
    sa.Column("email", sa.String(180), nullable=True),
    sa.Column("contact_type", sa.String(32), nullable=False),
    sa.Column("schedule", sa.String(160), nullable=True),
    sa.Column("primary_for_orders", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("primary_for_billing", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("primary_for_collection", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("notes", sa.String(400), nullable=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

supplier_branch_terms = sa.Table(
    "supplier_branch_terms",
    metadata,
    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), primary_key=True),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
    sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("lead_time_days", sa.Integer(), nullable=True),
    sa.Column("minimum_amount", sa.Numeric(18, 2), nullable=True),
    sa.Column("notes", sa.String(400), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

purchase_presentations = sa.Table(
    "purchase_presentations",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
    sa.Column("code", sa.String(64), nullable=False),
    sa.Column("name", sa.String(180), nullable=False),
    sa.Column("package_type", sa.String(40), nullable=False),
    sa.Column("commercial_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column(
        "commercial_unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False
    ),
    sa.Column("base_unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("base_unit_yield", sa.Numeric(18, 6), nullable=False),
    sa.Column("gross_content", sa.Numeric(18, 6), nullable=True),
    sa.Column("net_content", sa.Numeric(18, 6), nullable=True),
    sa.Column("usable_content", sa.Numeric(18, 6), nullable=False),
    sa.Column("yield_percent", sa.Numeric(9, 6), nullable=False),
    sa.Column("barcode", sa.String(64), nullable=True),
    sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
    sa.Column("last_net_price", sa.Numeric(18, 6), nullable=False),
    sa.Column("cost_per_base_unit", sa.Numeric(18, 6), nullable=False),
    sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_purchase_presentations_org_code"),
)

supplier_price_history = sa.Table(
    "supplier_price_history",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "presentation_id", sa.String(36), sa.ForeignKey("purchase_presentations.id"), nullable=False
    ),
    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
    sa.Column("net_price", sa.Numeric(18, 6), nullable=False),
    sa.Column("cost_per_base_unit", sa.Numeric(18, 6), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
    sa.Column(
        "effective_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
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
    sa.Column("category_name", sa.String(120), nullable=True),
    sa.Column("catalog_scope", sa.String(24), nullable=False, server_default="organization"),
    sa.Column("source_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
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
    sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
    sa.Column("output_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=True),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
    sa.Column("recipe_type", sa.String(24), nullable=False, server_default="sale"),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("yield_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("yield_unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
    sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("product_id", "version", name="uq_recipes_product_version"),
    sa.UniqueConstraint("output_item_id", "version", name="uq_recipes_output_item_version"),
)

recipe_components = sa.Table(
    "recipe_components",
    metadata,
    sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), primary_key=True),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), primary_key=True),
    sa.Column("quantity_base_units", sa.Numeric(18, 6), nullable=False),
    sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("net_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("waste_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
    sa.Column("gross_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("notes", sa.String(400), nullable=True),
)

recipe_cost_calculations = sa.Table(
    "recipe_cost_calculations",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("cost_before_waste", sa.Numeric(18, 6), nullable=False),
    sa.Column("waste_cost", sa.Numeric(18, 6), nullable=False),
    sa.Column("total_cost", sa.Numeric(18, 6), nullable=False),
    sa.Column("cost_per_yield_unit", sa.Numeric(18, 6), nullable=False),
    sa.Column("breakdown", sa.JSON(), nullable=False),
    sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("calculated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
)

production_batches = sa.Table(
    "production_batches",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
    sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=False),
    sa.Column("output_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
    sa.Column("lot_code", sa.String(80), nullable=False),
    sa.Column("planned_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("actual_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("actual_waste_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("branch_id", "lot_code", name="uq_production_batch_branch_lot"),
)

order_line_consumption_snapshots = sa.Table(
    "order_line_consumption_snapshots",
    metadata,
    sa.Column("order_line_id", sa.String(36), sa.ForeignKey("order_lines.id"), primary_key=True),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=False),
    sa.Column("recipe_version", sa.Integer(), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("components", sa.JSON(), nullable=False),
    sa.Column("modifiers", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("total_theoretical_cost", sa.Numeric(18, 6), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

waste_reasons = sa.Table(
    "waste_reasons",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("code", sa.String(40), nullable=False),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("classification", sa.String(40), nullable=False),
    sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("organization_id", "code", name="uq_waste_reason_organization_code"),
)

waste_records = sa.Table(
    "waste_records",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
    sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("reason_id", sa.String(36), sa.ForeignKey("waste_reasons.id"), nullable=False),
    sa.Column("stage", sa.String(48), nullable=False),
    sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
    sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("reversed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True),
    sa.Column(
        "reversal_movement_id",
        sa.String(36),
        sa.ForeignKey("inventory_movements.id"),
        nullable=True,
    ),
    sa.Column("confirmation_idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("reversal_idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("reversal_reason", sa.String(400), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
)

inventory_transfers = sa.Table(
    "inventory_transfers",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("source_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("source_warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
    sa.Column("destination_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column(
        "destination_warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False
    ),
    sa.Column("folio", sa.String(64), nullable=False),
    sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column("cancellation_reason", sa.String(400), nullable=True),
    sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("sent_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("received_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("send_idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("receive_idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("source_branch_id", "folio", name="uq_inventory_transfer_source_folio"),
)

inventory_transfer_lines = sa.Table(
    "inventory_transfer_lines",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "transfer_id", sa.String(36), sa.ForeignKey("inventory_transfers.id"), nullable=False
    ),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
    sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("requested_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("sent_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("received_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("difference_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("sent_total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("received_total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("difference_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("difference_reason", sa.String(400), nullable=True),
    sa.Column("condition", sa.String(40), nullable=True),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column(
        "out_movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True
    ),
    sa.Column(
        "in_movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("transfer_id", "item_id", name="uq_inventory_transfer_line_item"),
)

physical_count_sessions = sa.Table(
    "physical_count_sessions",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
    sa.Column("folio", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="counting"),
    sa.Column("scope", sa.String(32), nullable=False, server_default="all_active"),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column("cancellation_reason", sa.String(400), nullable=True),
    sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("submitted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("closed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("approval_idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("branch_id", "folio", name="uq_physical_count_branch_folio"),
)

physical_count_lines = sa.Table(
    "physical_count_lines",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "session_id", sa.String(36), sa.ForeignKey("physical_count_sessions.id"), nullable=False
    ),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
    sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("theoretical_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("snapshot_unit_cost", sa.Numeric(18, 6), nullable=False),
    sa.Column("snapshot_value", sa.Numeric(18, 6), nullable=False),
    sa.Column("counted_quantity", sa.Numeric(18, 6), nullable=True),
    sa.Column("snapshot_difference", sa.Numeric(18, 6), nullable=True),
    sa.Column("approval_ledger_quantity", sa.Numeric(18, 6), nullable=True),
    sa.Column("adjustment_quantity", sa.Numeric(18, 6), nullable=True),
    sa.Column("adjustment_unit_cost", sa.Numeric(18, 6), nullable=True),
    sa.Column("adjustment_cost", sa.Numeric(18, 6), nullable=True),
    sa.Column(
        "adjustment_movement_id",
        sa.String(36),
        sa.ForeignKey("inventory_movements.id"),
        nullable=True,
    ),
    sa.Column("captured_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.UniqueConstraint("session_id", "item_id", name="uq_physical_count_line_item"),
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
    sa.Column("quantity_delta", sa.Numeric(18, 6), nullable=False),
    sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
    sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column(
        "effective_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("document_type", sa.String(48), nullable=True),
    sa.Column("document_id", sa.String(36), nullable=True),
    sa.Column("reference", sa.String(120), nullable=True),
    sa.Column("reason", sa.String(240), nullable=False),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column("idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="confirmed"),
    sa.Column(
        "reversal_of_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True
    ),
    sa.Column("source_type", sa.String(80), nullable=True),
    sa.Column("source_id", sa.String(36), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

cash_movements = sa.Table(
    "cash_movements",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=False),
    sa.Column("movement_type", sa.String(32), nullable=False),
    sa.Column("amount_cents", sa.Integer(), nullable=False),
    sa.Column("reason_code", sa.String(48), nullable=False),
    sa.Column("reason", sa.String(240), nullable=False),
    sa.Column("source_type", sa.String(48), nullable=True),
    sa.Column("source_id", sa.String(36), nullable=True),
    sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("idempotency_key", sa.String(180), nullable=False, unique=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="confirmed"),
    sa.Column("reversal_of_id", sa.String(36), sa.ForeignKey("cash_movements.id"), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

purchase_documents = sa.Table(
    "purchase_documents",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
    sa.Column("document_type", sa.String(32), nullable=False),
    sa.Column("folio", sa.String(80), nullable=False),
    sa.Column("document_date", sa.DateTime(timezone=True), nullable=False),
    sa.Column("subtotal", sa.Numeric(18, 6), nullable=False),
    sa.Column("discount_total", sa.Numeric(18, 6), nullable=False),
    sa.Column("tax_total", sa.Numeric(18, 6), nullable=False),
    sa.Column("freight_total", sa.Numeric(18, 6), nullable=False, server_default="0"),
    sa.Column("total", sa.Numeric(18, 6), nullable=False),
    sa.Column("payment_method", sa.String(32), nullable=False),
    sa.Column("paid_from_cash", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("cash_movement_id", sa.String(36), sa.ForeignKey("cash_movements.id"), nullable=True),
    sa.Column("evidence_url", sa.String(600), nullable=True),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("confirmation_idempotency_key", sa.String(180), nullable=True, unique=True),
    sa.Column("cancellation_reason", sa.String(400), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint(
        "branch_id", "supplier_id", "document_type", "folio", name="uq_purchase_document_identity"
    ),
)

purchase_document_lines = sa.Table(
    "purchase_document_lines",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "purchase_document_id",
        sa.String(36),
        sa.ForeignKey("purchase_documents.id"),
        nullable=False,
    ),
    sa.Column(
        "presentation_id", sa.String(36), sa.ForeignKey("purchase_presentations.id"), nullable=False
    ),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
    sa.Column("presentation_snapshot", sa.JSON(), nullable=False),
    sa.Column("presentation_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("base_quantity", sa.Numeric(18, 6), nullable=False),
    sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
    sa.Column("discount", sa.Numeric(18, 6), nullable=False),
    sa.Column("tax", sa.Numeric(18, 6), nullable=False),
    sa.Column("line_total", sa.Numeric(18, 6), nullable=False),
    sa.Column("inventory_cost", sa.Numeric(18, 6), nullable=False),
    sa.Column("cost_per_base_unit", sa.Numeric(18, 6), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

inventory_cost_states = sa.Table(
    "inventory_cost_states",
    metadata,
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
    sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), primary_key=True),
    sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), primary_key=True),
    sa.Column("quantity_on_hand", sa.Numeric(18, 6), nullable=False),
    sa.Column("average_unit_cost", sa.Numeric(18, 6), nullable=False),
    sa.Column("last_unit_cost", sa.Numeric(18, 6), nullable=False),
    sa.Column("last_supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=True),
    sa.Column("last_cost_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
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

customers = sa.Table(
    "customers",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("email", sa.String(180), nullable=True),
    sa.Column("customer_type", sa.String(24), nullable=False, server_default="person"),
    sa.Column("customer_segment", sa.String(48), nullable=True),
    sa.Column("notes", sa.String(600), nullable=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("origin_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

customer_phones = sa.Table(
    "customer_phones",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False),
    sa.Column("captured_number", sa.String(32), nullable=False),
    sa.Column("normalized_number", sa.String(20), nullable=False),
    sa.Column("phone_type", sa.String(24), nullable=False, server_default="mobile"),
    sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

customer_addresses = sa.Table(
    "customer_addresses",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False),
    sa.Column("alias", sa.String(60), nullable=False),
    sa.Column("street", sa.String(180), nullable=False),
    sa.Column("exterior_number", sa.String(32), nullable=False),
    sa.Column("interior_number", sa.String(32), nullable=True),
    sa.Column("neighborhood", sa.String(120), nullable=False),
    sa.Column("postal_code", sa.String(12), nullable=False),
    sa.Column("city", sa.String(100), nullable=False),
    sa.Column("municipality", sa.String(100), nullable=False),
    sa.Column("state", sa.String(100), nullable=False),
    sa.Column("country", sa.String(2), nullable=False, server_default="MX"),
    sa.Column("cross_streets", sa.String(240), nullable=True),
    sa.Column("references", sa.String(600), nullable=True),
    sa.Column("delivery_instructions", sa.String(600), nullable=True),
    sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
    sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
    sa.Column("delivery_zone_id", sa.String(36), nullable=True),
    sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

legacy_import_batches = sa.Table(
    "legacy_import_batches",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("source_system", sa.String(80), nullable=False),
    sa.Column("manifest_checksum", sa.String(64), nullable=False),
    sa.Column("manifest", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="loading"),
    sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "organization_id",
        "branch_id",
        "source_system",
        "manifest_checksum",
        name="uq_legacy_import_batch_manifest",
    ),
)

legacy_import_records = sa.Table(
    "legacy_import_records",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("batch_id", sa.String(36), sa.ForeignKey("legacy_import_batches.id"), nullable=False),
    sa.Column("entity_type", sa.String(32), nullable=False),
    sa.Column("source_key", sa.String(160), nullable=False),
    sa.Column("source_row", sa.Integer(), nullable=False),
    sa.Column("raw_payload", sa.JSON(), nullable=False),
    sa.Column("normalized_payload", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("reason_code", sa.String(80), nullable=True),
    sa.Column("target_entity_type", sa.String(80), nullable=True),
    sa.Column("target_entity_id", sa.String(36), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "batch_id", "entity_type", "source_key", name="uq_legacy_import_record_source"
    ),
)

catalog_cleanup_runs = sa.Table(
    "catalog_cleanup_runs",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("revision", sa.String(80), nullable=False, unique=True),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("summary", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

catalog_cleanup_records = sa.Table(
    "catalog_cleanup_records",
    metadata,
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

customer_tax_profiles = sa.Table(
    "customer_tax_profiles",
    metadata,
    sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), primary_key=True),
    sa.Column("legal_name", sa.String(180), nullable=False),
    sa.Column("tax_id", sa.String(16), nullable=False),
    sa.Column("tax_regime", sa.String(12), nullable=False),
    sa.Column("fiscal_postal_code", sa.String(12), nullable=False),
    sa.Column("cfdi_use", sa.String(12), nullable=True),
    sa.Column("billing_email", sa.String(180), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

orders = sa.Table(
    "orders",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=False),
    sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
    sa.Column("customer_snapshot", sa.JSON(), nullable=True),
    sa.Column("delivery_address_snapshot", sa.JSON(), nullable=True),
    sa.Column("folio", sa.String(64), nullable=False),
    sa.Column("channel", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("total_cents", sa.Integer(), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
    sa.Column("owner_name", sa.String(160), nullable=True),
    sa.Column("order_type", sa.String(32), nullable=False, server_default="dine-in"),
    sa.Column("payment_method_intent", sa.String(32), nullable=True),
    sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("branch_id", "folio", name="uq_orders_branch_folio"),
)

delivery_assignments = sa.Table(
    "delivery_assignments",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False, unique=True),
    sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=False),
    sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
    sa.Column("driver_name_snapshot", sa.String(160), nullable=False),
    sa.Column("customer_name_snapshot", sa.String(160), nullable=False),
    sa.Column("delivery_address_snapshot", sa.JSON(), nullable=False),
    sa.Column("order_total_cents", sa.Integer(), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False),
    sa.Column("line_count", sa.Integer(), nullable=False),
    sa.Column("item_quantity", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="ASSIGNED"),
    sa.Column("assigned_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
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
    sa.Column("selected_modifiers", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("modifier_total_cents", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("line_notes", sa.String(500), nullable=True),
    sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("supersedes_line_id", sa.String(36), sa.ForeignKey("order_lines.id"), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

order_amendments = sa.Table(
    "order_amendments",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("sequence", sa.Integer(), nullable=False),
    sa.Column("expected_version", sa.Integer(), nullable=False),
    sa.Column("resulting_version", sa.Integer(), nullable=False),
    sa.Column("before_snapshot", sa.JSON(), nullable=False),
    sa.Column("after_snapshot", sa.JSON(), nullable=False),
    sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("idempotency_key", sa.String(160), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("order_id", "sequence", name="uq_order_amendment_sequence"),
    sa.UniqueConstraint("order_id", "idempotency_key", name="uq_order_amendment_idempotency"),
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
