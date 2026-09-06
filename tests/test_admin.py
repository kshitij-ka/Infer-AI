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


def test_readonly_cannot_create_user(client, seed_user):
    """A readonly user gets 403 when attempting to create a user."""
    seed_user(username="bob", password="password123", role=Role.readonly)
    token = _login(client, "bob", "password123")

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


def test_invalid_password_length_does_not_echo_password_in_response(client, seed_user):
    """
    Submitting a password that fails the min_length validation must not
    cause the plaintext password to appear anywhere in the 422 response
    body. FastAPI's default RequestValidationError handler echoes the
    raw "input" value for a failed field, which would leak the
    submitted password verbatim. This test proves the sanitization in
    app/main.py's handle_request_validation_error removes that leak,
    while still telling the client that the password field is the
    problem and why.
    """
    seed_user(username="admin", password="adminpass123", role=Role.admin)
    token = _login(client, "admin", "adminpass123")

    submitted_password = "wxy12"
    response = client.post(
        "/admin/users",
        json={"username": "newuser", "password": submitted_password, "role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    body = response.json()

    # The submitted password must not appear anywhere in the response body.
    assert submitted_password not in response.text

    # The response must still usefully communicate what went wrong.
    errors = body["detail"]
    assert isinstance(errors, list)
    password_errors = [e for e in errors if e.get("loc", [])[-1:] == ["password"]]
    assert len(password_errors) == 1
    password_error = password_errors[0]
    assert "input" not in password_error
    assert "min_length" in str(password_error.get("ctx", "")) or "at least 8" in (
        password_error.get("msg", "")
    )
    assert "password" in str(password_error["loc"])


def test_invalid_username_length_still_echoes_input(client, seed_user):
    """
    Non-sensitive fields (such as username) are not security sensitive
    to echo back, and doing so is useful for debugging, so the
    sanitization must be scoped only to the password field and must not
    strip "input" from other fields' validation errors.
    """
    seed_user(username="admin", password="adminpass123", role=Role.admin)
    token = _login(client, "admin", "adminpass123")

    response = client.post(
        "/admin/users",
        json={"username": "ab", "password": "password123", "role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    body = response.json()
    errors = body["detail"]
    username_errors = [e for e in errors if e.get("loc", [])[-1:] == ["username"]]
    assert len(username_errors) == 1
    assert username_errors[0]["input"] == "ab"
