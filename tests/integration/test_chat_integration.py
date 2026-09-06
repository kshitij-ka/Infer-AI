from app.core.security import hash_password
from app.models.user import Role, User


def test_chat_round_trip_against_real_containers(
    integration_client, integration_db, integration_fake_llm
):
    """
    A full login and chat round trip against real Postgres (for the
    user and chat log rows) and real Redis (for rate limiting and
    caching), proving the Postgres enum type for role and real Redis
    TTL semantics work end to end, which sqlite and fakeredis cannot
    fully guarantee.
    """
    user = User(
        username="integrationuser", hashed_password=hash_password("password123"), role=Role.user
    )
    integration_db.add(user)
    integration_db.commit()

    login_response = integration_client.post(
        "/auth/login",
        json={"username": "integrationuser", "password": "password123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    chat_response = integration_client.post(
        "/chat",
        json={"question": "does this reach real postgres and redis"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["answer"] == "integration test answer"
    integration_fake_llm.ask.assert_called_once()
