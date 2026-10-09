"""Fail CI if any collected mandatory PostgreSQL case did not actually pass."""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.etree import ElementTree

MODULES = (
    "cash_ledger",
    "purchase_workspace",
    "operating_expenses",
    "system_remediation",
)
PATHS = tuple(f"apps/api/tests/test_{name}_postgres.py" for name in MODULES)


def verify(collection: Path, junit: Path) -> dict[str, int]:
    expected: dict[tuple[str, str], str] = {}
    counts = dict.fromkeys(PATHS, 0)
    for line in collection.read_text(encoding="utf-8-sig").splitlines():
        path, separator, name = line.strip().replace("\\", "/").partition("::")
        if separator and path in PATHS:
            expected[(path[:-3].replace("/", "."), name)] = path
            counts[path] += 1
    if any(count == 0 for count in counts.values()):
        raise RuntimeError("Mandatory PostgreSQL collection omits a required suite")
    cases: dict[tuple[str, str], list[ElementTree.Element]] = {}
    for case in ElementTree.parse(junit).iter("testcase"):
        identity = (case.get("classname", ""), case.get("name", ""))
        cases.setdefault(identity, []).append(case)
    for identity in expected:
        actual = cases.get(identity, [])
        if len(actual) != 1 or any(
            actual[0].find(tag) is not None for tag in ("skipped", "failure", "error")
        ):
            raise RuntimeError(f"Mandatory PostgreSQL case did not pass: {identity}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    print(verify(args.collection, args.junit))


if __name__ == "__main__":
    main()
