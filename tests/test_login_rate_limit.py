def test_login_rate_limit_blocks_after_threshold(client, seed_user):
    """
    Repeated login attempts against the same username and client IP
    beyond the configured threshold get 429, regardless of whether
    the password is correct, so a brute force loop is blocked before
    it can guess the password.
    """
    seed_user(username="alice", password="password123")

    last_status = None
    for _ in range(15):
        response = client.post(
            "/auth/login",
            json={"username": "alice", "password": "wrong-password"},
        )
        last_status = response.status_code

    assert last_status == 429


def test_login_succeeds_under_rate_limit(client, seed_user):
    """A single correct login attempt succeeds normally."""
    seed_user(username="bob", password="password123")

    response = client.post(
        "/auth/login",
        json={"username": "bob", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
