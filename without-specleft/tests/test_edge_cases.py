"""Tests for Feature 5: Edge Cases.

Tests concurrent approval/rejection, no-reviewer submission,
self-approval prevention, and rejected document resubmission.
"""


class TestConcurrentApprovalAndRejection:
    """Scenario: Concurrent approval and rejection — rejection takes precedence."""

    def test_rejection_takes_precedence(self, client, submitted_document):
        doc_id = submitted_document["id"]
        # reviewer-1 approves
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "approved"},
        )
        # reviewer-2 rejects (simulating concurrent action)
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-2",
                "decision": "rejected",
                "reason": "Issues found.",
            },
        )
        data = response.json()
        assert data["status"] == "rejected"

    def test_after_rejection_remaining_reviewers_cannot_act(
        self, client, submitted_document
    ):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-1", "decision": "rejected", "reason": "No."},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-2", "decision": "approved"},
        )
        assert response.status_code == 409


class TestNoReviewersAssigned:
    """Scenario: Submit document with no reviewers returns error."""

    def test_submit_with_empty_reviewers_fails(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": []},
        )
        assert response.status_code == 422

    def test_submit_with_no_reviewer_field_fails(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={},
        )
        assert response.status_code == 422


class TestSelfApprovalPrevention:
    """Scenario: Author cannot approve own document."""

    def test_author_cannot_be_reviewer(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["author-1"]},
        )
        assert response.status_code == 400
        assert "author cannot be assigned" in response.json()["detail"].lower()

    def test_author_cannot_approve_own_document_at_review_time(
        self, client, sample_document
    ):
        doc_id = sample_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "author-1", "decision": "approved"},
        )
        assert response.status_code == 403
        assert "self-approval" in response.json()["detail"].lower()


class TestResubmitRejectedDocument:
    """Scenario: Resubmit rejected document creates new review cycle."""

    def test_resubmit_creates_new_cycle(self, client, submitted_document):
        doc_id = submitted_document["id"]
        # Reject
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Nope.",
            },
        )

        # Resubmit
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-4", "reviewer-5"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "review"
        assert len(data["review_cycles"]) == 2
        assert data["review_cycles"][-1]["cycle_number"] == 2

    def test_previous_review_history_preserved(self, client, submitted_document):
        doc_id = submitted_document["id"]
        # Reject
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Nope.",
            },
        )
        # Resubmit
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-4"]},
        )

        # Check history preserved
        response = client.get(f"/api/v1/documents/{doc_id}")
        data = response.json()
        assert len(data["review_cycles"]) == 2
        # First cycle should still have the rejection
        first_cycle = data["review_cycles"][0]
        rejected_assignment = next(
            (a for a in first_cycle["assignments"] if a["decision"] == "rejected"), None
        )
        assert rejected_assignment is not None
        assert rejected_assignment["reason"] == "Nope."

    def test_resubmit_with_fresh_reviewers(self, client, submitted_document):
        doc_id = submitted_document["id"]
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Bad.",
            },
        )
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-4"]},
        )
        data = response.json()
        new_cycle = data["review_cycles"][-1]
        assert len(new_cycle["assignments"]) == 1
        assert new_cycle["assignments"][0]["reviewer_id"] == "reviewer-4"
        assert new_cycle["assignments"][0]["decision"] == "pending"

    def test_full_resubmit_and_approve_flow(self, client, submitted_document):
        doc_id = submitted_document["id"]
        # Reject
        client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "reviewer_id": "reviewer-1",
                "decision": "rejected",
                "reason": "Bad.",
            },
        )
        # Resubmit
        client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=author-1",
            json={"reviewer_ids": ["reviewer-4"]},
        )
        # Approve in new cycle
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "reviewer-4", "decision": "approved"},
        )
        data = response.json()
        assert data["status"] == "approved"


class TestUnauthorizedReviewer:
    """Unassigned users cannot review."""

    def test_unassigned_reviewer_cannot_review(self, client, submitted_document):
        doc_id = submitted_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"reviewer_id": "random-user", "decision": "approved"},
        )
        assert response.status_code == 403
        assert "not an assigned reviewer" in response.json()["detail"].lower()


class TestOnlyAuthorCanSubmit:
    """Only the author can submit/edit."""

    def test_non_author_cannot_submit(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.post(
            f"/api/v1/documents/{doc_id}/submit?user_id=not-the-author",
            json={"reviewer_ids": ["reviewer-1"]},
        )
        assert response.status_code == 403

    def test_non_author_cannot_edit(self, client, sample_document):
        doc_id = sample_document["id"]
        response = client.patch(
            f"/api/v1/documents/{doc_id}?user_id=not-the-author",
            json={"title": "Hacked Title"},
        )
        assert response.status_code == 403
