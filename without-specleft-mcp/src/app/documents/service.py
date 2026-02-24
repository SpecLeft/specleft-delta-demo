from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.documents.exceptions import (
    InvalidTransitionError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from app.documents.models import Document, DocumentStatus
from app.documents.repository import DocumentRepository
from app.notifications.service import NotificationService


class DocumentService:
    def __init__(
        self,
        session: Session,
        repository: DocumentRepository,
        notifications: NotificationService,
    ):
        self._session = session
        self._repository = repository
        self._notifications = notifications

    def create_document(self, title: str, content: str, author_id: int) -> Document:
        document = self._repository.create_document(title, content, author_id)
        self._session.flush()
        return document

    def update_document(
        self, document_id: int, title: str, content: str, author_id: int
    ) -> Document:
        document = self._require_document(document_id)
        if document.status == DocumentStatus.APPROVED:
            raise InvalidTransitionError("Document is locked")
        if document.status == DocumentStatus.REVIEW:
            raise InvalidTransitionError("Document is under review")
        if document.author_id != author_id:
            raise PermissionError("Only the author can edit the document")
        return self._repository.update_document(document, title, content)

    def submit_document(
        self,
        document_id: int,
        author_id: int,
        reviewer_ids: list[int],
        escalation_timeout_seconds: int,
    ) -> Document:
        document = self._require_document(document_id)
        if document.author_id != author_id:
            raise PermissionError("Only the author can submit the document")
        if document.status not in {DocumentStatus.DRAFT, DocumentStatus.REJECTED}:
            raise InvalidTransitionError("Document cannot be submitted")
        if not reviewer_ids:
            raise ValidationError("At least one reviewer is required")

        if document.status == DocumentStatus.REJECTED:
            self._repository.clear_reviewers(document)

        self._repository.add_reviewers(document, reviewer_ids)
        self._repository.update_status(document, DocumentStatus.REVIEW)
        document.review_cycle_started_at = datetime.utcnow()
        deadline = datetime.utcnow() + timedelta(seconds=escalation_timeout_seconds)
        self._repository.set_escalation_deadline(document, deadline)

        for reviewer_id in reviewer_ids:
            self._notifications.notify_reviewer(document.id, reviewer_id)

        self._session.flush()
        return document

    def decide_review(
        self,
        document_id: int,
        reviewer_id: int,
        decision: str,
        reason: str | None,
    ) -> Document:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.REVIEW:
            if document.status == DocumentStatus.APPROVED:
                raise ValidationError("Reviewer has already submitted a decision")
            raise InvalidTransitionError("Document is not under review")

        effective_reviewer_id = reviewer_id
        delegated_by = None
        delegation = self._repository.get_delegation_by_substitute(
            document_id, reviewer_id
        )
        if delegation:
            if delegation.revoked:
                raise PermissionError("Delegation has been revoked")
            if delegation.expires_at < datetime.utcnow():
                raise PermissionError("Delegation has expired")
            effective_reviewer_id = delegation.delegator_id
            delegated_by = reviewer_id

        if effective_reviewer_id == document.author_id:
            raise PermissionError("Self-approval is not permitted")

        if not self._repository.has_active_reviewer(document_id, effective_reviewer_id):
            delegation_check = self._repository.get_delegation_by_substitute(
                document_id, reviewer_id, include_revoked=True
            )
            if delegation_check and delegation_check.revoked:
                raise PermissionError("Delegation has been revoked")
            raise PermissionError("Reviewer is not assigned")

        if self._repository.reviewer_has_decision(
            document_id, effective_reviewer_id, document.review_cycle_started_at
        ):
            raise ValidationError("Reviewer has already submitted a decision")

        if decision not in {"approved", "rejected"}:
            raise ValidationError("Decision must be approved or rejected")

        self._repository.record_decision(
            document,
            reviewer_id=effective_reviewer_id,
            decision=decision,
            reason=reason,
            delegated_by=delegated_by,
        )
        self._session.flush()

        if decision == "rejected":
            self._repository.update_status(document, DocumentStatus.REJECTED)
            self._repository.remove_pending_reviewers(document_id)
            self._session.flush()
            return document

        pending = self._repository.pending_reviewer_ids(
            document_id, document.review_cycle_started_at
        )
        if not pending:
            self._repository.update_status(document, DocumentStatus.APPROVED)

        self._session.flush()
        return document

    def delegate_review(
        self,
        document_id: int,
        delegator_id: int,
        substitute_id: int,
        expires_at: datetime,
    ) -> None:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.REVIEW:
            raise InvalidTransitionError("Document is not under review")

        if self._repository.get_delegation_by_substitute(
            document_id, delegator_id, include_revoked=True
        ):
            raise ValidationError("Re-delegation is not permitted")

        if not self._repository.has_active_reviewer(document_id, delegator_id):
            raise PermissionError("Delegator is not an assigned reviewer")

        existing = self._repository.get_active_delegation(document_id, delegator_id)
        if existing and not existing.revoked:
            raise ValidationError("Delegation already exists")

        self._repository.record_delegation(
            document,
            delegator_id=delegator_id,
            substitute_id=substitute_id,
            expires_at=expires_at,
        )
        self._session.flush()

    def revoke_delegation(self, document_id: int, delegator_id: int) -> None:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.REVIEW:
            raise InvalidTransitionError("Document is not under review")

        delegation = self._repository.get_active_delegation(document_id, delegator_id)
        if not delegation:
            raise ValidationError("Delegation not found")

        self._repository.revoke_delegation(delegation)
        self._session.flush()

    def escalate_document(
        self,
        document_id: int,
        next_level_reviewer_id: int,
        escalation_timeout_seconds: int,
        max_depth: int = 3,
    ) -> Document:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.REVIEW:
            return document

        if not self._repository.pending_reviewer_ids(
            document_id, document.review_cycle_started_at
        ):
            return document

        if document.escalation_depth >= max_depth:
            raise ValidationError("Maximum escalation depth reached")

        if (
            document.escalation_deadline
            and document.escalation_deadline > datetime.utcnow()
        ):
            raise ValidationError("Escalation timeout has not elapsed")

        new_depth = document.escalation_depth + 1
        self._repository.add_escalation(document, next_level_reviewer_id, new_depth)
        self._repository.assign_reviewer_if_missing(document, next_level_reviewer_id)
        self._repository.set_escalation_depth(document, new_depth)
        new_deadline = datetime.utcnow() + timedelta(seconds=escalation_timeout_seconds)
        self._repository.set_escalation_deadline(document, new_deadline)
        self._notifications.notify_escalation(document.id, next_level_reviewer_id)

        self._session.flush()
        return document

    def list_documents(self) -> list[Document]:
        return self._repository.list_documents()

    def get_document(self, document_id: int) -> Document:
        return self._require_document(document_id)

    def get_pending_reviewers(self, document_id: int) -> list[int]:
        document = self._require_document(document_id)
        return self._repository.pending_reviewer_ids(
            document_id, document.review_cycle_started_at
        )

    def get_decisions(self, document_id: int):
        return self._repository.get_decisions(document_id)

    def _require_document(self, document_id: int) -> Document:
        document = self._repository.get_document(document_id)
        if not document:
            raise NotFoundError("Document not found")
        return document
