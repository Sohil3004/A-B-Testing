"""Sample-size and power calculations for two-arm experiments."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

from .distributions import norm_cdf, norm_ppf

MdeType = Literal["relative", "absolute"]


@dataclass(frozen=True)
class SampleSizeResult:
    per_variant: int
    total: int
    baseline: float
    target: float           # expected value in treatment if the MDE is real
    absolute_effect: float
    alpha: float
    power: float

    def to_dict(self) -> dict:
        return asdict(self)


def _target(baseline: float, mde: float, mde_type: MdeType) -> float:
    if mde <= 0:
        raise ValueError("mde must be positive")
    return baseline * (1.0 + mde) if mde_type == "relative" else baseline + mde


def sample_size_proportions(
    baseline_rate: float,
    mde: float,
    mde_type: MdeType = "relative",
    alpha: float = 0.05,
    power: float = 0.8,
    traffic_split: float = 0.5,
) -> SampleSizeResult:
    """Per-variant n for a two-sided two-proportion z-test.

        n = ( z_{1-a/2} * sqrt(2 p̄ q̄) + z_{1-b} * sqrt(p1 q1 + p2 q2) )^2 / (p2 - p1)^2

    The first term uses the variance under H0 (pooled rate), the second the
    variance under H1 — the classic Fleiss formula without continuity
    correction. ``traffic_split`` (share of traffic in treatment) adjusts for
    unequal allocation; the returned ``per_variant`` is the size of the
    *smaller* arm for unequal splits.
    """
    if not 0 < baseline_rate < 1:
        raise ValueError("baseline_rate must be between 0 and 1")
    p1 = baseline_rate
    p2 = _target(baseline_rate, mde, mde_type)
    if not 0 < p2 < 1:
        raise ValueError("baseline + MDE must stay between 0 and 1")

    z_a = norm_ppf(1.0 - alpha / 2.0)
    z_b = norm_ppf(power)
    # k = n_treatment / n_control
    k = traffic_split / (1.0 - traffic_split)
    p_bar = (p1 + k * p2) / (1.0 + k)
    num = (z_a * math.sqrt(p_bar * (1 - p_bar) * (1 + 1 / k))
           + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / k)) ** 2
    n_control = math.ceil(num / (p2 - p1) ** 2)
    n_treatment = math.ceil(n_control * k)
    return SampleSizeResult(
        per_variant=min(n_control, n_treatment),
        total=n_control + n_treatment,
        baseline=p1,
        target=p2,
        absolute_effect=p2 - p1,
        alpha=alpha,
        power=power,
    )


def sample_size_means(
    baseline_mean: float,
    std_dev: float,
    mde: float,
    mde_type: MdeType = "relative",
    alpha: float = 0.05,
    power: float = 0.8,
) -> SampleSizeResult:
    """Per-variant n for a two-sided two-sample test of means (equal split).

        n = 2 * (z_{1-a/2} + z_{1-b})^2 * sigma^2 / delta^2
    """
    if std_dev <= 0:
        raise ValueError("std_dev must be positive")
    target = _target(baseline_mean, mde, mde_type)
    delta = target - baseline_mean
    z_a = norm_ppf(1.0 - alpha / 2.0)
    z_b = norm_ppf(power)
    n = math.ceil(2.0 * (z_a + z_b) ** 2 * std_dev**2 / delta**2)
    return SampleSizeResult(
        per_variant=n,
        total=2 * n,
        baseline=baseline_mean,
        target=target,
        absolute_effect=delta,
        alpha=alpha,
        power=power,
    )


def power_proportions(n_per_variant: int, p1: float, p2: float, alpha: float = 0.05) -> float:
    """Achieved power of the two-sided z-test with equal arms of size n."""
    if n_per_variant <= 0 or p1 == p2:
        return alpha if p1 == p2 else 0.0
    z_a = norm_ppf(1.0 - alpha / 2.0)
    p_bar = (p1 + p2) / 2.0
    se0 = math.sqrt(2.0 * p_bar * (1 - p_bar) / n_per_variant)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n_per_variant)
    d = abs(p2 - p1)
    # Include the (tiny) probability of rejecting in the wrong direction.
    return norm_cdf((d - z_a * se0) / se1) + norm_cdf((-d - z_a * se0) / se1)
