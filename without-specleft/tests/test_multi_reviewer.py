"""Tests for Feature 2: Multi-Reviewer Approval.

Tests that all reviewers must approve, any rejection rejects the document,
individual decisions are tracked, and duplicates are prevented.
"""


class TestMultiReviewerApproval:
    """Scenario: Require all assigned reviewers to approve."""

    def test_partial_approval_keeps_review_status(self, client, submitted_document):
        doc_id = submitted_document["id"]
        # Two of three reviewers approve
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-2", "decision": "approved"},
        )
        data = response.json()
        assert data["status"] == "review"
        assert "reviewer-3" in data["pending_reviewers"]

    def test_all_reviewers_approve_changes_to_approved(
        self, client, submitted_document
    ):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
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
        assert data["pending_reviewers"] == []


class TestRejectIfAnyRejects:
    """Scenario: Reject if any reviewer rejects."""

    def test_single_rejection_rejects_document(self, client, submitted_document):
        doc_id = submitted_document["id"]
        # First reviewer approves
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        # Second reviewer rejects
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-2",
                "decision": "rejected",
                "reason": "Not ready.",
            },
        )
        data = response.json()
        assert data["status"] == "rejected"

    def test_remaining_reviewers_not_required_after_rejection(
        self, client, submitted_document
    ):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Bad.",
            },
        )
        # Third reviewer tries to act — document already rejected
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-3", "decision": "approved"},
        )
        assert response.status_code == 409
        assert "rejected" in response.json()["detail"].lower()


class TestTrackDecisions:
    """Scenario: Track individual reviewer decisions with timestamps."""

    def test_decisions_recorded_with_reviewer_and_timestamp(
        self, client, submitted_document
    ):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        response = client.get(f"/api/v1/documents/{doc_id}")
        data = response.json()
        cycle = data["review_cycles"][-1]
        reviewer_1 = next(
            a for a in cycle["assignments"] if a["reviewer_id"] == "reviewer-1"
        )
        assert reviewer_1["decision"] == "approved"
        assert reviewer_1["decided_at"] is not None

        reviewer_2 = next(
            a for a in cycle["assignments"] if a["reviewer_id"] == "reviewer-2"
        )
        assert reviewer_2["decision"] == "pending"
        assert reviewer_2["decided_at"] is None


class TestPreventDuplicateApproval:
    """Scenario: Prevent duplicate approval from same reviewer."""

    def test_duplicate_approval_rejected(self, client, submitted_document):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        assert response.status_code == 409
        assert "already submitted" in response.json()["detail"].lower()

    def test_reviewer_decisions_are_immutable(self, client, submitted_document):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        # Try to change decision
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Changed my mind.",
            },
        )
        assert response.status_code == 409
