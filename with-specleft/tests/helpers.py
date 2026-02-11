from __future__ import annotations

from typing import Any

from app.state import reset_state


def reset_storage():
    reset_state()


def assert_error(
    response, status_code: int, code: str, message_contains: str | None = None
) -> None:
    assert response.status_code == status_code
    payload = response.json()
    assert "error" in payload
    assert payload["error"]["code"] == code
    if message_contains is not None:
        assert message_contains in payload["error"]["message"]


def create_document(
    client, author_id: str, title: str = "Draft", content: str = "Content"
):
    return client.post(
        "/documents",
        json={
            "title": title,
            "content": content,
            "author_id": author_id,
        },
    )


def update_document(client, document_id: str, editor_id: str, title: str, content: str):
    return client.patch(
        f"/documents/{document_id}",
        json={
            "title": title,
            "content": content,
            "editor_id": editor_id,
        },
    )


def submit_document(
    client,
    document_id: str,
    author_id: str,
    reviewer_ids: list[str],
    escalation: dict[str, Any] | None = None,
):
    payload: dict[str, Any] = {
        "author_id": author_id,
        "reviewer_ids": reviewer_ids,
    }
    if escalation is not None:
        payload["escalation"] = escalation
    return client.post(f"/documents/{document_id}/submit", json=payload)


def submit_document_with_start_time(
    client,
    document_id: str,
    author_id: str,
    reviewer_ids: list[str],
    escalation: dict[str, Any] | None,
    start_at: str,
):
    payload: dict[str, Any] = {
        "author_id": author_id,
        "reviewer_ids": reviewer_ids,
    }
    if escalation is not None:
        escalation_payload = dict(escalation)
        escalation_payload["start_at"] = start_at
        payload["escalation"] = escalation_payload
    return client.post(f"/documents/{document_id}/submit", json=payload)


def get_document(client, document_id: str):
    return client.get(f"/documents/{document_id}")


def approve_document(
    client,
    document_id: str,
    actor_id: str,
    on_behalf_of: str | None = None,
):
    payload: dict[str, Any] = {"actor_id": actor_id}
    if on_behalf_of is not None:
        payload["on_behalf_of"] = on_behalf_of
    return client.post(f"/documents/{document_id}/reviews/approve", json=payload)


def reject_document(
    client,
    document_id: str,
    actor_id: str,
    reason: str,
    on_behalf_of: str | None = None,
):
    payload: dict[str, Any] = {"actor_id": actor_id, "reason": reason}
    if on_behalf_of is not None:
        payload["on_behalf_of"] = on_behalf_of
    return client.post(f"/documents/{document_id}/reviews/reject", json=payload)


def create_delegation(
    client,
    document_id: str,
    delegator_id: str,
    substitute_id: str,
    expires_at: str,
):
    return client.post(
        f"/documents/{document_id}/delegations",
        json={
            "delegator_id": delegator_id,
            "substitute_id": substitute_id,
            "expires_at": expires_at,
        },
    )


def revoke_delegation(client, document_id: str, delegation_id: str, delegator_id: str):
    return client.post(
        f"/documents/{document_id}/delegations/{delegation_id}/revoke",
        json={"delegator_id": delegator_id},
    )


def trigger_escalation(client, document_id: str, now: str):
    return client.post(
        f"/documents/{document_id}/escalations/trigger",
        json={"now": now},
    )


def list_notifications(client, document_id: str):
    return client.get(f"/documents/{document_id}/notifications")
