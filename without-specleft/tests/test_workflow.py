from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app
from app.database import Base, get_db
from app.models import Delegation, Document, DocumentStatus, ReviewDecisionRecord


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_document(client, title="Doc", content="Body", author_id="author"):
    response = client.post(
        "/documents",
        json={"title": title, "content": content, "author_id": author_id},
    )
    assert response.status_code == 200
    return response.json()


def _submit_for_review(client, document_id, reviewers):
    response = client.post(
        f"/documents/{document_id}/submit",
        json={"reviewer_ids": reviewers},
    )
    assert response.status_code == 200
    return response.json()


def _approve(client, document_id, reviewer_id):
    return client.post(
        f"/documents/{document_id}/decisions",
        json={"reviewer_id": reviewer_id, "decision": "approved"},
    )


def _reject(client, document_id, reviewer_id, reason="no"):
    return client.post(
        f"/documents/{document_id}/decisions",
        json={
            "reviewer_id": reviewer_id,
            "decision": "rejected",
            "reason": reason,
        },
    )


def test_create_document_defaults_to_draft(client):
    document = _create_document(client)
    assert document["status"] == "draft"
    assert document["author_id"] == "author"


def test_submit_requires_reviewers(client):
    document = _create_document(client)
    response = client.post(
        f"/documents/{document['id']}/submit",
        json={"reviewer_ids": []},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one reviewer is required"


def test_submit_sets_review_state_and_notifications(client, db_session):
    document = _create_document(client)
    submitted = _submit_for_review(client, document["id"], ["r1", "r2"])
    assert submitted["status"] == "review"
    assert sorted(submitted["reviewers"]) == ["r1", "r2"]
    assert sorted(submitted["pending_reviewers"]) == ["r1", "r2"]
    notifications = (
        db_session.execute(select(Document).where(Document.id == document["id"]))
        .scalar_one()
        .notifications
    )
    assert len(notifications) == 2


def test_single_reviewer_approval(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    response = _approve(client, document["id"], "r1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["decisions"][0]["decision"] == "approved"
    assert payload["decisions"][0]["decided_at"]


def test_reject_records_reason(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    response = _reject(client, document["id"], "r1", "needs work")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["decisions"][0]["reason"] == "needs work"


def test_prevent_edit_when_under_review_or_approved(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    response = client.put(
        f"/documents/{document['id']}",
        json={"title": "New", "content": "Body"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Document is under review"

    _approve(client, document["id"], "r1")
    response = client.put(
        f"/documents/{document['id']}",
        json={"title": "New", "content": "Body"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Document is locked"


def test_multi_reviewer_requires_all(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1", "r2", "r3"])
    _approve(client, document["id"], "r1")
    response = _approve(client, document["id"], "r2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "review"
    assert payload["pending_reviewers"] == ["r3"]
    response = _approve(client, document["id"], "r3")
    assert response.json()["status"] == "approved"


def test_rejection_precedence(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1", "r2"])
    _approve(client, document["id"], "r1")
    response = _reject(client, document["id"], "r2", "no")
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    follow_up = _approve(client, document["id"], "r1")
    assert follow_up.status_code == 400
    assert follow_up.json()["detail"] == "Reviewer already submitted a decision"


def test_duplicate_reviewer_decision_rejected(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    _approve(client, document["id"], "r1")
    response = _approve(client, document["id"], "r1")
    assert response.status_code == 400
    assert response.json()["detail"] == "Reviewer already submitted a decision"


def test_self_approval_not_allowed(client):
    document = _create_document(client, author_id="r1")
    _submit_for_review(client, document["id"], ["r1"])
    response = _approve(client, document["id"], "r1")
    assert response.status_code == 400
    assert response.json()["detail"] == "Self-approval is not permitted"


def test_delegation_allows_substitute_to_approve(client, db_session):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    response = client.post(
        f"/documents/{document['id']}/delegations",
        json={
            "delegator_id": "r1",
            "substitute_id": "sub1",
            "expires_at": expires_at,
        },
    )
    assert response.status_code == 200

    approval = _approve(client, document["id"], "sub1")
    assert approval.status_code == 200
    payload = approval.json()
    assert payload["status"] == "approved"
    decisions = db_session.execute(select(ReviewDecisionRecord)).scalars().all()
    assert decisions[0].acting_on_behalf_of == "r1"


def test_expired_delegation_rejected(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    client.post(
        f"/documents/{document['id']}/delegations",
        json={
            "delegator_id": "r1",
            "substitute_id": "sub1",
            "expires_at": expires_at,
        },
    )
    response = _approve(client, document["id"], "sub1")
    assert response.status_code == 400
    assert response.json()["detail"] == "Delegation has expired"


def test_revoke_delegation_blocks_substitute(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    client.post(
        f"/documents/{document['id']}/delegations",
        json={
            "delegator_id": "r1",
            "substitute_id": "sub1",
            "expires_at": expires_at,
        },
    )
    response = client.post(
        f"/documents/{document['id']}/delegations/revoke",
        json={"delegator_id": "r1"},
    )
    assert response.status_code == 200
    approval = _approve(client, document["id"], "sub1")
    assert approval.status_code == 400
    assert approval.json()["detail"] == "Reviewer is not assigned"


def test_prevent_delegation_chain(client, db_session):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    client.post(
        f"/documents/{document['id']}/delegations",
        json={
            "delegator_id": "r1",
            "substitute_id": "sub1",
            "expires_at": expires_at,
        },
    )
    response = client.post(
        f"/documents/{document['id']}/delegations",
        json={
            "delegator_id": "sub1",
            "substitute_id": "sub2",
            "expires_at": expires_at,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Re-delegation is not permitted"
    delegation = db_session.execute(select(Delegation)).scalar_one()
    assert delegation.substitute_id == "sub1"


def test_escalation_adds_reviewer_and_resets_deadline(client):
    document = _create_document(
        client,
        author_id="author",
    )
    _submit_for_review(client, document["id"], ["r1"])
    now = datetime.utcnow()
    response = client.post(
        f"/documents/{document['id']}/escalate",
        json={"now": (now + timedelta(hours=2)).isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["escalation_level"] == 1
    assert payload["status"] == "review"
    assert payload["escalation_deadline"]

    response = client.post(
        f"/documents/{document['id']}/escalate",
        json={"now": (now + timedelta(hours=4)).isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["escalation_level"] == 2


def test_escalation_respects_max_level(client):
    document = _create_document(
        client,
        author_id="author",
    )
    _submit_for_review(client, document["id"], ["r1"])
    now = datetime.utcnow()
    response = client.post(
        f"/documents/{document['id']}/escalate",
        json={"now": (now + timedelta(hours=2)).isoformat()},
    )
    assert response.status_code == 200
    response = client.post(
        f"/documents/{document['id']}/escalate",
        json={"now": (now + timedelta(hours=4)).isoformat()},
    )
    assert response.status_code == 200
    response = client.post(
        f"/documents/{document['id']}/escalate",
        json={"now": (now + timedelta(hours=6)).isoformat()},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Maximum escalation level reached"


def test_resubmit_rejected_creates_new_cycle(client, db_session):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    _reject(client, document["id"], "r1", "no")
    response = client.post(
        f"/documents/{document['id']}/submit",
        json={"reviewer_ids": ["r2"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_cycle"] == 2
    assert payload["reviewers"] == ["r2"]
    decisions = (
        db_session.execute(
            select(ReviewDecisionRecord).where(
                ReviewDecisionRecord.document_id == document["id"]
            )
        )
        .scalars()
        .all()
    )
    assert len(decisions) == 1


def test_document_status_endpoint_includes_pending_reviewers(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1", "r2"])
    _approve(client, document["id"], "r1")
    response = client.get(f"/documents/{document['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pending_reviewers"] == ["r2"]
    assert payload["status"] == "review"


def test_document_locked_state_on_approved(client):
    document = _create_document(client)
    _submit_for_review(client, document["id"], ["r1"])
    _approve(client, document["id"], "r1")
    response = client.get(f"/documents/{document['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == DocumentStatus.APPROVED.value
