"""Redis-only limiter for externally exposed order capture.

No in-memory fallback is intentional: inability to verify the budget denies writes.
"""
from __future__ import annotations

import hashlib
import hmac

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
        # The raw source is never logged or persisted; Redis sees only a scoped HMAC.
        signal = hmac.new(self._secret, client_signal.encode("utf-8"), hashlib.sha256).hexdigest()
        # Apply both a branch-wide budget and a client-specific budget. Either
        # exhausted budget denies the request, so rotating sources cannot evade
        # the public-key ceiling and one noisy source cannot consume it alone.
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
