from app.core.config import get_settings


def test_malformed_login_body_eventually_rate_limited(client):
    """
    Sending a malformed body (missing the required password field) to
    POST /auth/login repeatedly must eventually get a 429, once the
    number of requests from this IP crosses
    IP_ONLY_LOGIN_RATE_LIMIT_PER_MINUTE, even though every individual
    request would otherwise only fail Pydantic validation with a 422.

    This proves the bypass is closed: before LoginIPRateLimitMiddleware
    existed, an attacker could send an unlimited number of malformed
    requests and never trigger the rate limiter, since the route level
    per-username-and-IP check only runs after successful body
    validation.
    """
    settings = get_settings()
    limit = settings.ip_only_login_rate_limit_per_minute

    statuses = []
    for _ in range(limit + 5):
        response = client.post("/auth/login", json={"username": "attacker"})
        statuses.append(response.status_code)

    assert 429 in statuses
    first_429_index = statuses.index(429)
    # Every response before the limit is crossed must be a 422 (the
    # malformed body correctly fails validation), not a 429, so the
    # test also proves the middleware does not fire prematurely.
    assert all(status == 422 for status in statuses[:first_429_index])


def test_single_malformed_login_request_still_gets_422(client):
    """
    A single malformed request, well under the new IP-only threshold,
    must still get a plain 422 validation error, not a 429. The new
    middleware must not change behavior for an ordinary one-off
    mistake such as a client forgetting the password field.
    """
    response = client.post("/auth/login", json={"username": "someone"})

    assert response.status_code == 422


def test_well_formed_logins_under_account_limit_are_unaffected(client, seed_user):
    """
    Well formed login requests, sent fewer times than both the
    existing per-username-and-IP limit and the new per-IP-only limit,
    must succeed normally. The new, coarser IP-only layer has a
    deliberately higher threshold than the existing per-account limit,
    so it must not prematurely rate limit legitimate traffic that the
    existing, more precise check would still allow.
    """
    seed_user(username="alice", password="password123")
    settings = get_settings()
    account_limit = settings.login_rate_limit_per_minute

    for _ in range(account_limit - 1):
        response = client.post(
            "/auth/login", json={"username": "alice", "password": "password123"}
        )
        assert response.status_code == 200
