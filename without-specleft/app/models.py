"""SQLAlchemy database models for the document approval workflow."""

import enum
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.DRAFT, nullable=False
    )
    author_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Escalation configuration
    escalation_timeout_hours: Mapped[int] = mapped_column(Integer, default=24)
    max_escalation_depth: Mapped[int] = mapped_column(Integer, default=3)

    review_cycles: Mapped[List["ReviewCycle"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ReviewCycle.cycle_number",
    )

    @property
    def current_cycle(self) -> Optional["ReviewCycle"]:
        if self.review_cycles:
            return self.review_cycles[-1]
        return None


class ReviewCycle(Base):
    __tablename__ = "review_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    document: Mapped["Document"] = relationship(back_populates="review_cycles")
    assignments: Mapped[List["ReviewerAssignment"]] = relationship(
        back_populates="review_cycle", cascade="all, delete-orphan"
    )
    escalations: Mapped[List["Escalation"]] = relationship(
        back_populates="review_cycle", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "cycle_number", name="uq_document_cycle"),
    )


class ReviewerAssignment(Base):
    __tablename__ = "reviewer_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_cycle_id: Mapped[int] = mapped_column(
        ForeignKey("review_cycles.id"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision), default=ReviewDecision.PENDING, nullable=False
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Track if this decision was made by a delegate
    decided_by_delegate_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Track if this reviewer was added via escalation
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False)

    review_cycle: Mapped["ReviewCycle"] = relationship(back_populates="assignments")
    delegations: Mapped[List["Delegation"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("review_cycle_id", "reviewer_id", name="uq_cycle_reviewer"),
    )


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("reviewer_assignments.id"), nullable=False
    )
    delegator_id: Mapped[str] = mapped_column(String(100), nullable=False)
    delegate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    assignment: Mapped["ReviewerAssignment"] = relationship(
        back_populates="delegations"
    )

    @property
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        # SQLite may return naive datetimes; treat them as UTC
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return not self.revoked and expires > now


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_cycle_id: Mapped[int] = mapped_column(
        ForeignKey("review_cycles.id"), nullable=False
    )
    escalated_from_reviewer_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    escalated_to_reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    escalation_depth: Mapped[int] = mapped_column(Integer, default=1)
    escalated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    timeout_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    review_cycle: Mapped["ReviewCycle"] = relationship(back_populates="escalations")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[str] = mapped_column(String(100), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
