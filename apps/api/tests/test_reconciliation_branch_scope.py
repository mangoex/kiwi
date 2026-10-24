from datetime import datetime, timezone

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.financial_reads import read_branches
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)


def test_multi_branch_consolidated_report_ignores_inactive_branches():
    """The money guard and materialization share the same active branch population."""
    client = _client_with_seeded_database()
    inactive_branch_id = "branch-inactive-reconciliation"
    with _test_session_factory(client)() as session:
        original = dict(
            session.execute(
                sa.select(models.branches).where(models.branches.c.id == BRANCH_ID)
            ).mappings().one()
        )
        session.execute(
            models.branches.insert().values(
                **{
                    **original,
                    "id": inactive_branch_id,
                    "code": "INACTIVE-RECON",
                    "name": "Sucursal inactiva",
                    "status": "inactive",
                }
            )
        )
        session.execute(
            models.blind_cash_policy_revisions.insert().values(
                organization_id=original["organization_id"],
                branch_id=inactive_branch_id,
                revision=1,
                manifest_digest="a" * 64,
                minimum_api_version=2,
                minimum_client_version=2,
                minimum_gateway_version=2,
                event="activated",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        assert inactive_branch_id in read_branches(session, None)
        assert inactive_branch_id not in read_branches(session, None, active_only=True)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    response = client.get(
        f"/api/v2/reports/branch-reconciliation/consolidated?date_from={today_str}&date_to={today_str}",
        headers=_admin_headers(),
    )

    assert response.status_code == 200, response.text
    assert inactive_branch_id not in {row["branch_id"] for row in response.json()["branches"]}
