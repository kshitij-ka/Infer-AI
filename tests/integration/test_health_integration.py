def test_health_reports_ok_against_real_containers(integration_client):
    """
    Against the real Postgres and Redis containers, health check
    reports ok for both, proving the app's actual connection strings
    and driver configuration work, not just the sqlite and fakeredis
    substitutes the unit tests use.
    """
    response = integration_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"
