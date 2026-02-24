from __future__ import annotations


def test_submission_succeeds_without_notification_delivery(client):
    response = client.post(
        "/documents",
        json={"title": "Doc", "content": "Body", "author_id": 1},
    )
    document_id = response.json()["id"]
    response = client.post(
        f"/documents/{document_id}/submit",
        json={"author_id": 1, "reviewer_ids": [2, 3]},
    )
    assert response.status_code == 200
