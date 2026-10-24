from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.models import Assignment, Event, Experiment, Variant
from app.services.analysis import analyze

BASE = {"name": "Checkout button colour", "metric_event": "purchase"}


def _create(client, **overrides):
    r = client.post("/api/v1/experiments", json={**BASE, **overrides})
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# Auth & CRUD
# --------------------------------------------------------------------------- #
def test_health_is_public(client):
    assert client.get("/health", headers={"X-API-Key": ""}).json() == {"status": "ok"}


@pytest.mark.parametrize("key", [None, "wrong"])
def test_api_requires_key(client, key):
    headers = {"X-API-Key": key} if key else {"X-API-Key": ""}
    assert client.get("/api/v1/experiments", headers=headers).status_code == 401


def test_create_list_get(client):
    exp = _create(client)
    assert exp["key"] == "checkout-button-colour"
    assert exp["status"] == "draft"
    assert [v["key"] for v in exp["variants"]] == ["control", "treatment"]
    assert client.get("/api/v1/experiments").json()[0]["id"] == exp["id"]
    assert client.get(f"/api/v1/experiments/{exp['id']}").json()["name"] == BASE["name"]
    assert client.get("/api/v1/experiments/999").status_code == 404


def test_duplicate_key_conflicts(client):
    _create(client)
    assert client.post("/api/v1/experiments", json=BASE).status_code == 409


@pytest.mark.parametrize("variants", [
    [{"key": "a", "name": "A", "weight": 0.5}, {"key": "b", "name": "B", "weight": 0.6}],
    [{"key": "a", "name": "A", "weight": 0.5}, {"key": "a", "name": "A2", "weight": 0.5}],
    [{"key": "a", "name": "A", "weight": 0.4}, {"key": "b", "name": "B", "weight": 0.3},
     {"key": "c", "name": "C", "weight": 0.3}],
])
def test_invalid_variants_rejected(client, variants):
    assert client.post("/api/v1/experiments", json={**BASE, "variants": variants}).status_code == 422


def test_lifecycle_state_machine(client):
    exp = _create(client)
    url = f"/api/v1/experiments/{exp['id']}"
    assert client.post(f"{url}/pause").status_code == 409          # draft -> paused not allowed
    assert client.post(f"{url}/start").json()["status"] == "running"
    assert client.post(f"{url}/pause").json()["status"] == "paused"
    assert client.post(f"{url}/start").json()["status"] == "running"  # resume
    done = client.post(f"{url}/end").json()
    assert done["status"] == "completed" and done["ended_at"]
    assert client.post(f"{url}/start").status_code == 409          # completed is terminal


def test_design_locked_after_start(client):
    exp = _create(client)
    url = f"/api/v1/experiments/{exp['id']}"
    assert client.patch(url, json={"mde": 0.2}).json()["mde"] == 0.2
    client.post(f"{url}/start")
    assert client.patch(url, json={"mde": 0.3}).status_code == 409
    assert client.patch(url, json={"description": "ok to edit"}).status_code == 200


def test_delete(client):
    exp = _create(client)
    assert client.delete(f"/api/v1/experiments/{exp['id']}").status_code == 204
    assert client.get(f"/api/v1/experiments/{exp['id']}").status_code == 404


# --------------------------------------------------------------------------- #
# Assignment & events
# --------------------------------------------------------------------------- #
def test_assignment_flow(client):
    exp = _create(client)
    body = {"experiment_key": exp["key"], "user_id": "alice"}

    r = client.post("/api/v1/assign", json=body).json()
    assert r == {**body, "variant": "control", "in_experiment": False, "reason": "experiment_not_running"}

    client.post(f"/api/v1/experiments/{exp['id']}/start")
    first = client.post("/api/v1/assign", json=body).json()
    assert first["in_experiment"] and first["reason"] == "assigned"
    again = client.post("/api/v1/assign", json=body).json()
    assert again["variant"] == first["variant"] and again["reason"] == "existing"
    assert client.get(f"/api/v1/experiments/{exp['id']}").json()["users"] == 1


def test_traffic_allocation_excludes_users(client):
    exp = _create(client, traffic_allocation=0.1)
    client.post(f"/api/v1/experiments/{exp['id']}/start")
    reasons = [client.post("/api/v1/assign", json={"experiment_key": exp["key"], "user_id": f"u{i}"})
               .json()["reason"] for i in range(300)]
    share = reasons.count("assigned") / len(reasons)
    assert 0.04 < share < 0.18


def test_events(client):
    exp = _create(client)
    client.post(f"/api/v1/experiments/{exp['id']}/start")
    client.post("/api/v1/assign", json={"experiment_key": exp["key"], "user_id": "bob"})

    ok = client.post("/api/v1/events", json={"experiment_key": exp["key"], "user_id": "bob", "event_type": "view"})
    assert ok.status_code == 202 and ok.json()["accepted"] == 1

    bad = client.post("/api/v1/events", json={"experiment_key": exp["key"], "user_id": "eve", "event_type": "view"})
    assert bad.status_code == 422 and "not assigned" in bad.json()["detail"]

    batch = client.post("/api/v1/events/batch", json={"events": [
        {"experiment_key": exp["key"], "user_id": "bob", "event_type": "purchase", "value": 19.99},
        {"experiment_key": exp["key"], "user_id": "nobody", "event_type": "purchase"},
        {"experiment_key": "missing", "user_id": "bob", "event_type": "purchase"},
    ]}).json()
    assert batch["accepted"] == 1 and batch["rejected"] == 2


def test_sample_size_endpoint(client):
    r = client.post("/api/v1/stats/sample-size",
                    json={"baseline": 0.1, "mde": 0.1, "daily_traffic": 1000}).json()
    assert 14_000 < r["per_variant"] < 15_500
    assert r["estimated_days"] == pytest.approx(r["total"] / 1000, abs=0.1)
    bad = client.post("/api/v1/stats/sample-size", json={"metric_type": "continuous", "baseline": 10, "mde": 0.1})
    assert bad.status_code == 422


# --------------------------------------------------------------------------- #
# End-to-end analysis / verdicts
# --------------------------------------------------------------------------- #
def _seed(db, *, n, p_control, p_treatment, metric_type="conversion", seed=0, mde=0.1):
    rng = np.random.default_rng(seed)
    exp = Experiment(key=f"exp-{seed}-{n}", name="t", metric_type=metric_type, metric_event="purchase",
                     status="running", mde=mde,
                     variants=[Variant(key="control", name="Control", weight=0.5, is_control=True, position=0),
                               Variant(key="treatment", name="Treatment", weight=0.5, position=1)])
    db.add(exp)
    db.flush()
    c, t = exp.variants
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        v = c if i % 2 == 0 else t
        ts = start + timedelta(minutes=i)
        db.add(Assignment(experiment_id=exp.id, variant_id=v.id, user_id=f"u{i}", assigned_at=ts))
        p = p_control if v is c else p_treatment
        if rng.random() < p:
            value = float(rng.lognormal(3, 0.5)) if metric_type == "continuous" else None
            db.add(Event(experiment_id=exp.id, variant_id=v.id, user_id=f"u{i}", event_type="purchase",
                         value=value, created_at=ts + timedelta(minutes=5)))
    db.commit()
    return exp


def test_verdict_not_enough_data(db):
    res = analyze(db, _seed(db, n=60, p_control=0.1, p_treatment=0.5))
    assert res["verdict"]["status"] == "not_enough_data"


def test_verdict_significant_positive(db):
    res = analyze(db, _seed(db, n=8000, p_control=0.10, p_treatment=0.16, seed=1))
    assert res["verdict"]["status"] == "significant_positive"
    assert res["comparison"]["p_value"] < 0.001
    assert res["variants"][0]["rate"] == pytest.approx(0.10, abs=0.015)
    assert len(res["timeseries"]) >= 6


def test_verdict_no_difference_after_full_sample(db):
    # Large n, no real effect, generous MDE => planned sample reached, not significant.
    res = analyze(db, _seed(db, n=12_000, p_control=0.2, p_treatment=0.2, seed=5, mde=0.25))
    assert res["progress"]["fraction"] >= 1
    assert res["verdict"]["status"] == "no_significant_difference"


def test_continuous_metric_uses_welch(db):
    res = analyze(db, _seed(db, n=4000, p_control=0.2, p_treatment=0.3, metric_type="continuous", seed=2))
    assert res["comparison"]["test"] == "welch_t_test"
    assert res["comparison"]["df"] > 100
    assert res["verdict"]["status"] == "significant_positive"


def test_results_endpoint(client, db):
    exp = _create(client)
    res = client.get(f"/api/v1/experiments/{exp['id']}/results")
    assert res.status_code == 200
    assert res.json()["verdict"]["status"] == "not_enough_data"
