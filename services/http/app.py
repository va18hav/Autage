import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.config import settings
from services.db.database import get_db_session
from services.http.auth import get_current_user
from services.http.csrf import require_csrf
from services.http.routes.auth import router as auth_router
from services.http.routes.webhook import router as webhook_router
from services.http.routes.incident import router as incident_router
from services.http.routes.runbook import router as runbook_router
from services.http.routes.settings import router as settings_router

logger = logging.getLogger("autage.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(settings.REDIS_URL, decode_responses=False)

    yield

    await app.state.redis.aclose()



app = FastAPI(
    title="Autage",
    description="Autonomous agentic SRE copilot",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(
    incident_router,
    dependencies=[Depends(get_current_user), Depends(require_csrf)],
)
app.include_router(
    runbook_router,
    dependencies=[Depends(get_current_user), Depends(require_csrf)],
)
app.include_router(
    settings_router,
    dependencies=[Depends(get_current_user), Depends(require_csrf)],
)


@app.get("/health", tags=["Meta"])
async def health(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    checks = {
        "status": "ok",
        "postgres": "ok",
        "redis": "ok",
    }

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Postgres health check failed")
        checks["postgres"] = "error"

    try:
        await request.app.state.redis.ping()
    except Exception:
        logger.exception("Redis health check failed")
        checks["redis"] = "error"

    if checks["postgres"] == "error" or checks["redis"] == "error":
        checks["status"] = "degraded"
        return JSONResponse(status_code=503, content=checks)

    return checks