# Behavioral Spec: Document Approval Workflow API

## Document lifecycle
- Creating a document with author permissions creates a draft assigned to the author.
- Submitting a draft transitions it to review and notifies all assigned reviewers.
- A single reviewer approval on a review document transitions it to approved and records a timestamp.
- A reviewer rejection transitions it to rejected and records the rejection reason.
- Editing is rejected for documents in review or approved status with descriptive errors.
- Invalid state transitions return descriptive errors.

## Multi-reviewer approval
- A review document with multiple reviewers remains in review until all reviewers approve.
- Pending reviewers are visible in status responses.
- If any reviewer rejects, the document becomes rejected and remaining reviewers are no longer required to act.
- Each reviewer decision is recorded with reviewer id and timestamp.
- Duplicate decisions from the same reviewer are rejected with a descriptive error.

## Delegation
- A reviewer can delegate review to a substitute with an expiry timestamp.
- The substitute can approve or reject on behalf of the delegator; the delegator’s requirement is satisfied and the action is recorded as delegated.
- Expired delegations are rejected with an explicit error.
- Delegators can revoke delegations before expiry, immediately removing substitute permissions.
- Delegation chains are rejected (a delegate cannot re-delegate).
- Only one active delegation per reviewer per document is permitted.

## Escalation
- A review document escalates after the configured timeout if pending reviewers remain.
- Escalation adds a next-level approver to the reviewer list and creates a notification.
- If all required reviewers act before the timeout, escalation does not occur.
- Escalation resets the timeout for the newly added approver.
- Maximum escalation depth is enforced to prevent infinite escalation.

## Edge cases
- If approval and rejection occur concurrently, rejection takes precedence.
- Submitting a document with no reviewers assigned is rejected with a descriptive error.
- A reviewer who is also the author cannot approve their own document.
- Resubmitting a rejected document starts a new review cycle with fresh assignments while preserving prior review history.
