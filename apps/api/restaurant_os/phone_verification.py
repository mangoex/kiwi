"""Phone verification port; secrets and provider payloads never enter the CRM."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

logger = logging.getLogger(__name__)


class VerificationUnavailable(Exception):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class PhoneVerifier(Protocol):
    def start(self, phone: str) -> str: ...
    def check(self, verification_id: str, code: str) -> bool: ...


class TwilioPhoneVerifier:
    def __init__(self, account_sid: str, auth_token: str, service_sid: str) -> None:
        if not re.fullmatch(r"AC[0-9a-fA-F]{32}", account_sid):
            raise ValueError("Invalid account SID")
        if not re.fullmatch(r"VA[0-9a-fA-F]{32}", service_sid):
            raise ValueError("Invalid Verify service SID")
        self._authorization = (
            "Basic " + base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        )
        self._base = f"https://verify.twilio.com/v2/Services/{service_sid}"

    def _post(self, resource: str, body: dict[str, str]) -> dict[str, Any]:
        request = Request(
            self._base + resource,
            data=urlencode(body).encode(),
            headers={
                "Authorization": self._authorization,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with build_opener(_NoRedirect()).open(request, timeout=8) as response:
                data: Any = json.loads(response.read(16384))
                if not isinstance(data, dict):
                    raise VerificationUnavailable()
                return dict(data)
        except HTTPError as exc:
            # Expired/used verification is deliberately indistinguishable from a bad code.
            if resource == "/VerificationCheck" and exc.code in (400, 404):
                return {"status": "denied"}
            logger.info("mobile_verification_provider", extra={"result": "unavailable"})
            raise VerificationUnavailable() from None
        except (URLError, TimeoutError, OSError, ValueError):
            logger.info("mobile_verification_provider", extra={"result": "unavailable"})
            raise VerificationUnavailable() from None

    def start(self, phone: str) -> str:
        data = self._post("/Verifications", {"To": phone, "Channel": "sms"})
        sid = str(data.get("sid", ""))
        if data.get("status") != "pending" or not re.fullmatch(r"VE[0-9a-fA-F]{32}", sid):
            raise VerificationUnavailable()
        return sid

    def check(self, verification_id: str, code: str) -> bool:
        return (
            self._post(
                "/VerificationCheck",
                {
                    "VerificationSid": verification_id,
                    "Code": code,
                },
            ).get("status")
            == "approved"
        )
