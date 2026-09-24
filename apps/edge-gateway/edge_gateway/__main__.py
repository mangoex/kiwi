from __future__ import annotations

import argparse
import ipaddress
import os
import ssl
from pathlib import Path

import uvicorn

from edge_gateway.order_runtime import (
    acknowledge_orders_catalog,
    handoff_orders,
    orders_status,
    prepare_orders,
    recover_orders,
    renew_orders,
)
from edge_gateway.runtime import create_gateway_runtime


def validate_listener(host: str, certificate: str | None, key: str | None) -> dict[str, str]:
    loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    if not certificate and not key and loopback:
        return {}
    if not certificate or not key:
        raise ValueError("LAN listener requires explicit TLS certificate and key")
    certificate_path, key_path = Path(certificate), Path(key)
    for path in (certificate_path, key_path):
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.is_file()
            or path.stat().st_nlink != 1
        ):
            raise ValueError("TLS paths must be absolute regular files")
    if os.name != "nt" and key_path.stat().st_mode & 0o077:
        raise ValueError("TLS private key permissions are unsafe")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(certificate_path), str(key_path))
    return {"ssl_certfile": str(certificate_path), "ssl_keyfile": str(key_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="restaurantos-edge")
    subcommands = parser.add_subparsers(dest="command", required=True)
    serve = subcommands.add_parser("serve")
    serve.add_argument("--config", required=True)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--tls-certificate")
    serve.add_argument("--tls-key")
    prepare_orders_command = subcommands.add_parser("prepare-orders")
    prepare_orders_command.add_argument("--config", required=True)
    handoff_orders_command = subcommands.add_parser("handoff-orders")
    handoff_orders_command.add_argument("--config", required=True)
    renew_orders_command = subcommands.add_parser("renew-orders")
    renew_orders_command.add_argument("--config", required=True)
    recover_orders_command = subcommands.add_parser("recover-orders")
    recover_orders_command.add_argument("--config", required=True)
    orders_status_command = subcommands.add_parser("orders-status")
    orders_status_command.add_argument("--config", required=True)
    acknowledge_command = subcommands.add_parser("acknowledge-catalog")
    acknowledge_command.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare-orders":
        try:
            prepare_orders(args.config)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print("Initial order bundle prepared.")
        return 0
    lifecycle_commands = {
        "acknowledge-catalog": acknowledge_orders_catalog,
        "handoff-orders": handoff_orders,
        "renew-orders": renew_orders,
        "recover-orders": recover_orders,
        "orders-status": orders_status,
    }
    if args.command in lifecycle_commands:
        try:
            result = lifecycle_commands[args.command](args.config)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(result["status"])
        return 0
    if args.command != "serve" or not 1 <= args.port <= 65535:
        return 2
    try:
        tls_options = validate_listener(args.host, args.tls_certificate, args.tls_key)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    runtime = create_gateway_runtime(args.config)
    try:
        uvicorn.run(
            runtime.app,
            host=args.host,
            port=args.port,
            ssl_certfile=tls_options.get("ssl_certfile"),
            ssl_keyfile=tls_options.get("ssl_keyfile"),
        )
    finally:
        runtime.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
