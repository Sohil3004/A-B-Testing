from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from .auth import require_api_key  # noqa: E402
from .config import get_settings  # noqa: E402
from .db import SessionLocal, init_db  # noqa: E402
from .models import Experiment  # noqa: E402
from .routers import experiments, stats, tracking  # noqa: E402

settings = get_settings()
_bootstrapped = False


def ensure_bootstrapped() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    init_db()
    if os.getenv("VERCEL") or os.getenv("AUTO_SEED") == "1":
        try:
            with SessionLocal() as db:
                count = db.scalar(select(func.count()).select_from(Experiment)) or 0
            if count == 0:
                from simulator.simulate import run_direct

                run_direct(scale=0.05, reset=False, seed=2026)
        except Exception as exc:
            print(f"[ExperimentIQ] Auto-seed warning: {exc}", file=sys.stderr)
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


@app.middleware("http")
async def bootstrap_middleware(request: Request, call_next):
    if not _bootstrapped:
        ensure_bootstrapped()
    return await call_next(request)


protected = [Depends(require_api_key)]
for r in (experiments.router, tracking.router, stats.router):
    app.include_router(r, prefix="/api/v1", dependencies=protected)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
