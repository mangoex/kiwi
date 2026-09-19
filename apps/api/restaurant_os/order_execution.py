"""Command-scoped deterministic inputs for offline order execution.

The context is intentionally small: it controls only values that the order
domain already obtains implicitly (time, generated identifiers and folio) and
the read-only catalog session.  It never redirects operational writes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ExecutionContext:
    """Inputs frozen for one command execution.

    ``folio`` is supplied by the gateway's persisted local sequence.  Keeping
    it optional preserves online folio allocation outside an offline command.
    ``catalog_session`` is read-only by contract; callers retain the separate
    operational session for inserts, transitions and authorization.
    """

    command_id: str
    accepted_at: datetime
    folio: str | None = None
    catalog_session: Session | None = None
    gateway_epoch: int | None = None
    execution_mode: Literal["online", "offline_reconcile"] = "online"

    def __post_init__(self) -> None:
        try:
            UUID(self.command_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("execution command_id must be a UUID") from exc
        if self.accepted_at.tzinfo is None or self.accepted_at.utcoffset() is None:
            raise ValueError("execution accepted_at must be timezone-aware")
        normalized = self.accepted_at.astimezone(UTC)
        object.__setattr__(self, "accepted_at", normalized)
        if self.folio is not None:
            folio = self.folio.strip()
            if not folio or len(folio) > 64:
                raise ValueError("execution folio must contain 1 to 64 characters")
            object.__setattr__(self, "folio", folio)
        if self.gateway_epoch is not None and (
            isinstance(self.gateway_epoch, bool) or self.gateway_epoch < 0
        ):
            raise ValueError("execution gateway_epoch must be a non-negative integer")
        if self.execution_mode not in {"online", "offline_reconcile"}:
            raise ValueError("execution mode is invalid")


_context: ContextVar[ExecutionContext | None] = ContextVar("order_execution_context", default=None)
_counter: ContextVar[int] = ContextVar("order_execution_counter", default=0)
_authorization_denials: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "order_execution_authorization_denials", default=None
)


@contextmanager
def order_execution_context(context: ExecutionContext) -> Iterator[ExecutionContext]:
    """Activate a context for the current task/thread and reset its ID stream."""
    context_token = _context.set(context)
    counter_token = _counter.set(0)
    try:
        yield context
    finally:
        _counter.reset(counter_token)
        _context.reset(context_token)


@contextmanager
def defer_authorization_audit() -> Iterator[list[dict[str, Any]]]:
    """Collect offline authorization denials for the owning transaction boundary.

    An offline command can be part of an outbox/inbox unit of work.  Its domain
    authorization check must never roll back or commit that owner transaction.
    The caller consumes the yielded records only after its savepoint decision.
    """
    records: list[dict[str, Any]] = []
    token = _authorization_denials.set(records)
    try:
        yield records
    finally:
        _authorization_denials.reset(token)


def defer_authorization_denial(
    *,
    actor_user_id: str | None,
    permission_code: str,
    branch_id: str | None,
    reason: str,
) -> bool:
    """Record an offline denial without taking ownership of the session."""
    context = current_execution_context()
    records = _authorization_denials.get()
    if context is None or context.execution_mode != "offline_reconcile" or records is None:
        return False
    records.append(
        {
            "actor_user_id": actor_user_id,
            "permission_code": permission_code,
            "branch_id": branch_id,
            "reason": reason,
        }
    )
    return True


def current_execution_context() -> ExecutionContext | None:
    return _context.get()


def catalog_session_for(operational_session: Session) -> Session:
    context = current_execution_context()
    if context is not None and context.catalog_session is not None:
        return context.catalog_session
    return operational_session


def next_id() -> str | None:
    """Return a deterministic UUIDv7 while a context is active.

    The timestamp portion comes from ``accepted_at``; the remainder is derived
    from the command UUID and an execution-local counter.  ContextVar makes
    counters independent for concurrent executions even when the same context
    value is reused.
    """
    context = current_execution_context()
    if context is None:
        return None
    counter = _counter.get()
    _counter.set(counter + 1)
    command = UUID(context.command_id)
    digest = sha256(command.bytes + counter.to_bytes(8, "big")).digest()
    milliseconds = int(context.accepted_at.timestamp() * 1000)
    if not 0 <= milliseconds < (1 << 48):
        raise ValueError("execution accepted_at is outside UUIDv7 range")
    value = milliseconds << 80
    value |= 0x7 << 76
    value |= (int.from_bytes(digest[:2], "big") & 0x0FFF) << 64
    value |= 0b10 << 62
    value |= int.from_bytes(digest[2:10], "big") & ((1 << 62) - 1)
    return str(UUID(int=value))
