"""Business logic for the document approval workflow."""

from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentStatus,
    ReviewCycle,
    ReviewerAssignment,
    ReviewDecision,
    Delegation,
    Escalation,
    Notification,
)
from app.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentSubmit,
    ReviewSubmit,
    DelegationCreate,
    DocumentResponse,
)


# --- Document Operations ---


def create_document(db: Session, data: DocumentCreate) -> Document:
    """Create a new document in draft status."""
    doc = Document(
        title=data.title,
        content=data.content,
        author_id=data.author_id,
        status=DocumentStatus.DRAFT,
        escalation_timeout_hours=data.escalation_timeout_hours,
        max_escalation_depth=data.max_escalation_depth,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, document_id: int) -> Document:
    """Retrieve a document by ID or raise 404."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return doc


def update_document(
    db: Session, document_id: int, data: DocumentUpdate, user_id: str
) -> Document:
    """Update a document. Only allowed when in draft status by the author."""
    doc = get_document(db, document_id)

    if doc.status == DocumentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit document: document is locked (approved)",
        )
    if doc.status == DocumentStatus.REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit document: document is under review",
        )
    if doc.status == DocumentStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit document: document is rejected. Resubmit first.",
        )
    if doc.author_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author can edit this document",
        )

    if data.title is not None:
        doc.title = data.title
    if data.content is not None:
        doc.content = data.content

    db.commit()
    db.refresh(doc)
    return doc


def submit_for_review(
    db: Session, document_id: int, data: DocumentSubmit, user_id: str
) -> Document:
    """Submit a document for review, creating a new review cycle."""
    doc = get_document(db, document_id)

    if doc.status not in (DocumentStatus.DRAFT, DocumentStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot submit document for review: current status is '{doc.status.value}'",
        )
    if doc.author_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author can submit the document for review",
        )
    if not data.reviewer_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one reviewer is required",
        )

    # Check that author is not in the reviewer list
    if user_id in data.reviewer_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Author cannot be assigned as a reviewer of their own document",
        )

    # Determine cycle number
    cycle_number = 1
    if doc.review_cycles:
        cycle_number = doc.review_cycles[-1].cycle_number + 1

    cycle = ReviewCycle(
        document_id=doc.id,
        cycle_number=cycle_number,
    )
    db.add(cycle)
    db.flush()

    for reviewer_id in data.reviewer_ids:
        assignment = ReviewerAssignment(
            review_cycle_id=cycle.id,
            reviewer_id=reviewer_id,
        )
        db.add(assignment)

    doc.status = DocumentStatus.REVIEW
    db.commit()
    db.refresh(doc)

    # Create notifications for reviewers
    for reviewer_id in data.reviewer_ids:
        notification = Notification(
            recipient_id=reviewer_id,
            document_id=doc.id,
            message=f"You have been assigned to review document '{doc.title}'",
        )
        db.add(notification)
    db.commit()

    return doc


# --- Review Operations ---


def _find_assignment_for_reviewer(
    db: Session, cycle: ReviewCycle, reviewer_id: str
) -> Optional[ReviewerAssignment]:
    """Find a reviewer's assignment, either directly or via delegation."""
    # Direct assignment
    direct = (
        db.query(ReviewerAssignment)
        .filter(
            ReviewerAssignment.review_cycle_id == cycle.id,
            ReviewerAssignment.reviewer_id == reviewer_id,
        )
        .first()
    )
    if direct:
        return direct

    return None


def _find_delegation_for_delegate(
    db: Session, cycle: ReviewCycle, delegate_id: str
) -> Optional[tuple[ReviewerAssignment, Delegation]]:
    """Find an active delegation where delegate_id is the substitute."""
    assignments = (
        db.query(ReviewerAssignment)
        .filter(ReviewerAssignment.review_cycle_id == cycle.id)
        .all()
    )
    for assignment in assignments:
        for delegation in assignment.delegations:
            if delegation.delegate_id == delegate_id and delegation.is_active:
                return assignment, delegation
    return None


def submit_review(db: Session, document_id: int, data: ReviewSubmit) -> Document:
    """Submit a review decision for a document."""
    doc = get_document(db, document_id)

    if doc.status != DocumentStatus.REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot review document: current status is '{doc.status.value}'",
        )

    if data.decision == ReviewDecision.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be 'approved' or 'rejected'",
        )

    cycle = doc.current_cycle
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active review cycle found",
        )

    # Self-approval guard: author cannot approve their own document
    if data.reviewer_id == doc.author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval is not permitted: reviewer is the document author",
        )

    # Check direct assignment first
    assignment = _find_assignment_for_reviewer(db, cycle, data.reviewer_id)
    delegate_id = None

    if not assignment:
        # Check if this reviewer is a delegate for someone
        result = _find_delegation_for_delegate(db, cycle, data.reviewer_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{data.reviewer_id}' is not an assigned reviewer or active delegate for this document",
            )
        assignment, delegation = result
        delegate_id = data.reviewer_id

    # Check if already decided
    if assignment.decision != ReviewDecision.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Reviewer '{assignment.reviewer_id}' has already submitted a decision",
        )

    # Record the decision
    now = datetime.now(timezone.utc)
    assignment.decision = data.decision
    assignment.decided_at = now
    assignment.reason = data.reason
    if delegate_id:
        assignment.decided_by_delegate_id = delegate_id

    # Determine document status change
    if data.decision == ReviewDecision.REJECTED:
        # Any rejection immediately rejects the document
        doc.status = DocumentStatus.REJECTED
        # Notify author
        notification = Notification(
            recipient_id=doc.author_id,
            document_id=doc.id,
            message=f"Document '{doc.title}' has been rejected by reviewer '{data.reviewer_id}'",
        )
        db.add(notification)
    else:
        # Check if all reviewers have approved
        all_decided = all(
            a.decision != ReviewDecision.PENDING for a in cycle.assignments
        )
        all_approved = all(
            a.decision == ReviewDecision.APPROVED for a in cycle.assignments
        )
        if all_decided and all_approved:
            doc.status = DocumentStatus.APPROVED
            notification = Notification(
                recipient_id=doc.author_id,
                document_id=doc.id,
                message=f"Document '{doc.title}' has been approved by all reviewers",
            )
            db.add(notification)

    db.commit()
    db.refresh(doc)
    return doc


# --- Delegation Operations ---


def create_delegation(
    db: Session, document_id: int, assignment_id: int, data: DelegationCreate
) -> Delegation:
    """Create a delegation for a reviewer assignment."""
    doc = get_document(db, document_id)

    if doc.status != DocumentStatus.REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delegation is only allowed for documents under review",
        )

    assignment = (
        db.query(ReviewerAssignment)
        .filter(ReviewerAssignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reviewer assignment {assignment_id} not found",
        )

    # Verify the delegator is the assigned reviewer
    if assignment.reviewer_id != data.delegator_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned reviewer can delegate their review",
        )

    # Prevent delegation chains: check if the delegator is themselves a delegate
    cycle = assignment.review_cycle
    for a in cycle.assignments:
        for d in a.delegations:
            if d.delegate_id == data.delegator_id and d.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Re-delegation is not permitted: you are acting as a delegate",
                )

    # Check if there's already an active delegation for this assignment
    for existing in assignment.delegations:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active delegation already exists for this assignment. Revoke it first.",
            )

    # Already decided
    if assignment.decision != ReviewDecision.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delegate: review decision has already been submitted",
        )

    # Validate expiry is in the future
    if data.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delegation expiry date must be in the future",
        )

    delegation = Delegation(
        assignment_id=assignment.id,
        delegator_id=data.delegator_id,
        delegate_id=data.delegate_id,
        expires_at=data.expires_at,
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)

    # Notify delegate
    notification = Notification(
        recipient_id=data.delegate_id,
        document_id=doc.id,
        message=f"You have been delegated review authority for document '{doc.title}' by '{data.delegator_id}'",
    )
    db.add(notification)
    db.commit()

    return delegation


def revoke_delegation(
    db: Session, document_id: int, delegation_id: int, user_id: str
) -> Delegation:
    """Revoke an active delegation."""
    doc = get_document(db, document_id)

    delegation = db.query(Delegation).filter(Delegation.id == delegation_id).first()
    if not delegation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delegation {delegation_id} not found",
        )

    if delegation.delegator_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the delegator can revoke the delegation",
        )

    if delegation.revoked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delegation is already revoked",
        )

    delegation.revoked = True
    delegation.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(delegation)

    return delegation


# --- Escalation Operations ---


def check_and_escalate(db: Session, document_id: int) -> Optional[Escalation]:
    """Check if a document needs escalation and process it.

    This would typically be called by a background job/scheduler.
    For the API, we also expose a manual trigger endpoint.
    """
    doc = get_document(db, document_id)

    if doc.status != DocumentStatus.REVIEW:
        return None

    cycle = doc.current_cycle
    if not cycle:
        return None

    now = datetime.now(timezone.utc)

    # Find pending reviewers who have exceeded the timeout
    pending_assignments = [
        a for a in cycle.assignments if a.decision == ReviewDecision.PENDING
    ]

    if not pending_assignments:
        return None

    # Determine the most recent escalation depth
    current_depth = 0
    if cycle.escalations:
        current_depth = max(e.escalation_depth for e in cycle.escalations)

    if current_depth >= doc.max_escalation_depth:
        # Maximum escalation depth reached
        return None

    # Check if timeout has elapsed since the last relevant timestamp
    # Use the latest of: cycle creation, or the most recent escalation timeout
    reference_time = cycle.created_at
    if cycle.escalations:
        latest_escalation = max(cycle.escalations, key=lambda e: e.escalated_at)
        reference_time = latest_escalation.escalated_at

    timeout_delta = timedelta(hours=doc.escalation_timeout_hours)
    if now < reference_time + timeout_delta:
        # Timeout hasn't elapsed yet
        return None

    return None  # Auto-escalation returns None; manual escalation is via trigger_escalation


def trigger_escalation(
    db: Session, document_id: int, escalated_to_reviewer_id: str
) -> Escalation:
    """Manually trigger escalation to a specific reviewer."""
    doc = get_document(db, document_id)

    if doc.status != DocumentStatus.REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Escalation is only allowed for documents under review",
        )

    # Self-escalation guard
    if escalated_to_reviewer_id == doc.author_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot escalate to the document author",
        )

    cycle = doc.current_cycle
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active review cycle found",
        )

    # Determine current escalation depth
    current_depth = 0
    if cycle.escalations:
        current_depth = max(e.escalation_depth for e in cycle.escalations)

    if current_depth >= doc.max_escalation_depth:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum escalation depth ({doc.max_escalation_depth}) reached",
        )

    # Check that the escalated_to reviewer isn't already assigned
    existing = (
        db.query(ReviewerAssignment)
        .filter(
            ReviewerAssignment.review_cycle_id == cycle.id,
            ReviewerAssignment.reviewer_id == escalated_to_reviewer_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Reviewer '{escalated_to_reviewer_id}' is already assigned to this review cycle",
        )

    now = datetime.now(timezone.utc)
    new_depth = current_depth + 1
    timeout_at = now + timedelta(hours=doc.escalation_timeout_hours)

    # Find pending reviewers to reference as "escalated from"
    pending = [
        a
        for a in cycle.assignments
        if a.decision == ReviewDecision.PENDING and not a.is_escalated
    ]
    escalated_from = pending[0].reviewer_id if pending else None

    # Create escalation record
    escalation = Escalation(
        review_cycle_id=cycle.id,
        escalated_from_reviewer_id=escalated_from,
        escalated_to_reviewer_id=escalated_to_reviewer_id,
        escalation_depth=new_depth,
        escalated_at=now,
        timeout_at=timeout_at,
    )
    db.add(escalation)

    # Add the new reviewer as an assignment
    new_assignment = ReviewerAssignment(
        review_cycle_id=cycle.id,
        reviewer_id=escalated_to_reviewer_id,
        is_escalated=True,
    )
    db.add(new_assignment)

    # Notify the new reviewer
    notification = Notification(
        recipient_id=escalated_to_reviewer_id,
        document_id=doc.id,
        message=f"Document '{doc.title}' has been escalated to you for review (depth: {new_depth})",
    )
    db.add(notification)

    db.commit()
    db.refresh(escalation)
    return escalation


# --- Notification Operations ---


def get_notifications(
    db: Session, user_id: str, document_id: Optional[int] = None
) -> List[Notification]:
    """Get notifications for a user, optionally filtered by document."""
    query = db.query(Notification).filter(Notification.recipient_id == user_id)
    if document_id:
        query = query.filter(Notification.document_id == document_id)
    return query.order_by(Notification.created_at.desc()).all()


# --- Helper for Response Building ---


def build_document_response(doc: Document) -> dict:
    """Build a DocumentResponse dict with computed fields."""
    pending_reviewers: List[str] = []
    if doc.status == DocumentStatus.REVIEW and doc.current_cycle:
        pending_reviewers = [
            a.reviewer_id
            for a in doc.current_cycle.assignments
            if a.decision == ReviewDecision.PENDING
        ]

    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "status": doc.status,
        "author_id": doc.author_id,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "escalation_timeout_hours": doc.escalation_timeout_hours,
        "max_escalation_depth": doc.max_escalation_depth,
        "review_cycles": doc.review_cycles,
        "pending_reviewers": pending_reviewers,
    }
