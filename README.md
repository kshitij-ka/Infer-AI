# AI Question-Answering API

A small production-shaped FastAPI service that authenticates users via JWT, forwards questions to an LLM (Groq, OpenAI-compatible API) with retry/timeout/ fallback handling, and persists chat history to PostgreSQL. Redis backs per-user rate limiting. Prometheus metrics and a health check are exposed for observability.

## Endpoints

| Method | Path          | Description                                  |
|--------|---------------|-----------------------------------------------|
| POST   | `/auth/login` | Exchange username/password for a JWT          |
| POST   | `/chat`       | Ask a question (requires `Authorization: Bearer <token>`) |
| GET    | `/health`     | DB + Redis connectivity check                  |
| GET    | `/metrics`    | Prometheus metrics (latency, token usage, request counts) |

## Running with Docker Compose

1. Copy the example environment file and fill in a real Groq API key and a random JWT secret:

   ```bash
   cp .env.example .env
   ```

2. Start the stack (API + PostgreSQL + Redis):

   ```bash
   docker compose up --build
   ```

   The API container runs `alembic upgrade head` on startup before serving
   traffic, so the `users` and `chat_logs` tables are created automatically.

3. The API is available at `http://localhost:8000`. No users exist yet, insert one directly (see "Creating a user" below) since user registration is out of scope for this assessment.

## Creating a user

There is no `/auth/register` endpoint.  Create a user directly against the running Postgres container:

```bash
docker compose exec api python - <<'EOF'
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models.user import User, Role

db = SessionLocal()
db.add(User(username="alice", hashed_password=hash_password("password123"), role=Role.user))
db.commit()
EOF
```

Then log in:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "password123"}'
```

And call `/chat` with the returned token:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is FastAPI?"}'
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

Tests use an in-memory SQLite database, `fakeredis`, and a mocked LLM client, no external services or API keys are required to run the suite.

## Configuration

All configuration is environment-based (see `.env.example`); no secrets are
hard-coded. Key variables:

- `JWT_SECRET_KEY` — HMAC secret for signing JWTs
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `GROQ_API_KEY`, `GROQ_MODEL` — LLM provider credentials/model
- `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` — retry/timeout tuning for LLM calls
- `RATE_LIMIT_PER_MINUTE` — per-user `/chat` rate limit

## Project layout

```
app/
  main.py            FastAPI app, /health, /metrics
  core/              settings, JWT + password hashing
  api/routes/        auth, chat route handlers
  api/deps.py        FastAPI dependencies (DB session, current user, RBAC)
  models/            SQLAlchemy models (User, ChatLog)
  schemas/           Pydantic request/response models
  services/          LLM client (retry/fallback), Redis rate limiter, metrics
alembic/             Database migrations
tests/               Pytest suite (sqlite + fakeredis + mocked LLM)
docs/architecture.md Architecture diagram, RBAC/SSO, scaling & migration notes
```
