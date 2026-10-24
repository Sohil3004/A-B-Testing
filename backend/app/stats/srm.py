"""Sample Ratio Mismatch (SRM) check.

If a 50/50 experiment ends up 52/48 with large n, the assignment or logging
pipeline is probably broken and the results should not be trusted. This is a
chi-square goodness-of-fit test of observed counts vs configured weights.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from .distributions import norm_sf

SRM_ALPHA = 0.001  # conventional, strict threshold: SRM is a data-quality alarm


def chi2_sf(x: float, df: int) -> float:
    """Survival function of the chi-square distribution, Q(df/2, x/2).

    df = 1 (the A/B case) uses the exact identity 2 * norm_sf(sqrt(x)).
    df = 2 has the closed form exp(-x/2). Other df use the power series of
    the regularised lower incomplete gamma function.
    """
    if x <= 0:
        return 1.0
    if df == 1:
        return 2.0 * norm_sf(math.sqrt(x))
    if df == 2:
        return math.exp(-x / 2.0)
    # Series expansion of the lower regularised gamma P(a, z).
    a, z = df / 2.0, x / 2.0
    term = total = 1.0 / a
    n = 1
    while abs(term) > 1e-15 * abs(total) and n < 10_000:
        term *= z / (a + n)
        total += term
        n += 1
    lower = total * math.exp(-z + a * math.log(z) - math.lgamma(a))
    return max(0.0, 1.0 - lower)


@dataclass(frozen=True)
class SRMResult:
    chi2: float
    p_value: float
    expected: list[float]
    observed: list[int]
    mismatch: bool

    def to_dict(self) -> dict:
        return asdict(self)


def srm_check(observed: Sequence[int], weights: Sequence[float]) -> SRMResult:
    total = sum(observed)
    wsum = sum(weights)
    expected = [total * w / wsum for w in weights]
    if total == 0:
        return SRMResult(0.0, 1.0, expected, list(observed), False)
    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected, strict=False) if e > 0)
    p = chi2_sf(chi2, len(observed) - 1)
    return SRMResult(chi2, p, expected, list(observed), p < SRM_ALPHA)


__all__ = ["srm_check", "chi2_sf", "SRMResult", "SRM_ALPHA"]
