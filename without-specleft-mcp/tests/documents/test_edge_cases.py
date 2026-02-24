from __future__ import annotations


def _create_and_submit(client, reviewers):
    create = client.post(
        "/documents",
        json={"title": "Doc", "content": "Body", "author_id": 1},
    )
    document_id = create.json()["id"]
    client.post(
        f"/documents/{document_id}/submit",
        json={"author_id": 1, "reviewer_ids": reviewers},
    )
    return document_id


def test_concurrent_approval_and_rejection_rejects(client):
    document_id = _create_and_submit(client, [2, 3])
    client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    response = client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 3, "decision": "rejected", "reason": "no"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_submit_without_reviewers_returns_error(client):
    create = client.post(
        "/documents",
        json={"title": "Doc", "content": "Body", "author_id": 1},
    )
    document_id = create.json()["id"]
    response = client.post(
        f"/documents/{document_id}/submit",
        json={"author_id": 1, "reviewer_ids": []},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one reviewer is required"


def test_author_cannot_self_approve(client):
    document_id = _create_and_submit(client, [1])
    response = client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 1, "decision": "approved"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Self-approval is not permitted"


def test_resubmit_rejected_document_starts_new_review_cycle(client):
    document_id = _create_and_submit(client, [2])
    client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 2, "decision": "rejected", "reason": "no"},
    )
    response = client.post(
        f"/documents/{document_id}/submit",
        json={"author_id": 1, "reviewer_ids": [3]},
    )
    assert response.status_code == 200
    response = client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 3, "decision": "approved"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
