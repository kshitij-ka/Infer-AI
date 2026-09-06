# Observability

This covers the three related pieces that let an operator see what this application is doing: structured logging, Prometheus metrics, and the health check.

## Structured logging

`app/core/logging.py` replaces the default plain text log format with single line JSON records, each carrying a timestamp, level, message, logger name, and request id. JSON output means logs can be shipped to any log aggregator (a container's stdout is captured by the platform regardless of format, but JSON means the aggregator can index and query fields instead of treating each line as opaque text).

Every request gets a UUID, assigned by `RequestIdMiddleware`, held in a context variable for the duration of that request, included in every log line emitted while handling it, and returned to the client as the `X-Request-ID` response header. A user reporting an issue can hand back that header value, and an operator can grep logs for that exact id to see everything that happened while handling that one request, without needing to correlate by timestamp alone.

The per request summary line (`app/core/logging.py`) includes `request.url.path`. This is safe today because no route in this application has path parameters or accepts credentials via query string, every route takes its data through a JSON request body, so the path is always one of a small fixed set of literal strings. This is a "true today" fact about the current route table, not a structural guarantee enforced by the logging code itself. Any future route that adds a path parameter (for example `/users/{user_id}` carrying a token, or a query string carrying sensitive data) would need to account for this before that route ships, either by keeping sensitive values out of the path and query string entirely or by sanitizing `request.url.path` before it reaches this log line. 

## Metrics

`GET /metrics` exposes Prometheus text format metrics, defined in `app/services/metrics.py`:

- `chat_request_latency_ms`, a histogram of `/chat` request latency.
- `chat_token_usage_total`, a counter of prompt and completion tokens, labeled by type.
- `chat_requests_total`, a counter of `/chat` requests labeled by status (`ok`, `fallback`, or `cache_hit`), so an operator can see the fallback rate (how often the LLM is failing) and the cache hit rate (how often repeated questions are being served without a real LLM call) as separate signals from the same counter.

## Health check

`GET /health` checks database and Redis connectivity and returns `{"status": "ok" | "degraded", "checks": {...}}`. This is meant to back an orchestrator's liveness or readiness probe: a degraded result should remove the instance from load balancer rotation rather than crash the process, since a transient Redis blip does not mean the instance cannot serve any traffic (read only routes would still work, for example), just that specific dependent features are unavailable.

## What this does not cover

- No log aggregation service is deployed (Prometheus itself is not deployed either; `/metrics` is the scrape target a real deployment would point a Prometheus server at). Both are out of scope for this assessment's repository, which provides the endpoints a production deployment would wire up.
- No distributed tracing (OpenTelemetry spans across service boundaries). This application is a single service; the request id approach here covers tracing within one request's handling, which is what a single service needs.

