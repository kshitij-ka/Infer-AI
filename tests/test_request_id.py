def test_response_includes_request_id_header(client):
    """
    Every response carries an X-Request-ID header, so a client
    reporting an issue can hand back an identifier that traces to
    the matching server side log line.
    """
    response = client.get("/health")

    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_two_requests_get_different_request_ids(client):
    """Each request gets its own unique request id."""
    first = client.get("/health")
    second = client.get("/health")

    assert first.headers["x-request-id"] != second.headers["x-request-id"]
