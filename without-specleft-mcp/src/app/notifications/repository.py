from __future__ import annotations

from sqlalchemy.orm import Session

from app.notifications.models import Notification


class NotificationRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(self, document_id: int, recipient_id: int, message: str) -> Notification:
        notification = Notification(
            document_id=document_id,
            recipient_id=recipient_id,
            message=message,
        )
        self._session.add(notification)
        return notification
