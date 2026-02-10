# Product Requirements Document

## Overview

A multi-step document approval workflow API built with FastAPI and SQLAlchemy. Documents move through defined states, support multiple reviewers, time-bound delegation, and automatic escalation. Designed to demonstrate spec-driven development with AI coding agents.

The initial goal is to support core approval flows with enforcement of business rules around state transitions, delegation, and escalation.

Tech Stack: UV, Python 3.12.5 + FastAPI + SQLAlchemy + SQLite + pytest

---

## Feature 1: Document Lifecycle

Documents must follow a strict state machine through their approval process.

### Scenario: Create document as draft

- Given a user with author permissions
- When they create a new document
- Then the document is created with status "draft"
- And the document is assigned to the author

### Scenario: Submit document for review

- Given a document in "draft" status
- When the author submits it for review
- Then the document status changes to "review"
- And all assigned reviewers are notified

### Scenario: Approve document with single reviewer

- Given a document in "review" status with one assigned reviewer
- When the reviewer approves the document
- Then the document status changes to "approved"
- And the approval is recorded with a timestamp

### Scenario: Reject document with reason

- Given a document in "review" status
- When a reviewer rejects the document
- Then the document status changes to "rejected"
- And the rejection reason is recorded

### Scenario: Prevent edits to approved documents

- Given a document in "approved" status
- When any user attempts to edit the document
- Then the edit is rejected
- And an error is returned indicating the document is locked

### Scenario: Prevent edits to documents under review

- Given a document in "review" status
- When the author attempts to edit the document
- Then the edit is rejected
- And an error is returned indicating the document is under review

### Notes

- Priority: critical
- All state transitions must be atomic
- Invalid transitions should return descriptive errors

---

## Feature 2: Multi-Reviewer Approval

Documents may require approval from multiple reviewers before being considered approved.

### Scenario: Require all assigned reviewers to approve

- Given a document in "review" status with three assigned reviewers
- When only two reviewers have approved
- Then the document remains in "review" status
- And the pending reviewer is visible in the status response

### Scenario: Reject if any reviewer rejects

- Given a document in "review" status with multiple reviewers
- When one reviewer rejects the document
- Then the document status changes to "rejected"
- And remaining reviewers are no longer required to act

### Scenario: Track individual reviewer decisions with timestamps

- Given a document in "review" status
- When a reviewer submits their decision
- Then the decision is recorded with the reviewer ID and timestamp
- And the decision is visible in the document review history

### Scenario: Prevent duplicate approval from same reviewer

- Given a reviewer who has already approved a document
- When they attempt to approve the same document again
- Then the request is rejected
- And an error is returned indicating they have already submitted a decision

### Notes

- Priority: critical
- Reviewer decisions are immutable once submitted
- The order of reviewer approvals does not matter

---

## Feature 3: Delegation

Reviewers may delegate their review responsibility to a substitute with time-bound permissions.

### Scenario: Delegate review to substitute with expiry date

- Given a reviewer assigned to a document
- When they delegate to a substitute with an expiry date
- Then the substitute is granted review permissions for that document
- And the delegation record includes the expiry timestamp

### Scenario: Substitute can approve on behalf of delegator

- Given a valid delegation that has not expired
- When the substitute approves the document
- Then the approval is recorded as the substitute acting on behalf of the delegator
- And the delegator's review requirement is satisfied

### Scenario: Expired delegation is rejected

- Given a delegation that has passed its expiry date
- When the substitute attempts to approve the document
- Then the approval is rejected
- And an error is returned indicating the delegation has expired

### Scenario: Delegator can revoke delegation before expiry

- Given an active delegation
- When the delegator revokes the delegation
- Then the substitute loses review permissions immediately
- And subsequent actions by the substitute are rejected

### Scenario: Prevent delegation chain

- Given a substitute who has been delegated review authority
- When the substitute attempts to delegate to another person
- Then the delegation is rejected
- And an error is returned indicating re-delegation is not permitted

### Notes

- Priority: high
- A reviewer can only have one active delegation per document
- Delegation does not transfer to other documents

---

## Feature 4: Escalation

Documents that remain in review without action should automatically escalate to a higher-level approver.

### Scenario: Auto-escalate after configurable timeout

- Given a document in "review" status
- When the configured timeout period elapses without all reviewers acting
- Then the document is escalated to the next-level approver
- And the escalation is recorded with a timestamp

### Scenario: Escalation notifies next-level approver

- Given a document that has been escalated
- When the escalation is triggered
- Then the next-level approver is added to the reviewer list
- And a notification is generated for the new approver

### Scenario: Original reviewer can still approve before escalation triggers

- Given a document approaching the escalation timeout
- When the original reviewer submits their decision before the timeout
- Then the escalation is cancelled
- And the document proceeds through normal approval flow

### Scenario: Escalation resets timeout for new approver

- Given a document that has been escalated to a new approver
- When the escalation is processed
- Then a new timeout period begins for the escalated approver
- And the original timeout is no longer active

### Notes

- Priority: high
- Escalation timeout is configurable per document or per organisation
- Maximum escalation depth should be enforced to prevent infinite chains

---

## Feature 5: Edge Cases

Boundary conditions and conflict resolution for the approval workflow.

### Scenario: Concurrent approval and rejection by different reviewers

- Given a document in "review" status with multiple reviewers
- When one reviewer approves and another rejects simultaneously
- Then the rejection takes precedence
- And the document status changes to "rejected"

### Scenario: Submit document with no reviewers assigned returns error

- Given a document in "draft" status
- When the author submits the document with no reviewers assigned
- Then the submission is rejected
- And an error is returned indicating at least one reviewer is required

### Scenario: Reviewer who is also the author cannot approve own document

- Given a user who is both the author and an assigned reviewer
- When they attempt to approve the document
- Then the approval is rejected
- And an error is returned indicating self-approval is not permitted

### Scenario: Resubmit rejected document creates new review cycle

- Given a document in "rejected" status
- When the author resubmits the document
- Then the document status changes to "review"
- And a new review cycle is created with fresh reviewer assignments
- And previous review history is preserved

### Notes

- Priority: medium
- Conflict resolution rules should be deterministic
- All edge case handling should return descriptive error messages

---

## Non-Goals

- User interface or frontend
- Email or push notification delivery (log-only)
- Role-based access control beyond author/reviewer
- Document versioning or diff tracking
- File attachment handling

---

## Open Questions

- Should escalation depth be unlimited or capped?
- Should rejected documents preserve the same reviewers on resubmission?
- How should delegation interact with escalation — can an escalated reviewer delegate?
