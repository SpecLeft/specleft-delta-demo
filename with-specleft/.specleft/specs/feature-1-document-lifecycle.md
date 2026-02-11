# Feature 1: Document Lifecycle

---
confidence: medium
source: prd
assumptions:
  - System uses REST-style HTTP endpoints.
  - Users are represented by UUIDs passed in requests (no auth system).
  - Notifications are recorded in a log table, not delivered externally.
tags:
  - documents
  - workflow
component: api
---

## Scenarios

### Scenario: Create document as draft
priority: medium
- Given a user with author permissions
- When they create a new document
- Then the document is created with status "draft"
- And the document is assigned to the author

### Scenario: Submit document for review
priority: medium
- Given a document in "draft" status
- When the author submits it for review
- Then the document status changes to "review"
- And all assigned reviewers are notified

### Scenario: Approve document with single reviewer
priority: medium
- Given a document in "review" status with one assigned reviewer
- When the reviewer approves the document
- Then the document status changes to "approved"
- And the approval is recorded with a timestamp

### Scenario: Reject document with reason
priority: medium
- Given a document in "review" status
- When a reviewer rejects the document
- Then the document status changes to "rejected"
- And the rejection reason is recorded

### Scenario: Prevent edits to approved documents
priority: medium
- Given a document in "approved" status
- When any user attempts to edit the document
- Then the edit is rejected
- And an error is returned indicating the document is locked

### Scenario: Prevent edits to documents under review
priority: medium
- Given a document in "review" status
- When the author attempts to edit the document
- Then the edit is rejected
- And an error is returned indicating the document is under review

### Scenario: Notes
priority: critical
- Then all state transitions are atomic
- And invalid transitions return descriptive error messages
