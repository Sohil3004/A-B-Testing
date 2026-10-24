"""Tests and intervals for conversion (binary) metrics."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .distributions import norm_ppf, norm_sf


@dataclass(frozen=True)
class Interval:
    low: float
    high: float


def wilson_interval(successes: int, n: int, alpha: float = 0.05) -> Interval:
    """Wilson score interval for a single proportion.

    Preferred over the textbook Wald interval because it behaves well for
    small samples and rates near 0 or 1 (Wald can produce negative bounds).
    """
    if n <= 0:
        return Interval(0.0, 1.0)
    z = norm_ppf(1.0 - alpha / 2.0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    return Interval(max(0.0, centre - half), min(1.0, centre + half))


@dataclass(frozen=True)
class TwoProportionResult:
    control_rate: float
    treatment_rate: float
    absolute_diff: float          # treatment - control
    relative_lift: float | None   # (treatment - control) / control
    z_stat: float
    p_value: float
    ci_diff: Interval             # CI for the absolute difference
    ci_relative_lift: Interval | None
    alpha: float
    significant: bool

    def to_dict(self) -> dict:
        return asdict(self)


def two_proportion_ztest(
    x_control: int,
    n_control: int,
    x_treatment: int,
    n_treatment: int,
    alpha: float = 0.05,
) -> TwoProportionResult:
    """Two-sided two-proportion z-test (treatment vs control).

    * Test statistic uses the **pooled** standard error (correct under H0: p1 = p2).
    * Confidence interval for the difference uses the **unpooled** SE
      (correct under H1, where the rates are allowed to differ).
    * Relative-lift CI uses the delta method on p_t / p_c.

    This matches ``statsmodels.stats.proportion.proportions_ztest`` and is
    equivalent to a 2x2 chi-square test without Yates' correction (z^2 = chi2).
    """
    if n_control <= 0 or n_treatment <= 0:
        raise ValueError("both groups need at least one observation")
    if not (0 <= x_control <= n_control and 0 <= x_treatment <= n_treatment):
        raise ValueError("successes must be between 0 and n")

    p_c = x_control / n_control
    p_t = x_treatment / n_treatment
    diff = p_t - p_c

    pooled = (x_control + x_treatment) / (n_control + n_treatment)
    se_pooled = math.sqrt(pooled * (1.0 - pooled) * (1.0 / n_control + 1.0 / n_treatment))
    if se_pooled == 0.0:
        z, p_value = 0.0, 1.0  # both groups all-0 or all-1: no evidence of a difference
    else:
        z = diff / se_pooled
        p_value = min(1.0, 2.0 * norm_sf(abs(z)))

    z_crit = norm_ppf(1.0 - alpha / 2.0)
    var_c = p_c * (1.0 - p_c) / n_control
    var_t = p_t * (1.0 - p_t) / n_treatment
    se_unpooled = math.sqrt(var_c + var_t)
    ci_diff = Interval(diff - z_crit * se_unpooled, diff + z_crit * se_unpooled)

    if p_c > 0:
        lift = diff / p_c
        # Var(p_t / p_c) ≈ var_t / p_c^2 + p_t^2 * var_c / p_c^4
        se_lift = math.sqrt(var_t / p_c**2 + (p_t**2) * var_c / p_c**4)
        ci_lift: Interval | None = Interval(lift - z_crit * se_lift, lift + z_crit * se_lift)
    else:
        lift, ci_lift = None, None

    return TwoProportionResult(
        control_rate=p_c,
        treatment_rate=p_t,
        absolute_diff=diff,
        relative_lift=lift,
        z_stat=z,
        p_value=p_value,
        ci_diff=ci_diff,
        ci_relative_lift=ci_lift,
        alpha=alpha,
        significant=p_value < alpha,
    )
