from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, status

from .. import stats
from ..models import MetricType
from ..schemas import SampleSizeRequest, SampleSizeResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.post("/sample-size", response_model=SampleSizeResponse)
def sample_size(req: SampleSizeRequest):
    """How many users per variant are needed to detect the given effect."""
    try:
        if req.metric_type == MetricType.conversion:
            r = stats.sample_size_proportions(req.baseline, req.mde, req.mde_type, req.alpha, req.power)
        else:
            r = stats.sample_size_means(req.baseline, req.std_dev, req.mde, req.mde_type, req.alpha, req.power)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    days = math.ceil(r.total / req.daily_traffic * 10) / 10 if req.daily_traffic else None
    return SampleSizeResponse(**r.to_dict(), estimated_days=days)
