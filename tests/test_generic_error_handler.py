def test_unhandled_exception_returns_generic_body(client, monkeypatch):
    """
    An unexpected exception inside a route must never return its
    message or type to the client, since exception text can leak
    internal file paths, query structure, or library versions.
    """
    from app.api.deps import get_db

    def broken_get_db():
        raise RuntimeError("simulated database connection failure with internal detail")
        yield  # pragma: no cover

    client.app.dependency_overrides[get_db] = broken_get_db

    response = client.get("/health")

    assert response.status_code == 500
    body = response.json()
    assert "simulated database connection failure" not in str(body)
    assert body == {"detail": "Internal server error"}


def test_unhandled_exception_response_includes_security_headers(client):
    """
    The generic 500 response for an unhandled exception must still
    carry the baseline security headers, since
    SecurityHeadersMiddleware is built on BaseHTTPMiddleware and never
    receives a Response object to stamp headers onto when call_next
    raises, so the headers have to be set directly on the error
    handler's own response instead.
    """
    from app.api.deps import get_db

    def broken_get_db():
        raise RuntimeError("simulated database connection failure with internal detail")
        yield  # pragma: no cover

    client.app.dependency_overrides[get_db] = broken_get_db

    response = client.get("/health")

    assert response.status_code == 500
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in response.headers
