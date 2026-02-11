from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    code: str
    message: str
    meta: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorPayload


class DocumentCreate(BaseModel):
    title: str
    content: str
    author_id: str


class DocumentUpdate(BaseModel):
    title: str
    content: str
    editor_id: str


class DocumentSubmit(BaseModel):
    author_id: str
    reviewer_ids: list[str]
    escalation: Optional[dict[str, Any]] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    author_id: str
    status: str
    reviewer_ids: list[str] = Field(default_factory=list)
    pending_reviewers: list[str] = Field(default_factory=list)


class DecisionPayload(BaseModel):
    status: str
    reviewer_id: str
    acted_by: str
    decided_at: datetime
    reason: Optional[str] = None


class DecisionResponse(BaseModel):
    decision: DecisionPayload


class RejectRequest(BaseModel):
    actor_id: str
    reason: str
    on_behalf_of: Optional[str] = None


class ApproveRequest(BaseModel):
    actor_id: str
    on_behalf_of: Optional[str] = None


class ReviewHistoryItem(BaseModel):
    reviewer_id: str
    acted_by: str
    status: str
    reason: Optional[str]
    decided_at: datetime


class ReviewHistoryResponse(BaseModel):
    items: list[ReviewHistoryItem]


class DelegationCreate(BaseModel):
    delegator_id: str
    substitute_id: str
    expires_at: datetime


class DelegationResponse(BaseModel):
    id: str
    delegator_id: str
    substitute_id: str
    expires_at: datetime


class DelegationRevoke(BaseModel):
    delegator_id: str


class EscalationTriggerRequest(BaseModel):
    now: datetime


class EscalationPayload(BaseModel):
    escalated_to: str
    escalated_at: datetime


class EscalationResponse(BaseModel):
    escalation: EscalationPayload


class NotificationItem(BaseModel):
    recipient_id: str
    message: str
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
