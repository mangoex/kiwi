# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-fiscal-document-transport-v1
"""Loopback-only slow-drip transport checks; never accesses a PAC."""

import time
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from restaurant_os.invoicing.facturapi_client import FacturapiClient


@pytest.mark.parametrize("mode", ["body", "headers"])
def test_twenty_second_limit_is_total_not_reset_per_received_chunk(monkeypatch, mode):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            try:
                if mode == "body":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", "11")
                    self.end_headers()
                    for _ in range(11):
                        time.sleep(2)
                        self.wfile.write(b"x")
                        self.wfile.flush()
                else:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\n")
                    self.wfile.flush()
                    for _ in range(11):
                        time.sleep(2)
                        self.wfile.write(b"X-Slow: x\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"Content-Length: 1\r\n\r\nx")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def loopback_connection(host, timeout):
        assert host == "www.facturapi.io"
        assert 0 < timeout <= 20
        return HTTPConnection("127.0.0.1", server.server_address[1], timeout=timeout)

    monkeypatch.setattr(
        "restaurant_os.invoicing.facturapi_client.http.client.HTTPSConnection", loopback_connection
    )
    started = time.monotonic()
    try:
        with pytest.raises(RuntimeError, match="fiscal_document_transport_failed"):
            FacturapiClient(api_key="synthetic-loopback-key").download_invoice("remote-safe", "pdf")
    finally:
        transport_elapsed = time.monotonic() - started
        server.shutdown()
        server.server_close()
        thread.join(3)
    assert transport_elapsed < 21.5, {
        "transport_elapsed": transport_elapsed,
        "including_fixture_cleanup": time.monotonic() - started,
    }
