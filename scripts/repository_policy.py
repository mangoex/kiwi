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
PROVENANCE = re.compile(
    r"^(?:(?:#|//)\s*)?SEC001-SYNTHETIC-FIXTURE provenance=([A-Za-z0-9._-]+)$"
)
PRIVATE_KEY_HEADER = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)
SQLITE_SIDECAR = re.compile(r"(?i)\.(?:db|sqlite|sqlite3)-(?:wal|shm|journal)$")


def _load_allowlist(root: Path) -> dict[str, dict[str, str]]:
    allowlist_path = root / "scripts" / "repository_policy_allowlist.json"
    if not allowlist_path.is_file():
        return {}
    raw: dict[str, Any] = json.loads(allowlist_path.read_text(encoding="utf-8"))
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
    try:
        text = path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0]
    except (UnicodeDecodeError, IndexError):
        return False
    provenance = PROVENANCE.match(first_line)
    raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    norm_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return bool(
        provenance
        and provenance.group(1) == entry["provenance"]
        and (raw_sha == entry["sha256"] or norm_sha == entry["sha256"])
        and relative == path.as_posix()[-len(relative) :]
    )


def _finding(path: Path) -> str | None:
    suffix = path.suffix.lower()
    lower_name = path.name.lower()
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return "database"
    if SQLITE_SIDECAR.search(lower_name):
        return "database_sidecar"
    if suffix in {".sql", ".dump", ".dmp"} or lower_name.endswith(
        (".sql.gz", ".dump.gz")
    ):
        return "database_export"
    if suffix in {".bak", ".backup"}:
        return "backup"
    content = path.read_text(errors="ignore")
    if PRIVATE_KEY_HEADER.search(content):
        return "private_key"
    if suffix in SOURCE_SUFFIXES:
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
