---
name: python-dev-best-practices
description: Apply Python and software engineering best practices when implementing a project. Use this skill whenever you are writing, structuring, or reviewing Python code — especially for REST APIs, backend services, or multi-feature projects. Trigger on any Python implementation task involving multiple components, layers, or features where design quality, testability, and maintainability matter.
---

# Python Software Development Best Practices

Apply the following principles whenever implementing a Python project.

---

## Project Structure

Organise code by responsibility, not by type. A flat `models.py` / `routes.py` / `utils.py` structure becomes unmaintainable. Prefer:

```
src/
  <domain>/
    models.py       # Data shapes
    repository.py   # Persistence logic
    service.py      # Business logic
    router.py       # HTTP layer (if FastAPI/Django)
    schemas.py      # Request/response validation
tests/
  <domain>/
    test_<feature>.py
```

One module per responsibility. If a file is doing more than one thing, split it.

---

## SOLID Principles

**Single Responsibility** — Each class or function has one reason to change. A route handler should not contain business logic or query construction.

**Open/Closed** — Extend behaviour without modifying existing code. Use abstract base classes or protocols for extensible components (e.g. dispatch channels, condition operators). Adding a new variant should require adding a new class, not editing a switch statement.

**Liskov Substitution** — Subtypes must be substitutable for their base types. Avoid overriding methods in ways that change their contract.

**Interface Segregation** — Depend on narrow interfaces. A service that only needs to read data should not depend on a full read/write repository.

**Dependency Inversion** — High-level modules depend on abstractions, not concrete implementations. Inject dependencies; do not instantiate them inside functions.

---

## DRY

- Extract repeated logic into named functions or classes immediately — do not wait until the third occurrence
- Shared validation belongs in one place (Pydantic validators, not scattered conditionals)
- Query patterns belong in a repository layer, not repeated across service methods

---

## Design Patterns to Apply

**Strategy** — For swappable behaviour (e.g. different channel dispatch types, different condition operators). Each variant implements a common interface; a registry or factory selects the right one.

**Repository** — Abstract all persistence behind a class with explicit methods (`get`, `create`, `delete`, etc.). Services call the repository; they never construct queries directly.

**Factory / Registry** — Use a dict-based registry to map string identifiers to classes. Avoids `if/elif` chains that violate Open/Closed.

```python
CHANNEL_REGISTRY: dict[str, type[BaseChannel]] = {
    "webhook": WebhookChannel,
    "email": EmailChannel,
    "log": LogChannel,
}
```

---

## Testing

- Write tests before or alongside implementation, not after
- Test behaviour, not implementation — assert on outcomes, not internal state
- One test file per feature domain, mirroring the source structure
- Use `pytest` fixtures for shared setup; avoid repetition in test bodies
- Mock at the boundary (I/O, HTTP, external services) — not deep inside business logic
- Each scenario in the spec maps to at least one test; edge cases and failure paths get their own tests

---

## FastAPI Specifics

- Define Pydantic schemas for all request and response bodies — never use raw dicts
- Keep routers thin: validate input, call a service, return output
- Use dependency injection (`Depends`) for database sessions, services, and auth
- Use `async def` for route handlers; use background tasks (`BackgroundTasks`) for fire-and-forget work
- Return appropriate HTTP status codes — do not default everything to `200`

---

## Code Readability

- Functions should fit on one screen; if they don't, break them up
- Name things after what they are, not how they work (`dispatch_to_channel`, not `do_thing`)
- Avoid comments that describe what the code does — write code that is self-describing
- Use type hints throughout; do not use `Any` unless genuinely unavoidable
- Prefer explicit over implicit — a reader should not need to trace three files to understand what a function does

---

## Error Handling

- Raise domain-specific exceptions from service and repository layers
- Catch and translate to HTTP errors at the router layer only
- Never swallow exceptions silently — log or re-raise
- Validate inputs at the boundary (Pydantic schemas); do not validate the same thing twice deeper in the stack