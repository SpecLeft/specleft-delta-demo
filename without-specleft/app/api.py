from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import ReviewDecision
from app.schemas import (
    DelegationRevokeRequest,
    DelegationRequest,
    DelegationResponse,
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    EscalationResponse,
    EscalationTriggerRequest,
    ReviewDecisionRequest,
    SubmitReviewRequest,
)
from app.services import (
    WorkflowError,
    create_document,
    delegate_reviewer,
    get_document_status,
    revoke_delegation,
    submit_decision,
    submit_for_review,
    trigger_escalation,
    update_document,
)

app = FastAPI(title="Document Approval API")

Base.metadata.create_all(bind=engine)


def _to_document_response(payload: dict[str, object]) -> DocumentResponse:
    document = payload["document"]
    decision_map = payload["decision_map"]
    pending = payload["pending_reviewers"]
    decisions = [
        {
            "reviewer_id": record.reviewer_id,
            "decision": record.decision,
            "decided_at": record.decided_at,
            "reason": record.reason,
            "acting_on_behalf_of": record.acting_on_behalf_of,
            "review_cycle": record.review_cycle,
        }
        for record in decision_map.values()
    ]
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        status=document.status,
        author_id=document.author_id,
        review_cycle=document.review_cycle,
        escalation_level=document.escalation_level,
        escalation_deadline=document.escalation_deadline,
        reviewers=[reviewer.reviewer_id for reviewer in document.reviewers],
        pending_reviewers=pending,
        decisions=decisions,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@app.post("/documents", response_model=DocumentResponse)
def create_document_endpoint(
    payload: DocumentCreate, db: Session = Depends(get_db)
) -> DocumentResponse:
    document = create_document(
        db,
        payload.title,
        payload.content,
        payload.author_id,
        payload.escalation_timeout_seconds,
        payload.escalation_max_level,
    )
    return _to_document_response(get_document_status(db, document.id))


@app.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document_endpoint(
    document_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)
) -> DocumentResponse:
    try:
        document = update_document(db, document_id, payload.title, payload.content)
        return _to_document_response(get_document_status(db, document.id))
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/documents/{document_id}/submit", response_model=DocumentResponse)
def submit_document_endpoint(
    document_id: int, payload: SubmitReviewRequest, db: Session = Depends(get_db)
) -> DocumentResponse:
    try:
        document = submit_for_review(db, document_id, payload.reviewer_ids)
        return _to_document_response(get_document_status(db, document.id))
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/documents/{document_id}/decisions", response_model=DocumentResponse)
def submit_decision_endpoint(
    document_id: int, payload: ReviewDecisionRequest, db: Session = Depends(get_db)
) -> DocumentResponse:
    try:
        document = submit_decision(
            db,
            document_id,
            payload.reviewer_id,
            ReviewDecision(payload.decision),
            payload.reason,
        )
        return _to_document_response(get_document_status(db, document.id))
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document_endpoint(
    document_id: int, db: Session = Depends(get_db)
) -> DocumentResponse:
    try:
        return _to_document_response(get_document_status(db, document_id))
    except WorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/documents/{document_id}/delegations", response_model=DelegationResponse)
def delegate_endpoint(
    document_id: int, payload: DelegationRequest, db: Session = Depends(get_db)
) -> DelegationResponse:
    try:
        delegation = delegate_reviewer(
            db,
            document_id,
            payload.delegator_id,
            payload.substitute_id,
            payload.expires_at,
        )
        return DelegationResponse(
            id=delegation.id,
            document_id=delegation.document_id,
            delegator_id=delegation.delegator_id,
            substitute_id=delegation.substitute_id,
            expires_at=delegation.expires_at,
            active=delegation.active,
            revoked_at=delegation.revoked_at,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/documents/{document_id}/delegations/revoke",
    response_model=DelegationResponse,
)
def revoke_delegation_endpoint(
    document_id: int, payload: DelegationRevokeRequest, db: Session = Depends(get_db)
) -> DelegationResponse:
    try:
        delegation = revoke_delegation(db, document_id, payload.delegator_id)
        return DelegationResponse(
            id=delegation.id,
            document_id=delegation.document_id,
            delegator_id=delegation.delegator_id,
            substitute_id=delegation.substitute_id,
            expires_at=delegation.expires_at,
            active=delegation.active,
            revoked_at=delegation.revoked_at,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/documents/{document_id}/escalate", response_model=DocumentResponse)
def escalate_document_endpoint(
    document_id: int, payload: EscalationTriggerRequest, db: Session = Depends(get_db)
) -> DocumentResponse:
    try:
        document = trigger_escalation(db, document_id, payload.now)
        return _to_document_response(get_document_status(db, document.id))
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/documents/{document_id}/escalations", response_model=list[EscalationResponse]
)
def list_escalations_endpoint(
    document_id: int, db: Session = Depends(get_db)
) -> list[EscalationResponse]:
    document = get_document_status(db, document_id)["document"]
    return [
        EscalationResponse(
            id=escalation.id,
            document_id=escalation.document_id,
            escalated_at=escalation.escalated_at,
            from_level=escalation.from_level,
            to_level=escalation.to_level,
            approver_id=escalation.approver_id,
        )
        for escalation in document.escalations
    ]
