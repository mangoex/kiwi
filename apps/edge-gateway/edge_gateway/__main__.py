from __future__ import annotations

import argparse

import uvicorn

from edge_gateway.runtime import create_gateway_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="restaurantos-edge")
    subcommands = parser.add_subparsers(dest="command", required=True)
    serve = subcommands.add_parser("serve")
    serve.add_argument("--config", required=True)
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.command != "serve" or not 1 <= args.port <= 65535:
        return 2
    runtime = create_gateway_runtime(args.config)
    try:
        uvicorn.run(runtime.app, host="127.0.0.1", port=args.port)
    finally:
        runtime.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
