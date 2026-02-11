# Feature 3: Delegation

---
confidence: medium
source: prd
assumptions:
  - Delegation applies per document only.
  - A reviewer can have at most one active delegation per document.
tags:
  - delegation
  - workflow
component: api
---

## Scenarios

### Scenario: Delegate review to substitute with expiry date
priority: medium
- Given a reviewer assigned to a document
- When they delegate to a substitute with an expiry date
- Then the substitute is granted review permissions for that document
- And the delegation record includes the expiry timestamp

### Scenario: Substitute can approve on behalf of delegator
priority: medium
- Given a valid delegation that has not expired
- When the substitute approves the document
- Then the approval is recorded as the substitute acting on behalf of the delegator
- And the delegator's review requirement is satisfied

### Scenario: Expired delegation is rejected
priority: medium
- Given a delegation that has passed its expiry date
- When the substitute attempts to approve the document
- Then the approval is rejected
- And an error is returned indicating the delegation has expired

### Scenario: Delegator can revoke delegation before expiry
priority: medium
- Given an active delegation
- When the delegator revokes the delegation
- Then the substitute loses review permissions immediately
- And subsequent actions by the substitute are rejected

### Scenario: Prevent delegation chain
priority: medium
- Given a substitute who has been delegated review authority
- When the substitute attempts to delegate to another person
- Then the delegation is rejected
- And an error is returned indicating re-delegation is not permitted

### Scenario: Notes
priority: high
- Then delegation does not transfer to other documents
- And a reviewer can only have one active delegation per document
