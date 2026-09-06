def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_metrics_exposes_prometheus_format(client, seed_user):
    """
    An admin can call GET /metrics and receive Prometheus formatted
    output. Metrics is restricted to admin role callers, so this test
    authenticates as an admin before calling it; see
    tests/test_metrics.py for the tests proving non-admin and
    unauthenticated callers are rejected.
    """
    from app.models.user import Role

    seed_user(username="admin", password="adminpass123", role=Role.admin)
    login_response = client.post(
        "/auth/login", json={"username": "admin", "password": "adminpass123"}
    )
    token = login_response.json()["access_token"]

    response = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
