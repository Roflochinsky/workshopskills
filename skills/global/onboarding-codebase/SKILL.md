---
name: onboarding-codebase
description: Use when working in a repository for the first time, or in an unfamiliar area of a large repo — before making any edit, especially when the task "should be quick".
---

# Onboarding to a Codebase

## Overview

The classic first-session failure: a locally-plausible edit that violates conventions you never surveyed — logic in the wrong layer, a hand-rolled duplicate of an existing utility, a pattern the repo deliberately avoids. Ten minutes of recon before the first edit is what separates "quick" from "quick and silently wrong".

## Recon before the first edit (~10 minutes, read-only)

1. **Orientation**: README, CLAUDE.md/AGENTS.md (if present — follow them and skip what they already answer), top-level layout, build files (Makefile/package.json/go.mod...) for the real commands: build, test, lint, run.
2. **The task's neighborhood**: find the code nearest to what you're asked to build (`grep` for the domain words). Read one complete example of the pattern you're about to imitate — a full handler/component/module, not a snippet. Note: layering (who calls whom), error handling style, test style and location.
3. **The data**: if the task touches data, read the actual schema/models — not the user's description of them. Nullable fields, join tables, and naming surprises live here; this is where "the data's all there" turns out to mean a three-way join.
4. **Baseline**: run the test suite once BEFORE changing anything. A pre-existing red suite discovered after your edits becomes your fault.

## While working

- **Imitate, don't innovate**: copy the repo's existing pattern even where you'd personally do it differently. An existing similar feature (an export button, a list endpoint) is your template — extend the pattern, don't invent a parallel one.
- **State assumptions in one message** when recon surfaced design decisions the user didn't specify (NULL handling, aggregation level, naming). Proceed unless contradicted — don't stall, don't guess silently.
- **No new dependencies or abstractions** in your first sessions in a repo unless the task demands it.

## Close the loop

If the repo had no CLAUDE.md: offer to record what you learned (run commands, layering, conventions, footguns) as one — the `init` skill or a short hand-written file. Your recon is exactly the onboarding the next agent will otherwise redo from scratch. If CLAUDE.md existed but was wrong/stale, report the mismatch (codifying-learnings).

## Red flags

| Thought | Reality |
|---|---|
| "Should be quick, I'll just add the endpoint" | Quick tasks hide schema wrinkles. Recon catches them in minutes; production catches them in weeks. |
| "I'll figure out conventions as I go" | "As you go" = after the reviewer rejects the diff. |
| "This repo surely has no helper for X" | Grep first. Duplicating an existing utility is the #1 onboarding diff smell. |
| "Tests are probably green on main" | Run them. Baselines are free; blame-untangling isn't. |
