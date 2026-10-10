"""AUD-CORE-001 gates must execute, and build inputs must be reproducible."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from test_cash_ledger_postgres import _postgres_url

ROOT = Path(__file__).resolve().parents[2]


def test_pco003_is_mandatory_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("PCO003_TEST_POSTGRES_URL", raising=False)
    with pytest.raises(pytest.fail.Exception, match="PCO003_TEST_POSTGRES_URL"):
        _postgres_url()


def test_ci_provisions_and_supplies_both_financial_database_gates():
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    steps = ci["jobs"]["python"]["steps"]
    tests = next(step for step in steps if step.get("name") == "Run tests")
    assert tests["env"]["PCO003_TEST_POSTGRES_URL"].endswith("/pco003_ci")
    assert tests["env"]["AUDCORE_TEST_POSTGRES_URL"].endswith("/audcore_ci")
    provision = "\n".join(step.get("run", "") for step in steps)
    assert "CREATE DATABASE pco003_ci" in provision
    assert "CREATE DATABASE audcore_ci" in provision


@pytest.mark.parametrize("fault", ["skip", "absent", "failed", "empty_collection", "pass"])
def test_required_postgres_evidence_rejects_omitted_or_unexecuted_case(tmp_path, fault):
    collection = tmp_path / "collection.txt"
    report = tmp_path / "report.xml"
    modules = ["cash_ledger", "purchase_workspace", "operating_expenses", "system_remediation"]
    collection.write_text(
        "\n".join(f"apps/api/tests/test_{module}_postgres.py::test_case" for module in modules)
        if fault != "empty_collection"
        else "",
        encoding="utf-8",
    )
    cases = []
    for index, module in enumerate(modules):
        if fault == "absent" and index == 0:
            continue
        marker = "<skipped/>" if fault == "skip" else "<failure/>" if fault == "failed" else ""
        cases.append(
            f'<testcase classname="apps.api.tests.test_{module}_postgres" '
            f'name="test_case">{marker if index == 0 else ""}</testcase>'
        )
    report.write_text(
        "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>", encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_postgres_evidence.py"),
            "--collection",
            str(collection),
            "--junit",
            str(report),
        ],
        capture_output=True,
        text=True,
    )
    if fault == "pass":
        assert result.returncode == 0, result.stderr
        assert "system_remediation" in result.stdout
    else:
        assert result.returncode != 0
        assert "Mandatory PostgreSQL" in result.stderr


@pytest.mark.parametrize("path", ["Dockerfile", "infra/docker/api.Dockerfile"])
def test_image_uses_hashed_python_and_immutable_frontend_input(path):
    content = (ROOT / path).read_text(encoding="utf-8")
    assert "pnpm install --frozen-lockfile" in content
    assert "RUN python /app/scripts/install_python_runtime.py" in content
    assert "api-runtime-linux-py312.lock" in content
    installer = (ROOT / "scripts/install_python_runtime.py").read_text(encoding="utf-8")
    assert "--require-hashes" in installer
    assert "--no-deps" in installer
    assert "--no-build-isolation" in installer


def test_manifest_drift_is_rejected_before_dependency_install(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from install_python_runtime import verify_lock_inputs

    for path in (
        "apps/api/pyproject.toml",
        "apps/edge-gateway/pyproject.toml",
        "requirements/dev-windows-py312.lock",
    ):
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, destination)
    verify_lock_inputs(tmp_path, "dev-windows")
    manifest = tmp_path / "apps/api/pyproject.toml"
    content = manifest.read_text(encoding="utf-8")
    content, count = re.subn(r'"fastapi[^"\n]*"', '"fastapi>=999,<1000"', content, count=1)
    assert count == 1
    manifest.write_text(content, encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest and frozen lock inputs differ"):
        verify_lock_inputs(tmp_path, "dev-windows")


def test_pip_rejects_corrupted_distribution_hash(tmp_path):
    lock = (ROOT / "requirements/dev-windows-py312.lock").read_text(encoding="utf-8")
    pin = re.search(r"^python-multipart==[^\s]+", lock, re.MULTILINE)
    assert pin is not None
    source = tmp_path / "bad-hash.txt"
    source.write_text(pin.group() + " --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--require-hashes",
            "--no-deps",
            "--only-binary=:all:",
            "--dest",
            str(tmp_path / "downloads"),
            "-r",
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "DO NOT MATCH THE HASHES" in result.stderr
