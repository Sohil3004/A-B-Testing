"""Verify every number the stats engine produces against SciPy.

The engine is pure Python; SciPy is a *test-only* dependency used as the
reference implementation.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import special
from scipy import stats as sps

from app import stats
from app.stats.distributions import betainc
from app.stats.srm import chi2_sf

DFS = [1, 2, 3.7, 5, 10, 29.5, 100, 1_000, 25_000, 1e6]
TS = [-40, -8.5, -3.1, -1.96, -0.5, -1e-3, 0, 1e-3, 0.7, 1.645, 2.4, 4.2, 9, 60]


# --------------------------------------------------------------------------- #
# Distributions
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("x", np.linspace(-9, 9, 73))
def test_norm_cdf_sf(x):
    assert stats.norm_cdf(x) == pytest.approx(sps.norm.cdf(x), rel=1e-12, abs=1e-300)
    assert stats.norm_sf(x) == pytest.approx(sps.norm.sf(x), rel=1e-12, abs=1e-300)


@pytest.mark.parametrize("p", [1e-12, 1e-6, 0.001, 0.01, 0.024, 0.025, 0.05, 0.1, 0.3, 0.5,
                               0.7, 0.8, 0.9, 0.95, 0.975, 0.976, 0.99, 0.999, 1 - 1e-9])
def test_norm_ppf(p):
    assert stats.norm_ppf(p) == pytest.approx(sps.norm.ppf(p), rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("df", DFS)
@pytest.mark.parametrize("t", TS)
def test_t_cdf_sf(t, df):
    assert stats.t_cdf(t, df) == pytest.approx(sps.t.cdf(t, df), rel=1e-9, abs=1e-15)
    assert stats.t_sf(t, df) == pytest.approx(sps.t.sf(t, df), rel=1e-9, abs=1e-15)


@pytest.mark.parametrize("df", DFS)
@pytest.mark.parametrize("p", [0.0005, 0.025, 0.1, 0.4, 0.6, 0.9, 0.95, 0.975, 0.995, 0.9995])
def test_t_ppf(p, df):
    assert stats.t_ppf(p, df) == pytest.approx(sps.t.ppf(p, df), rel=1e-9, abs=1e-10)


@pytest.mark.parametrize("a,b", [(0.5, 0.5), (1, 3), (2.5, 0.5), (50, 0.5), (12_500, 0.5), (3, 7)])
@pytest.mark.parametrize("x", [1e-6, 0.01, 0.2, 0.5, 0.8, 0.99, 0.999999])
def test_betainc(a, b, x):
    assert betainc(a, b, x) == pytest.approx(special.betainc(a, b, x), rel=1e-9, abs=1e-15)


@pytest.mark.parametrize("df", [1, 2, 3, 4, 7])
@pytest.mark.parametrize("x", [0.01, 0.5, 1, 3.84, 6.63, 10.8, 25])
def test_chi2_sf(x, df):
    assert chi2_sf(x, df) == pytest.approx(sps.chi2.sf(x, df), rel=1e-9, abs=1e-15)


# --------------------------------------------------------------------------- #
# Two-proportion z-test
# --------------------------------------------------------------------------- #
PROPORTION_CASES = [
    (120, 1000, 150, 1000),
    (500, 10_000, 560, 10_000),
    (31, 412, 29, 405),
    (2, 50, 9, 48),
    (4_800, 100_000, 5_050, 101_000),
    (0, 300, 5, 310),
]


@pytest.mark.parametrize("xc,nc,xt,nt", PROPORTION_CASES)
def test_ztest_matches_chi2_contingency(xc, nc, xt, nt):
    r = stats.two_proportion_ztest(xc, nc, xt, nt)
    table = np.array([[xc, nc - xc], [xt, nt - xt]])
    chi2, p, _, _ = sps.chi2_contingency(table, correction=False)
    # A 2x2 chi-square without Yates' correction is exactly the square of the pooled z.
    assert r.z_stat**2 == pytest.approx(chi2, rel=1e-9)
    assert r.p_value == pytest.approx(p, rel=1e-9)


@pytest.mark.parametrize("xc,nc,xt,nt", PROPORTION_CASES)
def test_ztest_ci_matches_scipy_normal(xc, nc, xt, nt):
    r = stats.two_proportion_ztest(xc, nc, xt, nt, alpha=0.05)
    pc, pt = xc / nc, xt / nt
    se = math.sqrt(pc * (1 - pc) / nc + pt * (1 - pt) / nt)
    lo, hi = sps.norm.interval(0.95, loc=pt - pc, scale=se) if se > 0 else (pt - pc, pt - pc)
    assert r.ci_diff.low == pytest.approx(lo, rel=1e-9, abs=1e-12)
    assert r.ci_diff.high == pytest.approx(hi, rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("k,n", [(0, 20), (3, 20), (50, 100), (999, 1000), (120, 1000), (7, 12_000)])
@pytest.mark.parametrize("alpha", [0.05, 0.01, 0.1])
def test_wilson_interval_matches_scipy(k, n, alpha):
    ref = sps.binomtest(k, n).proportion_ci(confidence_level=1 - alpha, method="wilson")
    ours = stats.wilson_interval(k, n, alpha)
    assert ours.low == pytest.approx(ref.low, rel=1e-9, abs=1e-12)
    assert ours.high == pytest.approx(ref.high, rel=1e-9, abs=1e-12)


def test_ztest_identical_groups_is_not_significant():
    r = stats.two_proportion_ztest(0, 100, 0, 100)
    assert r.p_value == 1.0 and not r.significant


def test_aa_false_positive_rate_is_alpha():
    """Simulated A/A tests: the z-test should reject ~5% of the time, not more."""
    rng = np.random.default_rng(7)
    sims, n, p = 4000, 2000, 0.1
    xs = rng.binomial(n, p, size=(sims, 2))
    rejections = sum(stats.two_proportion_ztest(int(a), n, int(b), n).significant for a, b in xs)
    assert 0.04 <= rejections / sims <= 0.06


# --------------------------------------------------------------------------- #
# Welch's t-test
# --------------------------------------------------------------------------- #
def _revenue_like(rng, n, p_buy, mean_spend):
    """Zero-inflated, right-skewed: realistic revenue-per-user."""
    buys = rng.random(n) < p_buy
    return np.where(buys, rng.lognormal(math.log(mean_spend), 0.8, n), 0.0)


WELCH_SAMPLES = [
    lambda r: (r.normal(10, 2, 50), r.normal(11, 3, 70)),
    lambda r: (r.normal(0, 1, 5), r.normal(0.5, 4, 8)),
    lambda r: (_revenue_like(r, 3000, 0.05, 40), _revenue_like(r, 3100, 0.055, 42)),
    lambda r: (r.exponential(3, 400), r.exponential(3.3, 380)),
    lambda r: (r.normal(100, 15, 20_000), r.normal(100.2, 16, 20_000)),
]


@pytest.mark.parametrize("make", WELCH_SAMPLES)
def test_welch_matches_scipy(make):
    rng = np.random.default_rng(42)
    a, b = make(rng)
    ours = stats.welch_ttest(stats.SampleSummary.from_values(a), stats.SampleSummary.from_values(b))
    ref = sps.ttest_ind(b, a, equal_var=False)
    assert ours.t_stat == pytest.approx(ref.statistic, rel=1e-9)
    assert ours.p_value == pytest.approx(ref.pvalue, rel=1e-8)
    assert ours.df == pytest.approx(ref.df, rel=1e-9)
    ci = ref.confidence_interval(0.95)
    assert ours.ci_diff.low == pytest.approx(ci.low, rel=1e-8)
    assert ours.ci_diff.high == pytest.approx(ci.high, rel=1e-8)


def test_welford_matches_numpy():
    rng = np.random.default_rng(1)
    x = rng.normal(1e6, 3, 10_000)  # large offset stresses naive sum-of-squares
    s = stats.SampleSummary.from_values(x)
    assert s.mean == pytest.approx(np.mean(x), rel=1e-12)
    assert s.variance == pytest.approx(np.var(x, ddof=1), rel=1e-8)


@pytest.mark.parametrize("n", [3, 30, 3000])
def test_mean_ci_matches_scipy(n):
    rng = np.random.default_rng(n)
    x = rng.normal(5, 2, n)
    s = stats.SampleSummary.from_values(x)
    lo, hi = sps.t.interval(0.95, n - 1, loc=np.mean(x), scale=sps.sem(x))
    ci = stats.mean_confidence_interval(s)
    assert ci.low == pytest.approx(lo, rel=1e-9) and ci.high == pytest.approx(hi, rel=1e-9)


# --------------------------------------------------------------------------- #
# Sample size & power
# --------------------------------------------------------------------------- #
def _analytic_power(n, p1, p2, alpha):
    z = sps.norm.ppf(1 - alpha / 2)
    pbar = (p1 + p2) / 2
    se0 = math.sqrt(2 * pbar * (1 - pbar) / n)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n)
    return sps.norm.cdf((abs(p2 - p1) - z * se0) / se1)


@pytest.mark.parametrize("baseline,mde,alpha,power", [
    (0.10, 0.10, 0.05, 0.8), (0.03, 0.20, 0.05, 0.9), (0.5, 0.02, 0.01, 0.8), (0.2, 0.05, 0.1, 0.8),
])
def test_sample_size_is_minimal_n_achieving_power(baseline, mde, alpha, power):
    r = stats.sample_size_proportions(baseline, mde, "relative", alpha, power)
    p2 = baseline * (1 + mde)
    assert _analytic_power(r.per_variant, baseline, p2, alpha) >= power - 1e-9
    assert _analytic_power(r.per_variant - 1, baseline, p2, alpha) < power
    assert stats.power_proportions(r.per_variant, baseline, p2, alpha) >= power - 1e-9


def test_sample_size_proportions_monte_carlo():
    """At the computed n, simulated experiments should detect the effect ~80% of the time."""
    r = stats.sample_size_proportions(0.10, 0.15, "relative", 0.05, 0.8)
    rng = np.random.default_rng(3)
    n, sims = r.per_variant, 3000
    xc = rng.binomial(n, 0.10, sims)
    xt = rng.binomial(n, 0.115, sims)
    hit = np.mean([stats.two_proportion_ztest(int(a), n, int(b), n).significant for a, b in zip(xc, xt)])
    assert 0.77 <= hit <= 0.83


def test_sample_size_means_vs_noncentral_t():
    r = stats.sample_size_means(50.0, 20.0, 0.05, "relative", 0.05, 0.8)
    n = r.per_variant
    df = 2 * n - 2
    nc = r.absolute_effect / (20.0 * math.sqrt(2 / n))
    tcrit = sps.t.ppf(0.975, df)
    exact_power = sps.nct.sf(tcrit, df, nc) + sps.nct.cdf(-tcrit, df, nc)
    assert exact_power == pytest.approx(0.8, abs=0.005)


def test_sample_size_rejects_impossible_target():
    with pytest.raises(ValueError):
        stats.sample_size_proportions(0.9, 0.2)  # 0.9 * 1.2 > 1


# --------------------------------------------------------------------------- #
# Sample ratio mismatch
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("obs,w", [([5000, 5000], [0.5, 0.5]), ([5100, 4900], [0.5, 0.5]),
                                   ([2050, 7950], [0.2, 0.8]), ([10_400, 9_600], [0.5, 0.5])])
def test_srm_matches_scipy_chisquare(obs, w):
    r = stats.srm_check(obs, w)
    ref = sps.chisquare(obs, [sum(obs) * x for x in w])
    assert r.chi2 == pytest.approx(ref.statistic, rel=1e-12, abs=1e-12)
    assert r.p_value == pytest.approx(ref.pvalue, rel=1e-9)


def test_srm_flags_broken_split():
    assert stats.srm_check([10_400, 9_600], [0.5, 0.5]).mismatch
    assert not stats.srm_check([5_030, 4_970], [0.5, 0.5]).mismatch
