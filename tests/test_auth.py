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
