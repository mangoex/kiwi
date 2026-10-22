"""Human print acknowledgements; raw ticket payloads belong to the device boundary."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.cash_views import active_revision
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock

JOB_FIELDS = (
    "id",
    "organization_id",
    "branch_id",
    "order_id",
    "job_type",
    "target",
    "status",
    "attempts",
    "created_at",
    "printed_at",
)
ATTEMPT_FIELDS = ("id", "print_job_id", "status", "created_at")


class PrintJobMetadata(FinancialRecord):
    id: str
    organization_id: str
    branch_id: str
    order_id: str
    job_type: str
    target: str
    status: str
    attempts: int
    created_at: datetime
    printed_at: datetime | None


class PrintAttemptMetadata(FinancialRecord):
    id: str
    print_job_id: str
    status: str
    created_at: datetime


def require_human_print(
    session: Session,
    actor: str | None,
    branch: str,
    permission: str,
) -> bool:
    governance_lock(session, ops.ORGANIZATION_ID)
    if active_revision(session, branch) is None:
        return False
    if actor is None:
        deny()
    assert actor is not None
    FinancialAuthority(session, actor, ops.ORGANIZATION_ID).policy_revision(branch)
    if not ops._actor_has_permission(session, actor, permission, branch):
        deny()
    return True


def retry_receipt(
    job: Mapping[str, Any], attempt: Mapping[str, Any], replay: bool
) -> dict[str, Any]:
    return {
        "job": PrintJobMetadata(**{key: job[key] for key in JOB_FIELDS}).model_dump(mode="json"),
        "attempt": PrintAttemptMetadata(**{key: attempt[key] for key in ATTEMPT_FIELDS}).model_dump(
            mode="json"
        ),
        "replayed": replay,
    }
