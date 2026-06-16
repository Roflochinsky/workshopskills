---
name: heavy-task-pipeline
description: Use for Tier 2 / heavy Workwatch tasks — a new dashboard section with its own business logic, anything spanning API + DB migrations + UI, or any ADR-gate trigger. Runs discuss → spec (+ADR) → bd epic → research → plan → execute → verify with sub-agents.
---

# Heavy task pipeline (Tier 2)

Run the phases in order. Do not skip Discuss. The ADR sign-off is the **only** user
approval gate; after it, run the rest to completion without further approval cycles.

## 1. Discuss — main session, dialogue with the user (never a sub-agent)

- Invoke the `grill-me` skill: interview the user one question at a time until every
  branch of the design tree is resolved; give your recommended answer with each
  question. If the codebase can answer a question, explore it instead of asking.
- Record the outcome as a **spec**: `docs/specs/<slug>.md` (create the directory on
  first use) — problem, decisions made
  (with the why), scope, non-goals, acceptance criteria, affected layers
  (DB / sync / API / frontend / export / RBAC).
- If any ADR-gate trigger is touched (see `AGENTS.md` → _ADR gates_): write or update
  the ADR in `docs/ADR/`, get the user's sign-off **before any code**, link spec ↔ ADR.

## 2. Epic in beads

- `bd create --type=epic` with the spec/ADR paths in the description.
- Child issues come from the Plan phase; wire them with
  `bd dep add <child> <blocker>` so `bd ready` reflects real execution order.

## 3. Research — read-only sub-agents, in parallel

- One Explore/general-purpose sub-agent per affected layer (schema+migrations,
  sync/worker, API, frontend, export/RBAC). Research agents read only — no edits.
- Each returns: current state, integration points, patterns to reuse, risks.
- Append findings to the spec under `## Research`. The plan must build on them.

## 4. Plan

- Superpowers `writing-plans` over spec + research: steps with a verify criterion per
  step. Save to `docs/plans/<slug>.md` (create the directory on first use).
- Convert plan steps into bd child issues — each independently executable, each
  carrying its verification command(s) in the description.

## 5. Execute — one bd issue = one executor sub-agent

- Superpowers `subagent-driven-development`: claim issue → implement (TDD where it
  fits) → run that layer's Mandatory verification block → close issue. Executor model:
  **Fable 5, low effort** (`model: fable`).
- Give each sub-agent a fresh context: pass the spec/plan/issue paths, not a retelling
  of the conversation. Raw-SQL / migration work inside an issue → also apply the
  `runtime-sql-review` skill.

## 6. Verify — separate sub-agents, never the author

- Per issue: an independent reviewer (`code-reviewer`/verifier, Opus; Superpowers
  `requesting-code-review`) checks the diff against spec + plan; loop fix → review
  until clean.
- Epic level: full Mandatory verification for every touched layer; prod smoke for
  schema/sync/auth/export/formula work; Superpowers `verification-before-completion`.
- Record verification notes in the ADR/plan. Close the epic, then commit & push per
  the session-completion protocol.

## Why this is a skill and not hooks

Hooks are for deterministic enforcement at lifecycle events (block a tool, run a
formatter). Phase orchestration is an advisory multi-step workflow — per Claude Code
best practices it belongs in a skill that loads on demand.
