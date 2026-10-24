"""Probability distributions implemented from first principles.

The stats engine deliberately avoids SciPy at runtime: every CDF / quantile
used by the hypothesis tests lives here, and the test-suite verifies each
function against SciPy to ~1e-9 precision. This keeps the production image
small *and* proves the maths is understood rather than imported.

Functions
---------
norm_cdf, norm_sf, norm_ppf   Standard normal distribution.
t_cdf, t_sf, t_ppf            Student's t distribution (real-valued df).
betainc                       Regularised incomplete beta function I_x(a, b).
"""

from __future__ import annotations

import math

_SQRT2 = math.sqrt(2.0)


# --------------------------------------------------------------------------- #
# Standard normal
# --------------------------------------------------------------------------- #
def norm_cdf(x: float) -> float:
    """P(Z <= x) for Z ~ N(0, 1). Uses erfc for accuracy in the lower tail."""
    return 0.5 * math.erfc(-x / _SQRT2)


def norm_sf(x: float) -> float:
    """Survival function P(Z > x). Accurate in the upper tail."""
    return 0.5 * math.erfc(x / _SQRT2)


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# Coefficients for Peter Acklam's rational approximation of the normal quantile.
_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
      1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
      6.680131188771972e01, -1.328068155288572e01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
      -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
      3.754408661907416e00)


def norm_ppf(p: float) -> float:
    """Quantile function (inverse CDF) of the standard normal.

    Acklam's approximation (relative error ~1e-9) followed by one Halley
    refinement step, which brings it to full double precision.
    """
    if not 0.0 < p < 1.0:
        if p == 0.0:
            return -math.inf
        if p == 1.0:
            return math.inf
        raise ValueError(f"p must be in [0, 1], got {p}")

    p_low = 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    elif p <= 1.0 - p_low:
        q = p - 0.5
        r = q * q
        x = (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / \
            (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log1p(-p))
        x = -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)

    # One step of Halley's method on f(x) = cdf(x) - p.
    e = (norm_cdf(x) - p) if p < 0.5 else -(norm_sf(x) - (1.0 - p))
    u = e * math.sqrt(2.0 * math.pi) * math.exp(0.5 * x * x)
    return x - u / (1.0 + 0.5 * x * u)


# --------------------------------------------------------------------------- #
# Regularised incomplete beta function
# --------------------------------------------------------------------------- #
_FPMIN = 1e-300
_EPS = 1e-15
_MAX_ITER = 50_000


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for I_x(a, b), modified Lentz's method."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FPMIN:
        d = _FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, _MAX_ITER + 1):
        m2 = 2 * m
        # Even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        h *= d * c
        # Odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            return h
    raise ArithmeticError(f"betacf failed to converge (a={a}, b={b}, x={x})")


def _lgamma_diff(a: float, b: float) -> float:
    """lgamma(a + b) - lgamma(a) for large a, without catastrophic cancellation.

    Subtracting two lgamma values of magnitude ~a*ln(a) loses ~log10(a) digits
    (≈1e-9 relative error at df = 1e6). Expanding Stirling's series
    analytically keeps every term O(b * ln a).
    """
    def corr(z: float) -> float:  # Stirling correction terms beyond (z-1/2)ln z - z + ln(2π)/2
        z2 = z * z
        return 1.0 / (12.0 * z) - 1.0 / (360.0 * z * z2) + 1.0 / (1260.0 * z * z2 * z2)

    return b * math.log(a) + (a + b - 0.5) * math.log1p(b / a) - b + corr(a + b) - corr(a)


def _log_inv_beta(a: float, b: float) -> float:
    """-log B(a, b) = lgamma(a+b) - lgamma(a) - lgamma(b)."""
    big, small = (a, b) if a >= b else (b, a)
    if big > 1e3:
        return _lgamma_diff(big, small) - math.lgamma(small)
    return math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)


def betainc(a: float, b: float, x: float, y: float | None = None) -> float:
    """Regularised incomplete beta I_x(a, b).

    ``y`` may be supplied as ``1 - x`` computed by the caller without
    cancellation error (important when x is very close to 1).
    """
    if y is None:
        y = 1.0 - x
    if x <= 0.0:
        return 0.0
    if y <= 0.0:
        return 1.0
    log_x = math.log1p(-y) if y < 0.5 else math.log(x)
    log_y = math.log1p(-x) if x < 0.5 else math.log(y)
    bt = math.exp(_log_inv_beta(a, b) + a * log_x + b * log_y)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, y) / b


# --------------------------------------------------------------------------- #
# Student's t
# --------------------------------------------------------------------------- #
_T_NORMAL_CUTOFF = 1e7  # beyond this df the t and normal agree to ~1e-8


def _t_two_sided_tail(t: float, df: float) -> float:
    """P(|T| > |t|), computed directly so small p-values keep precision."""
    t2 = t * t
    denom = df + t2
    return betainc(0.5 * df, 0.5, df / denom, t2 / denom)


def t_sf(t: float, df: float) -> float:
    """Survival function P(T > t) for T ~ t(df)."""
    if df <= 0:
        raise ValueError("df must be positive")
    if math.isinf(df) or df > _T_NORMAL_CUTOFF:
        return norm_sf(t)
    if t == 0:
        return 0.5
    tail = 0.5 * _t_two_sided_tail(t, df)
    return tail if t > 0 else 1.0 - tail


def t_cdf(t: float, df: float) -> float:
    """P(T <= t) for T ~ t(df)."""
    if df <= 0:
        raise ValueError("df must be positive")
    if math.isinf(df) or df > _T_NORMAL_CUTOFF:
        return norm_cdf(t)
    if t == 0:
        return 0.5
    tail = 0.5 * _t_two_sided_tail(t, df)
    return tail if t < 0 else 1.0 - tail


def t_pdf(t: float, df: float) -> float:
    log_pdf = (math.lgamma((df + 1) / 2) - math.lgamma(df / 2)
               - 0.5 * math.log(df * math.pi)
               - (df + 1) / 2 * math.log1p(t * t / df))
    return math.exp(log_pdf)


def t_ppf(p: float, df: float) -> float:
    """Quantile function of Student's t.

    Brackets the root, then bisects to near machine precision and polishes
    with a couple of Newton steps. Robust for any df > 0.
    """
    if not 0.0 < p < 1.0:
        if p == 0.0:
            return -math.inf
        if p == 1.0:
            return math.inf
        raise ValueError(f"p must be in [0, 1], got {p}")
    if math.isinf(df) or df > _T_NORMAL_CUTOFF:
        return norm_ppf(p)
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -t_ppf(1.0 - p, df)

    # Upper tail: find t > 0 with sf(t) = 1 - p.
    target = 1.0 - p
    lo, hi = 0.0, max(1.0, norm_ppf(p))
    while t_sf(hi, df) > target:
        lo, hi = hi, hi * 2.0
        if hi > 1e12:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_sf(mid, df) > target:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-13 * max(1.0, hi):
            break
    x = 0.5 * (lo + hi)
    for _ in range(2):  # Newton polish on f(x) = sf(x) - target, f'(x) = -pdf(x)
        pdf = t_pdf(x, df)
        if pdf <= 0:
            break
        x += (t_sf(x, df) - target) / pdf
    return x
