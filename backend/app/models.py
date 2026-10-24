"""Relational schema.

    experiments 1──* variants
    experiments 1──* assignments *──1 variants     (unique: experiment_id + user_id)
    experiments 1──* events      *──1 variants     (variant denormalised for fast GROUP BY)
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# BIGINT on Postgres, but SQLite only auto-increments "INTEGER PRIMARY KEY".
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


def utcnow() -> datetime:
    return datetime.now(UTC)


class MetricType(str, Enum):
    conversion = "conversion"   # did the user fire `metric_event` at least once?
    continuous = "continuous"   # sum of `value` on `metric_event` per user (e.g. revenue)


class ExperimentStatus(str, Enum):
    draft = "draft"
    running = "running"
    paused = "paused"
    completed = "completed"


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    hypothesis: Mapped[str] = mapped_column(Text, default="")

    metric_type: Mapped[str] = mapped_column(String(16), default=MetricType.conversion.value)
    metric_event: Mapped[str] = mapped_column(String(64))
    traffic_allocation: Mapped[float] = mapped_column(Float, default=1.0)

    # Analysis plan, fixed up front (pre-registration helps avoid p-hacking).
    alpha: Mapped[float] = mapped_column(Float, default=0.05)
    power: Mapped[float] = mapped_column(Float, default=0.8)
    mde: Mapped[float] = mapped_column(Float, default=0.10)  # relative minimum detectable effect

    status: Mapped[str] = mapped_column(String(16), default=ExperimentStatus.draft.value, index=True)
    # Per-experiment salt: the same user lands in independent buckets across experiments.
    salt: Mapped[str] = mapped_column(String(32), default=lambda: secrets.token_hex(8))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    variants: Mapped[list[Variant]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="Variant.position",
        lazy="selectin",
    )


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("experiment_id", "key", name="uq_variant_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    weight: Mapped[float] = mapped_column(Float)  # share of in-experiment traffic, sums to 1
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    experiment: Mapped[Experiment] = relationship(back_populates="variants")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "user_id", name="uq_assignment_user"),
        Index("ix_assignment_exp_variant", "experiment_id", "variant_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(128))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_event_exp_type_user", "experiment_id", "event_type", "user_id"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
