import time

import redis

from app.core.config import get_settings

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def is_rate_limited(client: redis.Redis, key: str, limit_per_minute: int) -> bool:
    """Fixed-window rate limiter keyed per user/IP, backed by Redis INCR + TTL."""
    window = int(time.time() // 60)
    redis_key = f"ratelimit:{key}:{window}"
    count = client.incr(redis_key)
    if count == 1:
        client.expire(redis_key, 60)
    return count > limit_per_minute
