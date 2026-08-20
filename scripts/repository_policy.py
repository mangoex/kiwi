from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SENSITIVE_SIGNATURE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|token|secret|password|private[_-]?key)"
    r"\s*[=:]\s*[^\s]+"
)
SOURCE_LITERAL_SIGNATURE = re.compile(
    r"(?i)(?:['\"]\s*)?\b(?:api[_-]?key|access[_-]?token|token|secret|password|private[_-]?key)\b"
    r"(?:\s*['\"])?\s*[=:]\s*['\"][^'\"\r\n]{8,}['\"]"
)
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".yml", ".yaml", ".json"}
PROVENANCE = re.compile(r"^SEC001-SYNTHETIC-FIXTURE provenance=([A-Za-z0-9._-]+)$")


def _load_allowlist(root: Path) -> dict[str, dict[str, str]]:
    allowlist_path = root / "scripts" / "repository_policy_allowlist.json"
    if not allowlist_path.is_file():
        return {}
    raw: dict[str, Any] = json.loads(allowlist_path.read_text())
    entries = raw.get("synthetic_allowlist", [])
    if not isinstance(entries, list):
        return {}
    return {
        entry["path"]: {"sha256": entry["sha256"], "provenance": entry["provenance"]}
        for entry in entries
        if isinstance(entry, dict)
        and all(isinstance(entry.get(key), str) for key in ("path", "sha256", "provenance"))
    }


def _is_exact_allowlisted(path: Path, relative: str, entry: dict[str, str] | None) -> bool:
    if entry is None:
        return False
    content = path.read_bytes()
    try:
        first_line = content.decode("utf-8").splitlines()[0]
    except (UnicodeDecodeError, IndexError):
        return False
    provenance = PROVENANCE.match(first_line)
    return bool(
        provenance
        and provenance.group(1) == entry["provenance"]
        and hashlib.sha256(content).hexdigest() == entry["sha256"]
        and relative == path.as_posix()[-len(relative) :]
    )


def _finding(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return "database"
    if suffix in {".bak", ".backup"}:
        return "backup"
    content = path.read_text(errors="ignore")
    # Test credentials are fixtures, not repository configuration or deployable source.
    if suffix in SOURCE_SUFFIXES:
        if path.name.startswith("test_"):
            return None
        signature = SOURCE_LITERAL_SIGNATURE
    else:
        signature = SENSITIVE_SIGNATURE
    if signature.search(content):
        return "sensitive_signature"
    return None


def main(root: Path) -> int:
    allowlist = _load_allowlist(root)
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        kind = _finding(path)
        if kind is not None and not _is_exact_allowlisted(path, relative, allowlist.get(relative)):
            findings.append(f"{relative}|{kind}")
    print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
