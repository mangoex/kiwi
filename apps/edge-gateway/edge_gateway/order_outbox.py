"""Durable order commands sharing the domain SQLite transaction.

The caller validates authorization before acceptance. The callback must execute
the domain with commit=False; its result and signed envelope commit together.
No network request occurs while the writer transaction is held.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from edge_gateway.outbox import _prepare_private_database_file

metadata = sa.MetaData()
commands = sa.Table(
    "local_order_commands",
    metadata,
    sa.Column("local_sequence", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("command_id", sa.String, nullable=False, unique=True),
    sa.Column("actor_id", sa.String, nullable=False),
    sa.Column("idempotency_key", sa.String, nullable=False),
    sa.Column("request_hash", sa.String, nullable=False),
    sa.Column("aggregate_id", sa.String, nullable=False),
    sa.Column("sequence", sa.Integer, nullable=False),
    sa.Column("command_hash", sa.String, nullable=False),
    sa.Column("envelope", sa.JSON, nullable=False),
    sa.Column("result", sa.JSON, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("checkpoint", sa.Integer),
    sa.Column("detail", sa.String),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("next_attempt_at", sa.Float, nullable=False, server_default="0"),
    sa.UniqueConstraint("actor_id", "idempotency_key"),
    sa.UniqueConstraint("aggregate_id", "sequence"),
    sqlite_autoincrement=True,
)
order_lifecycle = sa.Table(
    "local_order_lifecycle",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("handoff_id", sa.String),
    sa.Column("manifest", sa.JSON),
    sa.Column("manifest_hash", sa.String),
    sa.Column("signature", sa.String),
    sa.Column("refresh_bundle", sa.JSON),
    sa.Column("bundle_hash", sa.String),
    sa.Column("lease_epoch", sa.Integer),
    sa.CheckConstraint(
        "status IN ('ACTIVE', 'FREEZING', 'FROZEN', 'RELEASED', 'REFRESHING')",
        name="ck_local_order_lifecycle_status",
    ),
)
LIFECYCLE_ID = "orders"


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class OrderOutbox:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        def connect() -> sqlite3.Connection:
            _prepare_private_database_file(self.path)
            if self.path.stat().st_nlink != 1:
                raise ValueError("order_database_hardlink")
            conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            return conn

        self.engine = sa.create_engine("sqlite://", creator=connect, poolclass=sa.pool.NullPool)
        metadata.create_all(self.engine)

    def accept(
        self,
        actor_id: str,
        idempotency_key: str,
        intent: dict[str, Any],
        execute: Callable[[Session, int, str | None], tuple[dict[str, Any], dict[str, Any]]],
        *,
        aggregate_id: str | None = None,
        bundle_hash: str | None = None,
        lease_epoch: int | None = None,
    ) -> dict[str, Any]:
        if not actor_id or not 12 <= len(idempotency_key) <= 160:
            raise ValueError("order_idempotency_key_invalid")
        request_hash = digest(intent)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            # The connection owns the transaction. Session.commit by a faulty
            # domain callback cannot commit it (rollback_only join mode).
            with Session(bind=connection, join_transaction_mode="rollback_only") as session:
                existing = (
                    session.execute(
                        sa.select(commands).where(
                            commands.c.actor_id == actor_id,
                            commands.c.idempotency_key == idempotency_key,
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise ValueError("idempotency_conflict")
                    return dict(existing)
                lifecycle = (
                    session.execute(
                        sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                    )
                    .mappings()
                    .one_or_none()
                )
                if lifecycle is not None and lifecycle["status"] != "ACTIVE":
                    raise ValueError("gateway_orders_frozen")
                if (
                    lifecycle is not None
                    and bundle_hash is not None
                    and (
                        lifecycle["bundle_hash"] != bundle_hash
                        or lifecycle["lease_epoch"] != lease_epoch
                    )
                ):
                    raise ValueError("gateway_orders_stale_bundle")
                previous = None
                aggregate_sequence = 1
                if aggregate_id:
                    conflict = session.scalar(
                        sa.select(commands.c.command_id)
                        .where(
                            commands.c.aggregate_id == aggregate_id, commands.c.status == "CONFLICT"
                        )
                        .limit(1)
                    )
                    if conflict is not None:
                        raise ValueError("offline_order_stream_conflict")
                    prior = (
                        session.execute(
                            sa.select(commands)
                            .where(
                                commands.c.aggregate_id == aggregate_id,
                            )
                            .order_by(commands.c.sequence.desc())
                            .limit(1)
                        )
                        .mappings()
                        .first()
                    )
                    if prior:
                        if prior["status"] == "CONFLICT":
                            raise ValueError("offline_order_stream_conflict")
                        previous = prior["command_hash"]
                        aggregate_sequence = prior["sequence"] + 1
                local = (session.scalar(sa.select(sa.func.max(commands.c.local_sequence))) or 0) + 1
                epoch_sequence = local
                if lifecycle is not None and lifecycle["lease_epoch"] is not None:
                    epoch_sequence = (
                        session.scalar(
                            sa.select(
                                sa.func.max(commands.c.envelope["local_sequence"].as_integer())
                            ).where(
                                commands.c.envelope["lease_epoch"].as_integer()
                                == lifecycle["lease_epoch"]
                            )
                        )
                        or 0
                    ) + 1
                envelope, result = execute(session, epoch_sequence, previous)
                if (
                    envelope["sequence"] != aggregate_sequence
                    or envelope["previous_hash"] != previous
                    or (aggregate_id and envelope["aggregate_id"] != aggregate_id)
                ):
                    raise ValueError("offline_order_causality_invalid")
                unsigned = {k: v for k, v in envelope.items() if k != "device_signature"}
                row = dict(
                    local_sequence=local,
                    command_id=envelope["command_id"],
                    actor_id=actor_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    aggregate_id=envelope["aggregate_id"],
                    sequence=aggregate_sequence,
                    command_hash=digest(unsigned),
                    envelope=envelope,
                    result=result,
                    status="PENDING_SYNC",
                    checkpoint=None,
                    detail=None,
                    attempts=0,
                    next_attempt_at=0,
                )
                session.execute(commands.insert().values(**row))
                session.flush()
                connection.commit()
                return row

    def pending(self, limit: int = 100, *, now: float | None = None) -> list[dict[str, Any]]:
        prior = commands.alias("prior")
        blocked = sa.exists(
            sa.select(prior.c.command_id).where(
                prior.c.aggregate_id == commands.c.aggregate_id,
                prior.c.sequence < commands.c.sequence,
                prior.c.status != "CONFIRMED",
            )
        )
        with self.engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    sa.select(commands)
                    .where(
                        commands.c.status == "PENDING_SYNC",
                        ~blocked,
                        commands.c.next_attempt_at <= (time.time() if now is None else now),
                    )
                    .order_by(commands.c.local_sequence)
                    .limit(limit)
                ).mappings()
            ]

    def defer(self, command_id: str, *, now: float) -> None:
        with self.engine.begin() as connection:
            attempts = connection.scalar(
                sa.select(commands.c.attempts).where(
                    commands.c.command_id == command_id, commands.c.status == "PENDING_SYNC"
                )
            )
            if attempts is None:
                return
            connection.execute(
                commands.update()
                .where(
                    commands.c.command_id == command_id,
                    commands.c.status == "PENDING_SYNC",
                )
                .values(
                    attempts=attempts + 1, next_attempt_at=now + min(5 * 2 ** min(attempts, 6), 300)
                )
            )

    def get(self, command_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = (
                connection.execute(sa.select(commands).where(commands.c.command_id == command_id))
                .mappings()
                .first()
            )
            if row is None:
                raise KeyError(command_id)
            return dict(row)

    def resolve(
        self,
        command_id: str,
        *,
        status: str,
        checkpoint: int | None = None,
        detail: str | None = None,
    ) -> None:
        if status not in {"CONFIRMED", "CONFLICT"}:
            raise ValueError("invalid_resolution")
        if status == "CONFIRMED" and (type(checkpoint) is not int or checkpoint < 1):
            raise ValueError("invalid_checkpoint")
        if status == "CONFLICT" and not detail:
            raise ValueError("missing_conflict_reason")
        with self.engine.begin() as connection:
            updated = connection.execute(
                commands.update()
                .where(
                    commands.c.command_id == command_id,
                    commands.c.status == "PENDING_SYNC",
                )
                .values(status=status, checkpoint=checkpoint, detail=detail)
            )
            if updated.rowcount != 1:
                raise ValueError("command_missing_or_terminal")

    def begin_freeze(self, *, handoff_id: str, **scope: Any) -> str:
        """Persist the acceptance barrier even when the outbox still needs draining."""
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                )
                .mappings()
                .one_or_none()
            )
            if row is not None and row["status"] in {"FREEZING", "FROZEN", "RELEASED"}:
                manifest = dict(row["manifest"] or {})
                if any(manifest.get(field) != value for field, value in scope.items()):
                    raise ValueError("offline_handoff_scope_invalid")
                return str(row["handoff_id"])
            if row is not None and row["status"] != "ACTIVE":
                raise ValueError("offline_handoff_transition_invalid")
            values = dict(
                status="FREEZING",
                handoff_id=handoff_id,
                manifest={"handoff_id": handoff_id, **scope},
                manifest_hash=None,
                signature=None,
                refresh_bundle=None,
            )
            if row is None:
                connection.execute(order_lifecycle.insert().values(id=LIFECYCLE_ID, **values))
            else:
                connection.execute(
                    order_lifecycle.update()
                    .where(order_lifecycle.c.id == LIFECYCLE_ID)
                    .values(**values)
                )
            connection.commit()
            return handoff_id

    @contextmanager
    def cash_write_barrier(self) -> Iterator[None]:
        """Serialize the independent cash enqueue with the order authority freeze."""
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            status = connection.scalar(
                sa.select(order_lifecycle.c.status).where(order_lifecycle.c.id == LIFECYCLE_ID)
            )
            if status is not None and status != "ACTIVE":
                raise ValueError("gateway_orders_frozen")
            yield
            connection.commit()

    def freeze_for_handoff(
        self,
        *,
        handoff_id: str,
        organization_id: str,
        branch_id: str,
        device_id: str,
        lease_epoch: int,
    ) -> dict[str, Any]:
        """Durably stop new commands and attest every command of this epoch."""
        scope = {
            "organization_id": organization_id,
            "branch_id": branch_id,
            "device_id": device_id,
            "lease_epoch": lease_epoch,
        }
        handoff_id = self.begin_freeze(handoff_id=handoff_id, **scope)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                existing = (
                    connection.execute(
                        sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None and existing["status"] in {"FROZEN", "RELEASED"}:
                    saved = dict(existing.get("manifest") or {})
                    if saved.get("handoff_id") != handoff_id or any(
                        saved.get(field) != value for field, value in scope.items()
                    ):
                        raise ValueError("offline_handoff_frozen")
                    connection.commit()
                    return saved
                if existing is not None and existing["status"] != "FREEZING":
                    raise ValueError("offline_handoff_transition_invalid")
                rows = [
                    dict(row)
                    for row in connection.execute(
                        sa.select(commands).order_by(commands.c.local_sequence)
                    ).mappings()
                ]
                if any(row["status"] != "CONFIRMED" for row in rows):
                    raise ValueError("offline_handoff_reconciliation_incomplete")
                rows = [
                    row
                    for row in rows
                    if all(row["envelope"].get(field) == value for field, value in scope.items())
                ]
                entries = [
                    {
                        "local_sequence": int(row["envelope"]["local_sequence"]),
                        "command_id": row["command_id"],
                        "command_hash": row["command_hash"],
                        "aggregate_id": row["aggregate_id"],
                        "sequence": int(row["sequence"]),
                    }
                    for row in rows
                ]
                if [entry["local_sequence"] for entry in entries] != list(
                    range(1, len(entries) + 1)
                ):
                    raise ValueError("offline_handoff_manifest_incomplete")
                manifest = {
                    "schema_version": "ord-off-handoff/v1",
                    "handoff_id": handoff_id,
                    **scope,
                    "watermark": len(entries),
                    "commands": entries,
                }
                values = {
                    "id": LIFECYCLE_ID,
                    "status": "FROZEN",
                    "handoff_id": handoff_id,
                    "manifest": manifest,
                    "manifest_hash": digest(manifest),
                    "signature": None,
                    "refresh_bundle": None,
                }
                if existing is None:
                    connection.execute(order_lifecycle.insert().values(**values))
                else:
                    connection.execute(
                        order_lifecycle.update()
                        .where(order_lifecycle.c.id == LIFECYCLE_ID)
                        .values(**values)
                    )
                connection.commit()
                return manifest
            except Exception:
                connection.rollback()
                raise

    @contextmanager
    def _lifecycle_transaction(self) -> Iterator[sa.Connection]:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            yield connection
            connection.commit()

    def save_handoff_signature(self, handoff_id: str, signature: str) -> dict[str, Any]:
        with self._lifecycle_transaction() as connection:
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                )
                .mappings()
                .one_or_none()
            )
            if (
                row is None
                or row["status"] not in {"FROZEN", "RELEASED"}
                or row["handoff_id"] != handoff_id
            ):
                raise ValueError("offline_handoff_transition_invalid")
            if row["signature"] not in (None, signature):
                raise ValueError("offline_handoff_signature_conflict")
            connection.execute(
                order_lifecycle.update()
                .where(order_lifecycle.c.id == LIFECYCLE_ID)
                .values(signature=signature)
            )
            return {**dict(row), "signature": signature}

    def handoff_payload(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                )
                .mappings()
                .one_or_none()
            )
            if row is None or row["status"] not in {"FROZEN", "RELEASED"}:
                raise ValueError("offline_handoff_not_frozen")
            if not row["signature"]:
                raise ValueError("offline_handoff_signature_missing")
            return {"manifest": dict(row["manifest"]), "signature": row["signature"]}

    def acknowledge_handoff(self, receipt: dict[str, Any]) -> None:
        with self._lifecycle_transaction() as connection:
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                )
                .mappings()
                .one_or_none()
            )
            if row is None or row["status"] not in {"FROZEN", "RELEASED"}:
                raise ValueError("offline_handoff_not_frozen")
            manifest = dict(row["manifest"])
            if (
                receipt.get("handoff_id") != manifest.get("handoff_id")
                or receipt.get("manifest_hash") != row["manifest_hash"]
                or receipt.get("status") != "released"
                or receipt.get("branch_id") != manifest.get("branch_id")
                or receipt.get("lease_epoch") != manifest.get("lease_epoch")
                or receipt.get("watermark") != manifest.get("watermark")
            ):
                raise ValueError("offline_handoff_ack_invalid")
            connection.execute(
                order_lifecycle.update()
                .where(order_lifecycle.c.id == LIFECYCLE_ID)
                .values(status="RELEASED")
            )

    def begin_catalog_refresh(
        self, bundle: dict[str, Any], *, previous_bundle_hash: str | None = None
    ) -> None:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                )
                .mappings()
                .one_or_none()
            )
            if row is not None and row["status"] != "ACTIVE":
                raise ValueError("offline_catalog_refresh_frozen")
            if previous_bundle_hash is not None and (
                row is None
                or row["bundle_hash"] != previous_bundle_hash
                or row["lease_epoch"] != bundle["manifest"]["lease_epoch"]
            ):
                raise ValueError("gateway_orders_stale_bundle")
            unresolved = connection.scalar(
                sa.select(sa.func.count())
                .select_from(commands)
                .where(commands.c.status != "CONFIRMED")
            )
            if unresolved:
                raise ValueError("offline_catalog_refresh_reconciliation_incomplete")
            values = {
                "id": LIFECYCLE_ID,
                "status": "REFRESHING",
                "handoff_id": None,
                "manifest": None,
                "manifest_hash": None,
                "signature": None,
                "refresh_bundle": bundle,
            }
            if row is None:
                connection.execute(order_lifecycle.insert().values(**values))
            else:
                connection.execute(
                    order_lifecycle.update()
                    .where(order_lifecycle.c.id == LIFECYCLE_ID)
                    .values(**values)
                )
            connection.commit()

    def begin_recovery_refresh(
        self, bundle: dict[str, Any], *, handoff_id: str, expected_previous_epoch: int
    ) -> None:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                )
                .mappings()
                .one_or_none()
            )
            manifest = bundle["manifest"]
            if row is None or row["status"] != "RELEASED" or row["handoff_id"] != handoff_id:
                raise ValueError("offline_recovery_handoff_required")
            old = row["manifest"]
            if (
                old["lease_epoch"] != expected_previous_epoch
                or manifest["lease_epoch"] != expected_previous_epoch + 1
                or any(manifest[field] != old[field] for field in ("organization_id", "branch_id"))
            ):
                raise ValueError("offline_recovery_scope_invalid")
            if connection.scalar(
                sa.select(sa.func.count())
                .select_from(commands)
                .where(commands.c.status != "CONFIRMED")
            ):
                raise ValueError("offline_recovery_reconciliation_incomplete")
            connection.execute(
                order_lifecycle.update()
                .where(order_lifecycle.c.id == LIFECYCLE_ID)
                .values(status="REFRESHING", refresh_bundle=bundle)
            )
            connection.commit()

    def complete_catalog_refresh(self) -> None:
        with self._lifecycle_transaction() as connection:
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(
                        order_lifecycle.c.id == LIFECYCLE_ID,
                        order_lifecycle.c.status == "REFRESHING",
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ValueError("offline_catalog_refresh_transition_invalid")
            bundle = dict(row["refresh_bundle"] or {})
            manifest = bundle.get("manifest")
            if not isinstance(manifest, dict) or not isinstance(bundle.get("hash"), str):
                raise ValueError("offline_catalog_refresh_transition_invalid")
            updated = connection.execute(
                order_lifecycle.update()
                .where(
                    order_lifecycle.c.id == LIFECYCLE_ID,
                    order_lifecycle.c.status == "REFRESHING",
                )
                .values(
                    status="ACTIVE",
                    refresh_bundle=None,
                    bundle_hash=bundle["hash"],
                    lease_epoch=manifest.get("lease_epoch"),
                )
            )
            if updated.rowcount != 1:
                raise ValueError("offline_catalog_refresh_transition_invalid")

    def pending_catalog_refresh(self) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(
                        order_lifecycle.c.id == LIFECYCLE_ID,
                        order_lifecycle.c.status == "REFRESHING",
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else dict(row["refresh_bundle"])

    def lifecycle_status(self) -> str:
        with self.engine.connect() as connection:
            status = connection.scalar(
                sa.select(order_lifecycle.c.status).where(order_lifecycle.c.id == LIFECYCLE_ID)
            )
            return "ACTIVE" if status is None else str(status)

    def ensure_active_bundle(self, bundle_hash: str, lease_epoch: int) -> None:
        if not isinstance(bundle_hash, str) or len(bundle_hash) != 64 or lease_epoch < 1:
            raise ValueError("gateway_orders_bundle_invalid")
        with self._lifecycle_transaction() as connection:
            row = (
                connection.execute(
                    sa.select(order_lifecycle).where(order_lifecycle.c.id == LIFECYCLE_ID)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                connection.execute(
                    order_lifecycle.insert().values(
                        id=LIFECYCLE_ID,
                        status="ACTIVE",
                        handoff_id=None,
                        manifest=None,
                        manifest_hash=None,
                        signature=None,
                        refresh_bundle=None,
                        bundle_hash=bundle_hash,
                        lease_epoch=lease_epoch,
                    )
                )
                return
            if (
                row["status"] != "ACTIVE"
                or row["bundle_hash"] != bundle_hash
                or row["lease_epoch"] != lease_epoch
            ):
                raise ValueError("gateway_orders_stale_bundle")

    def active_bundle_matches(self, bundle_hash: str, lease_epoch: int) -> bool:
        try:
            self.ensure_active_bundle(bundle_hash, lease_epoch)
        except ValueError:
            return False
        return True
