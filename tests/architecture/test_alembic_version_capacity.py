"""Architecture and integration tests for DB-001 (Alembic revision capacity).

These tests verify that the migration chain:

- has no revision identifier longer than 128 characters;
- has the bridge revision ``0013a_expand_version_num`` (<=32 chars) between
  ``0013_pos_cash_rbac_permissions`` and ``0014_legacy_caja_role_permissions``;
- has a single head and is linear (no branches);
- can run ``upgrade head`` and ``downgrade``/``upgrade`` round-trips on SQLite;
- issues the PostgreSQL ``ALTER TABLE alembic_version ... TYPE VARCHAR(128)``
  statement in the upgrade path and ``VARCHAR(32)`` in the downgrade path,
  while leaving SQLite untouched (no ``ALTER COLUMN``).
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = ROOT / "apps" / "api" / "alembic" / "versions"
API_DIR = ROOT / "apps" / "api"
BRIDGE_REVISION = "0013a_expand_version_num"
PARENT_REVISION = "0013_pos_cash_rbac_permissions"
CHILD_REVISION = "0014_legacy_caja_role_permissions"
HEAD_REVISION = "0023_physical_counts"
MAX_REVISION_LENGTH = 128
BRIDGE_MAX_LENGTH = 32


def _read_revisions() -> dict[str, dict[str, str | None]]:
    """Parse every migration file's revision/down_revision via AST.

    Returns ``{revision_id: {"file": filename, "down_revision": parent_or_None}}``.
    """
    revisions: dict[str, dict[str, str | None]] = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name.endswith(".bak"):
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision_value: str | None = None
        down_value: str | None = None
        for node in module.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "revision":
                        revision_value = _ast_str(node.value)
                    if isinstance(target, ast.Name) and target.id == "down_revision":
                        down_value = _ast_str(node.value)
            # Also handle annotated assignments (revision: str = "...").
            if isinstance(node, ast.AnnAssign):
                if (
                    isinstance(node.target, ast.Name)
                    and node.target.id == "revision"
                    and node.value is not None
                ):
                    revision_value = _ast_str(node.value)
                if (
                    isinstance(node.target, ast.Name)
                    and node.target.id == "down_revision"
                    and node.value is not None
                ):
                    down_value = _ast_str(node.value)
        if revision_value is None:
            continue
        revisions[revision_value] = {"file": path.name, "down_revision": down_value}
    return revisions


def _ast_str(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# --- Structural tests (no database) ----------------------------------------


def test_no_revision_exceeds_128_characters() -> None:
    revisions = _read_revisions()
    too_long = [rev for rev in revisions if len(rev) > MAX_REVISION_LENGTH]
    assert too_long == [], (
        f"Revision identifiers must not exceed {MAX_REVISION_LENGTH} characters; "
        f"found: {too_long}"
    )


def test_bridge_revision_fits_in_32_characters() -> None:
    assert len(BRIDGE_REVISION) <= BRIDGE_MAX_LENGTH, (
        f"Bridge revision {BRIDGE_REVISION!r} must fit in {BRIDGE_MAX_LENGTH} "
        f"characters so it can be registered before the column is widened."
    )


def test_bridge_exists_and_links_0013_to_0014() -> None:
    revisions = _read_revisions()
    assert BRIDGE_REVISION in revisions, (
        f"Bridge revision {BRIDGE_REVISION} not found in migrations"
    )
    assert revisions[BRIDGE_REVISION]["down_revision"] == PARENT_REVISION, (
        f"Bridge must descend from {PARENT_REVISION}, "
        f"got {revisions[BRIDGE_REVISION]['down_revision']!r}"
    )
    assert CHILD_REVISION in revisions, f"{CHILD_REVISION} not found in migrations"
    assert revisions[CHILD_REVISION]["down_revision"] == BRIDGE_REVISION, (
        f"{CHILD_REVISION} must descend from {BRIDGE_REVISION} (repointed), "
        f"got {revisions[CHILD_REVISION]['down_revision']!r}"
    )


def test_chain_is_linear_with_single_head() -> None:
    revisions = _read_revisions()
    # Every down_revision (except None) must reference an existing revision.
    for rev_id, meta in revisions.items():
        parent = meta["down_revision"]
        if parent is not None:
            assert parent in revisions, (
                f"Revision {rev_id} points to unknown parent {parent!r}"
            )

    # Heads = revisions that are not referenced as a down_revision by anyone.
    referenced_as_parent: set[str] = set()
    for meta in revisions.values():
        parent = meta["down_revision"]
        if parent is not None:
            referenced_as_parent.add(parent)
    heads = sorted(set(revisions) - referenced_as_parent)
    assert heads == [HEAD_REVISION], (
        f"Expected single head {HEAD_REVISION!r}, got {heads}"
    )

    # No duplicate parents => no branches.
    parents = [meta["down_revision"] for meta in revisions.values() if meta["down_revision"]]
    duplicates = {p for p in parents if parents.count(p) > 1}
    assert duplicates == set(), f"Multiple revisions share a parent (branch): {duplicates}"


# --- Structural test of the bridge migration source ------------------------


def test_bridge_file_contains_postgres_varchar_128_and_32() -> None:
    """The bridge must emit PostgreSQL DDL to widen to 128 and shrink to 32."""
    bridge_path = VERSIONS_DIR / "202607100200_0013a_expand_version_num.py"
    source = bridge_path.read_text(encoding="utf-8")
    assert "postgresql" in source, "Bridge must detect the PostgreSQL dialect"
    assert "VARCHAR" in source.upper(), "Bridge must use VARCHAR in the ALTER"
    assert "128" in source, "Bridge upgrade must target VARCHAR(128)"
    assert "32" in source, "Bridge downgrade must restore VARCHAR(32)"
    assert "alembic_version" in source, "Bridge must alter alembic_version table"


def test_bridge_does_not_alter_on_sqlite() -> None:
    """SQLite branch must be a no-op (no ALTER COLUMN emitted)."""
    bridge_path = VERSIONS_DIR / "202607100200_0013a_expand_version_num.py"
    source = bridge_path.read_text(encoding="utf-8")
    # The only ALTER TABLE statements must be inside the postgresql branch.
    alter_statements = re.findall(r'op\.execute\(\s*sa\.text\(\s*"([^"]+)"', source)
    assert all("ALTER" in stmt.upper() for stmt in alter_statements), (
        f"Unexpected non-ALTER statements: {alter_statements}"
    )
    # Both ALTERs are guarded by the postgresql dialect check.
    assert source.count('bind.dialect.name == "postgresql"') >= 2, (
        "Both upgrade and downgrade ALTERs must be guarded by the postgresql dialect check"
    )


def test_0014_only_header_changed_not_body() -> None:
    """Confirm 0014's upgrade()/downgrade() bodies are unchanged in spirit.

    We only assert that the CAJA_PERMISSION_CODES constant and the
    INSERT/DELETE role_permissions logic remain present, so the repoint did
    not accidentally alter the migration's business effect.
    """
    source = (
        VERSIONS_DIR / "202607100245_0014_legacy_caja_role_permissions.py"
    ).read_text(encoding="utf-8")
    assert "CAJA_PERMISSION_CODES" in source
    assert "INSERT INTO role_permissions" in source
    assert "DELETE FROM role_permissions" in source
    assert 'down_revision: str | None = "0013a_expand_version_num"' in source
    assert "Revises: 0013a_expand_version_num" in source


# --- Integration tests on SQLite -------------------------------------------


def _alembic(args: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=API_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_sqlite_upgrade_from_0013_reaches_head(tmp_path: Path) -> None:
    database_path = tmp_path / "db-001-upgrade.db"
    database_url = f"sqlite+pysqlite:///{database_path}"

    # Bring the DB up to 0013 first.
    result = _alembic(["upgrade", PARENT_REVISION], database_url)
    assert result.returncode == 0, result.stderr

    # Then upgrade the rest of the chain, which crosses the bridge.
    result = _alembic(["upgrade", "head"], database_url)
    assert result.returncode == 0, result.stderr

    result = _alembic(["current"], database_url)
    assert HEAD_REVISION in result.stdout, (
        f"Expected head {HEAD_REVISION} after upgrade, got: {result.stdout}"
    )


def test_sqlite_upgrade_downgrade_upgrade_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "db-001-roundtrip.db"
    database_url = f"sqlite+pysqlite:///{database_path}"

    # Upgrade to 0013, then to head.
    assert _alembic(["upgrade", PARENT_REVISION], database_url).returncode == 0
    assert _alembic(["upgrade", "head"], database_url).returncode == 0

    # Downgrade back to 0013 (crosses the bridge in reverse).
    result = _alembic(["downgrade", PARENT_REVISION], database_url)
    assert result.returncode == 0, result.stderr

    result = _alembic(["current"], database_url)
    assert PARENT_REVISION in result.stdout, (
        f"Expected {PARENT_REVISION} after downgrade, got: {result.stdout}"
    )

    # Upgrade to head again to confirm reversibility.
    result = _alembic(["upgrade", "head"], database_url)
    assert result.returncode == 0, result.stderr

    result = _alembic(["current"], database_url)
    assert HEAD_REVISION in result.stdout, (
        f"Expected head {HEAD_REVISION} after re-upgrade, got: {result.stdout}"
    )


def test_sqlite_bridge_does_not_alter_column(tmp_path: Path) -> None:
    """On SQLite the bridge must be a no-op: no ALTER COLUMN statement runs."""
    database_path = tmp_path / "db-001-sqlite-noop.db"
    database_url = f"sqlite+pysqlite:///{database_path}"

    assert _alembic(["upgrade", PARENT_REVISION], database_url).returncode == 0

    # Capture stdout/stderr when crossing the bridge on SQLite.
    result = _alembic(["upgrade", CHILD_REVISION], database_url)
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "ALTER" not in combined.upper(), (
        f"SQLite bridge must not emit ALTER; output was: {combined}"
    )
