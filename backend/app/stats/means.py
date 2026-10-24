"""Tests and intervals for continuous metrics (e.g. revenue per user)."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from .distributions import t_ppf, t_sf
from .proportions import Interval


@dataclass(frozen=True)
class SampleSummary:
    n: int
    mean: float
    variance: float  # unbiased sample variance (ddof=1)

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    @classmethod
    def from_values(cls, values: Iterable[float]) -> SampleSummary:
        """Welford's online algorithm: numerically stable single pass."""
        n, mean, m2 = 0, 0.0, 0.0
        for v in values:
            n += 1
            delta = v - mean
            mean += delta / n
            m2 += delta * (v - mean)
        variance = m2 / (n - 1) if n > 1 else 0.0
        return cls(n=n, mean=mean, variance=variance)


def mean_confidence_interval(s: SampleSummary, alpha: float = 0.05) -> Interval:
    """t-based CI for a single mean."""
    if s.n < 2:
        return Interval(-math.inf, math.inf)
    se = math.sqrt(s.variance / s.n)
    t_crit = t_ppf(1.0 - alpha / 2.0, s.n - 1)
    return Interval(s.mean - t_crit * se, s.mean + t_crit * se)


@dataclass(frozen=True)
class WelchResult:
    control_mean: float
    treatment_mean: float
    absolute_diff: float
    relative_lift: float | None
    t_stat: float
    df: float
    p_value: float
    ci_diff: Interval
    ci_relative_lift: Interval | None
    alpha: float
    significant: bool

    def to_dict(self) -> dict:
        return asdict(self)


def welch_ttest(control: SampleSummary, treatment: SampleSummary, alpha: float = 0.05) -> WelchResult:
    """Two-sided Welch's t-test (unequal variances), treatment - control.

    Degrees of freedom from the Welch–Satterthwaite equation. Equivalent to
    ``scipy.stats.ttest_ind(treatment, control, equal_var=False)``.
    """
    if control.n < 2 or treatment.n < 2:
        raise ValueError("each group needs at least two observations")

    vc = control.variance / control.n
    vt = treatment.variance / treatment.n
    se = math.sqrt(vc + vt)
    diff = treatment.mean - control.mean

    if se == 0.0:
        t_stat, df, p_value = 0.0, float(control.n + treatment.n - 2), 1.0 if diff == 0 else 0.0
        ci = Interval(diff, diff)
    else:
        t_stat = diff / se
        df = (vc + vt) ** 2 / (vc**2 / (control.n - 1) + vt**2 / (treatment.n - 1))
        p_value = min(1.0, 2.0 * t_sf(abs(t_stat), df))
        t_crit = t_ppf(1.0 - alpha / 2.0, df)
        ci = Interval(diff - t_crit * se, diff + t_crit * se)

    if control.mean != 0:
        lift = diff / control.mean
        # Delta-method SE of mean_t / mean_c, normal critical value via df.
        se_lift = math.sqrt(vt / control.mean**2 + treatment.mean**2 * vc / control.mean**4)
        t_crit = t_ppf(1.0 - alpha / 2.0, df) if se > 0 else 0.0
        ci_lift: Interval | None = Interval(lift - t_crit * se_lift, lift + t_crit * se_lift)
    else:
        lift, ci_lift = None, None

    return WelchResult(
        control_mean=control.mean,
        treatment_mean=treatment.mean,
        absolute_diff=diff,
        relative_lift=lift,
        t_stat=t_stat,
        df=df,
        p_value=p_value,
        ci_diff=ci,
        ci_relative_lift=ci_lift,
        alpha=alpha,
        significant=p_value < alpha,
    )
