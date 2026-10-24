from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..assignment import choose_variant, in_experiment
from ..db import get_db
from ..models import Assignment, Event, Experiment, ExperimentStatus
from ..schemas import AssignRequest, AssignResponse, EventBatch, EventIn, EventIngestResult

router = APIRouter(tags=["assignment & events"])

EVENT_ACCEPTING = {ExperimentStatus.running.value, ExperimentStatus.paused.value}


def _by_key(db: Session, key: str) -> Experiment:
    exp = db.scalar(select(Experiment).where(Experiment.key == key))
    if exp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Experiment '{key}' not found")
    return exp


@router.post("/assign", response_model=AssignResponse)
def assign(req: AssignRequest, db: Session = Depends(get_db)):
    """Return the variant for a user. Idempotent: same user → same variant.

    Users outside the traffic allocation, or any user while the experiment is
    not running, get the control experience and are *not* recorded, so they
    never pollute the analysis.
    """
    exp = _by_key(db, req.experiment_key)
    control = next(v for v in exp.variants if v.is_control)

    def response(variant_key: str, in_exp: bool, reason: str) -> AssignResponse:
        return AssignResponse(experiment_key=exp.key, user_id=req.user_id,
                              variant=variant_key, in_experiment=in_exp, reason=reason)

    if exp.status != ExperimentStatus.running.value:
        return response(control.key, False, "experiment_not_running")

    existing = db.scalar(select(Assignment).where(
        Assignment.experiment_id == exp.id, Assignment.user_id == req.user_id))
    if existing:
        variant = next(v for v in exp.variants if v.id == existing.variant_id)
        return response(variant.key, True, "existing")

    if not in_experiment(exp.salt, req.user_id, exp.traffic_allocation):
        return response(control.key, False, "not_in_allocation")

    variant = choose_variant(exp.salt, req.user_id, exp.variants)
    db.add(Assignment(experiment_id=exp.id, variant_id=variant.id, user_id=req.user_id))
    try:
        db.commit()
    except IntegrityError:
        # Concurrent request for the same user won the race; hashing guarantees
        # it chose the same variant, so the answer is unchanged.
        db.rollback()
        return response(variant.key, True, "existing")
    return response(variant.key, True, "assigned")


def _ingest(db: Session, events: list[EventIn]) -> EventIngestResult:
    experiments: dict[str, Experiment | None] = {}
    users_by_key: dict[str, set[str]] = defaultdict(set)
    for e in events:
        if e.experiment_key not in experiments:
            experiments[e.experiment_key] = db.scalar(select(Experiment).where(Experiment.key == e.experiment_key))
        users_by_key[e.experiment_key].add(e.user_id)

    # One query per experiment to resolve user -> variant for the whole batch.
    assigned: dict[tuple[str, str], int] = {}
    for key, user_ids in users_by_key.items():
        exp = experiments[key]
        if exp is None:
            continue
        for uid, vid in db.execute(select(Assignment.user_id, Assignment.variant_id).where(
                Assignment.experiment_id == exp.id, Assignment.user_id.in_(user_ids))):
            assigned[(key, uid)] = vid

    accepted, errors = 0, []
    now = datetime.now(timezone.utc)
    for i, e in enumerate(events):
        exp = experiments[e.experiment_key]
        if exp is None:
            errors.append(f"[{i}] unknown experiment '{e.experiment_key}'")
            continue
        if exp.status not in EVENT_ACCEPTING:
            errors.append(f"[{i}] experiment '{exp.key}' is {exp.status}")
            continue
        variant_id = assigned.get((e.experiment_key, e.user_id))
        if variant_id is None:
            errors.append(f"[{i}] user '{e.user_id}' is not assigned to '{exp.key}' (call /assign first)")
            continue
        db.add(Event(experiment_id=exp.id, variant_id=variant_id, user_id=e.user_id,
                     event_type=e.event_type, value=e.value, created_at=e.timestamp or now))
        accepted += 1
    db.commit()
    return EventIngestResult(accepted=accepted, rejected=len(errors), errors=errors[:50])


@router.post("/events", response_model=EventIngestResult, status_code=status.HTTP_202_ACCEPTED)
def log_event(event: EventIn, db: Session = Depends(get_db)):
    result = _ingest(db, [event])
    if result.rejected:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result.errors[0].split("] ", 1)[1])
    return result


@router.post("/events/batch", response_model=EventIngestResult, status_code=status.HTTP_202_ACCEPTED)
def log_events_batch(batch: EventBatch, db: Session = Depends(get_db)):
    """Bulk ingestion (up to 5,000 events). Partial success: bad rows are reported, good rows stored."""
    return _ingest(db, batch.events)
