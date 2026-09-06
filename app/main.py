import logging

from fastapi import Depends, FastAPI, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_redis
from app.api.routes import auth, chat
from app.core.config import get_settings
from app.db.session import get_db
from app.services.metrics import render_metrics

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(title=settings.app_name)

app.include_router(auth.router)
app.include_router(chat.router)


@app.get("/health")
def health(db: Session = Depends(get_db), redis_client=Depends(get_redis)) -> dict:
    checks = {"database": "ok", "redis": "ok"}

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"

    try:
        redis_client.ping()
    except Exception:
        checks["redis"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


@app.get("/metrics")
def metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)
