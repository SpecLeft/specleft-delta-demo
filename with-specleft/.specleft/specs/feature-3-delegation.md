# Feature 3: Delegation

Reviewers may delegate their review responsibility to a substitute with time-bound permissions.

## Assumptions

- A reviewer can only have one active delegation per document.
- Delegation does not transfer to other documents.
- Delegation is scoped to a specific document, not global.
- Expiry dates are UTC timestamps.
- A delegator must be an assigned reviewer on the document.
- Revocation is immediate and idempotent.

## Scenarios

### Scenario: Delegate review to substitute with expiry date
priority: high
- Given a reviewer assigned to a document
- When they delegate to a substitute with an expiry date
- Then the substitute is granted review permissions for that document
- And the delegation record includes the expiry timestamp

### Scenario: Substitute can approve on behalf of delegator
priority: high
- Given a valid delegation that has not expired
- When the substitute approves the document
- Then the approval is recorded as the substitute acting on behalf of the delegator
- And the delegator's review requirement is satisfied

### Scenario: Expired delegation is rejected
priority: high
- Given a delegation that has passed its expiry date
- When the substitute attempts to approve the document
- Then the approval is rejected
- And an error is returned indicating the delegation has expired

### Scenario: Delegator can revoke delegation before expiry
priority: high
- Given an active delegation
- When the delegator revokes the delegation
- Then the substitute loses review permissions immediately
- And subsequent actions by the substitute are rejected

### Scenario: Prevent delegation chain
priority: high
- Given a substitute who has been delegated review authority
- When the substitute attempts to delegate to another person
- Then the delegation is rejected
- And an error is returned indicating re-delegation is not permitted

### Scenario: One active delegation per reviewer per document
priority: high
- Given a reviewer with an existing active delegation for a document
- When they attempt to create another delegation for the same document
- Then the delegation is rejected
- And an error is returned indicating an active delegation already exists
