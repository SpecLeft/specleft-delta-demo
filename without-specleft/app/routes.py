"""API routes for the document approval workflow."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentSubmit,
    DocumentResponse,
    ReviewSubmit,
    DelegationCreate,
    DelegationResponse,
    EscalationTrigger,
    EscalationResponse,
    NotificationResponse,
)
from app.services import (
    create_document,
    get_document,
    update_document,
    submit_for_review,
    submit_review,
    create_delegation,
    revoke_delegation,
    trigger_escalation,
    check_and_escalate,
    get_notifications,
    build_document_response,
)

router = APIRouter()


# --- Document Endpoints ---


@router.post("/documents", response_model=DocumentResponse, status_code=201)
def create_doc(data: DocumentCreate, db: Session = Depends(get_db)):
    """Create a new document in draft status."""
    doc = create_document(db, data)
    return build_document_response(doc)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_doc(document_id: int, db: Session = Depends(get_db)):
    """Retrieve a document by ID."""
    doc = get_document(db, document_id)
    return build_document_response(doc)


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
def update_doc(
    document_id: int,
    data: DocumentUpdate,
    user_id: str = Query(..., description="The ID of the user making the edit"),
    db: Session = Depends(get_db),
):
    """Update a document (only allowed in draft status by the author)."""
    doc = update_document(db, document_id, data, user_id)
    return build_document_response(doc)


@router.post("/documents/{document_id}/submit", response_model=DocumentResponse)
def submit_doc(
    document_id: int,
    data: DocumentSubmit,
    user_id: str = Query(..., description="The ID of the user submitting the document"),
    db: Session = Depends(get_db),
):
    """Submit a document for review."""
    doc = submit_for_review(db, document_id, data, user_id)
    return build_document_response(doc)


# --- Review Endpoints ---


@router.post("/documents/{document_id}/review", response_model=DocumentResponse)
def review_doc(document_id: int, data: ReviewSubmit, db: Session = Depends(get_db)):
    """Submit a review decision for a document."""
    doc = submit_review(db, document_id, data)
    return build_document_response(doc)


# --- Delegation Endpoints ---


@router.post(
    "/documents/{document_id}/assignments/{assignment_id}/delegate",
    response_model=DelegationResponse,
    status_code=201,
)
def delegate_review(
    document_id: int,
    assignment_id: int,
    data: DelegationCreate,
    db: Session = Depends(get_db),
):
    """Delegate review authority to a substitute."""
    delegation = create_delegation(db, document_id, assignment_id, data)
    return delegation


@router.post(
    "/documents/{document_id}/delegations/{delegation_id}/revoke",
    response_model=DelegationResponse,
)
def revoke_delegation_endpoint(
    document_id: int,
    delegation_id: int,
    user_id: str = Query(..., description="The ID of the delegator revoking"),
    db: Session = Depends(get_db),
):
    """Revoke an active delegation."""
    delegation = revoke_delegation(db, document_id, delegation_id, user_id)
    return delegation


# --- Escalation Endpoints ---


@router.post(
    "/documents/{document_id}/escalate",
    response_model=EscalationResponse,
    status_code=201,
)
def escalate_doc(
    document_id: int,
    data: EscalationTrigger,
    db: Session = Depends(get_db),
):
    """Trigger escalation for a document to a higher-level approver."""
    escalation = trigger_escalation(db, document_id, data.escalated_to_reviewer_id)
    return escalation


@router.post("/documents/{document_id}/check-escalation")
def check_escalation(document_id: int, db: Session = Depends(get_db)):
    """Check if a document needs auto-escalation (called by scheduler)."""
    result = check_and_escalate(db, document_id)
    if result:
        return {"escalated": True, "escalation_id": result.id}
    return {"escalated": False}


# --- Notification Endpoints ---


@router.get("/notifications", response_model=List[NotificationResponse])
def list_notifications(
    user_id: str = Query(...),
    document_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get notifications for a user."""
    return get_notifications(db, user_id, document_id)
