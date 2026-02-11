# Feature 5: Edge Cases

---
confidence: medium
source: prd
assumptions:
  - Concurrent decisions are resolved deterministically by database transaction ordering.
  - Rejected documents keep previous review history.
tags:
  - edge-cases
  - workflow
component: api
---

## Scenarios

### Scenario: Concurrent approval and rejection by different reviewers
priority: medium
- Given a document in "review" status with multiple reviewers
- When one reviewer approves and another rejects simultaneously
- Then the rejection takes precedence
- And the document status changes to "rejected"

### Scenario: Submit document with no reviewers assigned returns error
priority: medium
- Given a document in "draft" status
- When the author submits the document with no reviewers assigned
- Then the submission is rejected
- And an error is returned indicating at least one reviewer is required

### Scenario: Reviewer who is also the author cannot approve own document
priority: medium
- Given a user who is both the author and an assigned reviewer
- When they attempt to approve the document
- Then the approval is rejected
- And an error is returned indicating self-approval is not permitted

### Scenario: Resubmit rejected document creates new review cycle
priority: medium
- Given a document in "rejected" status
- When the author resubmits the document
- Then the document status changes to "review"
- And a new review cycle is created with fresh reviewer assignments
- And previous review history is preserved

### Scenario: Notes
priority: medium
- Then conflict resolution rules are deterministic
- And all edge case handling returns descriptive error messages
