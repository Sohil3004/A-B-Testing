from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_api_key
from .config import get_settings
from .db import init_db
from .routers import experiments, stats, tracking

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ExperimentIQ API",
    description="A/B testing platform: deterministic assignment, event logging and a "
                "SciPy-verified statistics engine.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

protected = [Depends(require_api_key)]
for r in (experiments.router, tracking.router, stats.router):
    app.include_router(r, prefix="/api/v1", dependencies=protected)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
