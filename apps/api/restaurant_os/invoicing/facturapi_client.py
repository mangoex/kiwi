"""Facturapi v2 HTTP REST Client."""

from __future__ import annotations

import http.client
import json
import logging
import socket
import ssl
import time
import urllib.error
import urllib.request
from threading import Timer
from typing import Any

from .documents import valid_remote_id
from .json_codec import encode_json

logger = logging.getLogger(__name__)

FACTURAPI_BASE_URL = "https://www.facturapi.io/v2"
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


class _DeadlineHTTPSConnection(http.client.HTTPSConnection):
    """One monotonic budget, including urllib's pre-response header reads."""

    def __init__(self, *args: Any, deadline: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.deadline = deadline
        self.watchdog: Timer | None = None
        self.transport: socket.socket | None = None

    def remaining(self) -> float:
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError("fiscal_provider_deadline")
        return seconds

    def _arm_deadline(self) -> None:
        if self.watchdog is not None:
            return
        transport = self.sock
        if transport is None:
            raise RuntimeError("fiscal_provider_transport_missing")
        self.transport = transport
        transport.settimeout(self.remaining())

        def expire() -> None:
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Already closed by EOF or finalization.

        self.watchdog = Timer(self.remaining(), expire)
        self.watchdog.daemon = True
        self.watchdog.start()

    def connect(self) -> None:
        self.timeout = self.remaining()
        super().connect()
        self._arm_deadline()

    def finish(self) -> None:
        if self.watchdog is not None:
            self.watchdog.cancel()
        self.close()


class _DeadlineHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, deadline: float) -> None:
        self.tls_context = ssl.create_default_context()
        self.tls_context.set_alpn_protocols(["http/1.1"])
        super().__init__(context=self.tls_context)
        self.deadline = deadline
        self.connections: list[_DeadlineHTTPSConnection] = []

    def https_open(self, req: Any) -> Any:
        def connection(host: str, **kwargs: Any) -> _DeadlineHTTPSConnection:
            result = _DeadlineHTTPSConnection(host, deadline=self.deadline, **kwargs)
            self.connections.append(result)
            return result

        return self.do_open(connection, req, context=self.tls_context)

    def remaining(self) -> float:
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError("fiscal_provider_deadline")
        return seconds

    def prepare_read(self) -> None:
        seconds = self.remaining()
        for connection in self.connections:
            if connection.transport is not None:
                connection.transport.settimeout(seconds)

    def finish(self) -> None:
        for connection in self.connections:
            connection.finish()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        # Never forward an issuer's Authorization header to a redirected destination.
        return None


class FacturapiClient:
    """HTTP Client for Facturapi v2 REST API."""

    def __init__(self, api_key: str | None = None, is_mock: bool = False):
        self.api_key = api_key
        self.is_mock = is_mock or not api_key or api_key.startswith("sk_test_mock")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "RestaurantOS-Kiwi/1.0",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            body_bytes = encode_json(data) if data is not None else None
        except (ValueError, TypeError, UnicodeError, OverflowError):
            raise RuntimeError("fiscal_provider_payload_invalid") from None
        if self.is_mock:
            return self._mock_response(method, endpoint, data)

        transport = _DeadlineHTTPSHandler(time.monotonic() + 20)
        url = f"{FACTURAPI_BASE_URL}{endpoint}"
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers=self._headers(),
            method=method,
        )

        try:
            opener = urllib.request.build_opener(_NoRedirect(), transport)
            with opener.open(req, timeout=transport.remaining()) as resp:
                content = bytearray()
                while True:
                    transport.prepare_read()
                    chunk = resp.read1(min(65536, MAX_RESPONSE_BYTES + 1 - len(content)))
                    transport.remaining()
                    if not chunk:
                        break
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise ValueError("fiscal_provider_response_size_invalid")
                    if isinstance(resp, http.client.HTTPResponse) and resp.isclosed():
                        break
                if isinstance(resp, http.client.HTTPResponse) and resp.length not in {None, 0}:
                    raise ValueError("fiscal_provider_response_incomplete")
                resp_bytes = bytes(content)
                transport.remaining()
                if len(resp_bytes) > MAX_RESPONSE_BYTES:
                    raise ValueError("fiscal_provider_response_size_invalid")
                result = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
                if not isinstance(result, dict):
                    raise ValueError("fiscal_provider_response_invalid")
                transport.remaining()
                return result
        except urllib.error.HTTPError as e:
            logger.warning("Facturapi HTTP failure status=%s", e.code)
            e.close()
            raise RuntimeError("fiscal_provider_request_failed") from None
        except Exception as e:
            logger.warning("Facturapi transport failure type=%s", type(e).__name__)
            raise RuntimeError("fiscal_provider_request_failed") from None
        finally:
            transport.finish()

    def _mock_response(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Deterministic sandbox / mock generator for local development and tests."""
        import uuid

        mock_id = f"facturapi-{uuid.uuid4().hex[:12]}"
        mock_uuid = str(uuid.uuid4()).upper()

        if "/receipts" in endpoint and method == "POST":
            domain = "demo"
            return {
                "id": mock_id,
                "created_at": "2026-08-31T20:00:00.000Z",
                "status": "open",
                "total": data.get("total", 100.0) if data else 100.0,
                "key": f"KEY-{uuid.uuid4().hex[:6].upper()}",
                "self_invoice_url": f"https://factura.space/{domain}/self-invoice/{mock_id}",
            }

        if "/invoices" in endpoint and method == "POST":
            return {
                "id": mock_id,
                "created_at": "2026-08-31T20:00:00.000Z",
                "status": "valid",
                "uuid": mock_uuid,
                "folio_number": data.get("folio_number", 101) if data else 101,
                "series": data.get("series", "F") if data else "F",
                "total": data.get("total", 250.0) if data else 250.0,
                "verification_url": f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?id={mock_uuid}",
                "customer": data.get("customer", {}) if data else {},
                "cancellation_status": "none",
            }

        if "/cancel" in endpoint:
            return {
                "id": mock_id,
                "status": "canceled",
                "cancellation_status": "accepted",
            }

        if "/test" in endpoint or "/organizations/me" in endpoint:
            return {
                "status": "ok",
                "legal_name": "RESTAURANTE KIWI SA DE CV",
                "rfc": "KIW210101ABC",
                "is_active": True,
            }

        return {"id": mock_id, "status": "ok"}

    def validate_api_key(self) -> dict[str, Any]:
        return self._request("GET", "/organizations/me")

    def download_invoice(self, invoice_id: str, format: str) -> bytes:
        if format not in {"pdf", "xml"} or not valid_remote_id(invoice_id):
            raise ValueError("fiscal_document_reference_invalid")
        if self.is_mock or not self.api_key:
            raise RuntimeError("fiscal_document_unavailable")
        deadline = time.monotonic() + 20
        connection = http.client.HTTPSConnection("www.facturapi.io", timeout=20)
        watchdog: Timer | None = None

        def remaining() -> float:
            seconds = deadline - time.monotonic()
            if seconds <= 0:
                raise TimeoutError("fiscal_document_deadline")
            return seconds

        try:
            connection.request(
                "GET", f"/v2/invoices/{invoice_id}/{format}", headers=self._headers()
            )
            transport = connection.sock
            if transport is None:
                raise RuntimeError("fiscal_document_transport_missing")

            def expire() -> None:
                try:
                    transport.shutdown(socket.SHUT_RDWR)
                except OSError:
                    return  # Already closed by response EOF or the finalizer.

            watchdog = Timer(remaining(), expire)
            watchdog.daemon = True
            watchdog.start()
            transport.settimeout(remaining())
            response = connection.getresponse()
            if response.status != 200:
                # Redirects are rejected, never followed or returned to a browser.
                raise RuntimeError("fiscal_document_status_invalid")
            media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            accepted = {"application/pdf"} if format == "pdf" else {"application/xml", "text/xml"}
            if media_type not in accepted:
                raise RuntimeError("fiscal_document_media_invalid")
            content = bytearray()
            while True:
                transport.settimeout(remaining())
                chunk = response.read1(min(65536, MAX_DOCUMENT_BYTES + 1 - len(content)))
                remaining()
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > MAX_DOCUMENT_BYTES:
                    raise RuntimeError("fiscal_document_size_invalid")
                if response.isclosed():
                    break
            if isinstance(response, http.client.HTTPResponse) and response.length not in {None, 0}:
                raise RuntimeError("fiscal_document_incomplete")
            if not content:
                raise RuntimeError("fiscal_document_size_invalid")
            return bytes(content)
        except Exception as exc:
            logger.warning("Fiscal document transport failure type=%s", type(exc).__name__)
            raise RuntimeError("fiscal_document_transport_failed") from None
        finally:
            if watchdog is not None:
                watchdog.cancel()
            connection.close()

    def create_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/receipts", payload)

    def create_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/invoices", payload)

    def cancel_invoice(
        self, invoice_id: str, motive: str = "02", substitution_id: str | None = None
    ) -> dict[str, Any]:
        params = f"?motive={motive}"
        if substitution_id:
            params += f"&substitution={substitution_id}"
        return self._request("DELETE", f"/invoices/{invoice_id}{params}")

    def send_email(self, invoice_id: str, email: str) -> dict[str, Any]:
        return self._request("POST", f"/invoices/{invoice_id}/email", {"email": email})
