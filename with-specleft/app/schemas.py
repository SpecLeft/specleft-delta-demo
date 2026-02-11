from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Document schemas ---


class DocumentCreate(BaseModel):
    title: str
    body: str = ""
    author_id: str


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None


class DocumentSubmit(BaseModel):
    reviewer_ids: list[str]


class DocumentResponse(BaseModel):
    id: int
    title: str
    body: str
    status: str
    author_id: str
    created_at: datetime
    updated_at: datetime
    review_cycle: int = 1

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    id: int
    status: str
    reviewers: list[str]
    pending_reviewers: list[str]
    decisions: list["ReviewDecisionResponse"]

    model_config = {"from_attributes": True}


# --- Review schemas ---


class ReviewSubmit(BaseModel):
    reviewer_id: str
    decision: str  # "approved" or "rejected"
    reason: Optional[str] = None


class ReviewDecisionResponse(BaseModel):
    reviewer_id: str
    decision: str
    reason: Optional[str]
    decided_at: datetime
    on_behalf_of: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Delegation schemas ---


class DelegationCreate(BaseModel):
    delegator_id: str
    substitute_id: str
    expires_at: datetime


class DelegationResponse(BaseModel):
    id: int
    document_id: int
    delegator_id: str
    substitute_id: str
    expires_at: datetime
    created_at: datetime
    revoked: bool

    model_config = {"from_attributes": True}


class DelegationRevoke(BaseModel):
    delegator_id: str


# --- Escalation schemas ---


class EscalationConfig(BaseModel):
    timeout_hours: int = 24
    next_approver_id: str


class EscalationResponse(BaseModel):
    id: int
    document_id: int
    escalated_to: str
    escalation_level: int
    escalated_at: datetime

    model_config = {"from_attributes": True}


# --- Error schema ---


class ErrorResponse(BaseModel):
    detail: str
