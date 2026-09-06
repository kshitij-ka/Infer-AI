# Testing

This project has two test tiers.

## Unit tests (tests/)

Run with `pytest tests/ -v`. Uses an in memory SQLite database, fakeredis, and a mocked LLM client. No Docker or external service is required. This is the tier to run on every change, since it runs in under a few seconds.

## Integration tests (tests/integration/)

Run with `pytest tests/ -v` as well (this single command collects both tiers, see the note below on why). Before running it, start the real containers: `docker compose up -d postgres redis`. Uses the actual Postgres and Redis containers this application runs against in production, with a mocked LLM client (a real LLM call would be slow, flaky, cost money, and does not prove anything about database or Redis correctness). This tier catches what the unit tier cannot: the Postgres enum type for user roles behaving correctly, real Redis TTL and key expiry semantics, and the actual `DATABASE_URL` and `REDIS_URL` connection strings and drivers working, not their sqlite and fakeredis substitutes.

If Postgres or Redis are not running, the integration tier skips every test with a message naming which container to start, rather than failing with a raw connection error. 

## Running both

```bash
docker compose up -d postgres redis
pytest tests/ -v
```

Passing both `tests/` and `tests/integration/` on the same pytest command line does not work as one might expect: pytest deduplicates a nested path when its parent path is also given, so `pytest tests/ tests/integration/ -v` silently collects only the integration tier and drops the unit tier. Passing just `tests/ -v` collects both tiers correctly, since `tests/integration/` is a subdirectory of `tests/`.

## A note on the integration database

The integration tier connects to a database named `qa_api` with the same credentials this project's own `docker-compose.yml` sets up (`postgres`/`postgres`), on `localhost:5432`. This is safe as long as the only Postgres running on that port is the one this project's compose file started, since that container exists solely for this project and its tables are recreated and torn down by the test fixtures on every run. If a developer ever points `DATABASE_URL` at a different Postgres instance that happens to also have a database named `qa_api` with real data in it, running the integration tests would truncate and drop tables in that database. Do not run the integration tier against any Postgres instance other than this project's own `docker-compose.yml` containers. 

