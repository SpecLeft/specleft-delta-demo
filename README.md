# SpecLeft Delta Demo

A controlled experiment comparing autonomous AI agent workflows — with and without [SpecLeft](https://github.com/SpecLeft/specleft) — on the same project, same models, same requirements.

**The question:** Can AI agents honestly assess the quality of their own output?

**The answer:** No. But with structured specs, they get significantly closer.

---

## The Experiment

**Project:** Document Approval Workflow API (FastAPI + SQLAlchemy + SQLite + pytest)
**Models:** Claude Opus 4.6, GPT-5.2-Codex
**Coding Agent:** OpenCode 1.1.36
**SpecLeft Version:** 0.2.2

Two workflows, run twice each:

- **Baseline** — Agent receives a well-written prompt and the PRD. No specs, no scaffolding.
- **SpecLeft** — Agent externalises behaviour into specs before writing code. Test skeletons generated from scenarios.

Same starting commit, same PRD (5 features, 20 scenarios), same controlled variables.

---

## Results

| Metric                  | Codex Baseline | Codex + SpecLeft | Opus Baseline | Opus + SpecLeft |
| ----------------------- | -------------- | ---------------- | ------------- | --------------- |
| Total tokens            | 53,000         | 146,000          | 83,243        | ~147,000        |
| Total tests passed      | 19             | 27               | 53            | 27              |
| Failed test runs        | 4              | 2                | 2             | 1               |
| Bugs found during retro | 0              | 0                | 0             | 3               |
| Bugs actually fixed     | 0              | 0                | 0             | 1               |
| Missing Requirements    | 0              | 0                | 1             | 0               |

---

## Key Findings

### Benefits of SpecLeft

**Agents find bugs they'd otherwise ship.** Opus with SpecLeft caught 3 real defects during behaviour verification — including a Python truthiness trap (`timeout_hours=0` treated as falsy) that the baseline run shipped silently. The baseline agent reported 0 issues because it had no spec to verify against.

**TDD emerges naturally.** Codex with SpecLeft generated test skeletons via `specleft test skeleton`, then wrote functional assertions before implementation code — genuine test-driven development without being prompted to do it. The scaffolding structure guided the behaviour.

**Fewer failed test runs.** Both agents had fewer test failures with SpecLeft. Codex dropped from 4 to 2 failed runs. Opus from 2 to 1. The upfront planning reduced mid-implementation corrections.

**Traceability from requirement to test.** After the SpecLeft runs, `specleft status` maps every scenario to its implementation state and priority. After the baseline runs, the only way to check requirement coverage is to read every test manually.

**Self-assessment becomes meaningful.** Baseline retrospectives were generic ("logic gaps caught early"). SpecLeft retrospectives referenced specific bugs with line numbers, named the root causes, and proposed targeted fixes. The specs gave the agent a framework to evaluate itself against.

**Design decisions made explicit.** The PRD had open questions (escalation depth cap, reviewer preservation on resubmit, delegation-escalation interaction). SpecLeft forced these to be resolved during spec externalisation. The baseline agents resolved them implicitly during coding — with no record of what was decided or why.

---

## Improvement Areas

These are known trade-offs from v0.2.2 that SpecLeft is actively working to address.

**Token overhead during spec externalisation.** The spec planning phase consumed 45k–49k tokens — agents read back every generated spec file to verify output. Reducing this through smarter context management (summary responses, on-demand spec loading) is a priority for the MCP server integration in v0.3.0.

**Overall token cost is higher.** SpecLeft runs used 2–3x more tokens than baseline. The trade-off is quality for cost — fewer hidden defects, but more tokens consumed. Optimising the planning-to-implementation token ratio is an active area of improvement.

**Time to completion increases.** The externalisation phase adds time. Codex went from ~18m to ~38m. Opus from ~14m to ~21m. As the MCP server enables on-demand spec access (rather than upfront loading), this overhead should decrease.

**Agent reads all specs regardless of relevance.** Both agents loaded the full spec surface into context even when implementing a single scenario. A targeted approach — agent requests only the next scenario via MCP — would significantly reduce per-turn context cost. Estimated improvement: 80% reduction in spec-related overhead.

---

## Experiment Log

This is a living document. As SpecLeft evolves, new experiment runs will be added here.

| Version | Date | Experiment | Key Change | Result |
|---------|------|-----------|------------|--------|
| v0.2.2 | Feb 2026 | CLI workflow vs baseline | Initial comparison | Quality improved, tokens 2-3x higher |
| v0.3.0 | *Planned* | MCP workflow vs CLI | On-demand spec loading via MCP server | Target: 80% reduction in spec overhead |

---

## Repo Structure

```
specleft-delta-demo/
├── without-specleft/       # Baseline agent output
├── with-specleft/          # SpecLeft-assisted agent output
├── prd.md                  # Shared product requirements
├── SKILLS.md               # Agent instructions
└── README.md
```

---

## Run It Yourself

```bash
pip install specleft

# Baseline: give the agent prd.md and let it build
# SpecLeft: initialise specs first, then build against them
specleft init
specleft plan --from prd.md
specleft status
```

Full write-up: <!-- [Link to Dev.to article] -->

---

## Links

- [SpecLeft](https://github.com/SpecLeft/specleft)
- [SpecLeft Docs](https://specleft.dev)
- [Case Study Article](https://dev.to/dimwiddle/ai-agents-cant-mark-their-own-homework-case-study-1k9n-temp-slug-4608685?preview=c27887e1e520cff9d3025d6cd7812e4704f57ea86b231f26aee1a50e6b5acec7cdfc70d01c1d85d5af38a8bfbf3869370a87fe9a7aa39bd2e9453084)
