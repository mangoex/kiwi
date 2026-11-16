"""Branch operating hours defaults, validation, persistence, and schedule checks."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import BusinessError

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

DAY_NAMES_ES = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)

DEFAULT_BRANCH_OPERATING_HOURS: tuple[dict[str, Any], ...] = (
    {"day_of_week": 0, "is_open": True, "open_time": "07:00", "close_time": "18:00"},
    {"day_of_week": 1, "is_open": True, "open_time": "07:00", "close_time": "18:00"},
    {"day_of_week": 2, "is_open": True, "open_time": "07:00", "close_time": "18:00"},
    {"day_of_week": 3, "is_open": True, "open_time": "07:00", "close_time": "18:00"},
    {"day_of_week": 4, "is_open": True, "open_time": "07:00", "close_time": "18:00"},
    {"day_of_week": 5, "is_open": True, "open_time": "07:30", "close_time": "16:00"},
    {"day_of_week": 6, "is_open": False, "open_time": None, "close_time": None},
)


def default_branch_operating_hours() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_BRANCH_OPERATING_HOURS]


def _validate_hhmm(value: Any, *, field: str, day_of_week: int) -> str:
    if not isinstance(value, str) or not _TIME_RE.match(value.strip()):
        raise BusinessError(
            "invalid_branch_operating_hours",
            f"Invalid {field} for day {day_of_week}; expected HH:MM",
        )
    return value.strip()


def normalize_operating_hours(raw_hours: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_hours, list) or len(raw_hours) != 7:
        raise BusinessError(
            "invalid_branch_operating_hours",
            "operating_hours must be a list of 7 entries (day_of_week 0..6)",
        )
    by_day: dict[int, dict[str, Any]] = {}
    for entry in raw_hours:
        if not isinstance(entry, dict):
            raise BusinessError(
                "invalid_branch_operating_hours",
                "Each operating_hours entry must be an object",
            )
        day = entry.get("day_of_week")
        if isinstance(day, bool) or not isinstance(day, int) or not 0 <= day <= 6:
            raise BusinessError(
                "invalid_branch_operating_hours",
                "day_of_week must be an integer between 0 and 6",
            )
        if day in by_day:
            raise BusinessError(
                "invalid_branch_operating_hours",
                f"Duplicate day_of_week: {day}",
            )
        is_open = entry.get("is_open")
        if not isinstance(is_open, bool):
            raise BusinessError(
                "invalid_branch_operating_hours",
                f"is_open must be a boolean for day {day}",
            )
        if not is_open:
            by_day[day] = {
                "day_of_week": day,
                "is_open": False,
                "open_time": None,
                "close_time": None,
            }
        else:
            open_time = _validate_hhmm(entry.get("open_time"), field="open_time", day_of_week=day)
            close_time = _validate_hhmm(
                entry.get("close_time"), field="close_time", day_of_week=day
            )
            if open_time >= close_time:
                raise BusinessError(
                    "invalid_branch_operating_hours",
                    f"open_time must be earlier than close_time for {DAY_NAMES_ES[day]}",
                )
            by_day[day] = {
                "day_of_week": day,
                "is_open": True,
                "open_time": open_time,
                "close_time": close_time,
            }
    return [by_day[day] for day in range(7)]


def get_operating_hours_by_branch(
    session: Session, branch_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    if not branch_ids:
        return {}
    rows = (
        session.execute(
            sa.select(
                models.branch_operating_hours.c.branch_id,
                models.branch_operating_hours.c.day_of_week,
                models.branch_operating_hours.c.is_open,
                models.branch_operating_hours.c.open_time,
                models.branch_operating_hours.c.close_time,
            )
            .where(models.branch_operating_hours.c.branch_id.in_(branch_ids))
            .order_by(
                models.branch_operating_hours.c.branch_id,
                models.branch_operating_hours.c.day_of_week,
            )
        )
        .mappings()
        .all()
    )
    grouped: dict[str, list[dict[str, Any]]] = {branch_id: [] for branch_id in branch_ids}
    for row in rows:
        grouped[str(row["branch_id"])].append(
            {
                "day_of_week": int(row["day_of_week"]),
                "is_open": bool(row["is_open"]),
                "open_time": row["open_time"],
                "close_time": row["close_time"],
            }
        )
    for branch_id in branch_ids:
        if len(grouped[branch_id]) != 7:
            grouped[branch_id] = default_branch_operating_hours()
    return grouped


def get_branch_operating_hours(session: Session, branch_id: str) -> list[dict[str, Any]]:
    return get_operating_hours_by_branch(session, [branch_id]).get(
        branch_id, default_branch_operating_hours()
    )


def upsert_branch_operating_hours(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    hours: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    normalized = normalize_operating_hours(hours)
    session.execute(
        sa.delete(models.branch_operating_hours).where(
            models.branch_operating_hours.c.branch_id == branch_id
        )
    )
    session.execute(
        models.branch_operating_hours.insert(),
        [
            {
                "branch_id": branch_id,
                "day_of_week": item["day_of_week"],
                "organization_id": organization_id,
                "is_open": item["is_open"],
                "open_time": item["open_time"],
                "close_time": item["close_time"],
                "updated_at": now,
            }
            for item in normalized
        ],
    )
    return normalized


def is_branch_open_at(
    session: Session,
    branch_id: str,
    target_dt: datetime,
    *,
    now_utc: datetime | None = None,
    min_lead_minutes: int = 0,
) -> dict[str, Any]:
    branch = (
        session.execute(
            sa.select(
                models.branches.c.id,
                models.branches.c.name,
                models.branches.c.timezone,
                models.branches.c.status,
            ).where(models.branches.c.id == branch_id)
        )
        .mappings()
        .first()
    )
    if not branch or branch["status"] != "active":
        raise BusinessError("branch_not_found", "Active branch was not found")

    if target_dt.tzinfo is None:
        raise BusinessError("scheduled_time_invalid", "Scheduled datetime must include timezone")
    target_utc = target_dt.astimezone(timezone.utc)
    if now_utc is not None:
        ref_utc = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
        if target_utc < ref_utc + timedelta(minutes=min_lead_minutes):
            return {
                "open": False,
                "reason": "scheduled_time_in_past",
                "branch_name": branch["name"],
                "timezone": branch["timezone"],
            }

    tz_name = str(branch["timezone"] or "America/Chihuahua")
    local_dt = target_utc.astimezone(ZoneInfo(tz_name))
    day_of_week = local_dt.weekday()
    local_hhmm = local_dt.strftime("%H:%M")

    hours = get_branch_operating_hours(session, branch_id)
    day_cfg = hours[day_of_week]
    if not day_cfg["is_open"]:
        return {
            "open": False,
            "reason": "branch_closed_on_day",
            "branch_name": branch["name"],
            "timezone": tz_name,
            "day_of_week": day_of_week,
            "day_name": DAY_NAMES_ES[day_of_week],
            "day_schedule": day_cfg,
        }

    open_time = str(day_cfg["open_time"])
    close_time = str(day_cfg["close_time"])
    is_open_now = open_time <= local_hhmm <= close_time
    return {
        "open": is_open_now,
        "reason": None if is_open_now else "outside_operating_hours",
        "branch_name": branch["name"],
        "timezone": tz_name,
        "day_of_week": day_of_week,
        "day_name": DAY_NAMES_ES[day_of_week],
        "local_time": local_hhmm,
        "day_schedule": day_cfg,
    }


def validate_branch_open_at(
    session: Session,
    branch_id: str,
    target_dt: datetime,
    *,
    now_utc: datetime | None = None,
    min_lead_minutes: int = 0,
) -> dict[str, Any]:
    result = is_branch_open_at(
        session,
        branch_id,
        target_dt,
        now_utc=now_utc,
        min_lead_minutes=min_lead_minutes,
    )
    if not result["open"]:
        if result["reason"] == "scheduled_time_in_past":
            raise BusinessError(
                "scheduled_time_in_past",
                "La fecha y hora programada debe ser posterior al margen mínimo permitido.",
            )
        day_cfg = result.get("day_schedule") or {}
        day_name = result.get("day_name", "")
        if not day_cfg.get("is_open"):
            raise BusinessError(
                "branch_closed_at_scheduled_time",
                f"La sucursal {result['branch_name']} permanece cerrada los {day_name}.",
            )
        raise BusinessError(
            "branch_closed_at_scheduled_time",
            (
                f"La sucursal {result['branch_name']} atiende los {day_name} de "
                f"{day_cfg.get('open_time')} a {day_cfg.get('close_time')}."
            ),
        )
    return result
