from __future__ import annotations

import os

from fastapi import FastAPI

from app.db import init_engine
from app.documents.router import get_router, register_exception_handlers


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Document Approval API")

    db_url = database_url or os.environ.get("DATABASE_URL", "sqlite:///./app.db")
    init_engine(db_url)
    app.include_router(get_router())
    register_exception_handlers(app)
    return app
