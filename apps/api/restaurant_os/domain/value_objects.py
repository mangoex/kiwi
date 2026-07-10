from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc

UTC = UTC
from decimal import Decimal

from .errors import ValidationError


@dataclass(frozen=True)
class Money:
    """
    Representa dinero en la menor unidad posible (centavos) para evitar errores de flotantes.
    Alternativamente, podríamos usar Decimal directamente, pero el patrón en enteros
    evita problemas silenciosos de redondeo en APIs.
    """
    cents: int

    @classmethod
    def from_decimal(cls, amount: Decimal) -> Money:
        """Crea Money a partir de un Decimal exacto, asumiendo 2 decimales para la moneda base."""
        # Multiplicamos por 100 y nos aseguramos de que no queden decimales ocultos
        cents_decimal = amount * Decimal("100")
        if cents_decimal % 1 != 0:
            raise ValidationError(f"Cantidad {amount} contiene fracciones de centavo.")
        return cls(cents=int(cents_decimal))

    def to_decimal(self) -> Decimal:
        return Decimal(self.cents) / Decimal("100")

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents - other.cents)

    def __mul__(self, multiplier: int | Decimal) -> Money:
        if isinstance(multiplier, int):
            return Money(self.cents * multiplier)
        elif isinstance(multiplier, Decimal):
            # Requiere redondeo si hay fracciones. Por simplicidad de dominio puro:
            cents_decimal = self.cents * multiplier
            return Money(int(cents_decimal.quantize(Decimal("1"))))
        return NotImplemented


@dataclass(frozen=True)
class Quantity:
    """
    Representa una cantidad de inventario o receta, la cual debe ser exacta.
    En RestaurantOS las cantidades deben calcularse con Decimal, nunca con float.
    """
    amount: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise ValidationError("Quantity debe ser inicializado con Decimal.")

    def __add__(self, other: Quantity) -> Quantity:
        if not isinstance(other, Quantity):
            return NotImplemented
        return Quantity(self.amount + other.amount)

    def __sub__(self, other: Quantity) -> Quantity:
        if not isinstance(other, Quantity):
            return NotImplemented
        return Quantity(self.amount - other.amount)

    def __mul__(self, multiplier: int | Decimal) -> Quantity:
        if isinstance(multiplier, (int, Decimal)):
            return Quantity(self.amount * multiplier)
        return NotImplemented


def utc_now() -> datetime:
    """Devuelve la fecha y hora actual en UTC."""
    return datetime.now(UTC)
