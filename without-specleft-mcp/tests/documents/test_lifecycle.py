from __future__ import annotations


def _create_document(client, author_id=10):
    response = client.post(
        "/documents",
        json={"title": "Doc", "content": "Body", "author_id": author_id},
    )
    assert response.status_code == 201
    return response.json()


def test_create_document_as_draft(client):
    payload = _create_document(client, author_id=1)
    assert payload["status"] == "draft"
    assert payload["author_id"] == 1


def test_submit_document_for_review_notifies_reviewers(client):
    document = _create_document(client, author_id=1)
    response = client.post(
        f"/documents/{document['id']}/submit",
        json={"author_id": 1, "reviewer_ids": [2, 3]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "review"
    assert sorted(payload["pending_reviewers"]) == [2, 3]


def test_approve_document_with_single_reviewer(client):
    document = _create_document(client, author_id=1)
    client.post(
        f"/documents/{document['id']}/submit",
        json={"author_id": 1, "reviewer_ids": [2]},
    )
    response = client.post(
        f"/documents/{document['id']}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["decisions"][0]["decided_at"]


def test_reject_document_with_reason(client):
    document = _create_document(client, author_id=1)
    client.post(
        f"/documents/{document['id']}/submit",
        json={"author_id": 1, "reviewer_ids": [2]},
    )
    response = client.post(
        f"/documents/{document['id']}/decisions",
        json={"reviewer_id": 2, "decision": "rejected", "reason": "needs work"},
    )
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["decisions"][0]["reason"] == "needs work"


def test_prevent_edit_approved_document(client):
    document = _create_document(client, author_id=1)
    client.post(
        f"/documents/{document['id']}/submit",
        json={"author_id": 1, "reviewer_ids": [2]},
    )
    client.post(
        f"/documents/{document['id']}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    response = client.put(
        f"/documents/{document['id']}",
        json={"title": "New", "content": "Updated", "author_id": 1},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Document is locked"


def test_prevent_edit_under_review_document(client):
    document = _create_document(client, author_id=1)
    client.post(
        f"/documents/{document['id']}/submit",
        json={"author_id": 1, "reviewer_ids": [2]},
    )
    response = client.put(
        f"/documents/{document['id']}",
        json={"title": "New", "content": "Updated", "author_id": 1},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Document is under review"
