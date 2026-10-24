from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import ExperimentStatus, MetricType

KEY_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
EVENT_PATTERN = r"^[A-Za-z0-9_.:-]{1,64}$"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:64] or "experiment"


# --------------------------------------------------------------------------- #
# Experiments
# --------------------------------------------------------------------------- #
class VariantIn(BaseModel):
    key: str = Field(pattern=KEY_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    weight: float = Field(gt=0, le=1)
    is_control: bool = False


def _default_variants() -> list[VariantIn]:
    return [
        VariantIn(key="control", name="Control", weight=0.5, is_control=True),
        VariantIn(key="treatment", name="Treatment", weight=0.5),
    ]


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    key: str | None = Field(default=None, pattern=KEY_PATTERN)
    description: str = ""
    hypothesis: str = ""
    metric_type: MetricType = MetricType.conversion
    metric_event: str = Field(pattern=EVENT_PATTERN, examples=["purchase"])
    traffic_allocation: float = Field(default=1.0, gt=0, le=1)
    alpha: float = Field(default=0.05, ge=0.001, le=0.2)
    power: float = Field(default=0.8, ge=0.5, le=0.99)
    mde: float = Field(default=0.10, gt=0, le=5, description="Relative minimum detectable effect")
    variants: list[VariantIn] = Field(default_factory=_default_variants)

    @model_validator(mode="after")
    def _check(self) -> "ExperimentCreate":
        if self.key is None:
            self.key = slugify(self.name)
        self.variants = validate_variants(self.variants)
        return self


def validate_variants(variants: list[VariantIn]) -> list[VariantIn]:
    # Scope decision: A/B only. The schema supports N arms; the API does not (yet).
    if len(variants) != 2:
        raise ValueError("exactly two variants (control and treatment) are supported")
    if len({v.key for v in variants}) != len(variants):
        raise ValueError("variant keys must be unique")
    controls = [v for v in variants if v.is_control]
    if len(controls) > 1:
        raise ValueError("only one variant can be the control")
    if not controls:
        variants[0].is_control = True
    total = sum(v.weight for v in variants)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"variant weights must sum to 1 (got {total:.4f})")
    return variants


class ExperimentUpdate(BaseModel):
    """Name/description/hypothesis are editable any time; the rest only in draft."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    hypothesis: str | None = None
    metric_type: MetricType | None = None
    metric_event: str | None = Field(default=None, pattern=EVENT_PATTERN)
    traffic_allocation: float | None = Field(default=None, gt=0, le=1)
    alpha: float | None = Field(default=None, ge=0.001, le=0.2)
    power: float | None = Field(default=None, ge=0.5, le=0.99)
    mde: float | None = Field(default=None, gt=0, le=5)
    variants: list[VariantIn] | None = None

    @field_validator("variants")
    @classmethod
    def _variants(cls, v: list[VariantIn] | None) -> list[VariantIn] | None:
        return validate_variants(v) if v is not None else None


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    weight: float
    is_control: bool


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str
    hypothesis: str
    metric_type: MetricType
    metric_event: str
    traffic_allocation: float
    alpha: float
    power: float
    mde: float
    status: ExperimentStatus
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    variants: list[VariantOut]
    users: int = 0


# --------------------------------------------------------------------------- #
# Assignment & events
# --------------------------------------------------------------------------- #
class AssignRequest(BaseModel):
    experiment_key: str
    user_id: str = Field(min_length=1, max_length=128)


class AssignResponse(BaseModel):
    experiment_key: str
    user_id: str
    variant: str | None
    in_experiment: bool
    reason: Literal["assigned", "existing", "not_in_allocation", "experiment_not_running"]


class EventIn(BaseModel):
    experiment_key: str
    user_id: str = Field(min_length=1, max_length=128)
    event_type: str = Field(pattern=EVENT_PATTERN)
    value: float | None = None
    timestamp: datetime | None = Field(default=None, description="Defaults to server time")


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=5000)


class EventIngestResult(BaseModel):
    accepted: int
    rejected: int
    errors: list[str] = []


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #
class SampleSizeRequest(BaseModel):
    metric_type: MetricType = MetricType.conversion
    baseline: float = Field(description="Baseline conversion rate (0-1) or baseline mean")
    std_dev: float | None = Field(default=None, gt=0, description="Required for continuous metrics")
    mde: float = Field(gt=0)
    mde_type: Literal["relative", "absolute"] = "relative"
    alpha: float = Field(default=0.05, ge=0.001, le=0.2)
    power: float = Field(default=0.8, ge=0.5, le=0.99)
    daily_traffic: int | None = Field(default=None, gt=0, description="Users/day entering the test")

    @model_validator(mode="after")
    def _check(self) -> "SampleSizeRequest":
        if self.metric_type == MetricType.conversion and not 0 < self.baseline < 1:
            raise ValueError("baseline conversion rate must be between 0 and 1")
        if self.metric_type == MetricType.continuous and self.std_dev is None:
            raise ValueError("std_dev is required for continuous metrics")
        return self


class SampleSizeResponse(BaseModel):
    per_variant: int
    total: int
    baseline: float
    target: float
    absolute_effect: float
    alpha: float
    power: float
    estimated_days: float | None = None


class IntervalOut(BaseModel):
    low: float
    high: float


class VariantResult(BaseModel):
    variant_id: int
    key: str
    name: str
    is_control: bool
    weight: float
    users: int
    conversions: int | None = None
    rate: float | None = None
    rate_ci: IntervalOut | None = None
    mean: float | None = None
    std: float | None = None
    mean_ci: IntervalOut | None = None


class ComparisonResult(BaseModel):
    test: Literal["two_proportion_z_test", "welch_t_test"]
    statistic: float
    df: float | None = None
    p_value: float
    alpha: float
    significant: bool
    absolute_diff: float
    relative_lift: float | None
    ci_diff: IntervalOut
    ci_relative_lift: IntervalOut | None


class Verdict(BaseModel):
    status: Literal[
        "not_enough_data", "significant_positive", "significant_negative", "no_significant_difference"
    ]
    headline: str
    detail: str


class SRMOut(BaseModel):
    chi2: float
    p_value: float
    expected: list[float]
    observed: list[int]
    mismatch: bool


class Progress(BaseModel):
    required_per_variant: int | None
    smallest_variant: int
    fraction: float | None


class TimePoint(BaseModel):
    t: datetime
    control: float | None
    treatment: float | None
    p_value: float | None


class ResultsOut(BaseModel):
    experiment: ExperimentOut
    variants: list[VariantResult]
    comparison: ComparisonResult | None
    verdict: Verdict
    srm: SRMOut
    progress: Progress
    timeseries: list[TimePoint]
    warnings: list[str]
    computed_at: datetime
