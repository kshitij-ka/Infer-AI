# Infer AI

A small production-shaped FastAPI service that authenticates users via JWT, forwards questions to an LLM (Groq) with retry/timeout/ fallback handling, and persists chat history to PostgreSQL. Redis backs per-user rate limiting. Prometheus metrics and a health check are exposed for observability.

See [`docs/README.md`](docs/README.md) for an index of every document covering this project's design and hardening.

See [`docs/architecture.md`](docs/architecture.md) for the full architecture diagram, RBAC/SSO extension notes, and the scaling/migration write-ups.

## Endpoints

| Method | Path          | Description                                  |
|--------|---------------|-----------------------------------------------|
| POST   | `/auth/login` | Exchange username/password for a JWT (rate limited) |
| POST   | `/chat`       | Ask a question (requires `Authorization: Bearer <token>`, cached, rate limited) |
| POST   | `/admin/users`| Create a user with a chosen role (admin role only) |
| GET    | `/health`     | DB + Redis connectivity check                  |
| GET    | `/metrics`    | Prometheus metrics (latency, token usage, request counts, admin role only) |

## Running with Docker Compose

1. Copy the example environment file and fill in a real Groq API key and a random JWT secret:

   ```bash
   cp .env.example .env
   ```

2. Start the stack (API + PostgreSQL + Redis):

   ```bash
   docker compose up --build
   ```

   The API container runs `alembic upgrade head` on startup before serving traffic, so the `users` and `chat_logs` tables are created automatically.

3. The API is available at `http://localhost:8000`. No users exist yet, see "Creating the first admin user" below, since user registration is out of scope for this assessment.

## Creating the first admin user

There is no open registration endpoint (out of scope for an internal QA tool, and covered in docs/security.md). Create the first admin with the seed script:

```bash
docker compose exec -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD=changeme123 api \
  python -m scripts.seed_admin
```

Every other user, of any role, is created by an admin through the API:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "changeme123"}'
# use the returned access_token below

curl -X POST http://localhost:8000/admin/users \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "password123", "role": "user"}'
```

## Local development (without Docker)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point DATABASE_URL/REDIS_URL at local instances, or use sqlite for quick testing
uvicorn app.main:app --reload
```

## Running tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

Tests use an in-memory SQLite database, `fakeredis`, and a mocked LLM client, so no external services or API keys are required to run the suite. See docs/testing.md for the second, Docker backed integration test tier.

## Configuration

All configuration is environment-based (see `.env.example`); no secrets are hard-coded. Key variables:

- `JWT_SECRET_KEY`: HMAC secret for signing JWTs, at least 32 characters
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `GROQ_API_KEY`, `GROQ_MODEL`: LLM provider credentials/model
- `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`: retry/timeout tuning for LLM calls
- `RATE_LIMIT_PER_MINUTE`, `LOGIN_RATE_LIMIT_PER_MINUTE`: per user chat and
  login rate limits
- `IP_ONLY_LOGIN_RATE_LIMIT_PER_MINUTE`: a coarser, per client IP login
  rate limit that runs before the request body is parsed, closing a
  bypass where a malformed login request skipped the per account limit
  above
- `CACHE_TTL_SECONDS`: how long a cached chat answer stays valid
- `CORS_ALLOWED_ORIGINS`: comma separated list of allowed origins, empty by
  default (no cross origin access), a literal `*` is rejected at startup
- `MAX_REQUEST_BODY_BYTES`: maximum accepted request body size

See docs/security.md for the reasoning behind each of these.

## Project layout

```
app/
  main.py            FastAPI app, middleware registration, /health, /metrics
  core/              settings, JWT + password hashing, security headers,
                     body size limit, structured logging with request id
  api/routes/        auth, chat, admin route handlers
  api/deps.py        FastAPI dependencies (DB session, current user, RBAC)
  models/            SQLAlchemy models (User, ChatLog)
  schemas/           Pydantic request/response models
  services/          LLM client (retry/fallback), Redis rate limiter and
                     cache, Prometheus metrics
alembic/             Database migrations
scripts/             One time admin seed script
tests/               Unit test suite (sqlite + fakeredis + mocked LLM)
tests/integration/   Integration test suite (real Postgres + Redis, mocked LLM)
docs/                Architecture, security, admin, observability, testing,
                     and development documentation; see docs/README.md
```
