import asyncio

import httpx
import pytest


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


def test_malformed_content_length_is_rejected(client):
    """
    A request with a non-numeric Content-Length header must be rejected
    with 400 before parsing, rather than crashing the middleware.
    """
    response = client.post(
        "/chat",
        content='{"question":"test"}',
        headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Content-Length header"}


@pytest.mark.asyncio
async def test_chunked_body_without_content_length_is_rejected():
    """
    A request sent with chunked transfer encoding (no Content-Length
    header at all) that streams more bytes than the configured limit
    must still be rejected with 413, proving the limit is enforced by
    counting actual received bytes rather than trusting a header that
    can be absent or dishonest.
    """
    from app.main import app

    async def oversized_chunk_generator():
        chunk = b"a" * 8192
        for _ in range(20):
            yield chunk
            await asyncio.sleep(0)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        response = await async_client.post(
            "/chat",
            content=oversized_chunk_generator(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer not-a-real-token",
            },
        )

    assert "content-length" not in response.request.headers
    assert response.status_code == 413
