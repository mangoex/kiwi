"""Independent local TLS refutations; synthetic cert/key, no provider or database."""

import datetime
import ipaddress
import socket
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from restaurant_os.invoicing import facturapi_client as transport


@pytest.mark.parametrize(
    "mode",
    [
        "fast",
        "headers",
        "body",
        "phasebody",
        "post_write",
        "redirect",
        "untrusted",
        "hostname",
        "truncated",
        "chunked",
        "no_length",
        "http_error",
    ],
)
def test_real_tls_deadline_and_fail_closed(monkeypatch, tmp_path, caplog, mode):
    marker = "synthetic-sensitive-local-tls-key"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    certificate_host = "synthetic-other.invalid" if mode == "hostname" else "www.facturapi.io"
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, certificate_host)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(certificate_host), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_file, key_file = tmp_path / "local-cert.pem", tmp_path / "local-key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    requests, sockets, timers, connections = [], [], [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append(
                (
                    self.path,
                    self.headers.get("Authorization"),
                    self.connection.selected_alpn_protocol(),
                )
            )
            try:
                if mode == "headers":
                    self.wfile.write(b"HTTP/1.0 200 OK\r\n")
                    self.wfile.flush()
                    for _ in range(20):
                        time.sleep(0.2)
                        self.wfile.write(b"X-Slow: x\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"Content-Length: 2\r\n\r\n{}")
                elif mode in {"body", "phasebody", "no_length", "chunked"}:
                    if mode == "phasebody":
                        time.sleep(0.6)
                    self.send_response(200)
                    if mode == "chunked":
                        self.send_header("Transfer-Encoding", "chunked")
                    elif mode != "no_length":
                        self.send_header("Content-Length", "29")
                    self.end_headers()
                    self.wfile.write(b'7\r\n{"id":"\r\n' if mode == "chunked" else b'{"id":"')
                    self.wfile.flush()
                    for _ in range(20):
                        time.sleep(0.2)
                        self.wfile.write(b"1\r\nx\r\n" if mode == "chunked" else b"x")
                        self.wfile.flush()
                    self.wfile.write(b'2\r\n"}\r\n0\r\n\r\n' if mode == "chunked" else b'"}')
                elif mode == "http_error":
                    self.send_response(400)
                    self.send_header("Content-Length", str(len(marker)))
                    self.end_headers()
                    self.wfile.write(marker.encode())
                elif mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "https://synthetic-attacker.invalid/private")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-Length", "100" if mode == "truncated" else "2")
                    self.end_headers()
                    self.wfile.write(b"{}")
                self.wfile.flush()
            except (OSError, ValueError):
                pass

        def do_POST(self):
            requests.append(
                (
                    self.path,
                    self.headers.get("Authorization"),
                    self.connection.selected_alpn_protocol(),
                )
            )
            # No consumption of the submitted body: exercise blocked TLS sendall.
            time.sleep(3)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    context.set_alpn_protocols(["http/1.1"])
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_connect = socket.create_connection
    original_context = ssl.create_default_context
    original_init = transport._DeadlineHTTPSHandler.__init__
    original_timer = transport.Timer
    original_connection_init = transport._DeadlineHTTPSConnection.__init__

    def mapped_connect(address, *args, **kwargs):
        assert address == ("www.facturapi.io", 443), address
        result = original_connect(("127.0.0.1", server.server_address[1]), *args, **kwargs)
        sockets.append(result)
        return result

    def short_budget(self, deadline):
        original_init(self, time.monotonic() + 1)

    def tracked_timer(*args, **kwargs):
        result = original_timer(*args, **kwargs)
        timers.append(result)
        return result

    def tracked_connection(self, *args, **kwargs):
        original_connection_init(self, *args, **kwargs)
        connections.append(self)

    monkeypatch.setattr(socket, "create_connection", mapped_connect)
    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda: original_context(cafile=None if mode == "untrusted" else str(cert_file)),
    )
    monkeypatch.setattr(transport._DeadlineHTTPSHandler, "__init__", short_budget)
    monkeypatch.setattr(transport._DeadlineHTTPSConnection, "__init__", tracked_connection)
    monkeypatch.setattr(transport, "Timer", tracked_timer)
    monkeypatch.setattr("urllib.request.getproxies", lambda: {})
    started = time.monotonic()
    try:
        if mode == "fast":
            assert transport.FacturapiClient(api_key=marker).validate_api_key() == {}
        else:
            with pytest.raises(RuntimeError, match="fiscal_provider_request_failed"):
                client = transport.FacturapiClient(api_key=marker)
                if mode == "post_write":
                    client._request("POST", "/invoices", {"blob": "x" * (16 * 1024 * 1024)})
                else:
                    client.validate_api_key()
    finally:
        elapsed = time.monotonic() - started
        server.shutdown()
        server.server_close()
        thread.join(2)
    # A fresh 1s body budget after .6s headers would exceed this 1.4s ceiling.
    ceiling = 1.4 if mode == "phasebody" else 1.8
    assert elapsed < ceiling, {"mode": mode, "elapsed": elapsed}
    assert len(sockets) == 1
    assert requests == (
        []
        if mode in {"untrusted", "hostname"}
        else [
            (
                "/v2/invoices" if mode == "post_write" else "/v2/organizations/me",
                f"Bearer {marker}",
                "http/1.1",
            )
        ]
    )
    for timer in timers:
        timer.join(0.2)
        assert not timer.is_alive()
    for connection in connections:
        assert connection.sock is None
        if connection.transport is not None:
            assert connection.transport.fileno() == -1
    assert marker not in caplog.text
