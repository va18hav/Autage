from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from arq import create_pool
from arq.connections import RedisSettings

from services.config import settings
from services.http.routes.webhook import router as webhook_router
from services.http.routes.incident import router as incident_router


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(incident_router)


@app.get("/health", tags=["Meta"])
async def health():
    return {"status": "ok"}