"""Deterministic, stateless variant assignment.

    bucket = SHA-256(f"{salt}:{namespace}:{user_id}")[:8] / 2**64   ∈ [0, 1)

* **Deterministic** – the same user always gets the same variant, on any
  server, with no lookup needed.
* **Uniform** – SHA-256 output is effectively uniform, so a 50/50 split is
  50/50 in expectation (we verify this with a chi-square test in the suite).
* **Independent across experiments** – each experiment has its own salt.
* **Two independent hashes** – one decides *whether* a user is in the
  experiment (traffic allocation), the other decides *which* variant. Using
  the same hash for both would correlate exposure with variant choice when
  allocation < 100%.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Protocol, TypeVar

_SCALE = float(2**64)


class Weighted(Protocol):
    weight: float


W = TypeVar("W", bound=Weighted)


def hash_to_unit(salt: str, namespace: str, user_id: str) -> float:
    digest = hashlib.sha256(f"{salt}:{namespace}:{user_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / _SCALE


def in_experiment(salt: str, user_id: str, traffic_allocation: float) -> bool:
    return hash_to_unit(salt, "allocation", user_id) < traffic_allocation


def choose_variant(salt: str, user_id: str, variants: Sequence[W]) -> W:
    """Walk the cumulative weight distribution with the user's bucket."""
    if not variants:
        raise ValueError("experiment has no variants")
    total = sum(v.weight for v in variants)
    point = hash_to_unit(salt, "variant", user_id) * total
    cumulative = 0.0
    for v in variants:
        cumulative += v.weight
        if point < cumulative:
            return v
    return variants[-1]  # guard against floating-point round-off
