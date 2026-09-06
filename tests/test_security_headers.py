def test_response_includes_security_headers(client):
    """
    Every response, including error responses, must carry the
    baseline security headers so a browser or intermediary enforces
    them regardless of which route answered the request.
    """
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in response.headers
