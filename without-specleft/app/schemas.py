from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import DocumentStatus, ReviewDecision


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author_id: str = Field(..., min_length=1, max_length=50)
    escalation_timeout_seconds: int | None = Field(None, ge=60, le=86400)
    escalation_max_level: int | None = Field(None, ge=1, le=10)


class DocumentUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class ReviewerAssign(BaseModel):
    reviewer_ids: list[str] = Field(...)


class SubmitReviewRequest(BaseModel):
    reviewer_ids: list[str] = Field(...)


class ReviewDecisionRequest(BaseModel):
    reviewer_id: str = Field(..., min_length=1, max_length=50)
    decision: ReviewDecision
    reason: str | None = None


class DelegationRequest(BaseModel):
    delegator_id: str = Field(..., min_length=1, max_length=50)
    substitute_id: str = Field(..., min_length=1, max_length=50)
    expires_at: datetime


class DelegationRevokeRequest(BaseModel):
    delegator_id: str = Field(..., min_length=1, max_length=50)


class EscalationTriggerRequest(BaseModel):
    now: datetime | None = None


class DecisionRecord(BaseModel):
    reviewer_id: str
    decision: ReviewDecision
    decided_at: datetime
    reason: str | None
    acting_on_behalf_of: str | None
    review_cycle: int


class ReviewerStatus(BaseModel):
    reviewer_id: str
    pending: bool


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    status: DocumentStatus
    author_id: str
    review_cycle: int
    escalation_level: int
    escalation_deadline: datetime | None
    reviewers: list[str]
    pending_reviewers: list[str]
    decisions: list[DecisionRecord]
    created_at: datetime
    updated_at: datetime


class DelegationResponse(BaseModel):
    id: int
    document_id: int
    delegator_id: str
    substitute_id: str
    expires_at: datetime
    active: bool
    revoked_at: datetime | None


class EscalationResponse(BaseModel):
    id: int
    document_id: int
    escalated_at: datetime
    from_level: int
    to_level: int
    approver_id: str


class ErrorResponse(BaseModel):
    detail: str
