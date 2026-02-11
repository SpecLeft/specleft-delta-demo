# Feature 2: Multi-Reviewer Approval

Documents may require approval from multiple reviewers before being considered approved.

## Assumptions

- Reviewers are assigned to a document before or during submission for review.
- All assigned reviewers must approve for the document to become "approved".
- A single rejection from any reviewer immediately moves the document to "rejected".
- Reviewer decisions are immutable once submitted — no changing from approve to reject.
- The order of reviewer approvals does not matter.
- Reviewer assignment uses user_id strings.

## Scenarios

### Scenario: Require all assigned reviewers to approve
priority: critical
- Given a document in "review" status with three assigned reviewers
- When only two reviewers have approved
- Then the document remains in "review" status
- And the pending reviewer is visible in the status response

### Scenario: Reject if any reviewer rejects
priority: critical
- Given a document in "review" status with multiple reviewers
- When one reviewer rejects the document
- Then the document status changes to "rejected"
- And remaining reviewers are no longer required to act

### Scenario: Track individual reviewer decisions with timestamps
priority: critical
- Given a document in "review" status
- When a reviewer submits their decision
- Then the decision is recorded with the reviewer ID and timestamp
- And the decision is visible in the document review history

### Scenario: Prevent duplicate approval from same reviewer
priority: critical
- Given a reviewer who has already approved a document
- When they attempt to approve the same document again
- Then the request is rejected
- And an error is returned indicating they have already submitted a decision

### Scenario: Reviewer decisions are immutable
priority: high
- Given a reviewer who has already approved a document
- When they attempt to reject the same document
- Then the request is rejected
- And an error is returned indicating their decision cannot be changed
