from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentStatus,
    Reviewer,
    ReviewDecisionRecord,
    ReviewDecision,
    Notification,
    Delegation,
    Escalation,
)


class ServiceError(Exception):
    """Base service error with an HTTP status code."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Document lifecycle
# ---------------------------------------------------------------------------


def create_document(db: Session, title: str, body: str, author_id: str) -> Document:
    doc = Document(
        title=title, body=body, author_id=author_id, status=DocumentStatus.DRAFT
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, document_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ServiceError("Document not found", status_code=404)
    return doc


def update_document(
    db: Session, document_id: int, title: str | None = None, body: str | None = None
) -> Document:
    doc = get_document(db, document_id)

    if doc.status == DocumentStatus.APPROVED:
        raise ServiceError(
            "Document is locked — approved documents cannot be edited", status_code=409
        )
    if doc.status == DocumentStatus.REVIEW:
        raise ServiceError(
            "Document is under review and cannot be edited", status_code=409
        )
    if doc.status == DocumentStatus.REJECTED:
        pass  # Rejected drafts can be edited before resubmission

    if doc.status != DocumentStatus.DRAFT and doc.status != DocumentStatus.REJECTED:
        raise ServiceError(
            f"Document cannot be edited in '{doc.status.value}' status", status_code=409
        )

    if title is not None:
        doc.title = title
    if body is not None:
        doc.body = body
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    return doc


def submit_for_review(
    db: Session, document_id: int, reviewer_ids: list[str]
) -> Document:
    doc = get_document(db, document_id)

    if doc.status not in (DocumentStatus.DRAFT, DocumentStatus.REJECTED):
        raise ServiceError(
            f"Cannot submit for review: transition from '{doc.status.value}' to 'review' is not allowed",
            status_code=409,
        )

    if not reviewer_ids:
        raise ServiceError("At least one reviewer is required", status_code=400)

    # Determine review cycle
    current_cycle = _current_review_cycle(db, document_id) + 1

    doc.status = DocumentStatus.REVIEW
    doc.review_started_at = datetime.now(timezone.utc)
    doc.escalation_depth = 0
    doc.updated_at = datetime.now(timezone.utc)

    for uid in reviewer_ids:
        db.add(
            Reviewer(document_id=document_id, user_id=uid, review_cycle=current_cycle)
        )

    for uid in reviewer_ids:
        db.add(
            Notification(
                document_id=document_id,
                user_id=uid,
                message=f"You have been assigned as a reviewer for document '{doc.title}'",
            )
        )

    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# Review decisions
# ---------------------------------------------------------------------------


def submit_review(
    db: Session,
    document_id: int,
    reviewer_id: str,
    decision: str,
    reason: str | None = None,
) -> Document:
    doc = get_document(db, document_id)

    if doc.status != DocumentStatus.REVIEW:
        raise ServiceError(
            f"Cannot review: document is in '{doc.status.value}' status, not 'review'",
            status_code=409,
        )

    cycle = _current_review_cycle(db, document_id)
    reviewer_ids = _reviewer_ids_for_cycle(db, document_id, cycle)

    # Check self-approval
    if reviewer_id == doc.author_id and reviewer_id in reviewer_ids:
        raise ServiceError("Self-approval is not permitted", status_code=403)

    # Resolve delegation: is this person acting as a substitute?
    on_behalf_of = None
    acting_reviewer_id = reviewer_id

    if reviewer_id not in reviewer_ids:
        delegation = _find_active_delegation(db, document_id, reviewer_id)
        if delegation is None:
            raise ServiceError(
                f"User '{reviewer_id}' is not an assigned reviewer for this document",
                status_code=403,
            )
        on_behalf_of = delegation.delegator_id
        acting_reviewer_id = delegation.delegator_id

    # Check duplicate / immutability
    existing = (
        db.query(ReviewDecisionRecord)
        .filter(
            ReviewDecisionRecord.document_id == document_id,
            ReviewDecisionRecord.review_cycle == cycle,
        )
        .all()
    )

    for d in existing:
        effective_reviewer = d.on_behalf_of if d.on_behalf_of else d.reviewer_id
        if effective_reviewer == acting_reviewer_id:
            raise ServiceError(
                "Reviewer has already submitted a decision", status_code=409
            )

    if decision not in ("approved", "rejected"):
        raise ServiceError("Decision must be 'approved' or 'rejected'", status_code=400)

    record = ReviewDecisionRecord(
        document_id=document_id,
        reviewer_id=reviewer_id,
        decision=ReviewDecision(decision),
        reason=reason,
        review_cycle=cycle,
        on_behalf_of=on_behalf_of,
    )
    db.add(record)

    # Check if rejection — immediate rejection
    if decision == "rejected":
        doc.status = DocumentStatus.REJECTED
        doc.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(doc)
        return doc

    # Check if all reviewers have approved
    all_decisions = (
        db.query(ReviewDecisionRecord)
        .filter(
            ReviewDecisionRecord.document_id == document_id,
            ReviewDecisionRecord.review_cycle == cycle,
        )
        .all()
    )
    # Include the one we just added
    decided_reviewer_ids = set()
    for d in all_decisions:
        effective = d.on_behalf_of if d.on_behalf_of else d.reviewer_id
        decided_reviewer_ids.add(effective)
    decided_reviewer_ids.add(acting_reviewer_id)

    if decided_reviewer_ids >= set(reviewer_ids):
        doc.status = DocumentStatus.APPROVED
        doc.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(doc)
    return doc


def get_document_status(db: Session, document_id: int) -> dict:
    doc = get_document(db, document_id)
    cycle = _current_review_cycle(db, document_id)
    reviewer_ids = _reviewer_ids_for_cycle(db, document_id, cycle)

    decisions_q = (
        db.query(ReviewDecisionRecord)
        .filter(
            ReviewDecisionRecord.document_id == document_id,
            ReviewDecisionRecord.review_cycle == cycle,
        )
        .all()
    )

    decided_ids = set()
    for d in decisions_q:
        effective = d.on_behalf_of if d.on_behalf_of else d.reviewer_id
        decided_ids.add(effective)

    pending = [rid for rid in reviewer_ids if rid not in decided_ids]

    decisions = [
        {
            "reviewer_id": d.reviewer_id,
            "decision": d.decision.value,
            "reason": d.reason,
            "decided_at": d.decided_at,
            "on_behalf_of": d.on_behalf_of,
        }
        for d in decisions_q
    ]

    return {
        "id": doc.id,
        "status": doc.status.value,
        "reviewers": reviewer_ids,
        "pending_reviewers": pending,
        "decisions": decisions,
    }


def get_review_history(db: Session, document_id: int) -> list[dict]:
    """Return all review decisions across all cycles."""
    get_document(db, document_id)  # Ensure exists
    decisions = (
        db.query(ReviewDecisionRecord)
        .filter(ReviewDecisionRecord.document_id == document_id)
        .order_by(ReviewDecisionRecord.review_cycle, ReviewDecisionRecord.decided_at)
        .all()
    )
    return [
        {
            "reviewer_id": d.reviewer_id,
            "decision": d.decision.value,
            "reason": d.reason,
            "decided_at": d.decided_at,
            "review_cycle": d.review_cycle,
            "on_behalf_of": d.on_behalf_of,
        }
        for d in decisions
    ]


# ---------------------------------------------------------------------------
# Delegation
# ---------------------------------------------------------------------------


def create_delegation(
    db: Session,
    document_id: int,
    delegator_id: str,
    substitute_id: str,
    expires_at: datetime,
) -> Delegation:
    doc = get_document(db, document_id)
    cycle = _current_review_cycle(db, document_id)
    reviewer_ids = _reviewer_ids_for_cycle(db, document_id, cycle)

    # Must be an assigned reviewer
    if delegator_id not in reviewer_ids:
        # Check if they are a substitute themselves (prevent chain)
        existing_as_sub = (
            db.query(Delegation)
            .filter(
                Delegation.document_id == document_id,
                Delegation.substitute_id == delegator_id,
                Delegation.revoked == False,
            )
            .first()
        )
        if existing_as_sub:
            raise ServiceError("Re-delegation is not permitted", status_code=403)
        raise ServiceError(
            f"User '{delegator_id}' is not an assigned reviewer", status_code=403
        )

    # Check for re-delegation attempt: is the delegator actually a substitute?
    is_substitute = (
        db.query(Delegation)
        .filter(
            Delegation.document_id == document_id,
            Delegation.substitute_id == delegator_id,
            Delegation.revoked == False,
        )
        .first()
    )
    if is_substitute:
        raise ServiceError("Re-delegation is not permitted", status_code=403)

    # One active delegation per reviewer per document
    active = (
        db.query(Delegation)
        .filter(
            Delegation.document_id == document_id,
            Delegation.delegator_id == delegator_id,
            Delegation.revoked == False,
        )
        .first()
    )
    if active:
        raise ServiceError(
            "An active delegation already exists for this reviewer on this document",
            status_code=409,
        )

    delegation = Delegation(
        document_id=document_id,
        delegator_id=delegator_id,
        substitute_id=substitute_id,
        expires_at=expires_at,
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


def revoke_delegation(db: Session, document_id: int, delegator_id: str) -> Delegation:
    delegation = (
        db.query(Delegation)
        .filter(
            Delegation.document_id == document_id,
            Delegation.delegator_id == delegator_id,
            Delegation.revoked == False,
        )
        .first()
    )
    if not delegation:
        raise ServiceError("No active delegation found to revoke", status_code=404)

    delegation.revoked = True
    db.commit()
    db.refresh(delegation)
    return delegation


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


def check_and_escalate(
    db: Session,
    document_id: int,
    next_approver_id: str,
    timeout_hours: int | None = None,
) -> dict:
    doc = get_document(db, document_id)

    if doc.status != DocumentStatus.REVIEW:
        raise ServiceError("Document is not in review status", status_code=409)

    # Check max depth
    if doc.escalation_depth >= doc.max_escalation_depth:
        return {"escalated": False, "reason": "Maximum escalation depth reached"}

    effective_timeout = (
        timeout_hours
        if timeout_hours is not None
        else (
            doc.escalation_timeout_hours
            if doc.escalation_timeout_hours is not None
            else 24
        )
    )
    now = datetime.now(timezone.utc)

    # Determine the reference time: last escalation or review start
    last_escalation = (
        db.query(Escalation)
        .filter(Escalation.document_id == document_id)
        .order_by(Escalation.escalated_at.desc())
        .first()
    )

    reference_time = (
        last_escalation.escalated_at if last_escalation else doc.review_started_at
    )
    if reference_time is None:
        raise ServiceError("Review start time not set", status_code=500)

    # Make sure reference_time is timezone-aware
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    elapsed_hours = (now - reference_time).total_seconds() / 3600

    # Check if all reviewers have already decided
    cycle = _current_review_cycle(db, document_id)
    reviewer_ids = _reviewer_ids_for_cycle(db, document_id, cycle)
    decided_ids = _decided_reviewer_ids(db, document_id, cycle)

    if decided_ids >= set(reviewer_ids):
        return {"escalated": False, "reason": "All reviewers have already decided"}

    if elapsed_hours < effective_timeout:
        return {"escalated": False, "reason": "Timeout has not elapsed"}

    # Escalate
    new_level = doc.escalation_depth + 1
    doc.escalation_depth = new_level
    doc.updated_at = now

    escalation = Escalation(
        document_id=document_id,
        escalated_to=next_approver_id,
        escalation_level=new_level,
        timeout_hours=effective_timeout,
    )
    db.add(escalation)

    # Add escalated reviewer
    db.add(
        Reviewer(document_id=document_id, user_id=next_approver_id, review_cycle=cycle)
    )

    # Notify
    db.add(
        Notification(
            document_id=document_id,
            user_id=next_approver_id,
            message=f"Document '{doc.title}' has been escalated to you (level {new_level})",
        )
    )

    db.commit()
    db.refresh(doc)

    return {
        "escalated": True,
        "escalation_level": new_level,
        "escalated_to": next_approver_id,
        "new_timeout_hours": effective_timeout,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_review_cycle(db: Session, document_id: int) -> int:
    max_cycle = (
        db.query(Reviewer.review_cycle)
        .filter(Reviewer.document_id == document_id)
        .order_by(Reviewer.review_cycle.desc())
        .first()
    )
    return max_cycle[0] if max_cycle else 0


def _reviewer_ids_for_cycle(db: Session, document_id: int, cycle: int) -> list[str]:
    reviewers = (
        db.query(Reviewer.user_id)
        .filter(Reviewer.document_id == document_id, Reviewer.review_cycle == cycle)
        .all()
    )
    return [r[0] for r in reviewers]


def _decided_reviewer_ids(db: Session, document_id: int, cycle: int) -> set[str]:
    decisions = (
        db.query(ReviewDecisionRecord)
        .filter(
            ReviewDecisionRecord.document_id == document_id,
            ReviewDecisionRecord.review_cycle == cycle,
        )
        .all()
    )
    result = set()
    for d in decisions:
        effective = d.on_behalf_of if d.on_behalf_of else d.reviewer_id
        result.add(effective)
    return result


def _find_active_delegation(
    db: Session, document_id: int, substitute_id: str
) -> Delegation | None:
    now = datetime.now(timezone.utc)
    delegation = (
        db.query(Delegation)
        .filter(
            Delegation.document_id == document_id,
            Delegation.substitute_id == substitute_id,
            Delegation.revoked == False,
            Delegation.expires_at > now,
        )
        .first()
    )
    return delegation
