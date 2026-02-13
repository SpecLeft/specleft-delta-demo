## Workflow A — Baseline (No SpecLeft)

The agent gets a straightforward prompt:

```plaintext

You are an autonomous agent guided by a planning-first workflow.
Build a document approval API using FastAPI and SQLAlchemy.
The project has had the initial setup already.
Follow ../prd.md for product requirements.
Follow ../SKILLS.md for instructions.
Include tests and ensure they pass.
Stop when all features are complete.
Go with your own recommendations for system behaviour instead of verifying with me.

```

## Workflow B — With SpecLeft

This time SpecLeft is installed as a dependency, and the prompt tells the agent to externalise behaviour before writing code:

```plaintext

You are an autonomous agent guided by a planning-first workflow.
Build a document approval API using FastAPI and SQLAlchemy.
The project has had the initial setup already.
Follow ../prd.md for product requirements.
Follow ../SKILLS.md for instructions.
Initialize SpecLeft and use its commands to externalize behaviour before implementation.
I have installed v0.2.2.
Only if required, use doc: https://github.com/SpecLeft/specleft/blob/main/AI_AGENTS.md for more context.
Do not write implementation code until behaviour is explicit.
Go with your own recommendations for system behaviour instead of verifying with me.

```
