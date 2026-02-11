"""FastAPI application entrypoint for tests."""

import json

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import services
from app.database import Base, engine, get_session
from app.schemas import (
    ApproveRequest,
    DecisionResponse,
    DelegationCreate,
    DelegationResponse,
    DelegationRevoke,
    DocumentCreate,
    DocumentResponse,
    DocumentSubmit,
    DocumentUpdate,
    EscalationResponse,
    EscalationTriggerRequest,
    NotificationListResponse,
    RejectRequest,
    ReviewHistoryResponse,
)


app = FastAPI(title="Document Approval API")

Base.metadata.create_all(bind=engine)


def _error_response(error: services.ApiError) -> JSONResponse:
    payload = {
        "error": {
            "code": error.code,
            "message": error.message,
            "meta": error.meta or None,
        }
    }
    return JSONResponse(status_code=error.status_code, content=payload)


@app.exception_handler(services.ApiError)
def api_error_handler(_, exc: services.ApiError):
    return _error_response(exc)


@app.post("/documents", response_model=DocumentResponse, status_code=201)
def create_document_endpoint(
    payload: DocumentCreate, session: Session = Depends(get_session)
):
    document = services.create_document(
        session, payload.title, payload.content, payload.author_id
    )
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        author_id=document.author_id,
        status=document.status,
        reviewer_ids=[],
        pending_reviewers=[],
    )


@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document_endpoint(document_id: str, session: Session = Depends(get_session)):
    document = services._get_document(session, document_id)
    cycle = services._get_active_cycle(session, document_id)
    reviewer_ids = services.list_reviewer_ids(session, cycle.id) if cycle else []
    pending_reviewers = (
        services.list_pending_reviewers(session, cycle.id) if cycle else []
    )
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        author_id=document.author_id,
        status=document.status,
        reviewer_ids=reviewer_ids,
        pending_reviewers=pending_reviewers,
    )


@app.patch("/documents/{document_id}", response_model=DocumentResponse)
def update_document_endpoint(
    document_id: str,
    payload: DocumentUpdate,
    session: Session = Depends(get_session),
):
    document = services.update_document(
        session,
        document_id,
        payload.editor_id,
        payload.title,
        payload.content,
    )
    cycle = services._get_active_cycle(session, document_id)
    reviewer_ids = services.list_reviewer_ids(session, cycle.id) if cycle else []
    pending_reviewers = (
        services.list_pending_reviewers(session, cycle.id) if cycle else []
    )
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        author_id=document.author_id,
        status=document.status,
        reviewer_ids=reviewer_ids,
        pending_reviewers=pending_reviewers,
    )


@app.post("/documents/{document_id}/submit", response_model=DocumentResponse)
def submit_document_endpoint(
    document_id: str,
    payload: DocumentSubmit,
    session: Session = Depends(get_session),
):
    services.submit_document(
        session,
        document_id,
        payload.author_id,
        payload.reviewer_ids,
        payload.escalation,
    )
    document = services._get_document(session, document_id)
    cycle = services._get_active_cycle(session, document_id)
    reviewer_ids = services.list_reviewer_ids(session, cycle.id) if cycle else []
    pending_reviewers = (
        services.list_pending_reviewers(session, cycle.id) if cycle else []
    )
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        author_id=document.author_id,
        status=document.status,
        reviewer_ids=reviewer_ids,
        pending_reviewers=pending_reviewers,
    )


@app.post(
    "/documents/{document_id}/reviews/approve",
    response_model=DecisionResponse,
)
def approve_document_endpoint(
    document_id: str,
    payload: ApproveRequest,
    session: Session = Depends(get_session),
):
    decision = services.approve_document(
        session,
        document_id,
        payload.actor_id,
        payload.on_behalf_of,
    )
    return DecisionResponse(
        decision={
            "status": decision.status,
            "reviewer_id": decision.reviewer_id,
            "acted_by": decision.acted_by,
            "decided_at": decision.decided_at,
            "reason": decision.reason,
        }
    )


@app.post(
    "/documents/{document_id}/reviews/reject",
    response_model=DecisionResponse,
)
def reject_document_endpoint(
    document_id: str,
    payload: RejectRequest,
    session: Session = Depends(get_session),
):
    decision = services.reject_document(
        session,
        document_id,
        payload.actor_id,
        payload.reason,
        payload.on_behalf_of,
    )
    return DecisionResponse(
        decision={
            "status": decision.status,
            "reviewer_id": decision.reviewer_id,
            "acted_by": decision.acted_by,
            "decided_at": decision.decided_at,
            "reason": decision.reason,
        }
    )


@app.get("/documents/{document_id}/reviews", response_model=ReviewHistoryResponse)
def list_reviews_endpoint(document_id: str, session: Session = Depends(get_session)):
    decisions = services.list_review_history_for_document(session, document_id)
    return ReviewHistoryResponse(
        items=[
            {
                "reviewer_id": decision.reviewer_id,
                "acted_by": decision.acted_by,
                "status": decision.status,
                "reason": decision.reason,
                "decided_at": decision.decided_at,
            }
            for decision in decisions
        ]
    )


@app.post(
    "/documents/{document_id}/delegations",
    response_model=DelegationResponse,
    status_code=201,
)
def create_delegation_endpoint(
    document_id: str,
    payload: DelegationCreate,
    session: Session = Depends(get_session),
):
    delegation = services.create_delegation(
        session,
        document_id,
        payload.delegator_id,
        payload.substitute_id,
        payload.expires_at,
    )
    return DelegationResponse(
        id=delegation.id,
        delegator_id=delegation.delegator_id,
        substitute_id=delegation.substitute_id,
        expires_at=delegation.expires_at,
    )


@app.post("/documents/{document_id}/delegations/{delegation_id}/revoke")
def revoke_delegation_endpoint(
    document_id: str,
    delegation_id: str,
    payload: DelegationRevoke,
    session: Session = Depends(get_session),
):
    delegation = services.revoke_delegation(
        session,
        document_id,
        delegation_id,
        payload.delegator_id,
    )
    return {"id": delegation.id, "revoked_at": delegation.revoked_at}


@app.get(
    "/documents/{document_id}/notifications", response_model=NotificationListResponse
)
def list_notifications_endpoint(
    document_id: str, session: Session = Depends(get_session)
):
    notifications = services.list_notifications(session, document_id)
    return NotificationListResponse(
        items=[
            {
                "recipient_id": notification.recipient_id,
                "message": notification.message,
                "created_at": notification.created_at,
            }
            for notification in notifications
        ]
    )


@app.post(
    "/documents/{document_id}/escalations/trigger", response_model=EscalationResponse
)
def trigger_escalation_endpoint(
    document_id: str,
    payload: EscalationTriggerRequest,
    session: Session = Depends(get_session),
):
    state = services.trigger_escalation(session, document_id, payload.now)
    ladder_list = json.loads(state.ladder_json or "[]")
    index = max(state.current_index - 1, 0)
    escalated_to = ladder_list[index] if ladder_list else ""
    return EscalationResponse(
        escalation={
            "escalated_to": escalated_to,
            "escalated_at": state.last_escalated_at,
        }
    )
