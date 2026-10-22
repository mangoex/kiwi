"""Own navigation metadata; a session snapshot never authorizes a later command."""

from __future__ import annotations

from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import (
    FinancialAuthority,
    authority_tables_available,
    protected_policy_revision,
)


class BranchFinancialAccess(FinancialRecord):
    branch_id: str
    policy_version: int | None
    state: Literal["legacy", "active", "suspended"]
    capabilities: dict[str, bool]
    datasets: list[str]


class SessionFinancialAccess(FinancialRecord):
    schema_version: Literal[2] = 2
    authorization_version: int
    branches: list[BranchFinancialAccess]


def session_financial_access(
    session: Session, actor: str, organization: str, branches: list[str], version: int
) -> dict[str, Any]:
    authority = FinancialAuthority(session, actor, organization)
    if not authority_tables_available(session):
        authority._begin(version)
        authority._branches(branches)
        return SessionFinancialAccess(
            authorization_version=version,
            branches=[
                BranchFinancialAccess(
                    branch_id=branch,
                    policy_version=None,
                    state="legacy",
                    capabilities={},
                    datasets=[],
                )
                for branch in sorted(branches)
            ],
        ).model_dump(mode="json")
    descriptions = authority.describe_scopes(branches, expected_version=version)
    table = models.blind_cash_policy_revisions
    result = []
    for branch in sorted(branches):
        row = session.execute(
            sa.select(table.c.revision, table.c.event)
            .where(table.c.organization_id == organization, table.c.branch_id == branch)
            .order_by(table.c.revision.desc())
            .limit(1)
        ).first()
        state: Literal["legacy", "active", "suspended"]
        try:
            state = (
                "legacy"
                if protected_policy_revision(session, organization, branch) is None
                else "active"
            )
        except ops.BusinessError as exc:
            if exc.code != "cash_policy_suspended":
                raise
            state = "suspended"
        capabilities: dict[str, bool] = {}
        datasets: list[str] = []
        if state == "active":
            capabilities, datasets = descriptions[branch]
        result.append(
            BranchFinancialAccess(
                branch_id=branch,
                policy_version=int(row.revision) if row else None,
                state=state,
                capabilities=capabilities,
                datasets=datasets,
            )
        )
    return SessionFinancialAccess(
        authorization_version=version,
        branches=result,
    ).model_dump(mode="json")
