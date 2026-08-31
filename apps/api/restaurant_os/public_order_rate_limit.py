"""Rate limiters for externally exposed order capture (Redis and resilient In-Memory fallback)."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import hmac
import threading
import time

from redis import Redis


class RedisPublicOrderRateLimiter:
    def __init__(
        self,
        redis_url: str,
        global_limit: int,
        client_limit: int,
        client_signal_secret: str,
    ) -> None:
        if global_limit < 1 or client_limit < 1:
            raise ValueError("public order rate limits must be positive")
        if client_limit > global_limit:
            raise ValueError("public order client limit cannot exceed the global limit")
        if not client_signal_secret:
            raise ValueError("public order client signal secret is required")
        self._client = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        self._global_limit = global_limit
        self._client_limit = client_limit
        self._secret = client_signal_secret.encode("utf-8")

    def allow(self, public_key: str, client_signal: str) -> bool:
        if not self._secret or not client_signal:
            raise ValueError("public order client signal cannot be verified")
        signal = hmac.new(self._secret, client_signal.encode("utf-8"), hashlib.sha256).hexdigest()
        global_bucket = f"restaurantos:public-order:{public_key}"
        client_bucket = f"{global_bucket}:{signal}"
        pipeline = self._client.pipeline(transaction=True)
        for bucket in (global_bucket, client_bucket):
            pipeline.incr(bucket)
            pipeline.expire(bucket, 60, nx=True)
        global_count, _, client_count, _ = pipeline.execute()
        return (
            int(global_count) <= self._global_limit
            and int(client_count) <= self._client_limit
        )


class InMemoryPublicOrderRateLimiter:
    """Thread-safe, sliding-window rate limiter for standalone deployments without Redis."""

    def __init__(
        self,
        global_limit: int = 60,
        client_limit: int = 15,
        client_signal_secret: str = "in-memory-public-order-rate-limiter-salt",
    ) -> None:
        if global_limit < 1 or client_limit < 1:
            raise ValueError("public order rate limits must be positive")
        if client_limit > global_limit:
            raise ValueError("public order client limit cannot exceed the global limit")
        self._global_limit = global_limit
        self._client_limit = client_limit
        self._secret = (client_signal_secret or "in-memory-salt").encode("utf-8")
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, public_key: str, client_signal: str) -> bool:
        if not client_signal:
            client_signal = "anonymous"
        signal = hmac.new(self._secret, client_signal.encode("utf-8"), hashlib.sha256).hexdigest()
        global_bucket = f"global:{public_key}"
        client_bucket = f"client:{public_key}:{signal}"

        now = time.time()
        cutoff = now - 60.0

        with self._lock:
            # Clean expired timestamps
            self._events[global_bucket] = [t for t in self._events[global_bucket] if t > cutoff]
            self._events[client_bucket] = [t for t in self._events[client_bucket] if t > cutoff]

            if len(self._events[global_bucket]) >= self._global_limit:
                return False
            if len(self._events[client_bucket]) >= self._client_limit:
                return False

            self._events[global_bucket].append(now)
            self._events[client_bucket].append(now)

            # Prevent unbounded memory growth
            if len(self._events) > 10000:
                expired_keys = [k for k, v in self._events.items() if not v or v[-1] <= cutoff]
                for k in expired_keys:
                    self._events.pop(k, None)

            return True
