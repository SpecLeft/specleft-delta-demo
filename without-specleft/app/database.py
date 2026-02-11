"""Database configuration and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

DATABASE_URL = "sqlite:///./approval.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
