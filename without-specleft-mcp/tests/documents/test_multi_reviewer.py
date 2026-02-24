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


def test_requires_all_reviewers_to_approve(client):
    document_id = _create_and_submit(client, [2, 3, 4])
    client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    response = client.get(f"/documents/{document_id}")
    payload = response.json()
    assert payload["status"] == "review"
    assert payload["pending_reviewers"] == [3, 4]


def test_reject_if_any_reviewer_rejects(client):
    document_id = _create_and_submit(client, [2, 3])
    client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 3, "decision": "rejected", "reason": "no"},
    )
    response = client.get(f"/documents/{document_id}")
    payload = response.json()
    assert payload["status"] == "rejected"


def test_duplicate_approval_rejected(client):
    document_id = _create_and_submit(client, [2])
    client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    response = client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Reviewer has already submitted a decision"


def test_review_history_records_timestamps(client):
    document_id = _create_and_submit(client, [2])
    client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    response = client.get(f"/documents/{document_id}")
    payload = response.json()
    assert payload["decisions"][0]["decided_at"]
