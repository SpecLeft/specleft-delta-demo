from __future__ import annotations

from app.notifications.repository import NotificationRepository


class NotificationService:
    def __init__(self, repository: NotificationRepository):
        self._repository = repository

    def notify_reviewer(self, document_id: int, reviewer_id: int) -> None:
        self._repository.create(
            document_id=document_id,
            recipient_id=reviewer_id,
            message="Review requested",
        )

    def notify_escalation(self, document_id: int, reviewer_id: int) -> None:
        self._repository.create(
            document_id=document_id,
            recipient_id=reviewer_id,
            message="Escalated review requested",
        )
