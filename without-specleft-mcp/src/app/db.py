from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def get_engine(database_url: str):
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if database_url.endswith(":memory:"):
            return create_engine(
                database_url,
                future=True,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(database_url, future=True, connect_args=connect_args)
    return create_engine(database_url, future=True)


def get_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_engine(database_url: str):
    global _engine, _session_factory
    _engine = get_engine(database_url)
    Base.metadata.create_all(_engine)
    _session_factory = get_session_factory(_engine)


def get_db():
    if _session_factory is None:
        raise RuntimeError("Database is not initialized")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
