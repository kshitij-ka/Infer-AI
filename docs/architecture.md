# Architecture

## 1. System diagram (as implemented + target production shape)

![[Architecture Diagram.png|700]]


`/metrics` exposes Prometheus counters/histograms (latency, token usage, request outcome) scraped by a Prometheus server; `/health` checks DB and Redis connectivity so the load balancer / orchestrator can evict unhealthy instances.

## 2. Authentication & Authorization

**Implemented now:** JWT auth (`/auth/login` issues an HS256-signed token with `sub` and `role` claims; `/chat` and other protected routes verify it via a FastAPI dependency). Passwords are bcrypt-hashed. A `require_role()` dependency enforces RBAC at the route level.

**Production SSO/OIDC extension:**

```
Application -> OAuth2/OIDC -> Identity Provider (Okta/Auth0/Azure AD)
           -> IdP issues signed JWT (or opaque token + introspection)
           -> API Gateway validates token (JWKS) at the edge
           -> AI Service trusts the gateway-forwarded, pre-validated identity
```

- The app stops minting its own tokens and instead validates tokens issued by the IdP, fetching signing keys from the IdP's JWKS endpoint (cached, rotated periodically) instead of a static shared secret.
- An API Gateway (Kong, AWS API Gateway, Envoy) sits in front of FastAPI and can terminate auth centrally, rejecting invalid tokens before they reach application pods, reducing load and centralizing policy.
- Role/permission claims come from the IdP (groups/roles mapped via SCIM or custom claims) rather than being stored only in the app DB, so RBAC stays consistent across every service that trusts the same IdP.

**RBAC roles:**

| Role      | Permissions |
|-----------|-------------|
| Admin     | Manage users/config, view `/metrics`, full `/chat` access |
| User      | `/chat` access only |
| Read-only | View permitted historical reports/chat logs, no new `/chat` calls |

This is enforced today via the `Role` enum on `User` plus `require_role()`, in production the same enum would map to IdP group claims.

## 3. Scaling to 100->500 RPS

- **Horizontal scaling:** FastAPI is stateless (auth is JWT, no server-side sessions) so instances scale out behind a load balancer with zero coordination. Multiple Uvicorn workers per pod plus multiple pods.
- **Load balancing:** L7 load balancer (ALB/NGINX/Kubernetes Service) with active health checks against `/health`; unhealthy pods are removed from rotation automatically.
- **Kubernetes HPA:** Scale pod replicas on CPU/memory or a custom metric (e.g. in-flight requests or queue depth from Redis) so capacity tracks the 100->500 RPS swing without manual intervention.
- **Redis:** Used for (a) distributed rate limiting so limits hold across many pods instead of per-process counters, and (b) optionally caching identical/frequent question->answer pairs to cut redundant LLM calls.
- **Background queues:** Slow LLM calls should not block a request thread indefinitely. For latency-tolerant use cases, `/chat` could enqueue a job (Celery/RQ backed by Redis) and return a job id immediately, with a separate `GET /chat/{id}` polling/streaming endpoint. This assessment's `/chat` is synchronous for simplicity, but the queue is where it would extend under real load.
- **Rate limiting:** Per-user fixed-window limiter (implemented in `app/services/cache.py`) protects both the app and the upstream LLM provider from being overwhelmed by a single client.
- **LLM API limits (RPM/TPM/concurrency):** A semaphore or token-bucket in the LLM gateway layer caps concurrent outbound calls to stay under the provider's RPM/TPM ceiling; requests beyond that queue or get a fast 429 rather than piling up and timing out.
- **Concurrent requests:** FastAPI's async model plus multiple worker processes handles many simultaneous in-flight LLM calls without blocking on I/O; the LLM client's own timeout bounds worst-case thread occupancy.
- **Failure recovery:** `tenacity`-based retry with exponential backoff for transient LLM errors, a hard timeout per call, and a canned fallback answer when retries are exhausted, so a single failing dependency degrades gracefully instead of cascading into 500s across the app.

## 4. Migration: single EC2 -> 10,000-user production system

**Target:**
```
Users -> Load Balancer -> Kubernetes/ECS (FastAPI pods, HPA)
      -> Redis (rate limit/cache) + Queue (async LLM jobs)
      -> LLM Gateway -> LLM APIs
      -> PostgreSQL (managed, e.g. RDS)
```

- **Scaling the application:** Containerize the app (already done here) and move it onto an orchestrator (EKS/ECS) so it can run N replicas behind a load balancer instead of one EC2 box. HPA scales replicas with demand.
- **LLM API limits:** Centralize all LLM calls through a single "LLM gateway" layer that enforces provider RPM/TPM/concurrency limits, so scaling FastAPI pods doesn't accidentally multiply outbound request rate past what the provider allows.
- **Slow/failing LLM requests:** Per-call timeout + bounded retries with backoff + fallback response (as implemented), and circuit-breaking if the provider is down for an extended window, so the app fails fast instead of piling up hung requests that exhaust worker threads.
- **Redis and queues:** Redis for distributed rate limiting/caching, a queue (Celery/RQ/SQS) for any LLM call expected to be slow, so the web tier stays responsive and a worker pool absorbs backpressure.
- **Retries/timeouts/fallbacks:** Same pattern as above, retry transient errors, cap wait time, return a degraded-but-valid response rather than an unhandled exception when everything fails.
- **Monitoring:** `/metrics` (Prometheus) for latency/token/error-rate, scraped and visualized in Grafana; alerts on error rate, p95 latency, and LLM fallback rate; structured logs shipped to a central log store; `/health` wired into orchestrator liveness/readiness probes.
- **Handling failures:** Multiple replicas + orchestrator self-healing (restart crashed pods) removes the single-point-of-failure the EC2 box represents today, a managed Postgres (RDS) with automated backups/failover removes the DB as a single point of failure too.
- **Migrating with minimal downtime:** Stand up the containerized stack alongside the existing EC2 app, point a fraction of traffic at it via the load balancer (canary/blue-green), validate metrics/error rates, then shift traffic over fully and decommission the EC2 instance. Database migration uses Alembic migrations applied ahead of cutover against the new managed Postgres instance, with data backfilled/replicated before the switch.
- **Secrets/configuration:** No secrets in code or images, all configuration (DB URL, Redis URL, JWT secret, LLM API key) comes from environment variables (`.env` locally, a secrets manager such as AWS Secrets Manager / Kubernetes Secrets in production), matching the `pydantic-settings`-based config already used in this app.

## Trade-offs

- **Synchronous `/chat` vs. queue-based:** Chose synchronous for this assessment's scope (simplicity, easy to test end-to-end); the design above shows where a queue would be introduced for genuinely long-running work without changing the public contract much (`/chat` could return a job id under load).
- **Fixed-window rate limiting vs. sliding window/token bucket:** Fixed window (Redis `INCR` + `EXPIRE`) is simpler and sufficiently accurate for this scale, a sliding window or token bucket would smooth boundary bursts at the cost of more Redis operations per request.
- **JWT with a shared secret vs. OIDC now:** A shared-secret JWT is enough to demonstrate the auth flow required by the assessment, production would move validation to an IdP's JWKS as described above rather than trusting a single static secret.


