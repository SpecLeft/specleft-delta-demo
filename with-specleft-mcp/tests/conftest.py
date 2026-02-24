from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import main


@pytest.fixture
def client() -> TestClient:
    main.configure_engine("sqlite+pysqlite:///:memory:")
    main.init_db()
    return TestClient(main.app)


@pytest.fixture
def author(client: TestClient) -> dict:
    response = client.post("/users", json={"name": "Author"})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def reviewer(client: TestClient) -> dict:
    response = client.post("/users", json={"name": "Reviewer"})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def additional_reviewer(client: TestClient) -> dict:
    response = client.post("/users", json={"name": "Reviewer Two"})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def third_reviewer(client: TestClient) -> dict:
    response = client.post("/users", json={"name": "Reviewer Three"})
    assert response.status_code == 200
    return response.json()


def create_document(
    client: TestClient,
    author_id: int,
    reviewer_ids: list[int],
    escalation_chain: list[int] | None = None,
    escalation_timeout_seconds: int = 3600,
) -> dict:
    payload = {
        "author_id": author_id,
        "title": "Test Document",
        "content": "Content",
        "reviewer_ids": reviewer_ids,
        "escalation_chain": escalation_chain or [],
        "escalation_timeout_seconds": escalation_timeout_seconds,
        "max_escalation_depth": 3,
    }
    response = client.post("/documents", json=payload)
    assert response.status_code == 200
    return response.json()


def submit_document(client: TestClient, document_id: int, author_id: int) -> dict:
    response = client.post(
        f"/documents/{document_id}/submit", json={"author_id": author_id}
    )
    assert response.status_code == 200
    return response.json()


def resubmit_document(
    client: TestClient, document_id: int, author_id: int, reviewer_ids: list[int] | None
) -> dict:
    payload = {"author_id": author_id, "reviewer_ids": reviewer_ids}
    response = client.post(f"/documents/{document_id}/resubmit", json=payload)
    assert response.status_code == 200
    return response.json()


def update_document(
    client: TestClient,
    document_id: int,
    author_id: int,
    title: str | None = None,
    content: str | None = None,
) -> Response:
    payload: dict[str, object] = {"author_id": author_id}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    return client.patch(f"/documents/{document_id}", json=payload)


def review_document(
    client: TestClient,
    document_id: int,
    actor_id: int,
    decision: str,
    reason: str | None = None,
) -> Response:
    payload: dict[str, object] = {"actor_id": actor_id, "decision": decision}
    if reason is not None:
        payload["reason"] = reason
    return client.post(f"/documents/{document_id}/review", json=payload)


def delegate_review(
    client: TestClient,
    document_id: int,
    delegator_id: int,
    substitute_id: int,
    expires_at: str,
) -> Response:
    payload = {
        "delegator_id": delegator_id,
        "substitute_id": substitute_id,
        "expires_at": expires_at,
    }
    return client.post(f"/documents/{document_id}/delegate", json=payload)


def revoke_delegation(
    client: TestClient, document_id: int, delegator_id: int
) -> Response:
    return client.post(
        f"/documents/{document_id}/delegate/revoke",
        json={"delegator_id": delegator_id},
    )


def escalate_document(client: TestClient, document_id: int) -> Response:
    return client.post(f"/documents/{document_id}/escalate", json={})
