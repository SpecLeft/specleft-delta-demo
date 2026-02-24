from __future__ import annotations

from datetime import datetime, timedelta


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


def test_delegate_review_with_expiry(client):
    document_id = _create_and_submit(client, [2])
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    response = client.post(
        f"/documents/{document_id}/delegate",
        json={"delegator_id": 2, "substitute_id": 99, "expires_at": expires_at},
    )
    assert response.status_code == 204


def test_substitute_can_approve_on_behalf_of_delegator(client):
    document_id = _create_and_submit(client, [2])
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    client.post(
        f"/documents/{document_id}/delegate",
        json={"delegator_id": 2, "substitute_id": 99, "expires_at": expires_at},
    )
    response = client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 99, "decision": "approved"},
    )
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["decisions"][0]["delegated_by"] == 99


def test_expired_delegation_rejected(client):
    document_id = _create_and_submit(client, [2])
    expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    client.post(
        f"/documents/{document_id}/delegate",
        json={"delegator_id": 2, "substitute_id": 99, "expires_at": expires_at},
    )
    response = client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 99, "decision": "approved"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Delegation has expired"


def test_revoke_delegation_prevents_action(client):
    document_id = _create_and_submit(client, [2])
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    client.post(
        f"/documents/{document_id}/delegate",
        json={"delegator_id": 2, "substitute_id": 99, "expires_at": expires_at},
    )
    client.post(
        f"/documents/{document_id}/delegate/revoke",
        json={"delegator_id": 2},
    )
    response = client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 99, "decision": "approved"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Delegation has been revoked"


def test_prevent_delegation_chain(client):
    document_id = _create_and_submit(client, [2])
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    client.post(
        f"/documents/{document_id}/delegate",
        json={"delegator_id": 2, "substitute_id": 99, "expires_at": expires_at},
    )
    response = client.post(
        f"/documents/{document_id}/delegate",
        json={"delegator_id": 99, "substitute_id": 100, "expires_at": expires_at},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Re-delegation is not permitted"
