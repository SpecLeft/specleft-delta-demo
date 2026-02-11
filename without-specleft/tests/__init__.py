"""Test configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from main import app


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with an overridden database dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_document(client):
    """Create a sample document and return the response."""
    response = client.post(
        "/api/v1/documents",
        json={
            "title": "Test Document",
            "content": "This is test content.",
            "author_id": "author-1",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def submitted_document(client, sample_document):
    """Create a document and submit it for review."""
    doc_id = sample_document["id"]
    response = client.post(
        f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
        json={"reviewer_ids": ["reviewer-1", "reviewer-2", "reviewer-3"]},
    )
    assert response.status_code == 200
    return response.json()
