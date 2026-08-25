"""Strict, non-secret configuration for the loopback edge process."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import UUID

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


@dataclass(frozen=True)
class GatewayRuntimeConfig:
    organization_id: str
    branch_id: str
    source_device_id: str
    runtime_root: Path
    central_url: str
    pos_origin: str
    sqlite_path: Path
    public_keyring_path: Path
    credential_path: Path
    log_path: Path


def load_runtime_config(path: str | Path) -> GatewayRuntimeConfig:
    config_path = Path(path)
    if not config_path.is_absolute():
        raise ValueError("gateway config path must be absolute")
    try:
        config_stat = config_path.stat()
        if config_path.is_symlink() or not stat.S_ISREG(config_stat.st_mode):
            raise OSError("config must be a regular file")
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("gateway config is unreadable") from exc
    required = {
        "organization_id",
        "branch_id",
        "source_device_id",
        "runtime_root",
        "central_url",
        "pos_origin",
        "sqlite_path",
        "public_keyring_path",
        "credential_path",
        "log_path",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("gateway config fields are invalid")
    if any(not isinstance(raw[field], str) or not raw[field] for field in required):
        raise ValueError("gateway config values are invalid")
    for field in ("organization_id", "branch_id", "source_device_id"):
        if not _canonical_uuid(raw[field]):
            raise ValueError(f"gateway config {field} must be a canonical UUID")
    _validate_central_url(raw["central_url"])
    pos_origin = _normalize_pos_origin(raw["pos_origin"])
    runtime_root = _absolute_directory(raw["runtime_root"], "runtime root")
    sqlite_path = _absolute_writable_path(raw["sqlite_path"], "sqlite", runtime_root)
    public_keyring_path = _absolute_readable_path(
        raw["public_keyring_path"], "public keyring", runtime_root
    )
    credential_path = _absolute_readable_path(
        raw["credential_path"], "credential", runtime_root
    )
    log_path = _absolute_writable_path(raw["log_path"], "log", runtime_root)
    _require_distinct_paths(
        (config_path, sqlite_path, public_keyring_path, credential_path, log_path)
    )
    return GatewayRuntimeConfig(
        organization_id=raw["organization_id"],
        branch_id=raw["branch_id"],
        source_device_id=raw["source_device_id"],
        runtime_root=runtime_root,
        central_url=raw["central_url"].rstrip("/"),
        pos_origin=pos_origin,
        sqlite_path=sqlite_path,
        public_keyring_path=public_keyring_path,
        credential_path=credential_path,
        log_path=log_path,
    )


def load_public_keyring(path: Path) -> dict[str, Ed25519PublicKey]:
    from edge_gateway.grants import parse_public_keyring

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("gateway public keyring is unreadable") from exc
    if not isinstance(raw, dict) or set(raw) != {"keys"} or not isinstance(raw["keys"], dict):
        raise ValueError("gateway public keyring is invalid")
    return parse_public_keyring(raw["keys"])


def load_gateway_credential(
    path: Path,
    *,
    platform_name: str | None = None,
    runtime_root: Path | None = None,
) -> str:
    try:
        if not path.is_file() or path.is_symlink():
            raise OSError("credential must be a regular file")
        if runtime_root is not None and not _is_within(path, runtime_root):
            raise OSError("credential is outside runtime root")
        credential = path.read_text(encoding="utf-8").strip()
        mode = path.stat().st_mode & 0o777
    except OSError as exc:
        raise ValueError("gateway credential is unreadable") from exc
    if not credential or ((platform_name or os.name) != "nt" and mode & 0o077):
        raise ValueError("gateway credential permissions are unsafe")
    return credential


def _canonical_uuid(value: str) -> bool:
    if not _UUID.fullmatch(value):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _validate_central_url(value: str) -> None:
    parsed = urlsplit(value)
    invalid = (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    )
    if not invalid and parsed.scheme == "https" and parsed.hostname:
        return
    if not invalid and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return
    raise ValueError("gateway central URL must use TLS outside localhost")


def _normalize_pos_origin(value: str) -> str:
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("gateway POS origin is invalid") from exc
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    if (
        not hostname
        or not hostname.isascii()
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or "*" in value
        or not (
            scheme == "https"
            or (scheme == "http" and hostname in {"localhost", "127.0.0.1"})
        )
    ):
        raise ValueError("gateway POS origin is invalid")
    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    authority_host = f"[{hostname}]" if ":" in hostname else hostname
    authority = authority_host if port is None or default_port else f"{authority_host}:{port}"
    return f"{scheme}://{authority}"


def _absolute_directory(value: str, label: str) -> Path:
    path = Path(value)
    try:
        file_stat = path.stat()
    except OSError as exc:
        raise ValueError(f"gateway {label} path is invalid") from exc
    unsafe_posix = os.name != "nt" and (
        file_stat.st_uid != os.geteuid() or file_stat.st_mode & 0o077
    )
    if (
        not path.is_absolute()
        or not stat.S_ISDIR(file_stat.st_mode)
        or path.is_symlink()
        or unsafe_posix
    ):
        raise ValueError(f"gateway {label} path is invalid")
    return path.resolve()


def _absolute_writable_path(value: str, label: str, runtime_root: Path) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or not _is_within(path, runtime_root)
        or path.is_symlink()
        or (path.exists() and not path.is_file())
        or not path.parent.is_dir()
        or not os.access(path.parent, os.W_OK)
    ):
        raise ValueError(f"gateway {label} path is not writable")
    return path


def _absolute_readable_path(value: str, label: str, runtime_root: Path) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or not _is_within(path, runtime_root)
        or not path.is_file()
        or path.is_symlink()
        or not os.access(path, os.R_OK)
    ):
        raise ValueError(f"gateway {label} path is not readable")
    return path


def _is_within(path: Path, runtime_root: Path) -> bool:
    try:
        path.resolve().relative_to(runtime_root.resolve())
    except ValueError:
        return False
    return True


def _require_distinct_paths(paths: tuple[Path, ...]) -> None:
    resolved = [path.resolve() for path in paths]
    identities: list[tuple[int, int]] = []
    for path in paths:
        try:
            file_stat = path.stat()
        except FileNotFoundError:
            continue
        identities.append((file_stat.st_dev, file_stat.st_ino))
    if len(set(resolved)) != len(resolved) or len(set(identities)) != len(identities):
        raise ValueError("gateway runtime paths must be distinct")
