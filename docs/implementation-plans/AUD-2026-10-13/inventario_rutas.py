"""Static route inventory for W01; hints require domain review, never certify fencing."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

METHODS = {"get", "post", "put", "patch", "delete"}
OPERATIONAL = (
    "/orders", "/payments", "/cash", "/kds", "/print", "/purchases",
    "/purchase-documents", "/production", "/inventory-transfers", "/waste",
    "/physical-count", "/operating-expenses", "/expenses",
)


def inventory(root: Path) -> list[dict[str, object]]:
    path = root / "apps/api/restaurant_os/api.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rows = []
    for function in tree.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = sorted({
            ast.unparse(node.func) for node in ast.walk(function) if isinstance(node, ast.Call)
        })
        arguments = sorted({arg.arg for arg in function.args.args})
        for decorator in function.decorator_list:
            if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in METHODS and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)):
                continue
            router = ast.unparse(decorator.func.value)
            route = decorator.args[0].value
            if router not in {"router", "reconciliation_v2_router"}:
                continue
            rows.append({
                "method": decorator.func.attr.upper(),
                "path": ("/api/v2" if router == "reconciliation_v2_router" else "/api/v1") + route,
                "handler": function.name, "file": str(path.relative_to(root)).replace("\\", "/"),
                "line": function.lineno, "arguments": arguments, "calls": calls,
                "category_hint": "branch_operation" if route.startswith(OPERATIONAL)
                    else "explicit_corporate" if route.startswith("/corporate-purchases")
                    else "review_required",
                "fence_status": "review_required",
            })
    return sorted(rows, key=lambda row: (str(row['path']), str(row['method'])))


def duplicate_registrations(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault((str(row["method"]), str(row["path"])), []).append(row)
    return [
        {"method": method, "path": path, "registrations": entries}
        for (method, path), entries in groups.items() if len(entries) > 1
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = inventory(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"kind": "static_inventory", "runtime_certified": False,
        "scope": "platform api.py; agent/device/sync routers require separate review",
        "duplicate_registrations": duplicate_registrations(rows), "routes": rows},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Inventoried {len(rows)} registrations, {len(duplicate_registrations(rows))} duplicates; "
          "no fencing gate is certified by this output")
