"""Phone verifier adapter contract, without contacting Twilio or sending SMS."""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from restaurant_os import phone_verification as provider


def verifier() -> provider.TwilioPhoneVerifier:
    return provider.TwilioPhoneVerifier("AC" + "a" * 32, "test", "VA" + "b" * 32)


def test_twilio_adapter_posts_bounded_sid_based_requests(monkeypatch: Any) -> None:
    recorded: list[Any] = []

    class Opener:
        def open(self, request: Any, timeout: int) -> Any:
            recorded.append((request, timeout))
            data = (
                {"status": "pending", "sid": "VE" + "c" * 32}
                if len(recorded) == 1
                else {"status": "approved"}
            )
            return io.BytesIO(json.dumps(data).encode())

    def opener(handler: Any) -> Any:
        assert handler.redirect_request(None, None, 302, "", None, "https://other") is None
        return Opener()

    monkeypatch.setattr(provider, "build_opener", opener)
    adapter = verifier()
    sid = adapter.start("+526691234567")
    assert adapter.check(sid, "123456")
    first, second = recorded
    assert (
        first[0].full_url
        == "https://verify.twilio.com/v2/Services/VA" + "b" * 32 + "/Verifications"
    )
    assert first[1] == 8
    assert b"Channel=sms" in first[0].data
    assert b"VerificationSid=VE" in second[0].data
    assert b"To=" not in second[0].data


def test_twilio_errors_do_not_become_approved_or_leak_values(monkeypatch: Any, caplog: Any) -> None:
    class Opener:
        def open(self, request: Any, timeout: int) -> Any:
            raise HTTPError(request.full_url, 404, "PRIVATE_SENTINEL", {}, None)

    monkeypatch.setattr(provider, "build_opener", lambda *args: Opener())
    assert not verifier().check("VE" + "c" * 32, "123456")
    with pytest.raises(provider.VerificationUnavailable):
        verifier().start("+526691234567")
    assert "PRIVATE_SENTINEL" not in caplog.text

    class Unavailable:
        def open(self, request: Any, timeout: int) -> Any:
            raise URLError("PRIVATE_SENTINEL")

    monkeypatch.setattr(provider, "build_opener", lambda *args: Unavailable())
    with pytest.raises(provider.VerificationUnavailable):
        verifier().check("VE" + "c" * 32, "123456")
    assert "PRIVATE_SENTINEL" not in caplog.text
