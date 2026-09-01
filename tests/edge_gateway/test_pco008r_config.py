"""PCO-008R configuration boundaries that do not require a crypto runtime."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "edge-gateway"))

from edge_gateway.config import load_gateway_credential, load_runtime_config  # noqa: E402
from edge_gateway.outbox import GatewayOutbox, InvalidCommandEnvelope  # noqa: E402
from edge_gateway.runtime_logging import (  # noqa: E402
    close_runtime_logging,
    configure_runtime_logging,
)

IDENTITY = {
    "organization_id": "018f6f73-2d0a-74f0-8f1c-000000000001",
    "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
    "source_device_id": "018f6f73-2d0a-74f0-8f1c-000000000401",
}


def _config(tmp_path: Path, **overrides: str) -> Path:
    keyring = tmp_path / "keyring.json"
    keyring.write_text('{"keys":{"active":"synthetic"}}', encoding="utf-8")
    credential = tmp_path / "gateway.credential"
    credential.write_text("synthetic-device-secret", encoding="utf-8")
    credential.chmod(0o600)
    values = {
        **IDENTITY,
        "runtime_root": str(tmp_path),
        "central_url": "https://central.example",
        "pos_origin": "https://pos.example",
        "sqlite_path": str(tmp_path / "gateway.db"),
        "public_keyring_path": str(keyring),
        "credential_path": str(credential),
        "log_path": str(tmp_path / "gateway.log"),
        **overrides,
    }
    path = tmp_path / "gateway.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_pos_origin_normalizes_a_single_trailing_slash(tmp_path: Path) -> None:
    config = load_runtime_config(_config(tmp_path, pos_origin="http://localhost:3001/"))

    assert config.pos_origin == "http://localhost:3001"

    tls = load_runtime_config(_config(tmp_path, pos_origin="HTTPS://POS.EXAMPLE:443/"))
    assert tls.pos_origin == "https://pos.example"


def test_pos_origin_preserves_ipv6_brackets(tmp_path: Path) -> None:
    config = load_runtime_config(
        _config(tmp_path, pos_origin="https://[2001:DB8::1]:8443/")
    )

    assert config.pos_origin == "https://[2001:db8::1]:8443"


@pytest.mark.parametrize(
    "origin",
    (
        "http://pos.example",
        "https://pos.example/admin",
    ),
)
def test_pos_origin_requires_tls_outside_loopback_and_rejects_paths(
    tmp_path: Path,
    origin: str,
) -> None:
    with pytest.raises(ValueError, match="gateway POS origin is invalid"):
        load_runtime_config(_config(tmp_path, pos_origin=origin))


@pytest.mark.parametrize("field", ("sqlite_path", "log_path"))
def test_writable_runtime_files_reject_existing_symlinks(tmp_path: Path, field: str) -> None:
    protected = tmp_path / "protected.txt"
    protected.write_text("do-not-overwrite", encoding="utf-8")
    redirected = tmp_path / f"{field}.link"
    try:
        redirected.symlink_to(protected)
    except OSError:
        pytest.skip("Symlinks not supported in current environment")

    with pytest.raises(ValueError, match=f"gateway {field.removesuffix('_path')}"):
        load_runtime_config(_config(tmp_path, **{field: str(redirected)}))


def test_runtime_log_is_written_and_closed_without_secret_context(tmp_path: Path) -> None:
    log_path = tmp_path / "gateway.log"
    handler = configure_runtime_logging(log_path)
    assert handler.handler.maxBytes == 5 * 1024 * 1024
    assert handler.handler.backupCount == 3

    import logging

    logging.getLogger("edge_gateway.runtime").info("pco008.runtime_ready")
    close_runtime_logging(handler)
    close_runtime_logging(handler)

    content = log_path.read_text(encoding="utf-8")
    assert "pco008.runtime_ready" in content
    assert "synthetic-device-secret" not in content


def test_config_and_runtime_files_are_absolute_confined_and_regular(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="gateway config path must be absolute"):
        load_runtime_config(Path("gateway.json"))

    outside = tmp_path.parent / "outside-gateway.db"
    with pytest.raises(ValueError, match="gateway sqlite path is not writable"):
        load_runtime_config(_config(tmp_path, sqlite_path=str(outside)))

    keyring = tmp_path / "keyring.json"
    target = tmp_path / "keyring-target.json"
    target.write_text('{"keys":{"active":"synthetic"}}', encoding="utf-8")
    keyring.unlink()
    try:
        keyring.symlink_to(target)
        with pytest.raises(ValueError, match="gateway public keyring path is not readable"):
            load_runtime_config(_config(tmp_path))
    except OSError:
        pass


def test_gateway_credential_requires_private_regular_file(tmp_path: Path) -> None:
    config_path = _config(tmp_path)
    config = load_runtime_config(config_path)
    config.credential_path.chmod(0o644)

    with pytest.raises(ValueError, match="gateway credential permissions are unsafe"):
        load_gateway_credential(
            config.credential_path,
            runtime_root=config.runtime_root,
            platform_name="posix",
        )


@pytest.mark.parametrize(
    "central_url",
    (
        "http://central.example",
        "https://user:password@central.example",
        "https://central.example/api",
    ),
)
def test_central_url_requires_tls_and_an_origin_without_credentials_or_path(
    tmp_path: Path,
    central_url: str,
) -> None:
    with pytest.raises(ValueError, match="gateway central URL must use TLS outside localhost"):
        load_runtime_config(_config(tmp_path, central_url=central_url))


def test_runtime_paths_must_be_distinct(tmp_path: Path) -> None:
    credential_path = str(tmp_path / "gateway.credential")

    with pytest.raises(ValueError, match="gateway runtime paths must be distinct"):
        load_runtime_config(_config(tmp_path, log_path=credential_path))


@pytest.mark.skipif(os.name == "nt", reason="POSIX hardlink identity contract")
def test_runtime_paths_reject_hardlink_aliases_and_the_config_file(tmp_path: Path) -> None:
    credential_path = tmp_path / "gateway.credential"
    log_path = tmp_path / "gateway.log"
    config_path = _config(tmp_path, log_path=str(log_path))
    os.link(credential_path, log_path)

    with pytest.raises(ValueError, match="gateway runtime paths must be distinct"):
        load_runtime_config(config_path)
    assert credential_path.read_text(encoding="utf-8") == "synthetic-device-secret"

    log_path.unlink()
    with pytest.raises(ValueError, match="gateway runtime paths must be distinct"):
        load_runtime_config(_config(tmp_path, log_path=str(config_path)))


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership and mode contract")
def test_runtime_root_and_created_sensitive_files_are_private(tmp_path: Path) -> None:
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match="gateway runtime root path is invalid"):
        load_runtime_config(_config(tmp_path))

    tmp_path.chmod(0o700)
    config = load_runtime_config(_config(tmp_path))
    outbox = GatewayOutbox(config.sqlite_path)
    handle = configure_runtime_logging(config.log_path)
    logging.getLogger("edge_gateway.runtime").info("pco008.private_files")
    close_runtime_logging(handle)

    assert config.sqlite_path.stat().st_mode & 0o077 == 0
    assert config.log_path.stat().st_mode & 0o077 == 0
    assert outbox.list_pending_commands() == []


def test_late_symlink_substitution_fails_closed_for_log_and_sqlite(tmp_path: Path) -> None:
    config = load_runtime_config(_config(tmp_path))
    protected = tmp_path / "protected-late.txt"
    protected.write_text("do-not-overwrite", encoding="utf-8")
    try:
        config.log_path.symlink_to(protected)
    except OSError:
        pytest.skip("Symlinks not supported in current environment")
    with pytest.raises(ValueError, match="gateway log path is unsafe"):
        configure_runtime_logging(config.log_path)
    assert protected.read_text(encoding="utf-8") == "do-not-overwrite"

    config.log_path.unlink()
    outbox = GatewayOutbox(config.sqlite_path)
    config.sqlite_path.unlink()
    config.sqlite_path.symlink_to(protected)
    with pytest.raises(InvalidCommandEnvelope, match="unsafe_sqlite_path"):
        outbox.list_pending_commands()
    assert protected.read_text(encoding="utf-8") == "do-not-overwrite"


def test_runtime_logging_rejects_duplicate_configuration_and_restores_level(
    tmp_path: Path,
) -> None:
    package_logger = logging.getLogger("edge_gateway")
    previous_level = package_logger.level
    path = tmp_path / "gateway.log"
    first = configure_runtime_logging(path)
    try:
        with pytest.raises(ValueError, match="gateway runtime logging is already configured"):
            configure_runtime_logging(path)
        logging.getLogger("edge_gateway.runtime").info("pco008.once")
    finally:
        close_runtime_logging(first)

    assert package_logger.level == previous_level
    assert path.read_text(encoding="utf-8").count("pco008.once") == 1


def test_runtime_logging_releases_global_state_when_close_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_logger = logging.getLogger("edge_gateway")
    previous_level = package_logger.level
    first = configure_runtime_logging(tmp_path / "first.log")

    def fail_flush() -> None:
        raise RuntimeError("synthetic_flush_failure")

    monkeypatch.setattr(first.handler, "flush", fail_flush)
    with pytest.raises(RuntimeError, match="synthetic_flush_failure"):
        close_runtime_logging(first)

    assert first.closed is True
    assert package_logger.level == previous_level
    second = configure_runtime_logging(tmp_path / "second.log")
    close_runtime_logging(second)


@pytest.mark.skipif(os.name == "nt", reason="POSIX private file mode contract")
def test_runtime_logging_rolls_over_with_private_bounded_files(tmp_path: Path) -> None:
    path = tmp_path / "gateway.log"
    package_logger = logging.getLogger("edge_gateway")
    previous_propagate = package_logger.propagate
    handle = configure_runtime_logging(path)
    package_logger.propagate = False
    try:
        payload = "x" * (1024 * 1024)
        for index in range(6):
            logging.getLogger("edge_gateway.runtime").info(
                "pco008.rollover_probe part=%d payload=%s", index, payload
            )
    finally:
        package_logger.propagate = previous_propagate
        close_runtime_logging(handle)

    backup = Path(f"{path}.1")
    assert backup.is_file()
    assert 0 < path.stat().st_size <= handle.handler.maxBytes
    assert 0 < backup.stat().st_size <= handle.handler.maxBytes
    assert path.stat().st_mode & 0o077 == 0
    assert backup.stat().st_mode & 0o077 == 0
