"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from app.models import DocumentStatus, ReviewDecision


# --- Document Schemas ---


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    author_id: str = Field(..., min_length=1, max_length=100)
    escalation_timeout_hours: int = Field(default=24, ge=1)
    max_escalation_depth: int = Field(default=3, ge=1)


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)


class DocumentSubmit(BaseModel):
    reviewer_ids: List[str]

    @field_validator("reviewer_ids")
    @classmethod
    def validate_reviewer_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one reviewer is required")
        return v


class ReviewerAssignmentResponse(BaseModel):
    id: int
    reviewer_id: str
    decision: ReviewDecision
    decided_at: Optional[datetime] = None
    reason: Optional[str] = None
    assigned_at: datetime
    decided_by_delegate_id: Optional[str] = None
    is_escalated: bool = False

    model_config = {"from_attributes": True}


class ReviewCycleResponse(BaseModel):
    id: int
    cycle_number: int
    created_at: datetime
    assignments: List[ReviewerAssignmentResponse] = []

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    status: DocumentStatus
    author_id: str
    created_at: datetime
    updated_at: datetime
    escalation_timeout_hours: int
    max_escalation_depth: int
    review_cycles: List[ReviewCycleResponse] = []
    pending_reviewers: List[str] = []

    model_config = {"from_attributes": True}


# --- Review Schemas ---


class ReviewSubmit(BaseModel):
    reviewer_id: str = Field(..., min_length=1)
    decision: ReviewDecision = Field(...)
    reason: Optional[str] = None


# --- Delegation Schemas ---


class DelegationCreate(BaseModel):
    delegator_id: str = Field(..., min_length=1)
    delegate_id: str = Field(..., min_length=1)
    expires_at: datetime


class DelegationResponse(BaseModel):
    id: int
    assignment_id: int
    delegator_id: str
    delegate_id: str
    expires_at: datetime
    created_at: datetime
    revoked: bool
    revoked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Escalation Schemas ---


class EscalationTrigger(BaseModel):
    escalated_to_reviewer_id: str = Field(..., min_length=1)


class EscalationResponse(BaseModel):
    id: int
    review_cycle_id: int
    escalated_from_reviewer_id: Optional[str] = None
    escalated_to_reviewer_id: str
    escalation_depth: int
    escalated_at: datetime
    timeout_at: datetime

    model_config = {"from_attributes": True}


# --- Notification Schemas ---


class NotificationResponse(BaseModel):
    id: int
    recipient_id: str
    document_id: int
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Error Schema ---


class ErrorResponse(BaseModel):
    detail: str
