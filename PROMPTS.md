# Implementation Prompt: Notification Rules Engine

## Context

You are implementing a REST API project from a PRD. The SpecLeft MCP may be installed and available. If mcp.json is installed - use it to drive the full workflow: generate a behavioural spec, produce tests from that spec, implement the code to pass those tests, and raise a pull request. Otherwise, follow the instructions below to achieve the same outcome without the MCP tooling. The PRD and SKILLS documents are available to reference for requirements and design guidance.

Do not ask clarifying questions. All requirements are defined in the PRD. Make reasonable engineering decisions where the PRD is silent.

---

## Prerequisites

- Python 3.12 environment available
- Git repository initialised with a `main` branch
- GitHub CLI (`gh`) available and authenticated

**If SpecLeft MCP is available:**
- Use SpecLeft MCP if the MCP config is setup in the project, otherwise follow your most suitable implementation workflow for this project that is not the SpecLeft process.
- you must follow its resources and CLI workflow pattern.
- If appropriate, update specleft prd-template.yml to exclude non feature headings from the spec generation.

---

## Resources

**Product Requirements Doc**: PRD.md

**Skill**: SKILLS.md

---

## Instructions

1. Derive a behavioural spec from the PRD
2. Produce tests from the spec before writing any implementation
3. Implement the API to pass all tests
4. Ensure all tests pass locally before proceeding
5. Commit the implementation to the current branch
6. Raise a pull request against `main` with a clear description of what was built and why

Do not modify the tests to make them pass. Fix the implementation instead.

### Retrospective

 1. Run server and verify behaviour in ../PRD.md.
 2. Confirm all behaviour from PRD are covered (if using SpecLeft MCP, run: `specleft status`)
 2. Once behaviour is confirmed as working - briefly summarise retrospectively on how the implementation went for this project:
- How many failed test runs before all tests pass
- Time spent on phases: spec externalisation, implementation, testing, behaviour verification
- Clarity of project scope on each phase (letter grade scoring): spec externalisation, implementation, testing, behaviour verification
- What went well with the workflow
- what was missed or inefficient with your workflow
- what would you do differently next time in terms of workflow or implementation approach
3. Publish this retro in to the comments of the created PR
