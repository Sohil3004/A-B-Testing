from __future__ import annotations

from dataclasses import dataclass

import pytest
from scipy import stats as sps

from app.assignment import choose_variant, hash_to_unit, in_experiment


@dataclass
class V:
    key: str
    weight: float


AB = [V("control", 0.5), V("treatment", 0.5)]


def test_assignment_is_deterministic():
    picks = {choose_variant("salt", f"user-{i}", AB).key for _ in range(5) for i in [42]}
    assert len(picks) == 1
    for i in range(200):
        assert choose_variant("s", f"u{i}", AB).key == choose_variant("s", f"u{i}", AB).key


def test_hash_is_in_unit_interval():
    vals = [hash_to_unit("s", "variant", str(i)) for i in range(5000)]
    assert all(0.0 <= v < 1.0 for v in vals)
    # Kolmogorov–Smirnov against Uniform(0, 1)
    assert sps.kstest(vals, "uniform").pvalue > 0.001


@pytest.mark.parametrize("weights", [(0.5, 0.5), (0.2, 0.8), (0.9, 0.1)])
def test_split_matches_weights(weights):
    variants = [V("control", weights[0]), V("treatment", weights[1])]
    n = 20_000
    counts = {"control": 0, "treatment": 0}
    for i in range(n):
        counts[choose_variant("exp-salt", f"user-{i}", variants).key] += 1
    obs = [counts["control"], counts["treatment"]]
    p = sps.chisquare(obs, [n * w for w in weights]).pvalue
    assert p > 0.001, f"split {obs} inconsistent with weights {weights}"


def test_traffic_allocation():
    n = 20_000
    inside = sum(in_experiment("salt", f"u{i}", 0.3) for i in range(n))
    assert sps.binomtest(inside, n, 0.3).pvalue > 0.001


def test_allocation_and_variant_hashes_are_independent():
    """Among allocated users the split must still be 50/50 (no correlation)."""
    counts = {"control": 0, "treatment": 0}
    for i in range(30_000):
        uid = f"u{i}"
        if in_experiment("salt", uid, 0.2):
            counts[choose_variant("salt", uid, AB).key] += 1
    obs = list(counts.values())
    assert sps.chisquare(obs).pvalue > 0.001


def test_different_salts_give_independent_assignments():
    same = sum(
        choose_variant("exp-a", f"u{i}", AB).key == choose_variant("exp-b", f"u{i}", AB).key
        for i in range(10_000)
    )
    # Independent 50/50 assignments agree ~50% of the time.
    assert sps.binomtest(same, 10_000, 0.5).pvalue > 0.001
