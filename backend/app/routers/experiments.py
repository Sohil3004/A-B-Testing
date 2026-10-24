from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import Assignment, Experiment, ExperimentStatus, Variant
from ..schemas import ExperimentCreate, ExperimentOut, ExperimentUpdate, ResultsOut
from ..services.analysis import analyze, experiment_out

router = APIRouter(prefix="/experiments", tags=["experiments"])

# Allowed lifecycle transitions: action -> (allowed from-states, to-state)
TRANSITIONS: dict[str, tuple[set[ExperimentStatus], ExperimentStatus]] = {
    "start": ({ExperimentStatus.draft, ExperimentStatus.paused}, ExperimentStatus.running),
    "pause": ({ExperimentStatus.running}, ExperimentStatus.paused),
    "end": ({ExperimentStatus.running, ExperimentStatus.paused}, ExperimentStatus.completed),
}
DRAFT_ONLY_FIELDS = {"metric_type", "metric_event", "traffic_allocation", "alpha", "power", "mde", "variants"}


def _get(db: Session, experiment_id: int) -> Experiment:
    exp = db.get(Experiment, experiment_id)
    if exp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    return exp


def _user_counts(db: Session, ids: list[int] | None = None) -> dict[int, int]:
    q = select(Assignment.experiment_id, func.count()).group_by(Assignment.experiment_id)
    if ids is not None:
        q = q.where(Assignment.experiment_id.in_(ids))
    return dict(db.execute(q).all())


@router.post("", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    exp = Experiment(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        hypothesis=payload.hypothesis,
        metric_type=payload.metric_type.value,
        metric_event=payload.metric_event,
        traffic_allocation=payload.traffic_allocation,
        alpha=payload.alpha,
        power=payload.power,
        mde=payload.mde,
        variants=[
            Variant(key=v.key, name=v.name, weight=v.weight, is_control=v.is_control, position=i)
            for i, v in enumerate(payload.variants)
        ],
    )
    db.add(exp)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Experiment key '{payload.key}' already exists"
        ) from None
    db.refresh(exp)
    return experiment_out(exp)


@router.get("", response_model=list[ExperimentOut])
def list_experiments(
    status_filter: ExperimentStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    q = select(Experiment).order_by(Experiment.created_at.desc(), Experiment.id.desc())
    if status_filter:
        q = q.where(Experiment.status == status_filter.value)
    exps = list(db.scalars(q))
    counts = _user_counts(db, [e.id for e in exps])
    return [experiment_out(e, counts.get(e.id, 0)) for e in exps]


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = _get(db, experiment_id)
    return experiment_out(exp, _user_counts(db, [exp.id]).get(exp.id, 0))


@router.patch("/{experiment_id}", response_model=ExperimentOut)
def update_experiment(experiment_id: int, payload: ExperimentUpdate, db: Session = Depends(get_db)):
    exp = _get(db, experiment_id)
    changes = payload.model_dump(exclude_unset=True)
    locked = DRAFT_ONLY_FIELDS & changes.keys()
    if locked and exp.status != ExperimentStatus.draft.value:
        # Changing the design mid-flight invalidates the data already collected.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot change {sorted(locked)} after the experiment has started",
        )
    variants = changes.pop("variants", None)
    for field, value in changes.items():
        setattr(exp, field, value.value if hasattr(value, "value") else value)
    if variants is not None:
        exp.variants.clear()
        db.flush()
        exp.variants.extend(
            Variant(key=v["key"], name=v["name"], weight=v["weight"], is_control=v["is_control"], position=i)
            for i, v in enumerate(variants)
        )
    db.commit()
    db.refresh(exp)
    return experiment_out(exp, _user_counts(db, [exp.id]).get(exp.id, 0))


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, experiment_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _transition(experiment_id: int, action: str, db: Session) -> dict:
    exp = _get(db, experiment_id)
    allowed_from, to_state = TRANSITIONS[action]
    current = ExperimentStatus(exp.status)
    if current not in allowed_from:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot {action} an experiment that is {current.value}")
    now = datetime.now(UTC)
    exp.status = to_state.value
    if action == "start" and exp.started_at is None:
        exp.started_at = now
    if action == "end":
        exp.ended_at = now
    db.commit()
    db.refresh(exp)
    return experiment_out(exp, _user_counts(db, [exp.id]).get(exp.id, 0))


@router.post("/{experiment_id}/start", response_model=ExperimentOut)
def start_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """Start a draft experiment, or resume a paused one."""
    return _transition(experiment_id, "start", db)


@router.post("/{experiment_id}/pause", response_model=ExperimentOut)
def pause_experiment(experiment_id: int, db: Session = Depends(get_db)):
    return _transition(experiment_id, "pause", db)


@router.post("/{experiment_id}/end", response_model=ExperimentOut)
def end_experiment(experiment_id: int, db: Session = Depends(get_db)):
    return _transition(experiment_id, "end", db)


@router.get("/{experiment_id}/results", response_model=ResultsOut)
def get_results(
    experiment_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return analyze(db, _get(db, experiment_id), settings.min_users_per_variant)
