import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

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

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False, default="")
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.DRAFT)
    author_id = Column(String(100), nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Escalation configuration
    escalation_timeout_hours = Column(Integer, nullable=True, default=24)
    escalation_depth = Column(Integer, nullable=False, default=0)
    max_escalation_depth = Column(Integer, nullable=False, default=3)
    review_started_at = Column(DateTime, nullable=True)

    reviewers = relationship(
        "Reviewer", back_populates="document", cascade="all, delete-orphan"
    )
    review_decisions = relationship(
        "ReviewDecisionRecord", back_populates="document", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="document", cascade="all, delete-orphan"
    )
    delegations = relationship(
        "Delegation", back_populates="document", cascade="all, delete-orphan"
    )
    escalations = relationship(
        "Escalation", back_populates="document", cascade="all, delete-orphan"
    )

    @property
    def review_cycle(self) -> int:
        """Return the current (highest) review cycle, or 1 if none yet."""
        if not self.reviewers:
            return 1
        return max(r.review_cycle for r in self.reviewers)


class Reviewer(Base):
    __tablename__ = "reviewers"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(String(100), nullable=False)
    review_cycle = Column(Integer, nullable=False, default=1)

    document = relationship("Document", back_populates="reviewers")

    __table_args__ = (
        UniqueConstraint(
            "document_id", "user_id", "review_cycle", name="uq_reviewer_per_cycle"
        ),
    )


class ReviewDecisionRecord(Base):
    __tablename__ = "review_decisions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    reviewer_id = Column(String(100), nullable=False)
    decision = Column(Enum(ReviewDecision), nullable=False)
    reason = Column(Text, nullable=True)
    decided_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    review_cycle = Column(Integer, nullable=False, default=1)
    on_behalf_of = Column(
        String(100), nullable=True
    )  # For delegation: the original reviewer

    document = relationship("Document", back_populates="review_decisions")

    __table_args__ = (
        UniqueConstraint(
            "document_id", "reviewer_id", "review_cycle", name="uq_decision_per_cycle"
        ),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    document = relationship("Document", back_populates="notifications")


class Delegation(Base):
    __tablename__ = "delegations"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    delegator_id = Column(String(100), nullable=False)
    substitute_id = Column(String(100), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    revoked = Column(Boolean, nullable=False, default=False)

    document = relationship("Document", back_populates="delegations")


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    escalated_to = Column(String(100), nullable=False)
    escalation_level = Column(Integer, nullable=False)
    escalated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    timeout_hours = Column(Integer, nullable=False)

    document = relationship("Document", back_populates="escalations")
