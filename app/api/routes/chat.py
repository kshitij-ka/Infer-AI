"""
Chat route.

Accepts a question from an authenticated, non readonly user,
checks a Redis cache for an existing answer to the same normalized
question, and if none exists, calls the LLM client, then stores the
result. Every request, whether served from cache or from the LLM,
gets a ChatLog row and updates Prometheus metrics, so history and
observability stay accurate regardless of cache status.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_redis
from app.core.config import get_settings
from app.models.chat_log import ChatLog
from app.models.user import Role, User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.cache import get_cached_answer, is_rate_limited, set_cached_answer
from app.services.llm_client import LLMClient, get_llm_client
from app.services.metrics import record_chat_metrics

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
    llm_client: LLMClient = Depends(get_llm_client),
) -> ChatResponse:
    """
    Answers a question, from cache if available, otherwise from the
    LLM client.

    Args:
        payload: the submitted question.
        user: the authenticated user, injected by get_current_user.
        db: the database session dependency.
        redis_client: the Redis client dependency.
        llm_client: the LLM client dependency.

    Returns:
        A ChatResponse with the answer, latency, and token usage
        (zero token usage on a cache hit).

    Raises:
        HTTPException: 403 if the user's role is readonly, 429 if
            the user's rate limit is exceeded.
    """
    if user.role == Role.readonly:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only users cannot use the chat API",
        )

    settings = get_settings()
    if is_rate_limited(
        redis_client, key=user.username, limit_per_minute=settings.rate_limit_per_minute
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded, please slow down",
        )

    start = time.perf_counter()
    cached_answer = get_cached_answer(redis_client, payload.question)

    if cached_answer is not None:
        latency_ms = (time.perf_counter() - start) * 1000
        prompt_tokens = 0
        completion_tokens = 0
        answer = cached_answer
        log_status = "cache_hit"
    else:
        result = llm_client.ask(payload.question)
        latency_ms = (time.perf_counter() - start) * 1000
        prompt_tokens = result.prompt_tokens
        completion_tokens = result.completion_tokens
        answer = result.answer
        log_status = "fallback" if result.is_fallback else "ok"
        if not result.is_fallback:
            set_cached_answer(redis_client, payload.question, answer, settings.cache_ttl_seconds)

    log = ChatLog(
        user_id=user.id,
        question=payload.question,
        answer=answer,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        status=log_status,
    )
    db.add(log)
    db.commit()

    record_chat_metrics(
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        status=log_status,
    )

    return ChatResponse(
        answer=answer,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
