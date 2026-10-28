"""PUR-DRAFT-001 additive SQLite migration and history protection."""

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

PREVIOUS = "0103_blind_cash_phases_2_6"
REVISION = "0104_purchase_draft_edits"


def test_purchase_draft_edit_migration_roundtrip_and_history_guard(tmp_path):
    path = tmp_path / "purchase-draft-edit.db"
    prepared = _sqlite_alembic(path, "upgrade", PREVIOUS)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    upgraded = _sqlite_alembic(path, "upgrade", REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(purchase_documents)")}
        assert "version" in columns
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_update_commands'"
        ).fetchone()
    assert _sqlite_alembic(path, "downgrade", PREVIOUS).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO purchase_update_commands "
            "(id,organization_id,branch_id,actor_user_id,purchase_id,idempotency_key,request_hash,"
            "expected_version,result,created_at) VALUES "
            "('command','org','branch','actor','purchase','key','hash',1,'{}','2026-10-27')"
        )
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "0104 downgrade blocked: purchase edit receipts exist" in blocked.stdout + blocked.stderr


def test_purchase_draft_edit_migration_blocks_edited_version_without_receipt(tmp_path):
    path = tmp_path / "purchase-draft-version.db"
    prepared = _sqlite_alembic(path, "upgrade", REVISION)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO purchase_documents "
            "(id,organization_id,branch_id,supplier_id,document_type,folio,document_date,"
            "subtotal,discount_total,tax_total,freight_total,total,payment_method,paid_from_cash,"
            "status,version,created_by,origin,created_at) VALUES "
            "('purchase','org','branch','supplier','note','EDITED','2026-10-27',0,0,0,0,0,"
            "'other',0,'draft',2,'actor','HUMAN','2026-10-27')"
        )
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "0104 downgrade blocked: edited purchase drafts exist" in blocked.stdout + blocked.stderr
