"""Tests for Feature 1: Document Lifecycle.

Tests the strict state machine: draft -> review -> approved/rejected
and enforcement of edit restrictions.
"""


class TestCreateDocument:
    """Scenario: Create document as draft."""

    def test_create_document_returns_draft_status(self, client):
        response = client.post(
            "/api/v1/documents",
            json={
                "title": "My Document",
                "content": "Document content here.",
                "author_id": "author-1",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "draft"
        assert data["author_id"] == "author-1"
        assert data["title"] == "My Document"

    def test_create_document_is_assigned_to_author(self, client):
        response = client.post(
            "/api/v1/documents",
            json={
                "title": "Another Doc",
                "content": "Content.",
                "author_id": "user-42",
            },
        )
        data = response.json()
        assert data["author_id"] == "user-42"

    def test_create_document_with_custom_escalation_config(self, client):
        response = client.post(
            "/api/v1/documents",
            json={
                "title": "Doc",
                "content": "Content.",
                "author_id": "author-1",
                "escalation_timeout_hours": 48,
                "max_escalation_depth": 5,
            },
        )
        data = response.json()
        assert data["escalation_timeout_hours"] == 48
        assert data["max_escalation_depth"] == 5


class TestSubmitForReview:
    """Scenario: Submit document for review."""

    def test_submit_changes_status_to_review(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "review"

    def test_submit_assigns_reviewers(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1", "reviewer-2"]},
        )
        data = response.json()
        assert len(data["review_cycles"]) == 1
        cycle = data["review_cycles"][0]
        reviewer_ids = [a["reviewer_id"] for a in cycle["assignments"]]
        assert "reviewer-1" in reviewer_ids
        assert "reviewer-2" in reviewer_ids

    def test_submit_creates_notifications_for_reviewers(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1", "reviewer-2"]},
        )
        # Check notifications for each reviewer
        for reviewer_id in ["reviewer-1", "reviewer-2"]:
            response = client.get(f"/api/v1/notifications?user_id={reviewer_id}")
            assert response.status_code == 200
            notifications = response.json()
            assert len(notifications) >= 1
            assert any("assigned to review" in n["message"] for n in notifications)


class TestApproveDocument:
    """Scenario: Approve document with single reviewer."""

    def test_single_reviewer_approve_changes_to_approved(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    def test_approval_recorded_with_timestamp(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        data = response.json()
        cycle = data["review_cycles"][-1]
        assignment = cycle["assignments"][0]
        assert assignment["decision"] == "approved"
        assert assignment["decided_at"] is not None


class TestRejectDocument:
    """Scenario: Reject document with reason."""

    def test_reject_changes_status_to_rejected(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Needs more detail.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

    def test_rejection_reason_is_recorded(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Incomplete analysis.",
            },
        )
        data = response.json()
        cycle = data["review_cycles"][-1]
        assignment = cycle["assignments"][0]
        assert assignment["reason"] == "Incomplete analysis."


class TestPreventEdits:
    """Scenarios: Prevent edits to approved and in-review documents."""

    def test_cannot_edit_approved_document(self, client, sample_document):
        doc_id = sample_document["id"]
        # Submit and approve
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        # Attempt edit
        response = client.patch(
            f"/api/v1/documents/{doc_id}?user_id=author-1",
            json={"title": "New Title"},
        )
        assert response.status_code == 409
        assert "locked" in response.json()["detail"].lower()

    def test_cannot_edit_document_under_review(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        response = client.patch(
            f"/api/v1/documents/{doc_id}?user_id=author-1",
            json={"title": "New Title"},
        )
        assert response.status_code == 409
        assert "under review" in response.json()["detail"].lower()

    def test_can_edit_draft_document(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.patch(
            f"/api/v1/documents/{doc_id}?user_id=author-1",
            json={"title": "Updated Title"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"


class TestInvalidTransitions:
    """Invalid state transitions return descriptive errors."""

    def test_cannot_submit_approved_document(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        assert response.status_code == 409

    def test_cannot_review_draft_document(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        assert response.status_code == 409

    def test_cannot_submit_document_already_in_review(self, client, sample_document):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-2"]},
        )
        assert response.status_code == 409
