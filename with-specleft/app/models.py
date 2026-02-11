from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    review_cycles = relationship("ReviewCycle", back_populates="document")


class ReviewCycle(Base):
    __tablename__ = "review_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    cycle_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    document = relationship("Document", back_populates="review_cycles")
    assignments = relationship("ReviewerAssignment", back_populates="cycle")
    decisions = relationship("ReviewDecision", back_populates="cycle")
    escalation_state = relationship(
        "EscalationState", back_populates="cycle", uselist=False
    )


class ReviewerAssignment(Base):
    __tablename__ = "reviewer_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("review_cycles.id"))
    reviewer_id: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    cycle = relationship("ReviewCycle", back_populates="assignments")

    __table_args__ = (UniqueConstraint("cycle_id", "reviewer_id"),)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("review_cycles.id"))
    reviewer_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    acted_by: Mapped[str] = mapped_column(String)
    decided_at: Mapped[datetime] = mapped_column(DateTime)

    cycle = relationship("ReviewCycle", back_populates="decisions")

    __table_args__ = (UniqueConstraint("cycle_id", "reviewer_id"),)


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("review_cycles.id"))
    delegator_id: Mapped[str] = mapped_column(String)
    substitute_id: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("cycle_id", "delegator_id"),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(String)
    recipient_id: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class EscalationState(Base):
    __tablename__ = "escalation_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("review_cycles.id"))
    timeout_hours: Mapped[int] = mapped_column(Integer)
    ladder_json: Mapped[str] = mapped_column(Text)
    current_index: Mapped[int] = mapped_column(Integer)
    next_escalation_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cycle = relationship("ReviewCycle", back_populates="escalation_state")
