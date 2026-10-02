from contextlib import asynccontextmanager
from fastapi import FastAPI
from arq import create_pool
from arq.connections import RedisSettings

from services.config import settings
from services.http.routes.webhook import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    
    yield

    await app.state.arq_pool.aclose()


app = FastAPI(
    title="Autage",
    description="Autonomous agentic SRE copilot",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)


@app.get("/health", tags=["Meta"])
async def health():
    return {"status": "ok"}