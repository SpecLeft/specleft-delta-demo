# Feature 2: Multi-Reviewer Approval

---
confidence: medium
source: prd
assumptions:
  - Review decisions are immutable once recorded.
  - Decision timestamps use UTC.
tags:
  - reviews
  - workflow
component: api
---

## Scenarios

### Scenario: Require all assigned reviewers to approve
priority: medium
- Given a document in "review" status with three assigned reviewers
- When only two reviewers have approved
- Then the document remains in "review" status
- And the pending reviewer is visible in the status response

### Scenario: Reject if any reviewer rejects
priority: medium
- Given a document in "review" status with multiple reviewers
- When one reviewer rejects the document
- Then the document status changes to "rejected"
- And remaining reviewers are no longer required to act

### Scenario: Track individual reviewer decisions with timestamps
priority: medium
- Given a document in "review" status
- When a reviewer submits their decision
- Then the decision is recorded with the reviewer ID and timestamp
- And the decision is visible in the document review history

### Scenario: Prevent duplicate approval from same reviewer
priority: medium
- Given a reviewer who has already approved a document
- When they attempt to approve the same document again
- Then the request is rejected
- And an error is returned indicating they have already submitted a decision

### Scenario: Notes
priority: critical
- Then reviewer decisions are immutable once submitted
- And approval order does not matter
