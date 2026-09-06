# Development

Commands for working on this codebase day to day. README.md covers running the application; this covers checking the code itself.

## Linting and formatting

```bash
ruff check app/ tests/ scripts/
ruff format app/ tests/ scripts/
```

## Type checking

```bash
mypy app/
```

## Unit tests

```bash
pytest tests/ -v
```

## Integration tests

```bash
docker compose up -d postgres redis
pytest tests/ -v
```

Both the unit tier and the integration tier run from the same command, `pytest tests/ -v`, since `tests/integration/` is a subdirectory of `tests/`. Without the containers running, the integration tests skip cleanly with a message naming which container to start; see docs/testing.md for the full explanation.

## Running everything before committing

```bash
ruff check app/ tests/ scripts/
ruff format app/ tests/ scripts/
mypy app/
docker compose up -d postgres redis
pytest tests/ -v
```

No CI pipeline is configured in this repository. These commands are what a CI workflow would run; adding one later is a matter of wiring these same commands into a workflow file, not redesigning anything.

