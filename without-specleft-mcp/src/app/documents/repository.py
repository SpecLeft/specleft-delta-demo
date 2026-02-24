from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.documents.models import (
    Delegation,
    Document,
    DocumentStatus,
    Escalation,
    ReviewerAssignment,
    ReviewDecision,
)


class DocumentRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_document(self, title: str, content: str, author_id: int) -> Document:
        document = Document(title=title, content=content, author_id=author_id)
        self._session.add(document)
        return document

    def get_document(self, document_id: int) -> Document | None:
        return self._session.get(Document, document_id)

    def list_documents(self) -> list[Document]:
        return list(self._session.scalars(select(Document).order_by(Document.id)))

    def update_document(self, document: Document, title: str, content: str) -> Document:
        document.title = title
        document.content = content
        return document

    def add_reviewers(self, document: Document, reviewer_ids: list[int]) -> None:
        for reviewer_id in reviewer_ids:
            document.reviewers.append(ReviewerAssignment(reviewer_id=reviewer_id))

    def clear_reviewers(self, document: Document) -> None:
        for assignment in document.reviewers:
            assignment.active = False

    def get_active_reviewer_ids(self, document_id: int) -> list[int]:
        stmt = select(ReviewerAssignment.reviewer_id).where(
            ReviewerAssignment.document_id == document_id,
            ReviewerAssignment.active.is_(True),
        )
        return list(self._session.scalars(stmt))

    def record_decision(
        self,
        document: Document,
        reviewer_id: int,
        decision: str,
        reason: str | None = None,
        delegated_by: int | None = None,
    ) -> ReviewDecision:
        entry = ReviewDecision(
            document=document,
            reviewer_id=reviewer_id,
            decision=decision,
            reason=reason,
            delegated_by=delegated_by,
        )
        self._session.add(entry)
        return entry

    def reviewer_has_decision(
        self, document_id: int, reviewer_id: int, cycle_start: datetime | None
    ) -> bool:
        conditions = [
            ReviewDecision.document_id == document_id,
            ReviewDecision.reviewer_id == reviewer_id,
        ]
        if cycle_start:
            conditions.append(ReviewDecision.decided_at >= cycle_start)
        stmt = select(func.count(ReviewDecision.id)).where(*conditions)
        return (self._session.scalar(stmt) or 0) > 0

    def record_delegation(
        self,
        document: Document,
        delegator_id: int,
        substitute_id: int,
        expires_at: datetime,
    ) -> Delegation:
        delegation = Delegation(
            document=document,
            delegator_id=delegator_id,
            substitute_id=substitute_id,
            expires_at=expires_at,
        )
        self._session.add(delegation)
        return delegation

    def get_active_delegation(
        self, document_id: int, delegator_id: int
    ) -> Delegation | None:
        stmt = select(Delegation).where(
            Delegation.document_id == document_id,
            Delegation.delegator_id == delegator_id,
            Delegation.revoked.is_(False),
        )
        return self._session.scalar(stmt)

    def get_delegation_by_substitute(
        self, document_id: int, substitute_id: int, include_revoked: bool = False
    ) -> Delegation | None:
        conditions = [
            Delegation.document_id == document_id,
            Delegation.substitute_id == substitute_id,
        ]
        if not include_revoked:
            conditions.append(Delegation.revoked.is_(False))
        stmt = select(Delegation).where(*conditions)
        return self._session.scalar(stmt)

    def revoke_delegation(self, delegation: Delegation) -> Delegation:
        delegation.revoked = True
        return delegation

    def add_escalation(
        self, document: Document, escalated_to_id: int, depth: int
    ) -> Escalation:
        escalation = Escalation(
            document=document, escalated_to_id=escalated_to_id, depth=depth
        )
        self._session.add(escalation)
        return escalation

    def update_status(self, document: Document, status: DocumentStatus) -> Document:
        document.status = status
        return document

    def set_escalation_deadline(
        self, document: Document, deadline: datetime
    ) -> Document:
        document.escalation_deadline = deadline
        return document

    def set_escalation_depth(self, document: Document, depth: int) -> Document:
        document.escalation_depth = depth
        return document

    def pending_reviewer_ids(
        self, document_id: int, cycle_start: datetime | None
    ) -> list[int]:
        reviewer_stmt = select(ReviewerAssignment.reviewer_id).where(
            ReviewerAssignment.document_id == document_id,
            ReviewerAssignment.active.is_(True),
        )
        reviewers = set(self._session.scalars(reviewer_stmt))

        decision_conditions = [ReviewDecision.document_id == document_id]
        if cycle_start:
            decision_conditions.append(ReviewDecision.decided_at >= cycle_start)
        decision_stmt = select(ReviewDecision.reviewer_id).where(*decision_conditions)
        decided = set(self._session.scalars(decision_stmt))
        return sorted(reviewers - decided)

    def get_decisions(self, document_id: int) -> list[ReviewDecision]:
        stmt = select(ReviewDecision).where(ReviewDecision.document_id == document_id)
        return list(self._session.scalars(stmt))

    def has_rejection_in_cycle(
        self, document_id: int, cycle_start: datetime | None
    ) -> bool:
        conditions = [
            ReviewDecision.document_id == document_id,
            ReviewDecision.decision == "rejected",
        ]
        if cycle_start:
            conditions.append(ReviewDecision.decided_at >= cycle_start)
        stmt = select(func.count(ReviewDecision.id)).where(*conditions)
        return (self._session.scalar(stmt) or 0) > 0

    def latest_rejection(self, document_id: int) -> ReviewDecision | None:
        stmt = (
            select(ReviewDecision)
            .where(
                ReviewDecision.document_id == document_id,
                ReviewDecision.decision == "rejected",
            )
            .order_by(ReviewDecision.decided_at.desc())
        )
        return self._session.scalar(stmt)

    def review_cycle_decisions(
        self, document_id: int, cycle_start: datetime
    ) -> list[ReviewDecision]:
        stmt = select(ReviewDecision).where(
            ReviewDecision.document_id == document_id,
            ReviewDecision.decided_at >= cycle_start,
        )
        return list(self._session.scalars(stmt))

    def get_escalations(self, document_id: int) -> list[Escalation]:
        stmt = select(Escalation).where(Escalation.document_id == document_id)
        return list(self._session.scalars(stmt))

    def active_reviewer_assignments(self, document_id: int) -> list[ReviewerAssignment]:
        stmt = select(ReviewerAssignment).where(
            ReviewerAssignment.document_id == document_id,
            ReviewerAssignment.active.is_(True),
        )
        return list(self._session.scalars(stmt))

    def assign_reviewer_if_missing(
        self, document: Document, reviewer_id: int
    ) -> ReviewerAssignment:
        stmt = select(ReviewerAssignment).where(
            ReviewerAssignment.document_id == document.id,
            ReviewerAssignment.reviewer_id == reviewer_id,
            ReviewerAssignment.active.is_(True),
        )
        existing = self._session.scalar(stmt)
        if existing:
            return existing
        assignment = ReviewerAssignment(reviewer_id=reviewer_id)
        document.reviewers.append(assignment)
        return assignment

    def has_active_reviewer(self, document_id: int, reviewer_id: int) -> bool:
        stmt = select(func.count(ReviewerAssignment.id)).where(
            ReviewerAssignment.document_id == document_id,
            ReviewerAssignment.reviewer_id == reviewer_id,
            ReviewerAssignment.active.is_(True),
        )
        return (self._session.scalar(stmt) or 0) > 0

    def remove_pending_reviewers(self, document_id: int) -> None:
        stmt = select(ReviewerAssignment).where(
            ReviewerAssignment.document_id == document_id,
            ReviewerAssignment.active.is_(True),
        )
        for assignment in self._session.scalars(stmt):
            assignment.active = False
