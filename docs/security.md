# Security

This document explains every security hardening measure in this application, why it exists, and what it does not cover.

## Response headers

Every response carries these headers, set by `app/core/middleware.py`:

- `X-Content-Type-Options: nosniff` stops a browser from guessing a different content type than what the server declared, which prevents a JSON response from being reinterpreted as HTML or JavaScript.
- `X-Frame-Options: DENY` stops the API from being loaded inside an iframe, which is not a legitimate use case for a JSON API and closes off clickjacking against any accidentally browser rendered error page.
- `Referrer-Policy: no-referrer` stops the browser from sending this API's URLs, which can contain no sensitive query parameters today but might in the future, to other sites in the Referer header.
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` denies loading any script, style, or frame, since this server never returns HTML and has nothing that needs a content source allowed.

## CORS

`CORS_ALLOWED_ORIGINS` is a comma separated list of allowed origins. An empty value, the default, allows no cross origin requests at all. This is deliberate: a wildcard origin on an API that accepts a bearer token in a header is not directly exploitable through CORS alone (CORS does not bypass the Authorization header requirement), but an explicit allowlist is still safer than an open default, since it means only origins the operator has actually approved can read response bodies from a browser context.

## Request body size limit

`MAX_REQUEST_BODY_BYTES` (default 65536) bounds the size of any request body. A request whose Content-Length exceeds this value is rejected with 413 before the body is read, so an attacker cannot force the server to spend memory or CPU time parsing an oversized payload.

## Generic error responses

Any exception not handled by a specific route gets caught by a global handler in `app/main.py` that logs the full exception server side and returns a fixed body, `{"detail": "Internal server error"}`, with no exception message, type, or traceback. This stops an attacker from learning internal file paths, library versions, or query structure from an error response.

## JWT secret strength

`JWT_SECRET_KEY` must be at least 32 characters, enforced by a Pydantic validator in `app/core/config.py`. The application refuses to start with a shorter secret rather than accepting one and being vulnerable to offline brute force against a captured token signature.

## Non root container user

The Docker image runs the application process as `appuser`, created in the Dockerfile, rather than root. A container escape or arbitrary code execution vulnerability in a dependency then does not hand an attacker root inside the container.

## What this does not cover

- No refresh token rotation or token revocation list. A compromised JWT remains valid until it expires (60 minutes by default). A production deployment handling higher value data would add a revocation list in Redis, checked on every request.
- No separate audit log of authentication events beyond what the structured logging feature (see docs/observability.md) captures in the general request log.
- No per route Content-Security-Policy tuning, since every route returns JSON and the same deny by default policy applies to all of them.
- No automated dependency vulnerability scanning in CI, since no CI system exists in this repository yet.

