import logging

import httpx
from groq import APIStatusError

from app.services.llm_client import LLMClient


def _make_api_status_error(status_code: int, secret_detail: str) -> APIStatusError:
    """Build a real APIStatusError whose message body carries a marker string.

    Used to prove that LLMClient.ask() never logs that free form message
    text, only the fixed safe fields (exception class name, status code).
    """
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code, request=request, text=secret_detail)
    return APIStatusError(
        f"Error code: {status_code} - {secret_detail}",
        response=response,
        body={"error": {"message": secret_detail}},
    )


def test_ask_logs_only_safe_fields_on_retry_exhaustion(monkeypatch, caplog):
    """When retries are exhausted, ask() must log the exception class name
    and status code only, never the exception's free form message text,
    and must still return the canned fallback result.
    """
    secret_detail = "super secret leaked detail xyz123"
    exc = _make_api_status_error(503, secret_detail)

    client = LLMClient.__new__(LLMClient)
    client._model = "test-model"
    client._timeout = 1
    client._max_retries = 1

    def _raise(question: str):
        raise exc

    monkeypatch.setattr(client, "_ask_with_retry", _raise)

    with caplog.at_level(logging.ERROR, logger="app.services.llm_client"):
        result = client.ask("hello")

    assert result.is_fallback is True

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_detail not in log_text
    assert "APIStatusError" in log_text
    assert "503" in log_text
