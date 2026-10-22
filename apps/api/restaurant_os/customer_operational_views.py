"""Closed contact projections for attending an order without sales history."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.cash_views import Projection


class ContactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def utc_timestamp(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            )
        return value


class ContactPhoneV2(ContactRecord):
    id: str
    customer_id: str
    captured_number: str
    normalized_number: str
    phone_type: str
    is_primary: bool
    whatsapp_enabled: bool
    is_verified: bool
    status: str
    created_at: datetime
    updated_at: datetime


class ContactAddressV2(ContactRecord):
    id: str
    customer_id: str
    alias: str
    street: str
    exterior_number: str
    interior_number: str | None
    neighborhood: str
    postal_code: str
    city: str
    municipality: str
    state: str
    country: str
    cross_streets: str | None
    references: str | None
    delivery_instructions: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    delivery_zone_id: str | None
    is_default: bool
    status: str
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContactTaxProfileV2(ContactRecord):
    customer_id: str
    legal_name: str
    tax_id: str
    tax_regime: str
    fiscal_postal_code: str
    cfdi_use: str | None
    billing_email: str | None
    updated_at: datetime


CUSTOMER_COLUMNS = (
    "id",
    "organization_id",
    "name",
    "email",
    "birthday_day",
    "birthday_month",
    "birthday_year",
    "customer_type",
    "notes",
    "status",
    "origin_branch_id",
    "created_at",
    "updated_at",
)


class CustomerOperationalV2(Projection):
    id: str
    organization_id: str
    name: str
    email: str | None
    birthday_day: int | None
    birthday_month: int | None
    birthday_year: int | None
    customer_type: str
    notes: str | None
    status: str
    origin_branch_id: str | None
    created_at: datetime
    updated_at: datetime
    phones: list[ContactPhoneV2]
    addresses: list[ContactAddressV2]
    tax_profile: ContactTaxProfileV2 | None
    legacy_address_reference: str | None


class CustomerOperationalPageV2(ContactRecord):
    items: list[CustomerOperationalV2] = Field(max_length=100)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


def legacy_addresses(
    session: Session, organization_id: str, branch_id: str, customer_ids: list[str]
) -> dict[str, str | None]:
    # Select only the contact field; import payloads may also contain historical money.
    records, batches = models.legacy_import_records, models.legacy_import_batches
    rows = session.execute(
        sa.select(
            records.c.target_entity_id,
            records.c.normalized_payload["legacy_address"].as_string().label("address"),
        )
        .select_from(records.join(batches, records.c.batch_id == batches.c.id))
        .where(
            records.c.target_entity_id.in_(customer_ids),
            records.c.entity_type == "customer",
            records.c.target_entity_type == "customer",
            batches.c.organization_id == organization_id,
            batches.c.branch_id == branch_id,
        )
        .order_by(records.c.created_at, records.c.id)
    ).mappings()
    return {str(row["target_entity_id"]): row["address"] for row in rows}
