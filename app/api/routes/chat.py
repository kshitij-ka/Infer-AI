import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_redis
from app.core.config import get_settings
from app.models.chat_log import ChatLog
from app.models.user import Role, User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.cache import is_rate_limited
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
    if user.role == Role.readonly:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only users cannot use the chat API",
        )

    settings = get_settings()
    if is_rate_limited(redis_client, key=user.username, limit_per_minute=settings.rate_limit_per_minute):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded, please slow down",
        )

    start = time.perf_counter()
    result = llm_client.ask(payload.question)
    latency_ms = (time.perf_counter() - start) * 1000

    log = ChatLog(
        user_id=user.id,
        question=payload.question,
        answer=result.answer,
        latency_ms=latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        status="fallback" if result.is_fallback else "ok",
    )
    db.add(log)
    db.commit()

    record_chat_metrics(
        latency_ms=latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        status=log.status,
    )

    return ChatResponse(
        answer=result.answer,
        latency_ms=latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
