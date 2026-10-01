from __future__ import annotations

import json
from pathlib import Path


def test_online_capture_contract_is_separate_from_offline_envelope() -> None:
    root = Path(__file__).resolve().parents[2] / "packages/contracts/schemas"
    http = json.loads((root / "purchase-create-http-v1.schema.json").read_text())
    offline = json.loads((root / "purchase-command.schema.json").read_text())
    assert http["additionalProperties"] is False
    assert "command_id" not in http["properties"]
    assert "command_id" in offline["$defs"]["create"]["required"]
    assert http["properties"]["lines"]["maxItems"] == 200
    assert "unit_price" in http["$defs"]["line"]["required"]
    assert {option["format"] for option in http["properties"]["document_date"]["oneOf"]} == {
        "date",
        "date-time",
    }
    assert http["properties"]["notes"]["maxLength"] == 600
