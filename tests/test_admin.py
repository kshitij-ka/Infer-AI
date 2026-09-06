from app.models.user import Role


def _login(client, username, password):
    response = client.post("/auth/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def test_non_admin_cannot_create_user(client, seed_user):
    """A regular user gets 403 when attempting to create a user."""
    seed_user(username="alice", password="password123", role=Role.user)
    token = _login(client, "alice", "password123")

    response = client.post(
        "/admin/users",
        json={"username": "newuser", "password": "password123", "role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_can_create_user(client, seed_user):
    """An admin can create a new user with a chosen role."""
    seed_user(username="admin", password="adminpass123", role=Role.admin)
    token = _login(client, "admin", "adminpass123")

    response = client.post(
        "/admin/users",
        json={"username": "newuser", "password": "password123", "role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newuser"
    assert body["role"] == "user"
    assert "password" not in body
    assert "hashed_password" not in body


def test_admin_cannot_create_duplicate_username(client, seed_user):
    """Creating a user with an existing username returns 409."""
    seed_user(username="admin", password="adminpass123", role=Role.admin)
    seed_user(username="existing", password="password123", role=Role.user)
    token = _login(client, "admin", "adminpass123")

    response = client.post(
        "/admin/users",
        json={"username": "existing", "password": "password123", "role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
