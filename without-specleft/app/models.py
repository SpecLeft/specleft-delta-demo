from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.DRAFT, index=True
    )
    author_id: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    review_cycle: Mapped[int] = mapped_column(Integer, default=1)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalation_max_level: Mapped[int] = mapped_column(Integer, default=2)
    escalation_timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    escalation_deadline: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    reviewers: Mapped[list["DocumentReviewer"]] = relationship(
        "DocumentReviewer", back_populates="document", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["ReviewDecisionRecord"]] = relationship(
        "ReviewDecisionRecord", back_populates="document", cascade="all, delete-orphan"
    )
    delegations: Mapped[list["Delegation"]] = relationship(
        "Delegation", back_populates="document", cascade="all, delete-orphan"
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        "Escalation", back_populates="document", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentReviewer(Base):
    __tablename__ = "document_reviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    reviewer_id: Mapped[str] = mapped_column(String(50), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship("Document", back_populates="reviewers")

    __table_args__ = (
        UniqueConstraint("document_id", "reviewer_id", name="uq_document_reviewer"),
    )


class ReviewDecisionRecord(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    reviewer_id: Mapped[str] = mapped_column(String(50), index=True)
    decision: Mapped[ReviewDecision] = mapped_column(Enum(ReviewDecision))
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    acting_on_behalf_of: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_cycle: Mapped[int] = mapped_column(Integer, default=1)

    document: Mapped[Document] = relationship("Document", back_populates="decisions")

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "reviewer_id",
            "review_cycle",
            name="uq_review_decision",
        ),
    )


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    delegator_id: Mapped[str] = mapped_column(String(50), index=True)
    substitute_id: Mapped[str] = mapped_column(String(50), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="delegations")

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "delegator_id",
            name="uq_delegation_delegator",
        ),
    )


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    escalated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    from_level: Mapped[int] = mapped_column(Integer)
    to_level: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[str] = mapped_column(String(50), index=True)

    document: Mapped[Document] = relationship("Document", back_populates="escalations")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    recipient_id: Mapped[str] = mapped_column(String(50), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(
        "Document", back_populates="notifications"
    )
