from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.documents.exceptions import (
    InvalidTransitionError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from app.documents.schemas import (
    DelegationRequest,
    DelegationRevokeRequest,
    DocumentCreateRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdateRequest,
    EscalationRequest,
    ReviewDecisionRequest,
    SubmitRequest,
)
from app.documents.service import DocumentService
from app.db import get_db


def get_router() -> APIRouter:
    router = APIRouter(prefix="/documents", tags=["documents"])

    @router.post(
        "", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
    )
    async def create_document(
        payload: DocumentCreateRequest, service: DocumentService = Depends(get_service)
    ):
        document = service.create_document(
            title=payload.title,
            content=payload.content,
            author_id=payload.author_id,
        )
        return _document_response(service, document.id)

    @router.get("", response_model=DocumentListResponse)
    async def list_documents(service: DocumentService = Depends(get_service)):
        documents = service.list_documents()
        response = [_document_response(service, document.id) for document in documents]
        return DocumentListResponse(documents=response)

    @router.get("/{document_id}", response_model=DocumentResponse)
    async def get_document(
        document_id: int, service: DocumentService = Depends(get_service)
    ):
        return _document_response(service, document_id)

    @router.put("/{document_id}", response_model=DocumentResponse)
    async def update_document(
        document_id: int,
        payload: DocumentUpdateRequest,
        service: DocumentService = Depends(get_service),
    ):
        document = service.update_document(
            document_id,
            title=payload.title,
            content=payload.content,
            author_id=payload.author_id,
        )
        return _document_response(service, document.id)

    @router.post("/{document_id}/submit", response_model=DocumentResponse)
    async def submit_document(
        document_id: int,
        payload: SubmitRequest,
        service: DocumentService = Depends(get_service),
    ):
        document = service.submit_document(
            document_id,
            author_id=payload.author_id,
            reviewer_ids=payload.reviewer_ids,
            escalation_timeout_seconds=payload.escalation_timeout_seconds,
        )
        return _document_response(service, document.id)

    @router.post("/{document_id}/decisions", response_model=DocumentResponse)
    async def decide_document(
        document_id: int,
        payload: ReviewDecisionRequest,
        service: DocumentService = Depends(get_service),
    ):
        document = service.decide_review(
            document_id,
            reviewer_id=payload.reviewer_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        return _document_response(service, document.id)

    @router.post("/{document_id}/delegate", status_code=status.HTTP_204_NO_CONTENT)
    async def delegate_review(
        document_id: int,
        payload: DelegationRequest,
        service: DocumentService = Depends(get_service),
    ):
        service.delegate_review(
            document_id=document_id,
            delegator_id=payload.delegator_id,
            substitute_id=payload.substitute_id,
            expires_at=payload.expires_at,
        )

    @router.post(
        "/{document_id}/delegate/revoke", status_code=status.HTTP_204_NO_CONTENT
    )
    async def revoke_delegation(
        document_id: int,
        payload: DelegationRevokeRequest,
        service: DocumentService = Depends(get_service),
    ):
        service.revoke_delegation(document_id, payload.delegator_id)

    @router.post("/{document_id}/escalate", response_model=DocumentResponse)
    async def escalate_document(
        document_id: int,
        payload: EscalationRequest,
        service: DocumentService = Depends(get_service),
    ):
        document = service.escalate_document(
            document_id=document_id,
            next_level_reviewer_id=payload.next_level_reviewer_id,
            escalation_timeout_seconds=payload.escalation_timeout_seconds,
        )
        return _document_response(service, document.id)

    return router


def _document_response(service: DocumentService, document_id: int) -> DocumentResponse:
    document = service.get_document(document_id)
    decisions = service.get_decisions(document_id)
    pending = service.get_pending_reviewers(document_id)
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        author_id=document.author_id,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        pending_reviewers=pending,
        decisions=[
            {
                "reviewer_id": decision.reviewer_id,
                "decision": decision.decision,
                "decided_at": decision.decided_at,
                "delegated_by": decision.delegated_by,
                "reason": decision.reason,
            }
            for decision in decisions
        ],
    )


def get_service(
    session: Session = Depends(get_db),
):
    from app.documents.repository import DocumentRepository
    from app.notifications.repository import NotificationRepository
    from app.notifications.service import NotificationService

    repo = DocumentRepository(session)
    notification_repo = NotificationRepository(session)
    notification_service = NotificationService(notification_repo)
    return DocumentService(session, repo, notification_service)


def register_exception_handlers(app):
    @app.exception_handler(NotFoundError)
    async def _not_found(_, exc: NotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
        )

    @app.exception_handler(PermissionError)
    async def _permission(_, exc: PermissionError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)}
        )

    @app.exception_handler(InvalidTransitionError)
    async def _invalid(_, exc: InvalidTransitionError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
        )

    @app.exception_handler(ValidationError)
    async def _validation(_, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
        )
