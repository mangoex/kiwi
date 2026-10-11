"""Redis rate limiting for externally authenticated Agent Tools identities."""

from __future__ import annotations

import hashlib
import hmac
from typing import cast

from redis import Redis


class RedisAgentRateLimiter:
    """Atomically reject an exhausted identity before consuming shared capacity."""

    _ALLOW_SCRIPT = """
local client_count = tonumber(redis.call('GET', KEYS[2]) or '0')
if client_count >= tonumber(ARGV[2]) then
  return 0
end
local global_count = tonumber(redis.call('GET', KEYS[1]) or '0')
if global_count >= tonumber(ARGV[1]) then
  return 0
end
global_count = redis.call('INCR', KEYS[1])
if global_count == 1 then
  redis.call('EXPIRE', KEYS[1], 60)
end
client_count = redis.call('INCR', KEYS[2])
if client_count == 1 then
  redis.call('EXPIRE', KEYS[2], 60)
end
return 1
"""

    def __init__(
        self,
        redis_url: str,
        global_limit: int,
        identity_limit: int,
        identity_signal_secret: str,
    ) -> None:
        if global_limit < 1 or identity_limit < 1:
            raise ValueError("agent rate limits must be positive")
        if identity_limit > global_limit:
            raise ValueError("agent identity limit cannot exceed the global limit")
        if not identity_signal_secret:
            raise ValueError("agent identity signal secret is required")
        self._client = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        self._global_limit = global_limit
        self._identity_limit = identity_limit
        self._secret = identity_signal_secret.encode("utf-8")

    def allow(self, namespace: str, identity_signal: str) -> bool:
        if not namespace or not identity_signal:
            raise ValueError("agent rate limit signals are required")
        identity_hash = hmac.new(
            self._secret, identity_signal.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        prefix = f"restaurantos:agent-tools:{namespace}"
        result = cast(
            int,
            self._client.eval(
                self._ALLOW_SCRIPT,
                2,
                f"{prefix}:global",
                f"{prefix}:identity:{identity_hash}",
                str(self._global_limit),
                str(self._identity_limit),
            ),
        )
        return result == 1
