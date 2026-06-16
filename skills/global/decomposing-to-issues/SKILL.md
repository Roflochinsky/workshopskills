---
name: decomposing-to-issues
description: Use when breaking a spec or plan into tracker issues for execution — especially when different agents or sessions will pick the pieces up independently.
---

# Decomposing to Issues

## Overview

Tasks larger than one context window get abandoned mid-way; tasks split by horizontal layer ("all backend", then "all frontend") serialize everything and integrate nothing until the end. Decompose into **vertical slices** sized for one fresh-context agent each, with contracts frozen up front so slices run in parallel.

## Rules

1. **Epic carries the frozen contracts.** Schema, API shapes, naming — pinned in the epic description before child issues are written. Children build against the contract, not against each other's unmerged code. Contract changes happen by editing the epic and notifying dependents, never silently inside a child.
2. **Vertical slices, tracer bullet first.** Each issue delivers something testable end-to-end or a self-contained layer of one feature path — not "all models for everything". The first issue is the thin universal blocker (e.g. migration + model), kept deliberately tiny so it merges fast and unblocks parallel tracks.
3. **Sized for one fresh agent.** An issue a new agent can complete from the issue text + spec/plan paths alone, without the conversation. If describing it needs "and then... and also..." — split it.
4. **Verification command inside each issue.** Every issue states how to prove it done (`pytest path/...`, `npm test -- x`). "Done" without a named check isn't a definition of done.
5. **Real dependencies only** (`bd dep add child blocker`), so `bd ready` reflects true execution order and everything else runs in parallel. Don't chain issues out of habit.
6. **A separate final verification issue**, owned by a non-implementer agent: walk the whole flow against the spec, file discrepancies as new issues rather than fixing inline.

## Anti-patterns

| Smell | Fix |
|---|---|
| Issues named "Backend", "Frontend", "Tests" | Horizontal layers. Re-cut by feature path. |
| Child issues referencing each other's future code | Missing frozen contract in the epic. |
| One issue with 8 checkboxes | 8 issues wearing a trenchcoat. Split. |
| "Verify everything works" as a checklist item of the last feature issue | Verification by the implementer. Separate issue, separate agent. |
| Every issue depends on the previous one | Fake serialization. Wire only real blockers. |
