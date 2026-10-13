# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-fiscal-exact-json-tests-v1
"""Exact synthetic JSON requests; only loopback, no issuer/database effects."""

import json
import socket
from decimal import Decimal, Inexact, localcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from restaurant_os.invoicing import facturapi_client as transport
from restaurant_os.invoicing import json_codec


@pytest.mark.parametrize("operation", ["invoice", "receipt"])
def test_decimal_payload_reaches_http_without_float_or_string_coercion(monkeypatch, operation):
    captured = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            captured.append((self.path, self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Length", "21")
            self.end_headers()
            self.wfile.write(b'{"id":"synthetic-id"}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def loopback_connect(self):
        assert self.host == "www.facturapi.io" and self.port == 443
        self.sock = socket.create_connection(("127.0.0.1", server.server_address[1]), self.timeout)
        self._arm_deadline()

    monkeypatch.setattr(transport.http.client.HTTPSConnection, "connect", loopback_connect)
    monkeypatch.setattr("urllib.request.getproxies", lambda: {})
    payload = {
        "items": [
            {
                "quantity": Decimal("1.000001"),
                "product": {
                    "price": Decimal("19.99"),
                    "taxes": [{"rate": Decimal("0.160000")}],
                    "description": 'Café "á" 𐐷 {"price":1}',
                },
            }
        ],
        "large": Decimal("21474836.47"),
        "fraction": Decimal("0.005000"),
        "negative": Decimal("-0.000001"),
        "flag": True,
        "nullable": None,
        "number_text": "19.99",
    }
    try:
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            client = transport.FacturapiClient(api_key="synthetic-explicit-key")
            method = client.create_invoice if operation == "invoice" else client.create_receipt
            assert method(payload) == {"id": "synthetic-id"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
    assert len(captured) == 1
    path, body = captured[0]
    assert path == "/v2/" + ("invoices" if operation == "invoice" else "receipts")
    decoded = json.loads(body, parse_float=Decimal)
    assert decoded == payload
    assert isinstance(decoded["items"][0]["product"]["price"], Decimal)
    assert b'"price":19.99' in body and b'"rate":0.160000' in body
    assert decoded["number_text"] == "19.99"


@pytest.mark.parametrize(
    "bad",
    [
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        float("nan"),
        float("inf"),
        object(),
        Decimal("1E129"),
        Decimal("1E-129"),
        Decimal("9" * 129),
        10**129,
        {"key": {1: "private-marker"}},
        "private-marker" + chr(0xD800),
    ],
)
@pytest.mark.parametrize("mock", [False, True])
def test_invalid_payload_fails_before_connection_without_private_data(
    monkeypatch, caplog, bad, mock
):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid payload reached provider setup")

    monkeypatch.setattr(transport.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(transport._DeadlineHTTPSHandler, "__init__", forbidden)
    with pytest.raises(RuntimeError, match="^fiscal_provider_payload_invalid$") as denied:
        transport.FacturapiClient(api_key="synthetic-explicit-key", is_mock=mock).create_invoice(
            {"private-marker": bad}
        )
    assert denied.value.__suppress_context__
    assert "private-marker" not in str(denied.value) + caplog.text


@pytest.mark.parametrize("structure", ["list_cycle", "dict_cycle", "deep"])
def test_structural_invalidity_rejects_before_network(monkeypatch, structure):
    value = []
    if structure == "list_cycle":
        value.append(value)
    elif structure == "dict_cycle":
        value = {}
        value["private-marker"] = value
    else:
        for _ in range(66):
            value = [value]
    monkeypatch.setattr(
        transport._DeadlineHTTPSHandler,
        "__init__",
        lambda *a, **kw: pytest.fail("structure reached network"),
    )
    with pytest.raises(RuntimeError, match="^fiscal_provider_payload_invalid$"):
        transport.FacturapiClient(api_key="synthetic-explicit-key").create_invoice({"value": value})


def test_utf8_body_limit_counts_bytes_and_accepts_exact_boundary(monkeypatch):
    expected = b'{"text":"' + "é".encode() + b'"}'
    monkeypatch.setattr(json_codec, "MAX_REQUEST_BYTES", len(expected))
    assert json_codec.encode_json({"text": "é"}) == expected
    with pytest.raises(ValueError, match="size_invalid"):
        json_codec.encode_json({"text": "éé"})


def test_shared_containers_scalars_and_legacy_floats_remain_valid():
    shared = {"price": Decimal("19.99")}
    payload = {
        "items": [shared, shared],
        "tuple": (0, -1, False),
        "rate": 0.16,
        "small": Decimal("1E-128"),
        "large": Decimal("1E128"),
    }
    decoded = json.loads(json_codec.encode_json(payload), parse_float=Decimal)
    assert decoded["items"] == [shared, shared]
    assert decoded["tuple"] == [0, -1, False]
    assert decoded["rate"] == Decimal("0.16")
    assert decoded["small"] == payload["small"] and decoded["large"] == payload["large"]


def test_number_digit_boundaries_are_numeric():
    value = Decimal("9" * 128)
    result = json.loads(
        json_codec.encode_json({"integer": 10**127, "decimal": value}),
        parse_float=Decimal,
        parse_int=Decimal,
    )
    assert result == {"integer": Decimal(10**127), "decimal": value}


def test_chunked_escape_matches_standard_json_across_unicode_control_boundaries():
    value = ('"\\' + chr(0) + "é𐐷\n") * 2000
    expected = json.dumps({"text": value}, ensure_ascii=False, separators=(",", ":")).encode()
    assert json_codec.encode_json({"text": value}) == expected
