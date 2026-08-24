from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SENSITIVE_SIGNATURE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|token|secret(?:[_-]?key)?|password|private[_-]?key)"
    r"\s*[=:]\s*[^\s]+"
)
SOURCE_LITERAL_SIGNATURE = re.compile(
    r"(?i)(?:['\"]\s*)?\b(?:api[_-]?key|access[_-]?token|token|secret(?:[_-]?key)?|password|private[_-]?key)\b"
    r"(?:\s*['\"])?\s*[=:]\s*['\"][^'\"\r\n]{8,}['\"]"
)
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".yml", ".yaml", ".json"}
PROVENANCE = re.compile(
    r"^(?:(?:#|//)\s*)?SEC001-SYNTHETIC-FIXTURE provenance=([A-Za-z0-9._-]+)$"
    r"|^<!--\s*SEC001-SYNTHETIC-FIXTURE provenance=([A-Za-z0-9._-]+)\s*-->$"
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


def _is_exact_allowlisted(path: Path, entry: dict[str, str] | None) -> bool:
    if entry is None:
        return False
    try:
        content = path.read_bytes()
        first_line = content.decode("utf-8").splitlines()[0]
    except (UnicodeDecodeError, IndexError):
        return False
    provenance = PROVENANCE.match(first_line)
    normalized_content = content.replace(b"\r\n", b"\n")
    return bool(
        provenance
        and (provenance.group(1) or provenance.group(2)) == entry["provenance"]
        and hashlib.sha256(normalized_content).hexdigest() == entry["sha256"]
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
    signature = (
        SENSITIVE_SIGNATURE
        if suffix in {".yml", ".yaml"}
        else SOURCE_LITERAL_SIGNATURE
        if suffix in SOURCE_SUFFIXES
        else SENSITIVE_SIGNATURE
    )
    if signature.search(content):
        return "sensitive_signature"
    return None


IGNORED_PARTS = {
    ".git",
    "node_modules",
    "dist",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    "build",
}


def _candidate_paths(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            candidate
            for candidate in root.rglob("*")
            if candidate.is_file()
            and not any(part in IGNORED_PARTS for part in candidate.parts)
        )
    return sorted(root / item.decode() for item in result.stdout.split(b"\0") if item)


def main(root: Path) -> int:
    allowlist = _load_allowlist(root)
    findings: list[str] = []
    for path in _candidate_paths(root):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        kind = _finding(path)
        if kind is not None and not _is_exact_allowlisted(path, allowlist.get(relative)):
            findings.append(f"{relative}|{kind}")
    print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
