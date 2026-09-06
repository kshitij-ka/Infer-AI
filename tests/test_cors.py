def test_no_cors_headers_when_no_origins_configured(client):
    """
    With no configured origins (the test environment default), a
    cross origin preflight request must not receive an
    Access-Control-Allow-Origin header, since the safe default is to
    allow no cross origin access rather than allow all origins.
    """
    response = client.options(
        "/chat",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_configured_origin_is_allowed(monkeypatch):
    """
    When CORS_ALLOWED_ORIGINS names an origin, a preflight request
    from that exact origin receives the matching
    Access-Control-Allow-Origin header.
    """
    import os

    os.environ["CORS_ALLOWED_ORIGINS"] = "https://app.example.com"

    from app.core.config import get_settings

    get_settings.cache_clear()

    import importlib

    from fastapi.testclient import TestClient

    import app.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as test_client:
        response = test_client.options(
            "/chat",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.headers["access-control-allow-origin"] == "https://app.example.com"

    del os.environ["CORS_ALLOWED_ORIGINS"]
    get_settings.cache_clear()
    importlib.reload(main_module)
