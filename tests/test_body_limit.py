def test_oversized_request_body_is_rejected(client):
    """
    A request body larger than the configured limit must be rejected
    with 413, before it reaches route handler validation, so a large
    payload cannot consume memory or CPU parsing it as JSON first.
    """
    oversized_question = "a" * 100_000
    response = client.post(
        "/chat",
        json={"question": oversized_question},
    )

    assert response.status_code == 413
