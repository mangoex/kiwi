# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-repository-policy-tests-v1
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "repository_policy.py"


def test_tc145_policy_output_is_deterministic_and_redacted(tmp_path: Path) -> None:
    (tmp_path / "local.db").write_text("do-not-print-this-marker")
    (tmp_path / "backup.bak").write_text("do-not-print-this-marker")
    (tmp_path / "token.txt").write_text("api" + "_key=do-not-print-this-marker")
    command = [sys.executable, str(SCRIPT), str(tmp_path)]
    first = subprocess.run(command, text=True, capture_output=True)
    second = subprocess.run(command, text=True, capture_output=True)
    assert first.returncode == second.returncode == 1
    assert first.stdout == second.stdout
    assert "do-not-print-this-marker" not in first.stdout + first.stderr
    assert "local.db|database" in first.stdout
    assert "backup.bak|backup" in first.stdout
    assert "token.txt|sensitive_signature" in first.stdout


def test_tc145_exact_synthetic_allowlist_requires_path_hash_and_provenance(tmp_path: Path) -> None:
    fixture = tmp_path / "fixtures" / "allowed.txt"
    fixture.parent.mkdir()
    content = "SEC001-SYNTHETIC-FIXTURE provenance=fixture-v1\ntoken=synthetic-value\n"
    fixture.write_text(content)
    allowlist = tmp_path / "scripts"
    allowlist.mkdir()
    (allowlist / "repository_policy_allowlist.json").write_text(
        json.dumps(
            {
                "synthetic_allowlist": [
                    {
                        "path": "fixtures/allowed.txt",
                        "sha256": hashlib.sha256(content.encode()).hexdigest(),
                        "provenance": "fixture-v1",
                    }
                ]
            }
        )
    )
    command = [sys.executable, str(SCRIPT), str(tmp_path)]
    exact = subprocess.run(command, text=True, capture_output=True)
    assert exact.returncode == 0
    fixture.write_text(content + "tampered\n")
    tampered = subprocess.run(command, text=True, capture_output=True)
    assert tampered.returncode == 1
    fixture.write_text(content)
    moved = tmp_path / "fixtures" / "moved.txt"
    fixture.rename(moved)
    wrong_path = subprocess.run(command, text=True, capture_output=True)
    assert wrong_path.returncode == 1
    moved.rename(fixture)
    fixture.write_text(content.replace("fixture-v1", "other-v1"))
    wrong_provenance = subprocess.run(command, text=True, capture_output=True)
    assert wrong_provenance.returncode == 1
    for result in (tampered, wrong_path, wrong_provenance):
        assert "synthetic-value" not in result.stdout + result.stderr
        assert "fixture-v1" not in result.stdout + result.stderr
        assert hashlib.sha256(content.encode()).hexdigest() not in result.stdout + result.stderr


def test_tc145_scans_literal_sensitive_assignment_in_source_without_leaking_value(
    tmp_path: Path,
) -> None:
    source = tmp_path / "config.py"
    source.write_text("private" + '_key = "do-not-print-source-marker"\n')
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)], text=True, capture_output=True
    )
    assert result.returncode == 1
    assert "config.py|sensitive_signature" in result.stdout
    assert "do-not-print-source-marker" not in result.stdout + result.stderr


def test_tc145_scans_json_and_yaml_literals_without_leaking_value(tmp_path: Path) -> None:
    marker = "do-not-print-config-marker"
    (tmp_path / "config.json").write_text('{"to' + 'ken": "' + marker + '"}')
    (tmp_path / "config.yaml").write_text("secret" + ': "' + marker + '"\n')
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)], text=True, capture_output=True
    )
    assert result.returncode == 1
    assert "config.json|sensitive_signature" in result.stdout
    assert "config.yaml|sensitive_signature" in result.stdout
    assert marker not in result.stdout + result.stderr


def test_tc145_scans_unquoted_yaml_secret_values(tmp_path: Path) -> None:
    marker = "do-not-print-unquoted-yaml-marker"
    (tmp_path / "compose.yaml").write_text("password: " + marker + "\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)], text=True, capture_output=True
    )
    assert result.returncode == 1
    assert "compose.yaml|sensitive_signature" in result.stdout
    assert marker not in result.stdout + result.stderr


def test_tc145_scans_tests_private_key_headers_sidecars_and_exports(
    tmp_path: Path,
) -> None:
    marker = "do-not-print-scanner-marker"
    (tmp_path / "test_config.py").write_text(
        "access_" + 'token = "' + marker + '"\n'
    )
    (tmp_path / "identity.pem").write_text(
        "-----BEGIN OPEN" + "SSH PRIVATE KEY-----\n" + marker
    )
    (tmp_path / "encrypted.pem").write_text(
        "-----BEGIN ENCRYPTED " + "PRIVATE KEY-----\n" + marker
    )
    for name in (
        "local.db-wal",
        "local.sqlite-shm",
        "local.sqlite3-journal",
        "snapshot.sql",
        "snapshot.dump",
    ):
        (tmp_path / name).write_text(marker)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)], text=True, capture_output=True
    )

    assert result.returncode == 1
    assert "test_config.py|sensitive_signature" in result.stdout
    assert "identity.pem|private_key" in result.stdout
    assert "encrypted.pem|private_key" in result.stdout
    assert "local.db-wal|database_sidecar" in result.stdout
    assert "local.sqlite-shm|database_sidecar" in result.stdout
    assert "local.sqlite3-journal|database_sidecar" in result.stdout
    assert "snapshot.sql|database_export" in result.stdout
    assert "snapshot.dump|database_export" in result.stdout
    assert marker not in result.stdout + result.stderr
