from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Delegation,
    Document,
    DocumentReviewer,
    DocumentStatus,
    Escalation,
    Notification,
    ReviewDecision,
    ReviewDecisionRecord,
)


class WorkflowError(ValueError):
    pass


def _now(value: datetime | None = None) -> datetime:
    return value or datetime.utcnow()


def _get_document(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise WorkflowError("Document not found")
    return document


def _get_active_reviewers(document: Document) -> list[DocumentReviewer]:
    return [reviewer for reviewer in document.reviewers if reviewer.active]


def _decision_key(decision: ReviewDecisionRecord) -> str:
    return decision.acting_on_behalf_of or decision.reviewer_id


def _get_decision_map(document: Document) -> dict[str, ReviewDecisionRecord]:
    return {
        _decision_key(decision): decision
        for decision in document.decisions
        if decision.review_cycle == document.review_cycle
    }


def _pending_reviewers(document: Document) -> list[str]:
    decision_map = _get_decision_map(document)
    return [
        reviewer.reviewer_id
        for reviewer in _get_active_reviewers(document)
        if reviewer.reviewer_id not in decision_map
    ]


def _ensure_not_author(document: Document, reviewer_id: str) -> None:
    if reviewer_id == document.author_id:
        raise WorkflowError("Self-approval is not permitted")


def _ensure_review_state(document: Document) -> None:
    if document.status != DocumentStatus.REVIEW:
        raise WorkflowError("Document is not in review")


def _ensure_editable(document: Document) -> None:
    if document.status == DocumentStatus.REVIEW:
        raise WorkflowError("Document is under review")
    if document.status == DocumentStatus.APPROVED:
        raise WorkflowError("Document is locked")


def create_document(
    db: Session,
    title: str,
    content: str,
    author_id: str,
    escalation_timeout_seconds: int | None = None,
    escalation_max_level: int | None = None,
) -> Document:
    document = Document(title=title, content=content, author_id=author_id)
    if escalation_timeout_seconds is not None:
        document.escalation_timeout_seconds = escalation_timeout_seconds
    if escalation_max_level is not None:
        document.escalation_max_level = escalation_max_level
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def update_document(
    db: Session, document_id: int, title: str, content: str
) -> Document:
    document = _get_document(db, document_id)
    _ensure_editable(document)
    document.title = title
    document.content = content
    db.commit()
    db.refresh(document)
    return document


def assign_reviewers(db: Session, document: Document, reviewer_ids: list[str]) -> None:
    for reviewer_id in reviewer_ids:
        existing = db.scalar(
            select(DocumentReviewer).where(
                DocumentReviewer.document_id == document.id,
                DocumentReviewer.reviewer_id == reviewer_id,
            )
        )
        if existing:
            continue
        db.add(DocumentReviewer(document_id=document.id, reviewer_id=reviewer_id))


def submit_for_review(
    db: Session, document_id: int, reviewer_ids: list[str]
) -> Document:
    document = _get_document(db, document_id)
    if document.status not in {DocumentStatus.DRAFT, DocumentStatus.REJECTED}:
        raise WorkflowError("Only draft or rejected documents can be submitted")
    if not reviewer_ids:
        raise WorkflowError("At least one reviewer is required")

    if document.status == DocumentStatus.REJECTED:
        document.review_cycle += 1
        document.status = DocumentStatus.DRAFT
        document.reviewers.clear()
        document.delegations.clear()
        document.escalations.clear()

    assign_reviewers(db, document, reviewer_ids)
    document.status = DocumentStatus.REVIEW
    document.escalation_level = 0
    document.escalation_deadline = _now() + timedelta(
        seconds=document.escalation_timeout_seconds
    )
    for reviewer_id in reviewer_ids:
        db.add(
            Notification(
                document_id=document.id,
                recipient_id=reviewer_id,
                message=f"Document {document.id} submitted for review",
            )
        )
    db.commit()
    db.refresh(document)
    return document


def _find_delegation(
    document: Document, substitute_id: str, now: datetime
) -> Delegation | None:
    for delegation in document.delegations:
        if (
            delegation.substitute_id == substitute_id
            and delegation.active
            and delegation.expires_at > now
        ):
            return delegation
    return None


def delegate_reviewer(
    db: Session,
    document_id: int,
    delegator_id: str,
    substitute_id: str,
    expires_at: datetime,
) -> Delegation:
    document = _get_document(db, document_id)
    if delegator_id == substitute_id:
        raise WorkflowError("Delegator and substitute must differ")
    now_value = _now()
    delegator_is_substitute = db.scalar(
        select(Delegation).where(
            Delegation.document_id == document.id,
            Delegation.substitute_id == delegator_id,
            Delegation.active.is_(True),
            Delegation.expires_at > now_value,
        )
    )
    if delegator_is_substitute:
        raise WorkflowError("Re-delegation is not permitted")
    delegator = db.scalar(
        select(DocumentReviewer).where(
            DocumentReviewer.document_id == document.id,
            DocumentReviewer.reviewer_id == delegator_id,
        )
    )
    if not delegator:
        raise WorkflowError("Delegator is not a reviewer")
    if delegator.reviewer_id == substitute_id:
        raise WorkflowError("Delegator and substitute must differ")

    substitute_is_reviewer = db.scalar(
        select(DocumentReviewer).where(
            DocumentReviewer.document_id == document.id,
            DocumentReviewer.reviewer_id == substitute_id,
        )
    )
    if substitute_is_reviewer:
        raise WorkflowError("Re-delegation is not permitted")

    existing = db.scalar(
        select(Delegation).where(
            Delegation.document_id == document.id,
            Delegation.delegator_id == delegator_id,
            Delegation.active.is_(True),
        )
    )
    if existing:
        raise WorkflowError("Delegation already active")

    delegation = Delegation(
        document_id=document.id,
        delegator_id=delegator_id,
        substitute_id=substitute_id,
        expires_at=expires_at,
        active=True,
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


def revoke_delegation(db: Session, document_id: int, delegator_id: str) -> Delegation:
    document = _get_document(db, document_id)
    delegation = db.scalar(
        select(Delegation).where(
            Delegation.document_id == document.id,
            Delegation.delegator_id == delegator_id,
            Delegation.active.is_(True),
        )
    )
    if not delegation:
        raise WorkflowError("No active delegation found")
    delegation.active = False
    delegation.revoked_at = _now()
    db.commit()
    db.refresh(delegation)
    return delegation


def _record_decision(
    db: Session,
    document: Document,
    reviewer_id: str,
    decision: ReviewDecision,
    reason: str | None,
    acting_on_behalf_of: str | None,
    now: datetime,
) -> ReviewDecisionRecord:
    record = ReviewDecisionRecord(
        document=document,
        reviewer_id=reviewer_id,
        decision=decision,
        reason=reason,
        acting_on_behalf_of=acting_on_behalf_of,
        decided_at=now,
        review_cycle=document.review_cycle,
    )
    db.add(record)
    return record


def submit_decision(
    db: Session,
    document_id: int,
    reviewer_id: str,
    decision: ReviewDecision,
    reason: str | None,
    now: datetime | None = None,
) -> Document:
    document = _get_document(db, document_id)
    now_value = _now(now)

    _ensure_not_author(document, reviewer_id)

    decision_map = _get_decision_map(document)
    if reviewer_id in decision_map:
        raise WorkflowError("Reviewer already submitted a decision")

    _ensure_review_state(document)

    reviewer = db.scalar(
        select(DocumentReviewer).where(
            DocumentReviewer.document_id == document.id,
            DocumentReviewer.reviewer_id == reviewer_id,
            DocumentReviewer.active.is_(True),
        )
    )

    acting_on_behalf_of = None
    if not reviewer:
        delegation = _find_delegation(document, reviewer_id, now_value)
        if not delegation:
            expired = any(
                delegation.substitute_id == reviewer_id
                and delegation.active
                and delegation.expires_at <= now_value
                for delegation in document.delegations
            )
            if expired:
                raise WorkflowError("Delegation has expired")
            raise WorkflowError("Reviewer is not assigned")
        acting_on_behalf_of = delegation.delegator_id
        if acting_on_behalf_of in decision_map:
            raise WorkflowError("Reviewer already submitted a decision")

    _record_decision(
        db,
        document,
        reviewer_id=reviewer_id,
        decision=decision,
        reason=reason,
        acting_on_behalf_of=acting_on_behalf_of,
        now=now_value,
    )
    db.flush()

    if decision == ReviewDecision.REJECTED:
        document.status = DocumentStatus.REJECTED
        document.escalation_deadline = None
        db.commit()
        db.refresh(document)
        return document

    if not _pending_reviewers(document):
        document.status = DocumentStatus.APPROVED
        document.escalation_deadline = None
    db.commit()
    db.refresh(document)
    return document


def trigger_escalation(
    db: Session, document_id: int, now: datetime | None = None
) -> Document:
    document = _get_document(db, document_id)
    _ensure_review_state(document)

    now_value = _now(now)
    if document.escalation_deadline and now_value < document.escalation_deadline:
        return document

    if document.escalation_level >= document.escalation_max_level:
        raise WorkflowError("Maximum escalation level reached")

    if not _pending_reviewers(document):
        document.status = DocumentStatus.APPROVED
        document.escalation_deadline = None
        db.commit()
        db.refresh(document)
        return document

    document.escalation_level += 1
    new_level = document.escalation_level
    approver_id = f"escalated-{document.id}-{new_level}"
    db.add(
        DocumentReviewer(
            document_id=document.id,
            reviewer_id=approver_id,
            active=True,
            escalated=True,
        )
    )
    db.add(
        Escalation(
            document_id=document.id,
            from_level=new_level - 1,
            to_level=new_level,
            approver_id=approver_id,
        )
    )
    document.escalation_deadline = now_value + timedelta(
        seconds=document.escalation_timeout_seconds
    )
    db.add(
        Notification(
            document_id=document.id,
            recipient_id=approver_id,
            message=f"Document {document.id} escalated for review",
        )
    )
    db.commit()
    db.refresh(document)
    return document


def get_document_status(db: Session, document_id: int) -> dict[str, object]:
    document = _get_document(db, document_id)
    decision_map = _get_decision_map(document)
    pending = _pending_reviewers(document)
    return {
        "document": document,
        "decision_map": decision_map,
        "pending_reviewers": pending,
    }
