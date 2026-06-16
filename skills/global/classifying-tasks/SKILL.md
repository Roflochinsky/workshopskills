---
name: classifying-tasks
description: Use when receiving any new work request, before writing code or choosing an approach — especially multi-item requests, vague one-liners, "quick" asks, or work under deadline pressure.
---

# Classifying Tasks

## Overview

The cost of being wrong — not the size of the ask — determines how much process a task needs. Classify BEFORE acting. A "small column" that changes a contract is heavy; a 500-line copy update is trivial.

**A deadline never downgrades the tier.** Time pressure changes what scope you negotiate, never which gates you skip.

## How to classify

1. If the project's CLAUDE.md defines its own tiers/dispatcher — follow it. This skill is the fallback and the default for projects without one.
2. Classify **each item separately** when a request contains several asks. One message ≠ one tier.
3. Check signals top-down, **first match wins**. Unsure between tiers → take the higher one or ask ONE question.

| Tier | Signals (any one) | Route |
|---|---|---|
| **Heavy** | New feature with its own business logic; ≥2 layers with a new/changed contract (e.g. DB + API + UI); touches a gated decision: auth/session, schema strategy, money, metric/status semantics, public API, RBAC/visibility; destructive or hard-to-reverse operation | **delivering-heavy-features** skill |
| **Standard** | Real behavior change, one layer or a thin slice, no gated decision | Brief clarification if ambiguous → tracker issue → short plan if non-obvious (superpowers:writing-plans) → TDD → verify (superpowers:verification-before-completion) |
| **Trivial** | Copy/label/locale text, single-spot style or cosmetic tweak, comment/docs typo | Do directly, surgical diff; verify only what's relevant (typecheck/lint) |

A bug fix is classified by its **fix**, not its symptom: a fix that changes a formula or contract is Heavy. Any debugging starts with superpowers:systematic-debugging regardless of tier.

## State it out loud

Before starting, tell the user the classification in one line:
"Item 2 is heavy (DB+API+UI, new contract) — running the heavy pipeline; items 1 and 3 are trivial/standard."

This gives the user a chance to veto before process diverges.

## Red flags — you are rationalizing

| Thought | Reality |
|---|---|
| "Deadline is tight, I'll run a compressed pipeline" | Compression = silently making the user's product decisions. Negotiate scope down instead: ship fewer items at full discipline. |
| "It's just one small column" | Columns come with contracts, defaults, migrations, and consumers. Classify by blast radius, not line count. |
| "The user is unavailable, so I'll skip the questions" | Unavailability defers gates, it doesn't remove them. See delivering-heavy-features for how to proceed safely. |
| "I'll classify after I look at the code" | Looking is fine; coding before classifying is not. |
| "The whole batch is basically one task" | Batches hide a heavy item behind two trivial ones. Per-item, always. |
