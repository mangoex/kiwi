import json
from datetime import timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from restaurant_os.operations import _now
from test_operating_expenses import BRANCH_A, command, draft, setup_expenses

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[2] / "packages/contracts/operating-expenses-v1.schema.json"
    ).read_text(encoding="utf-8")
)


def validate(name, data):
    Draft202012Validator(
        {**SCHEMA, "$ref": f"#/$defs/{name}"}, format_checker=FormatChecker()
    ).validate(data)


def test_real_expense_payloads_conform_across_transitions():
    client, headers = setup_expenses()
    doc = draft(client, headers)
    validate("document", doc)
    validate(
        "cashContext",
        client.get(f"/api/v1/expenses/cash-context?branch_id={BRANCH_A}", headers=headers).json(),
    )
    for concept in client.get(
        f"/api/v1/expense-concepts?branch_id={BRANCH_A}", headers=headers
    ).json():
        validate("concept", concept)
    confirmed = command(
        client,
        headers,
        f"/expenses/{doc['id']}/confirm",
        {
            "branch_id": BRANCH_A,
            "version": 1,
            "register_id": "CAJA-01",
            "expected_cash_shift_id": "expense-shift",
        },
    )
    assert confirmed.status_code == 200
    validate("document", confirmed.json())
    cancelled = command(
        client,
        headers,
        f"/expenses/{doc['id']}/cancel",
        {
            "branch_id": BRANCH_A,
            "version": 2,
            "reason": "Devolución",
            "cash_returned": True,
            "evidence_refs": ["archivo:reembolso"],
        },
    )
    assert cancelled.status_code == 200
    validate("document", cancelled.json())
    validate("page", client.get(f"/api/v1/expenses?branch_id={BRANCH_A}", headers=headers).json())
    report = client.get(
        "/api/v1/expenses/summary",
        headers=headers,
        params={
            "branch_id": BRANCH_A,
            "from_utc": (_now() - timedelta(days=1)).isoformat(),
            "to_utc": (_now() + timedelta(days=1)).isoformat(),
        },
    )
    assert report.status_code == 200, report.text
    validate("summary", report.json())
    assert report.json()["net_cents"] == 0
