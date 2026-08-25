"""Bounded file logging for the local gateway runtime."""

from __future__ import annotations

import logging
import os
import stat
import time
from dataclasses import dataclass
from io import TextIOWrapper
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import cast

LOGGER_NAME = "edge_gateway"


@dataclass
class RuntimeLogHandle:
    handler: RotatingFileHandler
    previous_level: int
    closed: bool = False


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self) -> TextIOWrapper:
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if Path(self.baseFilename).is_symlink():
            raise OSError("gateway log path is unsafe")
        descriptor = os.open(self.baseFilename, flags, 0o600)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise OSError("gateway log path is unsafe")
            if os.name != "nt":
                if file_stat.st_uid != os.geteuid():
                    raise OSError("gateway log path is unsafe")
                os.fchmod(descriptor, 0o600)
            return cast(
                TextIOWrapper,
                os.fdopen(
                    descriptor,
                    self.mode,
                    encoding=self.encoding,
                    errors=self.errors,
                ),
            )
        except Exception:
            os.close(descriptor)
            raise


_ACTIVE_HANDLE: RuntimeLogHandle | None = None


def configure_runtime_logging(path: Path) -> RuntimeLogHandle:
    global _ACTIVE_HANDLE
    if _ACTIVE_HANDLE is not None and not _ACTIVE_HANDLE.closed:
        raise ValueError("gateway runtime logging is already configured")
    logger = logging.getLogger(LOGGER_NAME)
    try:
        handler = PrivateRotatingFileHandler(
            path,
            mode="a",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError as exc:
        raise ValueError("gateway log path is unsafe") from exc
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    previous_level = logger.level
    if logger.getEffectiveLevel() > logging.INFO:
        logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    handle = RuntimeLogHandle(handler=handler, previous_level=previous_level)
    _ACTIVE_HANDLE = handle
    return handle


def close_runtime_logging(handle: RuntimeLogHandle) -> None:
    global _ACTIVE_HANDLE
    if handle.closed:
        return
    logger = logging.getLogger(LOGGER_NAME)
    logger.removeHandler(handle.handler)
    failure: Exception | None = None
    try:
        handle.handler.flush()
    except Exception as exc:
        failure = exc
    try:
        handle.handler.close()
    except Exception as exc:
        if failure is None:
            failure = exc
    finally:
        logger.setLevel(handle.previous_level)
        handle.closed = True
        if _ACTIVE_HANDLE is handle:
            _ACTIVE_HANDLE = None
    if failure is not None:
        raise failure
