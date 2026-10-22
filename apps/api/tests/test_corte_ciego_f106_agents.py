"""A technical capability is not an approved human financial audience."""

from datetime import datetime, timezone

import pytest
from restaurant_os import models
from test_agent_tools import ORGANIZATION_ID, _client, _configure, _factory, _token
from test_platform_api import BRANCH_ID


@pytest.mark.parametrize(
    "path,capability",
    [
        ("sales/summary", "agent.sales.read"),
        ("cash/cuts", "agent.cash_cuts.read"),
    ],
)
def test_technical_financial_reader_requires_human_audience(path: str, capability: str) -> None:
    factory = _factory()
    with _client(factory) as client:
        client_id, secret = _configure(client, "administrator", [capability])
        headers = {"Authorization": f"Bearer {_token(client, client_id, secret)}"}
        params = {
            "branch_id": BRANCH_ID,
            "from_utc": "2026-08-01T00:00:00Z",
            "to_utc": "2026-08-02T00:00:00Z",
        }
        baseline = client.get(f"/api/v1/agent-tools/{path}", params=params, headers=headers)
        assert baseline.status_code == 200, baseline.text
        with factory() as session:
            session.execute(
                models.blind_cash_policy_revisions.insert().values(
                    organization_id=ORGANIZATION_ID,
                    branch_id=BRANCH_ID,
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
        protected = client.get(f"/api/v1/agent-tools/{path}", params=params, headers=headers)
        assert protected.status_code == 403, protected.text
        assert protected.json()["detail"]["code"] == "financial_access_denied"
