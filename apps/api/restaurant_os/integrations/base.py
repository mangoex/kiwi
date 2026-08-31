from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NormalizedOrderItem:
    product_id: str
    product_name: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int
    special_instructions: str | None = None
    selected_modifiers: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NormalizedOrder:
    external_order_id: str
    provider: str
    display_code: str
    external_store_id: str
    customer_name: str
    customer_phone: str | None
    delivery_notes: str | None
    items: list[NormalizedOrderItem]
    total_cents: int
    currency: str
    placed_at: datetime
    raw_payload: dict[str, Any]


class IOrderChannelAdapter(ABC):
    @abstractmethod
    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str | None,
        secret: str | None,
    ) -> bool:
        """Verifica la autenticidad criptográfica del webhook."""
        pass

    @abstractmethod
    def parse_webhook_event(
        self, payload: dict[str, Any]
    ) -> tuple[str, str | None]:
        """Extrae el tipo de evento y el identificador de recurso."""
        pass

    @abstractmethod
    def normalize_order(
        self,
        payload: dict[str, Any],
        product_mappings: dict[str, str],
        default_products: list[dict[str, Any]] | None = None,
    ) -> NormalizedOrder:
        """Convierte el payload del marketplace en una orden canónica."""
        pass
