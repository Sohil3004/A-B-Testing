"""Vercel Serverless entrypoint for the ExperimentIQ FastAPI backend."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("VERCEL", "1")

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app, ensure_bootstrapped  # noqa: E402

ensure_bootstrapped()

__all__ = ["app"]
