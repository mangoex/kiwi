"""Compose the installable loopback gateway without opening sockets in tests."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from typing import Any

import httpx
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from edge_gateway.config import (
    GatewayRuntimeConfig,
    load_gateway_credential,
    load_public_keyring,
    load_runtime_config,
)
from edge_gateway.grants import verify_offline_grant_v2
from edge_gateway.local_api import create_local_cash_app
from edge_gateway.outbox import GatewayOutbox
from edge_gateway.runtime_logging import (
    RuntimeLogHandle,
    close_runtime_logging,
    configure_runtime_logging,
)
from edge_gateway.sync import CashSyncWorker
from edge_gateway.transport import HTTPXGatewayTransport

UTC = timezone.utc
EDGE_VERSION = "pco-008r-1"
LOGGER = logging.getLogger(__name__)


@dataclass
class GatewayWorkerRunner:
    worker: CashSyncWorker
    now: Callable[[], datetime]
    interval_seconds: float
    _stop: Event = field(default_factory=Event)
    _thread: Thread | None = None
    started: bool = False
    healthy: bool = True
    failure: str | None = None

    @property
    def is_stopped(self) -> bool:
        return self._thread is None or not self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="restaurantos-edge-sync", daemon=True)
        self._thread.start()

    def tick(self) -> list[dict[str, Any]]:
        return self.worker.reconcile_once(now=self.now().isoformat())

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            # Recovery and transport close must never race an in-flight sync.
            # HTTP transport already has a finite timeout, so wait for the
            # worker to finish before mutating outbox state.
            self._thread.join()

    def _run(self) -> None:
        self.started = True
        while not self._stop.is_set():
            try:
                self.worker.reconcile_once(now=self.now().isoformat(), limit=1)
            except Exception:
                self.healthy = False
                self.failure = "unexpected_worker_failure"
                LOGGER.error("pco008.edge_runner_failed", extra={"result": "failed"})
                return
            if self._stop.wait(self.interval_seconds):
                return


@dataclass
class GatewayRuntime:
    config: GatewayRuntimeConfig
    outbox: GatewayOutbox
    worker: CashSyncWorker
    app: Any
    transport: HTTPXGatewayTransport
    runner: GatewayWorkerRunner
    log_handle: RuntimeLogHandle | None
    ready: bool

    def start(self) -> None:
        self.runner.start()

    def tick(self) -> list[dict[str, Any]]:
        return self.runner.tick()

    def shutdown(self) -> None:
        if self.log_handle is None:
            return
        self.ready = False
        self.app.state.gateway_ready = False
        failure: Exception | None = None
        try:
            self.runner.stop()
        except Exception as exc:
            failure = exc
        try:
            self.outbox.recover_syncing(now=datetime.now(UTC).isoformat())
        except Exception as exc:
            if failure is None:
                failure = exc
        try:
            self.transport.close()
        except Exception as exc:
            if failure is None:
                failure = exc
        try:
            LOGGER.info("pco008.runtime_stopped")
        except Exception as exc:
            if failure is None:
                failure = exc
        try:
            close_runtime_logging(self.log_handle)
        except Exception as exc:
            if failure is None:
                failure = exc
        finally:
            self.log_handle = None
        if failure is not None:
            raise failure


def create_gateway_runtime(
    config_path: str | Path,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    client_factory: Callable[..., httpx.Client] = httpx.Client,
    worker_interval_seconds: float = 5.0,
) -> GatewayRuntime:
    if worker_interval_seconds <= 0:
        raise ValueError("gateway worker interval is invalid")
    config = load_runtime_config(config_path)
    keyring = load_public_keyring(config.public_keyring_path)
    credential = load_gateway_credential(config.credential_path, runtime_root=config.runtime_root)
    outbox = GatewayOutbox(config.sqlite_path)
    outbox.recover_syncing(now=now().isoformat())
    transport = HTTPXGatewayTransport(config.central_url, credential, client_factory=client_factory)
    log_handle: RuntimeLogHandle | None = None
    try:
        worker = CashSyncWorker(outbox, transport)
        app = create_local_cash_app(
            outbox,
            {
                "organization_id": config.organization_id,
                "branch_id": config.branch_id,
                "source_device_id": config.source_device_id,
            },
            lambda token: verify_offline_grant_v2(token, keyring),
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[config.pos_origin],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

        @app.get("/health/live")
        def live() -> dict[str, str]:
            return {"status": "live"}

        @app.get("/health/ready")
        def ready() -> dict[str, str]:
            if not runtime.ready or not runtime.runner.healthy:
                raise HTTPException(status_code=503, detail={"code": "gateway_not_ready"})
            return {"status": "ready"}

        @app.get("/version")
        def version() -> dict[str, str]:
            return {"service": "restaurantos-edge", "version": EDGE_VERSION}

        runner = GatewayWorkerRunner(worker, now, worker_interval_seconds)
        log_handle = configure_runtime_logging(config.log_path)
        runtime = GatewayRuntime(
            config=config,
            outbox=outbox,
            worker=worker,
            app=app,
            transport=transport,
            runner=runner,
            log_handle=log_handle,
            ready=True,
        )
        app.state.gateway_ready = True
        app.state.gateway_runtime = runtime
        LOGGER.info("pco008.runtime_ready")

        @asynccontextmanager
        async def gateway_lifespan(_app: Any) -> AsyncIterator[None]:
            runtime.start()
            try:
                yield
            finally:
                runtime.shutdown()

        app.router.lifespan_context = gateway_lifespan
        return runtime
    except Exception:
        try:
            transport.close()
        except Exception:
            pass
        if log_handle is not None:
            try:
                close_runtime_logging(log_handle)
            except Exception:
                pass
        raise
