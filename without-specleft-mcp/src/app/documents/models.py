from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if False:  # pragma: no cover
    from app.documents.models import (
        ReviewerAssignment,
        ReviewDecision,
        Delegation,
        Escalation,
    )

from app.db import Base


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    review_cycle_started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    escalation_deadline: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    escalation_depth: Mapped[int] = mapped_column(Integer, default=0)

    reviewers: Mapped[list[ReviewerAssignment]] = relationship(
        "ReviewerAssignment", back_populates="document", cascade="all, delete-orphan"
    )
    decisions: Mapped[list[ReviewDecision]] = relationship(
        "ReviewDecision", back_populates="document", cascade="all, delete-orphan"
    )
    delegations: Mapped[list[Delegation]] = relationship(
        "Delegation", back_populates="document", cascade="all, delete-orphan"
    )
    escalations: Mapped[list[Escalation]] = relationship(
        "Escalation", back_populates="document", cascade="all, delete-orphan"
    )


class ReviewerAssignment(Base):
    __tablename__ = "reviewer_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(Integer, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship("Document", back_populates="reviewers")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(Integer, index=True)
    decision: Mapped[str] = mapped_column(String(20))
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    delegated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="decisions")


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    delegator_id: Mapped[int] = mapped_column(Integer, index=True)
    substitute_id: Mapped[int] = mapped_column(Integer, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship("Document", back_populates="delegations")


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    escalated_to_id: Mapped[int] = mapped_column(Integer, index=True)
    escalated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    depth: Mapped[int] = mapped_column(Integer)

    document: Mapped[Document] = relationship("Document", back_populates="escalations")
