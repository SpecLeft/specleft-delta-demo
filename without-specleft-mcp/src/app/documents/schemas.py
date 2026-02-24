from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.documents.models import DocumentStatus


class DocumentCreateRequest(BaseModel):
    title: str
    content: str
    author_id: int


class ReviewerAssignmentRequest(BaseModel):
    reviewer_ids: list[int] = Field(default_factory=list)


class DocumentUpdateRequest(BaseModel):
    title: str
    content: str
    author_id: int


class SubmitRequest(BaseModel):
    author_id: int
    reviewer_ids: list[int] = Field(default_factory=list)
    escalation_timeout_seconds: int = Field(default=3600, ge=1)


class ReviewDecisionRequest(BaseModel):
    reviewer_id: int
    decision: str
    reason: str | None = None


class DelegationRequest(BaseModel):
    delegator_id: int
    substitute_id: int
    expires_at: datetime


class DelegationRevokeRequest(BaseModel):
    delegator_id: int


class EscalationRequest(BaseModel):
    next_level_reviewer_id: int
    escalation_timeout_seconds: int = Field(default=3600, ge=1)


class ReviewerDecisionResponse(BaseModel):
    reviewer_id: int
    decision: str
    decided_at: datetime
    delegated_by: int | None
    reason: str | None


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    author_id: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    pending_reviewers: list[int]
    decisions: list[ReviewerDecisionResponse]


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
