# Feature 1: Document Lifecycle

Documents must follow a strict state machine through their approval process.

Valid states: draft -> review -> approved | rejected
Rejected documents can be resubmitted (see Feature 5).

## Assumptions

- A "user" is identified by a unique user_id string passed in the request (no auth system).
- Author permissions are implicit: the creator of a document is the author.
- "Notified" means a notification log entry is created (no email/push delivery per non-goals).
- State transitions are enforced at the service layer; invalid transitions return HTTP 409 Conflict.
- Documents have a title and body as content fields.
- All state transitions are atomic (single DB transaction).

## Scenarios

### Scenario: Create document as draft
priority: critical
- Given a user with author permissions
- When they create a new document
- Then the document is created with status "draft"
- And the document is assigned to the author

### Scenario: Submit document for review
priority: critical
- Given a document in "draft" status
- When the author submits it for review
- Then the document status changes to "review"
- And all assigned reviewers are notified

### Scenario: Approve document with single reviewer
priority: critical
- Given a document in "review" status with one assigned reviewer
- When the reviewer approves the document
- Then the document status changes to "approved"
- And the approval is recorded with a timestamp

### Scenario: Reject document with reason
priority: critical
- Given a document in "review" status
- When a reviewer rejects the document
- Then the document status changes to "rejected"
- And the rejection reason is recorded

### Scenario: Prevent edits to approved documents
priority: critical
- Given a document in "approved" status
- When any user attempts to edit the document
- Then the edit is rejected
- And an error is returned indicating the document is locked

### Scenario: Prevent edits to documents under review
priority: critical
- Given a document in "review" status
- When the author attempts to edit the document
- Then the edit is rejected
- And an error is returned indicating the document is under review

### Scenario: Invalid state transitions return errors
priority: critical
- Given a document in "approved" status
- When any user attempts to submit it for review
- Then the transition is rejected
- And a descriptive error is returned indicating the transition is not allowed
