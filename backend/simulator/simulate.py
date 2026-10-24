"""Traffic simulator: generates realistic demo data for ExperimentIQ.

Each scenario has a *known ground truth*, including several with no real
effect, so you can check that the stats engine finds real effects and —
just as importantly — does not invent fake ones.

Usage
-----
    # Fast: write straight to the database (uses the same hashing as the API)
    python -m simulator.simulate --reset

    # End-to-end through the HTTP API (slower; scale traffic down)
    python -m simulator.simulate --mode api --base-url http://localhost:8000 \
        --api-key dev-secret-key --scale 0.05
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, insert, select

from app.assignment import choose_variant, in_experiment
from app.db import SessionLocal, init_db
from app.models import Assignment, Event, Experiment, Variant


@dataclass
class Arm:
    conversion: float          # P(user fires the metric event)
    click: float = 0.3         # P(click) — secondary funnel event for realism
    spend_mean: float = 0.0    # mean order value (continuous metrics only)


@dataclass
class Scenario:
    key: str
    name: str
    hypothesis: str
    metric_type: str
    metric_event: str
    users: int
    days: int
    status: str
    control: Arm
    treatment: Arm
    truth: str
    weights: tuple[float, float] = (0.5, 0.5)
    traffic_allocation: float = 1.0
    mde: float = 0.10
    description: str = ""
    extra: dict = field(default_factory=dict)


SCENARIOS: list[Scenario] = [
    Scenario(
        key="checkout-cta-colour", name="Checkout CTA: green vs orange",
        hypothesis="A higher-contrast orange 'Buy now' button will increase purchase conversion.",
        metric_type="conversion", metric_event="purchase", users=40_000, days=14, status="completed",
        control=Arm(0.040), treatment=Arm(0.047), mde=0.15,
        truth="REAL EFFECT: +17.5% relative lift in conversion",
    ),
    Scenario(
        key="homepage-hero-copy", name="Homepage hero headline rewrite",
        hypothesis="Benefit-led headline copy will increase sign-ups.",
        metric_type="conversion", metric_event="signup", users=30_000, days=14, status="completed",
        control=Arm(0.10), treatment=Arm(0.10), mde=0.10,
        truth="NO EFFECT: identical 10% sign-up rate in both arms",
    ),
    Scenario(
        key="bundle-upsell", name="'Frequently bought together' upsell",
        hypothesis="Showing bundles on the product page will raise revenue per visitor.",
        metric_type="continuous", metric_event="revenue", users=40_000, days=21, status="completed",
        control=Arm(0.05, spend_mean=48.0), treatment=Arm(0.05, spend_mean=56.0), mde=0.15,
        truth="REAL EFFECT: same buy rate, ~17% higher order value",
    ),
    Scenario(
        key="free-shipping-banner", name="Free-shipping threshold banner",
        hypothesis="A sticky banner advertising free shipping over $50 will increase revenue per user.",
        metric_type="continuous", metric_event="revenue", users=30_000, days=14, status="running",
        control=Arm(0.06, spend_mean=42.0), treatment=Arm(0.06, spend_mean=42.0), mde=0.20,
        truth="NO EFFECT: identical revenue distribution",
    ),
    Scenario(
        key="search-autocomplete-v2", name="Search autocomplete v2",
        hypothesis="New ranking model in autocomplete will increase search-to-purchase conversion.",
        metric_type="conversion", metric_event="purchase", users=36_000, days=10, status="paused",
        control=Arm(0.120), treatment=Arm(0.108), mde=0.10,
        truth="REAL NEGATIVE EFFECT: -10% relative (the new model is worse)",
    ),
    Scenario(
        key="onboarding-checklist", name="Onboarding checklist",
        hypothesis="A 3-step checklist will increase week-1 activation.",
        metric_type="conversion", metric_event="activated", users=2_400, days=3, status="running",
        control=Arm(0.30), treatment=Arm(0.315), mde=0.05, traffic_allocation=0.5,
        truth="SMALL REAL EFFECT, UNDERPOWERED: +5% relative but far too few users so far",
    ),
    Scenario(
        key="pricing-page-annual-toggle", name="Pricing page: annual plan default",
        hypothesis="Defaulting the toggle to annual billing will increase paid conversions.",
        metric_type="conversion", metric_event="subscribe", users=0, days=0, status="draft",
        control=Arm(0.02), treatment=Arm(0.02), weights=(0.5, 0.5),
        truth="DRAFT: not started, no data",
    ),
]


# --------------------------------------------------------------------------- #
# Event generation (shared by both modes)
# --------------------------------------------------------------------------- #
def _arrival_times(rng: random.Random, n: int, start: datetime, days: int) -> list[datetime]:
    """Arrivals with weekly seasonality (weekends ~30% busier) and a daily cycle."""
    if n == 0:
        return []
    out = []
    span = days * 86_400
    while len(out) < n:
        s = rng.uniform(0, span)
        t = start + timedelta(seconds=s)
        weekly = 1.3 if t.weekday() >= 5 else 1.0
        daily = 0.6 + 0.4 * math.sin(math.pi * ((t.hour - 6) % 24) / 24)  # peak in the evening
        if rng.random() < weekly * daily / 1.3:
            out.append(t)
    out.sort()
    return out


def _user_events(rng: random.Random, sc: Scenario, arm: Arm, uid: str, t0: datetime, end: datetime) -> list[dict]:
    events = [{"user_id": uid, "event_type": "view", "value": None, "created_at": t0}]
    if rng.random() < arm.click:
        events.append({"user_id": uid, "event_type": "click", "value": None,
                       "created_at": t0 + timedelta(seconds=rng.expovariate(1 / 40))})
    if rng.random() < arm.conversion:
        ts = t0 + timedelta(minutes=rng.expovariate(1 / 30))
        if ts <= end:  # conversions after "now" haven't happened yet
            value = None
            if sc.metric_type == "continuous":
                # Lognormal order values with the requested mean (sigma 0.6 → realistic right skew).
                sigma = 0.6
                mu = math.log(arm.spend_mean) - sigma**2 / 2
                value = round(rng.lognormvariate(mu, sigma), 2)
            events.append({"user_id": uid, "event_type": sc.metric_event, "value": value, "created_at": ts})
    return events


# --------------------------------------------------------------------------- #
# Direct-to-database mode
# --------------------------------------------------------------------------- #
def run_direct(scale: float, reset: bool, seed: int) -> None:
    init_db()
    rng = random.Random(seed)
    now = datetime.now(UTC).replace(microsecond=0)
    with SessionLocal() as db:
        for sc in SCENARIOS:
            existing = db.scalar(select(Experiment).where(Experiment.key == sc.key))
            if existing and not reset:
                print(f"  skip {sc.key} (exists; use --reset to regenerate)")
                continue
            if existing:
                db.execute(delete(Event).where(Event.experiment_id == existing.id))
                db.execute(delete(Assignment).where(Assignment.experiment_id == existing.id))
                db.delete(existing)
                db.commit()

            n_users = int(sc.users * scale)
            # Completed experiments ended a few days ago; running ones end "now".
            end = now - timedelta(days=3) if sc.status == "completed" else now
            start = end - timedelta(days=sc.days)
            exp = Experiment(
                key=sc.key, name=sc.name, hypothesis=sc.hypothesis, description=sc.description,
                metric_type=sc.metric_type, metric_event=sc.metric_event, status=sc.status,
                traffic_allocation=sc.traffic_allocation, mde=sc.mde,
                created_at=start - timedelta(days=1),
                started_at=start if sc.status != "draft" else None,
                ended_at=end if sc.status == "completed" else None,
                variants=[
                    Variant(key="control", name="Control", weight=sc.weights[0], is_control=True, position=0),
                    Variant(key="treatment", name="Treatment", weight=sc.weights[1], position=1),
                ],
            )
            db.add(exp)
            db.flush()
            arms = {v.id: (sc.control if v.is_control else sc.treatment) for v in exp.variants}

            assignments, events = [], []
            arrivals = _arrival_times(rng, n_users, start, sc.days)
            for i, t0 in enumerate(arrivals):
                uid = f"{sc.key[:6]}-user-{i:06d}"
                if not in_experiment(exp.salt, uid, exp.traffic_allocation):
                    continue
                v = choose_variant(exp.salt, uid, exp.variants)
                assignments.append({"experiment_id": exp.id, "variant_id": v.id, "user_id": uid, "assigned_at": t0})
                for e in _user_events(rng, sc, arms[v.id], uid, t0, end):
                    events.append({"experiment_id": exp.id, "variant_id": v.id, **e})

            for chunk in range(0, len(assignments), 5000):
                db.execute(insert(Assignment), assignments[chunk:chunk + 5000])
            for chunk in range(0, len(events), 5000):
                db.execute(insert(Event), events[chunk:chunk + 5000])
            db.commit()
            print(f"  {sc.key:<28} {sc.status:<10} {len(assignments):>6,} users {len(events):>7,} events  | {sc.truth}")


# --------------------------------------------------------------------------- #
# HTTP API mode (exercises the real endpoints end-to-end)
# --------------------------------------------------------------------------- #
def run_api(base_url: str, api_key: str, scale: float, seed: int) -> None:
    import httpx

    rng = random.Random(seed)
    client = httpx.Client(base_url=base_url.rstrip("/") + "/api/v1", headers={"X-API-Key": api_key}, timeout=30)
    suffix = datetime.now().strftime("%m%d%H%M")
    for sc in SCENARIOS:
        if sc.status == "draft":
            continue
        payload = {
            "key": f"{sc.key}-{suffix}"[:64], "name": f"{sc.name} (API sim)", "hypothesis": sc.hypothesis,
            "metric_type": sc.metric_type, "metric_event": sc.metric_event,
            "traffic_allocation": sc.traffic_allocation, "mde": sc.mde,
            "variants": [
                {"key": "control", "name": "Control", "weight": sc.weights[0], "is_control": True},
                {"key": "treatment", "name": "Treatment", "weight": sc.weights[1]},
            ],
        }
        r = client.post("/experiments", json=payload)
        r.raise_for_status()
        exp = r.json()
        client.post(f"/experiments/{exp['id']}/start").raise_for_status()

        batch: list[dict] = []
        n_users = max(50, int(sc.users * scale))
        assigned = 0
        for i in range(n_users):
            uid = f"api-{sc.key[:6]}-{i:06d}"
            a = client.post("/assign", json={"experiment_key": exp["key"], "user_id": uid}).json()
            if not a["in_experiment"]:
                continue
            assigned += 1
            arm = sc.control if a["variant"] == "control" else sc.treatment
            now = datetime.now(UTC)
            for e in _user_events(rng, sc, arm, uid, now, now + timedelta(days=1)):
                batch.append({"experiment_key": exp["key"], "user_id": uid, "event_type": e["event_type"],
                              "value": e["value"]})
            if len(batch) >= 1000:
                client.post("/events/batch", json={"events": batch}).raise_for_status()
                batch = []
        if batch:
            client.post("/events/batch", json={"events": batch}).raise_for_status()
        print(f"  {exp['key']:<36} {assigned:>6,} users via API | {sc.truth}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["direct", "api"], default="direct")
    p.add_argument("--scale", type=float, default=1.0, help="Multiply user counts (e.g. 0.1 for a quick run)")
    p.add_argument("--reset", action="store_true", help="Regenerate demo experiments that already exist")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--api-key", default="dev-secret-key")
    args = p.parse_args(argv)

    print(f"ExperimentIQ simulator — mode={args.mode}, scale={args.scale}")
    if args.mode == "direct":
        run_direct(args.scale, args.reset, args.seed)
    else:
        run_api(args.base_url, args.api_key, args.scale, args.seed)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
