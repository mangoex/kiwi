from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SOURCE_SUFFIXES = {".cjs", ".js", ".jsx", ".mjs", ".py", ".ts", ".tsx"}
VALID_EXCEPTION = re.compile(
    r"quality-ratchet:\s*allow\s*--\s*\S(?:.*\S)?\s*$", re.IGNORECASE
)
HUNK_HEADER = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@")
RULES = (
    (
        "python_type_suppression",
        re.compile(r"#\s*type:\s*ignore(?:\[[^\]]+\])?\b", re.IGNORECASE),
    ),
    (
        "typescript_type_suppression",
        re.compile(r"@ts-(?:ignore|nocheck)\b", re.IGNORECASE),
    ),
    (
        "lint_suppression",
        re.compile(
            r"(?:#\s*noqa\b|"
            r"eslint-disable(?:-next-line|-line)?\b)",  # quality-ratchet: allow -- self detector
            re.IGNORECASE,
        ),
    ),
    (
        "coverage_suppression",
        re.compile(r"#\s*pragma:\s*no\s*cover\b", re.IGNORECASE),
    ),
    (
        "test_disabled",
        re.compile(
            r"(?:@pytest\.mark\.(?:skip|xfail)\b|"
            r"\b(?:describe|it|test)\.skip\s*\(|"
            r"\b(?:xit|xdescribe)\s*\()",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str


def _git_path(header_value: str) -> str | None:
    if header_value == "/dev/null":
        return None
    try:
        values = shlex.split(header_value, posix=True)
    except ValueError:
        return None
    if len(values) != 1:
        return None
    path = values[0]
    return path[2:] if path.startswith("b/") else path


def _supported(path: str | None) -> bool:
    return path is not None and PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES


def analyze_diff(diff: str) -> list[Finding]:
    findings: list[Finding] = []
    current_path: str | None = None
    new_line: int | None = None

    for raw_line in diff.splitlines():
        if raw_line.startswith("+++ "):
            current_path = _git_path(raw_line[4:])
            new_line = None
            continue

        hunk = HUNK_HEADER.match(raw_line)
        if hunk:
            new_line = int(hunk.group(1))
            continue

        if new_line is None or not _supported(current_path):
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            added = raw_line[1:]
            if not VALID_EXCEPTION.search(added):
                for category, pattern in RULES:
                    if pattern.search(added):
                        findings.append(Finding(current_path or "", new_line, category))
            new_line += 1
        elif raw_line.startswith("-") or raw_line.startswith("\\ No newline"):
            continue
        else:
            new_line += 1

    return findings


def format_findings(findings: Sequence[Finding]) -> list[str]:
    return [f"{finding.path}:{finding.line}: {finding.category}" for finding in findings]


def _diff(root: Path, base: str, head: str) -> str | None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--unified=0",
            "--no-ext-diff",
            "--no-renames",
            f"{base}...{head}",
            "--",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reject newly added quality suppressions.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)

    diff = _diff(args.root.resolve(), args.base, args.head)
    if diff is None:
        print(
            f"quality-ratchet: unable to inspect diff {args.base}...{args.head}",
            file=sys.stderr,
        )
        return 2

    findings = analyze_diff(diff)
    if findings:
        print("\n".join(format_findings(findings)))
        return 1

    print("quality-ratchet: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
