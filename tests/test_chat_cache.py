from app.core.config import get_settings
from app.models.user import Role


def _login(client, username, password):
    response = client.post("/auth/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def test_identical_question_served_from_cache(client, seed_user, fake_llm):
    """
    A second request with the same question, even from a different
    user, does not call the LLM client a second time, since the
    answer to a factual question does not depend on who asked it.
    """
    seed_user(username="alice", password="password123", role=Role.user)
    seed_user(username="bob", password="password123", role=Role.user)
    alice_token = _login(client, "alice", "password123")
    bob_token = _login(client, "bob", "password123")

    first_response = client.post(
        "/chat",
        json={"question": "What is FastAPI?"},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    second_response = client.post(
        "/chat",
        json={"question": "  What IS FastAPI?  "},
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["answer"] == first_response.json()["answer"]
    fake_llm.ask.assert_called_once()


def test_cached_answer_still_logs_chat_history(client, seed_user, fake_llm, test_db):
    """
    A cache hit still writes a ChatLog row, so metrics and history
    stay accurate, but with zero token counts since no LLM call was
    made for that specific request.
    """
    from app.models.chat_log import ChatLog

    seed_user(username="alice", password="password123", role=Role.user)
    token = _login(client, "alice", "password123")

    client.post(
        "/chat",
        json={"question": "cache me please"},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/chat",
        json={"question": "cache me please"},
        headers={"Authorization": f"Bearer {token}"},
    )

    logs = test_db.query(ChatLog).filter(ChatLog.question == "cache me please").all()
    assert len(logs) == 2
    cache_hit_logs = [log for log in logs if log.status == "cache_hit"]
    assert len(cache_hit_logs) == 1
    assert cache_hit_logs[0].prompt_tokens == 0
    assert cache_hit_logs[0].completion_tokens == 0


def test_fallback_answer_is_never_cached(client, seed_user, fake_llm):
    """
    A fallback answer, returned when the LLM client itself is
    unavailable, is never written to the cache, so a temporary outage
    does not get remembered as the permanent answer for that question
    once the LLM recovers.
    """
    from app.services.llm_client import LLMResult

    seed_user(username="alice", password="password123", role=Role.user)
    token = _login(client, "alice", "password123")

    fake_llm.ask.return_value = LLMResult(
        answer="The AI service is temporarily unavailable. Please try again in a moment.",
        prompt_tokens=0,
        completion_tokens=0,
        is_fallback=True,
    )
    first_response = client.post(
        "/chat",
        json={"question": "will this be cached"},
        headers={"Authorization": f"Bearer {token}"},
    )

    fake_llm.ask.return_value = LLMResult(
        answer="a real answer once the LLM recovered",
        prompt_tokens=3,
        completion_tokens=4,
        is_fallback=False,
    )
    second_response = client.post(
        "/chat",
        json={"question": "will this be cached"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert "temporarily unavailable" in first_response.json()["answer"]
    assert second_response.json()["answer"] == "a real answer once the LLM recovered"
    assert fake_llm.ask.call_count == 2


def test_rate_limit_still_applies_with_warm_cache(client, seed_user, fake_llm):
    """
    Repeated requests for the same question that are served from
    cache still count against the requesting user's rate limit, so a
    warm cache cannot be used to bypass the rate limiter by asking a
    single question in a tight loop.
    """
    seed_user(username="alice", password="password123", role=Role.user)
    token = _login(client, "alice", "password123")
    limit = get_settings().rate_limit_per_minute

    statuses = []
    for _ in range(limit + 5):
        response = client.post(
            "/chat",
            json={"question": "am i rate limited yet"},
            headers={"Authorization": f"Bearer {token}"},
        )
        statuses.append(response.status_code)

    assert fake_llm.ask.call_count == 1
    assert statuses.count(429) > 0
    assert statuses[-1] == 429
