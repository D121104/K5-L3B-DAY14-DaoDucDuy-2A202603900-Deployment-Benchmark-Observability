"""Redis-backed, atomic sliding-window rate limiting."""
import hashlib
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

_WINDOW_SECONDS = 60
_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = now - tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = math.max(1, math.ceil(tonumber(oldest[2]) + tonumber(ARGV[2]) - now))
  return {0, retry}
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('EXPIRE', key, tonumber(ARGV[2]) + 1)
return {1, 0}
"""


def check_rate_limit(key: str) -> None:
    digest = hashlib.sha256(key.encode()).hexdigest()
    try:
        allowed, retry_after = r.eval(
            _SLIDING_WINDOW,
            1,
            f"rate-limit:{digest}",
            time.time(),
            _WINDOW_SECONDS,
            settings.rate_limit_per_minute,
            uuid.uuid4().hex,
        )
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, int(retry_after)))},
        )
