from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from .auth import require_api_key
from .config import get_settings
from .db import SessionLocal, init_db
from .models import Experiment
from .routers import experiments, stats, tracking

settings = get_settings()
_bootstrapped = False


def ensure_bootstrapped() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    init_db()
    if os.getenv("VERCEL") or os.getenv("AUTO_SEED") == "1":
        with SessionLocal() as db:
            count = db.scalar(select(func.count()).select_from(Experiment)) or 0
        if count == 0:
            from simulator.simulate import run_direct

            run_direct(scale=0.1, reset=False, seed=2026)
    _bootstrapped = True


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_bootstrapped()
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


if os.getenv("VERCEL"):
    ensure_bootstrapped()
