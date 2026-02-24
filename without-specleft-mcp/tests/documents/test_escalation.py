from __future__ import annotations

from datetime import datetime, timedelta

import app.documents.service as service_module


def _create_and_submit(client, reviewers, timeout_seconds=120):
    create = client.post(
        "/documents",
        json={"title": "Doc", "content": "Body", "author_id": 1},
    )
    document_id = create.json()["id"]
    client.post(
        f"/documents/{document_id}/submit",
        json={
            "author_id": 1,
            "reviewer_ids": reviewers,
            "escalation_timeout_seconds": timeout_seconds,
        },
    )
    return document_id


def test_escalate_after_timeout_adds_reviewer(client, monkeypatch):
    frozen_time = datetime.utcnow()

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return frozen_time

    monkeypatch.setattr(service_module, "datetime", FrozenDateTime)

    document_id = _create_and_submit(client, [2], timeout_seconds=120)
    frozen_time = frozen_time + timedelta(seconds=121)

    response = client.post(
        f"/documents/{document_id}/escalate",
        json={"next_level_reviewer_id": 50, "escalation_timeout_seconds": 300},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "review"
    assert 50 in payload["pending_reviewers"]


def test_escalation_not_triggered_if_pending_cleared(client, monkeypatch):
    frozen_time = datetime.utcnow()

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return frozen_time

    monkeypatch.setattr(service_module, "datetime", FrozenDateTime)

    document_id = _create_and_submit(client, [2], timeout_seconds=120)
    client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": 2, "decision": "approved"},
    )
    frozen_time = frozen_time + timedelta(seconds=121)
    response = client.post(
        f"/documents/{document_id}/escalate",
        json={"next_level_reviewer_id": 50, "escalation_timeout_seconds": 1},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_escalation_resets_timeout(client, monkeypatch):
    frozen_time = datetime.utcnow()

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return frozen_time

    monkeypatch.setattr(service_module, "datetime", FrozenDateTime)

    document_id = _create_and_submit(client, [2], timeout_seconds=120)
    frozen_time = frozen_time + timedelta(seconds=121)
    response = client.post(
        f"/documents/{document_id}/escalate",
        json={"next_level_reviewer_id": 50, "escalation_timeout_seconds": 300},
    )
    assert response.status_code == 200

    response = client.post(
        f"/documents/{document_id}/escalate",
        json={"next_level_reviewer_id": 51, "escalation_timeout_seconds": 300},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Escalation timeout has not elapsed"
