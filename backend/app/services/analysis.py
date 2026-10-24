"""Turns raw assignments + events into an analysis an analyst would sign off on.

Pipeline:
  1. Load assignments (the denominator — every exposed user counts, even
     those who never fire an event; dropping them is a classic bias).
  2. Collapse metric events to one number per user (converted? / total value).
  3. Run the appropriate test (two-proportion z-test or Welch's t-test).
  4. Check sample-ratio mismatch and progress against the planned sample size.
  5. Produce a plain-English verdict that never over-claims.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import stats
from ..models import Assignment, Event, Experiment, MetricType
from ..schemas import ExperimentOut


def _utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo; treat naive timestamps as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iv(interval) -> dict | None:
    if interval is None:
        return None
    return {"low": interval.low, "high": interval.high}


def _pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:+.{digits}f}%"


def _rate(x: float) -> str:
    return f"{x * 100:.2f}%"


def _fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


@dataclass
class _User:
    variant_id: int
    assigned_at: datetime
    value: float = 0.0
    converted: bool = False
    events: list[tuple[datetime, float]] = field(default_factory=list)


def experiment_out(exp: Experiment, users: int = 0) -> dict:
    data = ExperimentOut.model_validate(exp).model_dump()
    data["users"] = users
    return data


def analyze(db: Session, exp: Experiment, min_users_per_variant: int = 100) -> dict:
    variants = list(exp.variants)
    control = next(v for v in variants if v.is_control)
    treatment = next(v for v in variants if not v.is_control)
    is_conversion = exp.metric_type == MetricType.conversion.value
    alpha = exp.alpha

    # ---- 1. load ---------------------------------------------------------- #
    users: dict[str, _User] = {}
    for user_id, variant_id, assigned_at in db.execute(
        select(Assignment.user_id, Assignment.variant_id, Assignment.assigned_at)
        .where(Assignment.experiment_id == exp.id)
    ):
        users[user_id] = _User(variant_id, _utc(assigned_at))

    # ---- 2. collapse events to one row per user --------------------------- #
    for user_id, ts, value in db.execute(
        select(Event.user_id, Event.created_at, Event.value)
        .where(Event.experiment_id == exp.id, Event.event_type == exp.metric_event)
        .order_by(Event.created_at)
    ):
        u = users.get(user_id)
        if u is None:
            continue
        v = float(value) if value is not None else 0.0
        u.converted = True
        u.value += v
        u.events.append((_utc(ts), v))

    by_variant: dict[int, list[_User]] = {v.id: [] for v in variants}
    for u in users.values():
        by_variant.setdefault(u.variant_id, []).append(u)

    # ---- 3. per-variant stats + comparison -------------------------------- #
    variant_results: list[dict] = []
    summaries: dict[int, stats.SampleSummary] = {}
    conv_counts: dict[int, tuple[int, int]] = {}
    for v in variants:
        group = by_variant.get(v.id, [])
        n = len(group)
        row: dict = {
            "variant_id": v.id, "key": v.key, "name": v.name,
            "is_control": v.is_control, "weight": v.weight, "users": n,
        }
        if is_conversion:
            x = sum(1 for u in group if u.converted)
            conv_counts[v.id] = (x, n)
            row.update(
                conversions=x,
                rate=(x / n) if n else None,
                rate_ci=_iv(stats.wilson_interval(x, n, alpha)) if n else None,
            )
        else:
            s = stats.SampleSummary.from_values(u.value for u in group)
            summaries[v.id] = s
            row.update(
                mean=s.mean if n else None,
                std=s.std if n > 1 else None,
                mean_ci=_iv(stats.mean_confidence_interval(s, alpha)) if n > 1 else None,
                conversions=sum(1 for u in group if u.converted),
            )
        variant_results.append(row)

    n_c = len(by_variant.get(control.id, []))
    n_t = len(by_variant.get(treatment.id, []))
    smallest = min(n_c, n_t)

    comparison: dict | None = None
    if is_conversion and n_c > 0 and n_t > 0:
        r = stats.two_proportion_ztest(*conv_counts[control.id], *conv_counts[treatment.id], alpha=alpha)
        comparison = {
            "test": "two_proportion_z_test", "statistic": r.z_stat, "df": None,
            "p_value": r.p_value, "alpha": alpha, "significant": r.significant,
            "absolute_diff": r.absolute_diff, "relative_lift": r.relative_lift,
            "ci_diff": _iv(r.ci_diff), "ci_relative_lift": _iv(r.ci_relative_lift),
        }
    elif not is_conversion and n_c > 1 and n_t > 1:
        r = stats.welch_ttest(summaries[control.id], summaries[treatment.id], alpha=alpha)
        comparison = {
            "test": "welch_t_test", "statistic": r.t_stat, "df": r.df,
            "p_value": r.p_value, "alpha": alpha, "significant": r.significant,
            "absolute_diff": r.absolute_diff, "relative_lift": r.relative_lift,
            "ci_diff": _iv(r.ci_diff), "ci_relative_lift": _iv(r.ci_relative_lift),
        }

    # ---- 4. data quality + planned sample size ---------------------------- #
    srm = stats.srm_check([n_c, n_t], [control.weight, treatment.weight])

    required: int | None = None
    try:
        if is_conversion and n_c > 0:
            baseline = conv_counts[control.id][0] / n_c
            if 0 < baseline < 1:
                required = stats.sample_size_proportions(
                    baseline, exp.mde, "relative", alpha, exp.power, traffic_split=treatment.weight
                ).per_variant
        elif not is_conversion and n_c > 1:
            s = summaries[control.id]
            if s.mean != 0 and s.std > 0:
                required = stats.sample_size_means(abs(s.mean), s.std, exp.mde, "relative", alpha, exp.power).per_variant
    except ValueError:
        required = None

    progress = {
        "required_per_variant": required,
        "smallest_variant": smallest,
        "fraction": (smallest / required) if required else None,
    }

    # ---- 5. verdict ------------------------------------------------------- #
    verdict = _verdict(exp, comparison, variant_results, smallest, required, min_users_per_variant,
                       control.name, treatment.name, is_conversion)

    warnings: list[str] = []
    if srm.mismatch:
        warnings.append(
            f"Sample ratio mismatch: observed {n_c:,} vs {n_t:,} users but expected "
            f"{srm.expected[0]:,.0f} vs {srm.expected[1]:,.0f} ({_fmt_p(srm.p_value)}). "
            "Assignment or logging is likely broken — do not trust these results until it is explained."
        )
    if comparison and comparison["significant"] and required and smallest < required:
        warnings.append(
            "Significant before reaching the planned sample size. Stopping early because a result "
            "looks significant (\"peeking\") inflates the false-positive rate well above "
            f"{alpha:.0%}. Keep running to {required:,} users per variant before deciding."
        )

    return {
        "experiment": experiment_out(exp, len(users)),
        "variants": variant_results,
        "comparison": comparison,
        "verdict": verdict,
        "srm": srm.to_dict(),
        "progress": progress,
        "timeseries": _timeseries(users, control.id, treatment.id, is_conversion, alpha),
        "warnings": warnings,
        "computed_at": datetime.now(timezone.utc),
    }


def _verdict(exp, comparison, variant_results, smallest, required, min_n,
             control_name, treatment_name, is_conversion) -> dict:
    conf = f"{1 - exp.alpha:.0%}"
    if comparison is None or smallest < min_n:
        return {
            "status": "not_enough_data",
            "headline": "Not enough data yet",
            "detail": f"Each variant needs at least {min_n:,} users before results are meaningful "
                      f"(smallest variant currently has {smallest:,}).",
        }

    c = next(v for v in variant_results if v["is_control"])
    t = next(v for v in variant_results if not v["is_control"])
    if is_conversion:
        movement = f"Conversion went from {_rate(c['rate'])} ({control_name}) to {_rate(t['rate'])} ({treatment_name})"
    else:
        movement = (f"Average {exp.metric_event} per user went from {c['mean']:.2f} ({control_name}) "
                    f"to {t['mean']:.2f} ({treatment_name})")

    lift = comparison["relative_lift"]
    ci = comparison["ci_relative_lift"]
    lift_txt = f"a relative lift of {_pct(lift)}"
    if ci:
        lift_txt += f" ({conf} CI {_pct(ci['low'])} to {_pct(ci['high'])})"
    p_txt = _fmt_p(comparison["p_value"])

    if comparison["significant"]:
        positive = comparison["absolute_diff"] > 0
        return {
            "status": "significant_positive" if positive else "significant_negative",
            "headline": (f"{treatment_name} is significantly better" if positive
                         else f"{treatment_name} is significantly worse"),
            "detail": f"{movement}, {lift_txt}; {p_txt}. If there were truly no difference, a gap "
                      f"this large would show up less than {exp.alpha:.0%} of the time.",
        }

    if required is not None and smallest >= required:
        return {
            "status": "no_significant_difference",
            "headline": "No significant difference",
            "detail": f"{movement} ({p_txt}). The planned sample size was reached, so a real effect "
                      f"of {exp.mde:.0%} or more would very likely have been detected. "
                      "Any true effect is probably small — keep the simpler option.",
        }

    need = f" Roughly {required:,} users per variant are needed to reliably detect a {exp.mde:.0%} lift; " \
           f"you have {smallest:,} ({smallest / required:.0%})." if required else ""
    return {
        "status": "not_enough_data",
        "headline": "Not enough data yet",
        "detail": f"No significant difference so far ({p_txt}).{need} "
                  "Absence of evidence is not evidence of absence — keep the test running.",
    }


# --------------------------------------------------------------------------- #
# Cumulative time series (makes the "peeking" problem visible on the chart)
# --------------------------------------------------------------------------- #
_STEPS = [timedelta(days=1), timedelta(hours=6), timedelta(hours=1),
          timedelta(minutes=15), timedelta(minutes=5), timedelta(minutes=1)]
_MAX_POINTS = 90


def _timeseries(users: dict[str, _User], control_id: int, treatment_id: int,
                is_conversion: bool, alpha: float) -> list[dict]:
    if not users:
        return []
    assigns = sorted(users.items(), key=lambda kv: kv[1].assigned_at)
    events = sorted(((ts, uid, val) for uid, u in users.items() for ts, val in u.events), key=lambda e: e[0])
    start = assigns[0][1].assigned_at
    end = max(assigns[-1][1].assigned_at, events[-1][0] if events else start)
    span = end - start
    if span.total_seconds() <= 0:
        return []

    step = _STEPS[-1]
    for s in _STEPS:
        if span / s >= 6:
            step = s
            break
    if span / step > _MAX_POINTS:
        step = span / _MAX_POINTS

    # running aggregates per variant: n, conversions, sum, sumsq
    agg = {vid: [0, 0, 0.0, 0.0] for vid in (control_id, treatment_id)}
    active: set[str] = set()
    current: dict[str, float] = {}
    converted: set[str] = set()
    pending: dict[str, list[float]] = {}

    def apply_event(uid: str, val: float) -> None:
        a = agg[users[uid].variant_id]
        if uid not in converted:
            converted.add(uid)
            a[1] += 1
        old = current[uid]
        new = old + val
        current[uid] = new
        a[2] += val
        a[3] += new * new - old * old

    points: list[dict] = []
    ai = ei = 0
    boundary = start + step
    while True:
        b = min(boundary, end)
        while ai < len(assigns) and assigns[ai][1].assigned_at <= b:
            uid, u = assigns[ai]
            agg[u.variant_id][0] += 1
            active.add(uid)
            current[uid] = 0.0
            for val in pending.pop(uid, []):
                apply_event(uid, val)
            ai += 1
        while ei < len(events) and events[ei][0] <= b:
            _, uid, val = events[ei]
            if uid in active:
                apply_event(uid, val)
            else:
                pending.setdefault(uid, []).append(val)
            ei += 1
        points.append(_point(b, agg[control_id], agg[treatment_id], is_conversion, alpha))
        if b >= end:
            break
        boundary += step
    return points


def _point(t: datetime, c: list, tr: list, is_conversion: bool, alpha: float) -> dict:
    n_c, x_c, s_c, ss_c = c
    n_t, x_t, s_t, ss_t = tr
    p_value = None
    if is_conversion:
        cv = x_c / n_c if n_c else None
        tv = x_t / n_t if n_t else None
        if n_c and n_t:
            p_value = stats.two_proportion_ztest(x_c, n_c, x_t, n_t, alpha).p_value
    else:
        cv = s_c / n_c if n_c else None
        tv = s_t / n_t if n_t else None
        if n_c > 1 and n_t > 1:
            var_c = max(0.0, (ss_c - s_c * s_c / n_c) / (n_c - 1))
            var_t = max(0.0, (ss_t - s_t * s_t / n_t) / (n_t - 1))
            if var_c > 0 or var_t > 0:
                p_value = stats.welch_ttest(
                    stats.SampleSummary(n_c, cv, var_c), stats.SampleSummary(n_t, tv, var_t), alpha
                ).p_value
    if p_value is not None and math.isnan(p_value):
        p_value = None
    return {"t": t, "control": cv, "treatment": tv, "p_value": p_value}
