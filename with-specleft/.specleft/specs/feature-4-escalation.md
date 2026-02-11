# Feature 4: Escalation

Documents that remain in review without action should automatically escalate to a higher-level approver.

## Assumptions

- Escalation timeout is configurable per document (defaults to a system-wide setting).
- Maximum escalation depth is capped at 3 to prevent infinite chains.
- Escalation is triggered by a check/process endpoint (not a background worker) for testability.
- The "next-level approver" is specified at escalation configuration time.
- Escalated reviewers can also delegate (they are treated as regular reviewers).
- Notification is a log entry (per non-goals).

## Open Question Resolutions

- Escalation depth: capped at 3 levels maximum.
- Escalated reviewers CAN delegate (they are full reviewers once assigned).

## Scenarios

### Scenario: Auto-escalate after configurable timeout
priority: high
- Given a document in "review" status
- When the configured timeout period elapses without all reviewers acting
- Then the document is escalated to the next-level approver
- And the escalation is recorded with a timestamp

### Scenario: Escalation notifies next-level approver
priority: high
- Given a document that has been escalated
- When the escalation is triggered
- Then the next-level approver is added to the reviewer list
- And a notification is generated for the new approver

### Scenario: Original reviewer can still approve before escalation triggers
priority: high
- Given a document approaching the escalation timeout
- When the original reviewer submits their decision before the timeout
- Then the escalation is cancelled
- And the document proceeds through normal approval flow

### Scenario: Escalation resets timeout for new approver
priority: high
- Given a document that has been escalated to a new approver
- When the escalation is processed
- Then a new timeout period begins for the escalated approver
- And the original timeout is no longer active

### Scenario: Maximum escalation depth is enforced
priority: high
- Given a document that has already been escalated to the maximum depth
- When the escalation timeout elapses again
- Then no further escalation occurs
- And an error or warning is logged indicating max depth reached
