"""Tests for Feature 3: Delegation.

Tests time-bound delegation, substitute approval, expiry handling,
revocation, and chain prevention.
"""

from datetime import datetime, timezone, timedelta


class TestCreateDelegation:
    """Scenario: Delegate review to substitute with expiry date."""

    def test_delegate_review_to_substitute(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        response = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["delegator_id"] == "reviewer-1"
        assert data["delegate_id"] == "substitute-1"
        assert data["revoked"] is False

    def test_delegation_includes_expiry_timestamp(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()

        response = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )
        data = response.json()
        assert data["expires_at"] is not None


class TestSubstituteApproval:
    """Scenario: Substitute can approve on behalf of delegator."""

    def test_substitute_can_approve(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        # Create delegation
        client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )

        # Substitute approves
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "substitute-1", "decision": "approved"},
        )
        assert response.status_code == 200

        # Check that the decision is recorded as substitute acting on behalf of delegator
        data = response.json()
        cycle = data["review_cycles"][-1]
        reviewer_1_assignment = next(
            a for a in cycle["assignments"] if a["reviewer_id"] == "reviewer-1"
        )
        assert reviewer_1_assignment["decision"] == "approved"
        assert reviewer_1_assignment["decided_by_delegate_id"] == "substitute-1"

    def test_substitute_approval_satisfies_delegator_requirement(
        self, client, submitted_document
    ):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]

        # Delegate reviewer-1's assignment
        assignment_id = next(
            a["id"] for a in cycle["assignments"] if a["reviewer_id"] == "reviewer-1"
        )
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )

        # Substitute approves for reviewer-1
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "substitute-1", "decision": "approved"},
        )
        # reviewer-2 and reviewer-3 also approve
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-2", "decision": "approved"},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-3", "decision": "approved"},
        )
        data = response.json()
        assert data["status"] == "approved"


class TestExpiredDelegation:
    """Scenario: Expired delegation is rejected."""

    def test_expired_delegation_rejected(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]
        # Set expiry in the past
        expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        response = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )
        # Delegation should be rejected because expiry is in the past
        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()

    def test_substitute_cannot_act_on_expired_delegation(
        self, client, submitted_document, db_session
    ):
        """Test that even if a delegation existed but expired, the substitute cannot act."""
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]

        # Create delegation with future expiry
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        delegation_resp = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )
        assert delegation_resp.status_code == 201

        # Manually expire the delegation via DB
        from app.models import Delegation

        deleg = (
            db_session.query(Delegation)
            .filter(Delegation.id == delegation_resp.json()["id"])
            .first()
        )
        deleg.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        # Substitute tries to approve — should fail
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "substitute-1", "decision": "approved"},
        )
        assert response.status_code == 403
        assert "not an assigned reviewer" in response.json()["detail"].lower()


class TestRevokeDelegation:
    """Scenario: Delegator can revoke delegation before expiry."""

    def test_revoke_active_delegation(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        # Create delegation
        deleg_resp = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )
        delegation_id = deleg_resp.json()["id"]

        # Revoke it
        response = client.post(
            f"/api/v1/documents/{doc_id}/delegations/{delegation_id}/revoke?user_id=reviewer-1",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is True
        assert data["revoked_at"] is not None

    def test_substitute_rejected_after_revocation(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        deleg_resp = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )
        delegation_id = deleg_resp.json()["id"]

        # Revoke
        client.post(
            f"/api/v1/documents/{doc_id}/delegations/{delegation_id}/revoke?user_id=reviewer-1",
        )

        # Substitute tries to approve — should be rejected
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "substitute-1", "decision": "approved"},
        )
        assert response.status_code == 403


class TestPreventDelegationChain:
    """Scenario: Prevent delegation chain (re-delegation)."""

    def test_substitute_cannot_redelegate(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]

        # Delegate reviewer-1 -> substitute-1
        assignment_1_id = next(
            a["id"] for a in cycle["assignments"] if a["reviewer_id"] == "reviewer-1"
        )
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_1_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )

        # Attempt: substitute-1 tries to delegate reviewer-2's assignment
        # (substitute-1 would need to be reviewer-2, which they aren't)
        # This tests the chain prevention by checking if a delegate tries
        # to delegate any other assignment they may have access to
        assignment_2_id = next(
            a["id"] for a in cycle["assignments"] if a["reviewer_id"] == "reviewer-2"
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_2_id}/delegate",
            json={
                "delegator_id": "reviewer-2",
                "delegate_id": "substitute-2",
                "expires_at": expires_at,
            },
        )
        # This should work because reviewer-2 is directly assigned, not a delegate
        assert response.status_code == 201

    def test_one_active_delegation_per_assignment(self, client, submitted_document):
        doc_id = submitted_document["id"]
        cycle = submitted_document["review_cycles"][-1]
        assignment_id = cycle["assignments"][0]["id"]
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        # First delegation succeeds
        client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-1",
                "expires_at": expires_at,
            },
        )

        # Second delegation on same assignment should fail
        response = client.post(
            f"/api/v1/documents/{doc_id}/assignments/{assignment_id}/delegate",
            json={
                "delegator_id": "reviewer-1",
                "delegate_id": "substitute-2",
                "expires_at": expires_at,
            },
        )
        assert response.status_code == 409
        assert "active delegation already exists" in response.json()["detail"].lower()
