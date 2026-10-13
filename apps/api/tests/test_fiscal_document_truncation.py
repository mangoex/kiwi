# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-fiscal-document-truncation-v1
"""Out-of-increment parity finding requested during JSON deadline audit."""

from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from restaurant_os.invoicing.facturapi_client import FacturapiClient


def test_document_rejects_early_eof_with_unfulfilled_content_length(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"%PDF-1.4\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def loopback_connection(host, timeout):
        assert host == "www.facturapi.io"
        return HTTPConnection("127.0.0.1", server.server_address[1], timeout=timeout)

    monkeypatch.setattr(
        "restaurant_os.invoicing.facturapi_client.http.client.HTTPSConnection", loopback_connection
    )
    try:
        with pytest.raises(RuntimeError, match="fiscal_document_transport_failed"):
            FacturapiClient(api_key="synthetic-loopback-key").download_invoice("remote-safe", "pdf")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
