"""Synthetic loopback-only JSON deadline regression; no external provider calls."""

import json
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from restaurant_os.invoicing import facturapi_client as transport


@pytest.mark.parametrize("mode", ["headers", "body", "fast"])
def test_json_transport_budget_is_total_and_does_not_retry(monkeypatch, caplog, mode):
    requests = []
    marker = "synthetic-private-json-key"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append((self.path, self.headers.get("Authorization")))
            try:
                if mode == "headers":
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n")
                    self.wfile.flush()
                    for _ in range(11):
                        time.sleep(2)
                        self.wfile.write(b"X-Slow: x\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"Content-Length: 2\r\n\r\n{}")
                    self.wfile.flush()
                elif mode == "body":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", "13")
                    self.end_headers()
                    self.wfile.write(b'{"id":"')
                    self.wfile.flush()
                    for _ in range(4):
                        time.sleep(5.5)
                        self.wfile.write(b"x")
                        self.wfile.flush()
                    self.wfile.write(b'"}')
                    self.wfile.flush()
                else:
                    body = json.dumps({"id": "synthetic-org", "legal": {}}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Redirect only the test's TCP/TLS connection bootstrap to our plaintext loopback.
    # All production request/response/deadline and socket shutdown code still runs.
    def loopback_connect(self):
        assert self.host == "www.facturapi.io" and self.port == 443
        assert 0 < self.timeout <= 20
        self.sock = socket.create_connection(("127.0.0.1", server.server_address[1]), self.timeout)
        arm = getattr(self, "_arm_deadline", None)
        if arm is not None:
            arm()

    monkeypatch.setattr(transport.http.client.HTTPSConnection, "connect", loopback_connect)
    monkeypatch.setattr("urllib.request.getproxies", lambda: {})
    started = time.monotonic()
    try:
        if mode == "fast":
            assert transport.FacturapiClient(api_key=marker).validate_api_key() == {
                "id": "synthetic-org",
                "legal": {},
            }
        else:
            with pytest.raises(RuntimeError, match="fiscal_provider_request_failed"):
                transport.FacturapiClient(api_key=marker).validate_api_key()
    finally:
        elapsed = time.monotonic() - started
        server.shutdown()
        server.server_close()
        thread.join(3)
    assert elapsed < 21.5, {"elapsed": elapsed, "mode": mode}
    assert requests == [("/v2/organizations/me", f"Bearer {marker}")]
    assert marker not in caplog.text
