from app.models.user import Role


def _login(client, username, password):
    response = client.post("/auth/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def test_unauthenticated_cannot_access_metrics(client):
    """A request with no token at all is rejected from GET /metrics."""
    response = client.get("/metrics")
    assert response.status_code == 401


def test_non_admin_user_cannot_access_metrics(client, seed_user):
    """A regular "user" role account gets 403 from GET /metrics."""
    seed_user(username="alice", password="password123", role=Role.user)
    token = _login(client, "alice", "password123")

    response = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_readonly_user_cannot_access_metrics(client, seed_user):
    """A readonly role account gets 403 from GET /metrics."""
    seed_user(username="bob", password="password123", role=Role.readonly)
    token = _login(client, "bob", "password123")

    response = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_admin_can_access_metrics(client, seed_user):
    """An admin role account can call GET /metrics and gets Prometheus output."""
    seed_user(username="admin", password="adminpass123", role=Role.admin)
    token = _login(client, "admin", "adminpass123")

    response = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
