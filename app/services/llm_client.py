import logging
from dataclasses import dataclass

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "The AI service is temporarily unavailable. Please try again in a moment."
)

_RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, APIStatusError)


@dataclass
class LLMResult:
    answer: str
    prompt_tokens: int
    completion_tokens: int
    is_fallback: bool = False


class LLMClient:
    """Thin wrapper around the Groq (OpenAI-compatible) chat completion API.

    Retries transient failures with exponential backoff, bounds each call
    with a timeout, and returns a canned fallback answer if all attempts
    are exhausted so callers never have to handle a raised LLM error.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.groq_model
        self._timeout = settings.llm_timeout_seconds
        self._max_retries = settings.llm_max_retries
        self._client = Groq(api_key=settings.groq_api_key, timeout=self._timeout)

    def ask(self, question: str) -> LLMResult:
        """Ask the LLM a question, falling back to a canned answer on failure.

        Retries transient Groq SDK errors internally. If retries are
        exhausted, this catches the exception and returns a fallback
        result instead of raising, so callers never need their own
        try/except for LLM failures. Only a fixed, safe set of fields
        (exception class name and, when present, HTTP status code) is
        logged, never the exception's free form string representation,
        since that text originates from Groq's own API response body
        and is not on an allowlist of safe-to-log content.
        """
        try:
            return self._ask_with_retry(question)
        except _RETRYABLE_EXCEPTIONS as exc:
            logger.error(
                "LLM call failed after retries: %s (status_code=%s)",
                exc.__class__.__name__,
                getattr(exc, "status_code", None),
            )
            return LLMResult(answer=FALLBACK_ANSWER, prompt_tokens=0, completion_tokens=0, is_fallback=True)

    def _ask_with_retry(self, question: str) -> LLMResult:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        )
        def _call() -> LLMResult:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": question}],
            )
            choice = completion.choices[0].message.content or ""
            usage = completion.usage
            return LLMResult(
                answer=choice,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            )

        return _call()


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
