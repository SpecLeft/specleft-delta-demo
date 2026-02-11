from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentSubmit,
    DocumentResponse,
    DocumentStatusResponse,
    ReviewSubmit,
    DelegationCreate,
    DelegationResponse,
    DelegationRevoke,
    EscalationConfig,
)
from app import services

router = APIRouter()


# --- Documents ---


@router.post("/documents", response_model=DocumentResponse, status_code=201)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    doc = services.create_document(
        db, title=payload.title, body=payload.body, author_id=payload.author_id
    )
    return doc


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    return services.get_document(db, document_id)


@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)
):
    return services.update_document(
        db, document_id, title=payload.title, body=payload.body
    )


@router.post("/documents/{document_id}/submit", response_model=DocumentResponse)
def submit_for_review(
    document_id: int, payload: DocumentSubmit, db: Session = Depends(get_db)
):
    return services.submit_for_review(
        db, document_id, reviewer_ids=payload.reviewer_ids
    )


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(document_id: int, db: Session = Depends(get_db)):
    return services.get_document_status(db, document_id)


@router.get("/documents/{document_id}/history")
def get_review_history(document_id: int, db: Session = Depends(get_db)):
    return services.get_review_history(db, document_id)


# --- Reviews ---


@router.post("/documents/{document_id}/review", response_model=DocumentResponse)
def submit_review(
    document_id: int, payload: ReviewSubmit, db: Session = Depends(get_db)
):
    return services.submit_review(
        db,
        document_id,
        reviewer_id=payload.reviewer_id,
        decision=payload.decision,
        reason=payload.reason,
    )


# --- Delegation ---


@router.post(
    "/documents/{document_id}/delegate",
    response_model=DelegationResponse,
    status_code=201,
)
def create_delegation(
    document_id: int, payload: DelegationCreate, db: Session = Depends(get_db)
):
    return services.create_delegation(
        db,
        document_id,
        delegator_id=payload.delegator_id,
        substitute_id=payload.substitute_id,
        expires_at=payload.expires_at,
    )


@router.post(
    "/documents/{document_id}/delegate/revoke", response_model=DelegationResponse
)
def revoke_delegation(
    document_id: int, payload: DelegationRevoke, db: Session = Depends(get_db)
):
    return services.revoke_delegation(
        db, document_id, delegator_id=payload.delegator_id
    )


# --- Escalation ---


@router.post("/documents/{document_id}/escalate")
def check_escalation(
    document_id: int, payload: EscalationConfig, db: Session = Depends(get_db)
):
    return services.check_and_escalate(
        db,
        document_id,
        next_approver_id=payload.next_approver_id,
        timeout_hours=payload.timeout_hours,
    )
