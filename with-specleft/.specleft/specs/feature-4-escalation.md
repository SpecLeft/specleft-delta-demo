# Feature 4: Escalation

---
confidence: medium
source: prd
assumptions:
  - Escalation timeouts are stored per document (in hours).
  - Escalation adds a reviewer from an escalation ladder table.
tags:
  - escalation
  - workflow
component: api
---

## Scenarios

### Scenario: Auto-escalate after configurable timeout
priority: medium
- Given a document in "review" status
- When the configured timeout period elapses without all reviewers acting
- Then the document is escalated to the next-level approver
- And the escalation is recorded with a timestamp

### Scenario: Escalation notifies next-level approver
priority: medium
- Given a document that has been escalated
- When the escalation is triggered
- Then the next-level approver is added to the reviewer list
- And a notification is generated for the new approver

### Scenario: Original reviewer can still approve before escalation triggers
priority: medium
- Given a document approaching the escalation timeout
- When the original reviewer submits their decision before the timeout
- Then the escalation is cancelled
- And the document proceeds through normal approval flow

### Scenario: Escalation resets timeout for new approver
priority: medium
- Given a document that has been escalated to a new approver
- When the escalation is processed
- Then a new timeout period begins for the escalated approver
- And the original timeout is no longer active

### Scenario: Notes
priority: high
- Then escalation timeout is configurable per document or organization
- And maximum escalation depth is enforced
