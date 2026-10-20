"""Shared birthday contract for CRM and mobile self-service."""

from __future__ import annotations

from datetime import date
from typing import Any


def birthday_values(payload: dict[str, Any]) -> dict[str, int | None]:
    values = {
        field: payload.get(field) for field in ("birthday_day", "birthday_month", "birthday_year")
    }
    day, month, year = values.values()
    if day is None and month is None and year is None:
        return values
    if (
        type(day) is not int
        or type(month) is not int
        or (year is not None and type(year) is not int)
    ):
        raise ValueError("Birthday needs day and month; year is optional")
    actual = date(2000 if year is None else year, month, day)
    if year is not None and (year < 1900 or actual > date.today()):
        raise ValueError("Birth date must not be in the future")
    return values
