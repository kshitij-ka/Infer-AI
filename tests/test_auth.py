def test_login_success(client, seed_user):
    seed_user(username="alice", password="password123")

    response = client.post("/auth/login", json={"username": "alice", "password": "password123"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client, seed_user):
    seed_user(username="alice", password="password123")

    response = client.post("/auth/login", json={"username": "alice", "password": "wrong"})

    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post("/auth/login", json={"username": "ghost", "password": "whatever"})

    assert response.status_code == 401


def test_login_rejects_oversized_password(client, seed_user):
    """
    A password past bcrypt's 72-byte input ceiling must be rejected by
    schema validation (422), not reach verify_password and raise
    passlib's PasswordSizeError as an unhandled 500.
    """
    seed_user(username="alice", password="password123")

    response = client.post("/auth/login", json={"username": "alice", "password": "a" * 129})

    assert response.status_code == 422


def test_login_rejects_oversized_username(client):
    response = client.post("/auth/login", json={"username": "a" * 65, "password": "whatever"})

    assert response.status_code == 422
