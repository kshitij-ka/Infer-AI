import hashlib
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
    # redis-py types INCR's return as Awaitable[Any] | Any because the
    # same command mixin backs both the sync and async clients; this
    # client is always the sync redis.Redis, so INCR always returns int.
    count: int = client.incr(redis_key)  # type: ignore[assignment]
    if count == 1:
        client.expire(redis_key, 60)
    return count > limit_per_minute


def _normalize_question(question: str) -> str:
    """
    Normalizes a question for cache key purposes: trims whitespace
    and lowercases it, so "What is FastAPI?" and "  what IS
    fastapi?  " share a cache entry.

    Args:
        question: the raw question text.

    Returns:
        The normalized question text.
    """
    return question.strip().lower()


def _cache_key(question: str) -> str:
    """
    Builds a Redis key for a question's cached answer, hashing the
    normalized question so the key has a fixed length regardless of
    question length.

    Args:
        question: the raw question text.

    Returns:
        A Redis key string.
    """
    normalized = _normalize_question(question)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"chatcache:{digest}"


def get_cached_answer(client: redis.Redis, question: str) -> str | None:
    """
    Looks up a cached answer for the given question.

    Args:
        client: the Redis client.
        question: the raw question text.

    Returns:
        The cached answer string if present, otherwise None.
    """
    # redis-py types GET's return as Awaitable[Any] | Any for the same
    # reason as INCR above; this client is decode_responses=True sync
    # redis.Redis, so GET always returns str or None.
    return client.get(_cache_key(question))  # type: ignore[return-value]


def set_cached_answer(client: redis.Redis, question: str, answer: str, ttl_seconds: int) -> None:
    """
    Stores an answer for the given question, expiring after
    ttl_seconds.

    Args:
        client: the Redis client.
        question: the raw question text.
        answer: the answer text to cache.
        ttl_seconds: how many seconds until the cache entry expires.
    """
    client.setex(_cache_key(question), ttl_seconds, answer)
