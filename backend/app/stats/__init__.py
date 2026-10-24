"""ExperimentIQ stats engine.

Pure-Python implementations (no SciPy at runtime) of everything needed to
analyse a two-arm A/B test. Each function is verified against SciPy in
``tests/test_stats_vs_scipy.py``.
"""

from .distributions import norm_cdf, norm_ppf, norm_sf, t_cdf, t_ppf, t_sf
from .means import SampleSummary, WelchResult, mean_confidence_interval, welch_ttest
from .power import power_proportions, sample_size_means, sample_size_proportions
from .proportions import Interval, TwoProportionResult, two_proportion_ztest, wilson_interval
from .srm import srm_check

__all__ = [
    "Interval",
    "SampleSummary",
    "TwoProportionResult",
    "WelchResult",
    "mean_confidence_interval",
    "norm_cdf",
    "norm_ppf",
    "norm_sf",
    "power_proportions",
    "sample_size_means",
    "sample_size_proportions",
    "srm_check",
    "t_cdf",
    "t_ppf",
    "t_sf",
    "two_proportion_ztest",
    "welch_ttest",
    "wilson_interval",
]
