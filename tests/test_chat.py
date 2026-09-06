from app.models.user import Role


def _login(client, username, password):
    response = client.post("/auth/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def test_chat_requires_auth(client):
    response = client.post("/chat", json={"question": "hello"})
    assert response.status_code == 401


def test_chat_success(client, seed_user, fake_llm):
    seed_user(username="alice", password="password123", role=Role.user)
    token = _login(client, "alice", "password123")

    response = client.post(
        "/chat",
        json={"question": "What is FastAPI?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "mocked answer"
    assert body["prompt_tokens"] == 5
    assert body["completion_tokens"] == 10
    fake_llm.ask.assert_called_once_with("What is FastAPI?")


def test_chat_forbidden_for_readonly(client, seed_user):
    seed_user(username="bob", password="password123", role=Role.readonly)
    token = _login(client, "bob", "password123")

    response = client.post(
        "/chat",
        json={"question": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_chat_falls_back_on_llm_error(client, seed_user, fake_llm):
    from app.services.llm_client import LLMResult

    seed_user(username="alice", password="password123", role=Role.user)
    token = _login(client, "alice", "password123")
    fake_llm.ask.return_value = LLMResult(
        answer="The AI service is temporarily unavailable. Please try again in a moment.",
        prompt_tokens=0,
        completion_tokens=0,
        is_fallback=True,
    )

    response = client.post(
        "/chat",
        json={"question": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "temporarily unavailable" in response.json()["answer"]
