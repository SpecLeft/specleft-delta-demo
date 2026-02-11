from __future__ import annotations

from app.database import reset_db


def reset_state() -> None:
    reset_db()
