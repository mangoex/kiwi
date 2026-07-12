from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone

UTC = timezone.utc
from pathlib import Path
from typing import Any


class InvalidCommandEnvelope(ValueError):
    pass


class GatewayOutbox:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def enqueue_command(self, envelope: dict[str, Any]) -> dict[str, Any]:
        _validate_command(envelope)
        now = _now_iso()
        payload_json = json.dumps(envelope["payload"], sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            existing = connection.execute(
                "select * from local_commands where idempotency_key = ?",
                (envelope["idempotency_key"],),
            ).fetchone()
            if existing:
                return _row_to_command(existing)

            connection.execute(
                """
                insert into local_commands (
                    command_id,
                    idempotency_key,
                    organization_id,
                    branch_id,
                    source_device_id,
                    command_type,
                    payload_json,
                    status,
                    occurred_at,
                    created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (
                    envelope["command_id"],
                    envelope["idempotency_key"],
                    envelope["organization_id"],
                    envelope["branch_id"],
                    envelope["source_device_id"],
                    envelope["command_type"],
                    payload_json,
                    envelope["occurred_at"],
                    now,
                ),
            )
            row = connection.execute(
                "select * from local_commands where idempotency_key = ?",
                (envelope["idempotency_key"],),
            ).fetchone()
        return _row_to_command(row)

    def list_pending_commands(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select * from local_commands
                where status = 'PENDING'
                order by created_at asc, id asc
                """
            ).fetchall()
        return [_row_to_command(row) for row in rows]

    def mark_confirmed(self, idempotency_key: str, checkpoint: int) -> dict[str, Any]:
        if checkpoint <= 0:
            raise InvalidCommandEnvelope("checkpoint must be positive")
        now = _now_iso()
        with self._connect() as connection:
            row = connection.execute(
                "select * from local_commands where idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise InvalidCommandEnvelope("command was not found")
            connection.execute(
                """
                update local_commands
                set status = 'CONFIRMED',
                    confirmed_checkpoint = ?,
                    confirmed_at = ?
                where idempotency_key = ?
                """,
                (checkpoint, now, idempotency_key),
            )
            connection.execute(
                """
                insert into sync_state (branch_id, last_checkpoint, updated_at)
                values (?, ?, ?)
                on conflict(branch_id)
                do update set
                    last_checkpoint = max(last_checkpoint, excluded.last_checkpoint),
                    updated_at = excluded.updated_at
                """,
                (row["branch_id"], checkpoint, now),
            )
            updated = connection.execute(
                "select * from local_commands where idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return _row_to_command(updated)

    def get_sync_state(self, branch_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "select * from sync_state where branch_id = ?",
                (branch_id,),
            ).fetchone()
        if row is None:
            return {"branch_id": branch_id, "last_checkpoint": 0, "updated_at": None}
        return dict(row)

    def journal_mode(self) -> str:
        with self._connect() as connection:
            return str(connection.execute("pragma journal_mode").fetchone()[0]).lower()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.execute(
                """
                create table if not exists local_commands (
                    id integer primary key autoincrement,
                    command_id text not null,
                    idempotency_key text not null unique,
                    organization_id text not null,
                    branch_id text not null,
                    source_device_id text not null,
                    command_type text not null,
                    payload_json text not null,
                    status text not null,
                    occurred_at text not null,
                    created_at text not null,
                    confirmed_checkpoint integer,
                    confirmed_at text
                )
                """
            )
            connection.execute(
                """
                create table if not exists sync_state (
                    branch_id text primary key,
                    last_checkpoint integer not null,
                    updated_at text not null
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _validate_command(envelope: dict[str, Any]) -> None:
    required: Iterable[str] = (
        "schema_version",
        "command_id",
        "idempotency_key",
        "organization_id",
        "branch_id",
        "source_device_id",
        "command_type",
        "occurred_at",
        "payload",
    )
    missing = [field for field in required if not envelope.get(field)]
    if missing:
        raise InvalidCommandEnvelope(f"missing fields: {', '.join(missing)}")
    if envelope["schema_version"] != "1.0":
        raise InvalidCommandEnvelope("unsupported schema_version")
    if len(str(envelope["idempotency_key"])) < 12:
        raise InvalidCommandEnvelope("idempotency_key is too short")
    if not isinstance(envelope["payload"], dict):
        raise InvalidCommandEnvelope("payload must be an object")


def _row_to_command(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "command_id": row["command_id"],
        "idempotency_key": row["idempotency_key"],
        "organization_id": row["organization_id"],
        "branch_id": row["branch_id"],
        "source_device_id": row["source_device_id"],
        "command_type": row["command_type"],
        "payload": json.loads(row["payload_json"]),
        "status": row["status"],
        "occurred_at": row["occurred_at"],
        "created_at": row["created_at"],
        "confirmed_checkpoint": row["confirmed_checkpoint"],
        "confirmed_at": row["confirmed_at"],
    }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
