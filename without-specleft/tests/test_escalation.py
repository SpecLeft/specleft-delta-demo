"""Tests for Feature 4: Escalation.

Tests auto-escalation trigger, notification to next-level approver,
escalation depth limits, and timeout reset.
"""

from datetime import datetime, timezone, timedelta


class TestTriggerEscalation:
    """Scenario: Escalation adds a next-level approver."""

    def test_escalate_adds_new_reviewer(self, client, submitted_document):
        doc_id = submitted_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "senior-reviewer-1"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["escalated_to_reviewer_id"] == "senior-reviewer-1"
        assert data["escalation_depth"] == 1

        # Verify reviewer was added to the cycle
        doc_resp = client.get(f"/api/v1/documents/{doc_id}")
        doc_data = doc_resp.json()
        cycle = doc_data["review_cycles"][-1]
        reviewer_ids = [a["reviewer_id"] for a in cycle["assignments"]]
        assert "senior-reviewer-1" in reviewer_ids

    def test_escalation_creates_notification(self, client, submitted_document):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "senior-reviewer-1"},
        )
        response = client.get(f"/api/v1/notifications?user_id=senior-reviewer-1")
        notifications = response.json()
        assert len(notifications) >= 1
        assert any("escalated" in n["message"].lower() for n in notifications)


class TestEscalationDepthLimit:
    """Scenario: Maximum escalation depth is enforced."""

    def test_max_depth_prevents_further_escalation(self, client):
        # Create a document with max depth 2
        doc_resp = client.post(
            "/api/v1/documents",
            json={
                "title": "Limited Doc",
                "content": "Content.",
                "author_id": "author-1",
                "max_escalation_depth": 2,
            },
        )
        doc_id = doc_resp.json()["id"]

        # Submit for review
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )

        # Escalation 1
        resp1 = client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "senior-1"},
        )
        assert resp1.status_code == 201
        assert resp1.json()["escalation_depth"] == 1

        # Escalation 2
        resp2 = client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "senior-2"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["escalation_depth"] == 2

        # Escalation 3 — should fail
        resp3 = client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "senior-3"},
        )
        assert resp3.status_code == 409
        assert "maximum escalation depth" in resp3.json()["detail"].lower()


class TestOriginalReviewerApproveBeforeEscalation:
    """Scenario: Original reviewer can still approve normally."""

    def test_original_reviewer_can_still_approve(self, client, submitted_document):
        doc_id = submitted_document["id"]

        # Escalate
        client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "senior-reviewer-1"},
        )

        # Original reviewers still approve
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-2", "decision": "approved"},
        )
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-3", "decision": "approved"},
        )

        # Senior reviewer also needs to approve (they were added to the cycle)
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "senior-reviewer-1", "decision": "approved"},
        )
        data = response.json()
        assert data["status"] == "approved"


class TestEscalationTimeout:
    """Scenario: Escalation resets timeout for new approver."""

    def test_escalation_has_new_timeout(self, client, submitted_document):
        doc_id = submitted_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "senior-reviewer-1"},
        )
        data = response.json()
        assert data["timeout_at"] is not None
        # The timeout should be in the future
        timeout = datetime.fromisoformat(data["timeout_at"])
        if timeout.tzinfo is None:
            timeout = timeout.replace(tzinfo=timezone.utc)
        assert timeout > datetime.now(timezone.utc)


class TestCannotEscalateToExistingReviewer:
    """Prevent escalation to someone already assigned."""

    def test_escalate_to_existing_reviewer_fails(self, client, submitted_document):
        doc_id = submitted_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "reviewer-1"},
        )
        assert response.status_code == 409
        assert "already assigned" in response.json()["detail"].lower()

    def test_cannot_escalate_to_author(self, client, submitted_document):
        doc_id = submitted_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/escalate",
            json={"escalated_to_reviewer_id": "author-1"},
        )
        assert response.status_code == 400
        assert "author" in response.json()["detail"].lower()
