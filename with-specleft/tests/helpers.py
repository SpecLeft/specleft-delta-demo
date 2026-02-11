"""Test helper functions for creating common test fixtures via the API."""

from fastapi.testclient import TestClient


def create_draft_document(
    client: TestClient,
    author_id: str = "author-1",
    title: str = "Test Doc",
    body: str = "Body",
) -> dict:
    resp = client.post(
        "/api/documents", json={"title": title, "body": body, "author_id": author_id}
    )
    assert resp.status_code == 201
    return resp.json()


def submit_document(client: TestClient, doc_id: int, reviewer_ids: list[str]) -> dict:
    resp = client.post(
        f"/api/documents/{doc_id}/submit", json={"reviewer_ids": reviewer_ids}
    )
    assert resp.status_code == 200
    return resp.json()


def approve_document(client: TestClient, doc_id: int, reviewer_id: str) -> dict:
    resp = client.post(
        f"/api/documents/{doc_id}/review",
        json={"reviewer_id": reviewer_id, "decision": "approved"},
    )
    return resp.json()


def reject_document(
    client: TestClient, doc_id: int, reviewer_id: str, reason: str = "Not good"
) -> dict:
    resp = client.post(
        f"/api/documents/{doc_id}/review",
        json={"reviewer_id": reviewer_id, "decision": "rejected", "reason": reason},
    )
    return resp.json()


def create_and_submit_document(
    client: TestClient,
    author_id: str = "author-1",
    reviewer_ids: list[str] | None = None,
) -> dict:
    """Create a document and submit it for review in one step."""
    if reviewer_ids is None:
        reviewer_ids = ["reviewer-1"]
    doc = create_draft_document(client, author_id=author_id)
    submit_document(client, doc["id"], reviewer_ids)
    return doc


def get_approved_document(
    client: TestClient, author_id: str = "author-1", reviewer_id: str = "reviewer-1"
) -> dict:
    """Create, submit, and approve a document."""
    doc = create_and_submit_document(
        client, author_id=author_id, reviewer_ids=[reviewer_id]
    )
    approve_document(client, doc["id"], reviewer_id)
    return doc
