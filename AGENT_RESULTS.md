## Who Won the Experiment?

As this experiment is agent-focused: I've requested feedback from a few neutral agents to evaluate the codebases on quality, maintainability, and correctness.

Here's the summary of their assessments:

### Gemini-3  

```markdown

If I had to pick one codebase to inherit and maintain, it would be **Claude Opus with SpecLeft**.

While the baseline runs produced working code, the difference in "production readiness" is stark:

1. **Code Quality:** The Opus + SpecLeft codebase uses a clean Service Pattern, explicit Pydantic schemas that map correctly to ORM models (using `from_attributes=True`), and modern timezone handling (`datetime.now(timezone.utc)`). The Codex baseline, by comparison, triggered 175 deprecation warnings during testing due to outdated datetime usage.

2. **Traceability:** Every test in the SpecLeft version maps to a specific, human-readable scenario in the specs. I know *why* the code exists. The Opus baseline generated 53 tests—more than double the SpecLeft run—but they were a "black box" of whatever the agent felt like verifying at the time.

3. **Architecture:** The SpecLeft version correctly exposed business logic (like `review_cycle`) as robust model properties, whereas the baseline implementations relied on implicit behavior that was harder to verify and prone to the bugs described earlier.

The baseline gets you a prototype. The SpecLeft workflow gets you a product.
  

```

### Kimi K2.5

```markdown

If I had to pick one codebase to inherit and maintain, it would be **GPT-Codex with SpecLeft**.

While both SpecLeft-assisted runs produced functional code, the architectural decisions in the Codex version demonstrate superior engineering judgment:  

1. **Data Model Architecture:** The Codex version uses a normalized relational design with separate `ReviewCycle`, `ReviewerAssignment`, and `ReviewDecision` entities. This properly separates concerns and supports complex workflows like concurrent reviews across cycles. The Opus version flattens everything onto the `Document` model, creating implicit dependencies that will complicate future enhancements.


2. **Code Organization:** Codex's service layer uses focused helper functions (`_ensure_reviewer_assignment`, `_ensure_no_decision`, `_resolve_actor`) that make business logic explicit and testable. The code reads like a specification. Opus interleaves logic inline with redundant validation blocks scattered throughout.
  

3. **Error Handling:** Codex implements a structured `ApiError` class with status codes, error codes, messages, and metadata—essential for API consumers to programmatically handle failures. Opus's basic `ServiceError` lacks the richness needed for production APIs.

4. **SQLAlchemy Patterns:** Codex uses modern 2.0 syntax with `Mapped` types and explicit relationships. Opus uses legacy 1.x `Column` declarations that are deprecated.


The Codex version has deprecation warnings (easily fixed). The Opus version has a logic bug in decision counting that could incorrectly approve documents. One requires a one-line fix; the other requires refactoring core business logic.

The SpecLeft workflow elevated both agents above their baselines. But Codex + SpecLeft delivers maintainable architecture; Opus + SpecLeft delivers working code with structural debt.

```

### Grok

  
```markdown
f I had to pick one codebase to inherit and maintain as the most production-ready, it would be **GPT-Codex with SpecLeft**.

From a CTO perspective prioritizing scalability, maintainability, and correctness for enterprise use:

1. **Superior Architecture**: Normalized data model with dedicated entities for ReviewCycle, ReviewerAssignment, and ReviewDecision provides clean separation of concerns and supports complex concurrent workflows without implicit dependencies.


2. **Better Error Handling and API Design**: Structured ApiError class with rich metadata (status codes, error codes, messages) enables robust client-side error handling, essential for production APIs.

3. **Modern SQLAlchemy Patterns**: Uses 2.0 syntax with Mapped types and explicit relationships, avoiding deprecations and ensuring long-term compatibility.

4. **Code Quality and Testability**: Focused helper functions make business logic explicit and unit-testable, reading like executable specifications. The TDD approach naturally enforced by SpecLeft skeletons resulted in high-quality, scenario-mapped tests.


While both SpecLeft implementations are superior to baselines, Codex + SpecLeft offers the best balance of correctness and extensibility. The logic bugs in Opus + SpecLeft (e.g., decision counting) pose higher risks for approval workflows, whereas Codex's deprecation warnings are easily fixed. For a document approval system requiring production deployment, Codex + SpecLeft minimizes technical debt and future refactoring needs.
```
