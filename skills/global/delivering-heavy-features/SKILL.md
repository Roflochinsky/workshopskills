---
name: delivering-heavy-features
description: Use when a task is classified heavy — a new feature with its own business logic, work spanning several layers with a new or changed contract, or anything touching a gated decision (auth, schema, money, metric semantics, public API).
---

# Delivering Heavy Features

## Overview

Heavy features fail in predictable ways: built on guessed requirements, no durable spec/plan artifacts, the author approving their own work. This pipeline prevents all three. Phases run in order; the design sign-off is the **only** user approval gate — after it, run to completion.

**Dependencies:** superpowers (brainstorming, writing-plans, subagent-driven-development, requesting-code-review, verification-before-completion), grill-me, an issue tracker (beads `bd` recommended). If anything is missing, run the **doctor** skill first.

## Phase 0 — Project conventions

Read the project's CLAUDE.md / AGENTS.md for: approval gates (e.g. ADR triggers), layer list, where specs/plans live, mandatory verification commands, tracker conventions. If the project defines its own heavy pipeline — use that one instead. If conventions are missing, use defaults below and offer to record them in the project CLAUDE.md at the end.

## Phase 1 — Discuss (main session, with the user — never a sub-agent)

- Invoke **grill-me**: one question at a time until every branch of the design tree is resolved; recommend an answer with each question. If the codebase can answer a question, explore instead of asking.
- If the project has approval gates (ADR etc.) and one is touched: write/update the decision record and get the user's sign-off **before any code**.

**If the user is unreachable:** unavailability defers the gate, it does not remove it.
- Write every assumption down in the spec, marked ASSUMPTION.
- Build only the **safe, reversible subset**; leave hard-to-undo decisions (real sends to users, destructive migrations, public contract finalization) behind explicit "needs your yes" items.
- Send the batched questions through whatever channel exists; present them prominently when the user returns.

## Phase 2 — Spec (durable artifact)

Persist to `docs/specs/<slug>.md` (create dir on first use) or the project's convention: problem, decisions with the why, scope, non-goals, acceptance criteria, affected layers, assumptions. The spec must survive compaction and session changes — chat history is not an artifact.

## Phase 3 — Decompose into tracked issues

Epic + child issues in the tracker (`bd create --type=epic`, children wired with `bd dep add`). Each child = one vertical slice independently executable by a fresh agent, carrying its verification command(s) in the description. Use the **decomposing-to-issues** skill.

## Phase 4 — Research (read-only sub-agents, parallel)

One Explore-type sub-agent per affected layer. Research agents read only — no edits. Each returns: current state, integration points, patterns to reuse, risks. Append findings to the spec under `## Research`.

## Phase 5 — Plan

superpowers:writing-plans over spec + research: steps with a verify criterion per step. Persist to `docs/plans/<slug>.md` or project convention. Sync plan steps with the tracker issues.

## Phase 6 — Execute

superpowers:subagent-driven-development: one issue = one executor sub-agent with a **fresh context** — pass spec/plan/issue paths, not a retelling of the conversation. TDD where it fits. Close issues as they complete.

## Phase 7 — Verify (never the author)

- Per issue: independent reviewer sub-agent (superpowers:requesting-code-review) checks the diff against spec + plan; loop fix → review until clean. Reviewers get different lenses (correctness / simplicity / conventions), not N identical passes.
- Epic level: project's mandatory verification for every touched layer + run the actual app and observe the feature working (superpowers:verification-before-completion).
- Record verification notes in the spec/plan. Close the epic. Ship via **shipping-a-release** only on the user's explicit ask.

## Red flags — you are rationalizing

| Thought | Reality |
|---|---|
| "Deadline tomorrow → compressed pipeline" | Compress SCOPE (smaller vertical slice at full discipline), never phases. |
| "User is in meetings, so no approval gate" | Deferred ≠ removed. Safe subset + queued decisions. |
| "The spec is the tracker issue / chat history" | Issues fragment, chat compacts. One durable spec file. |
| "I'll review my own diff carefully" | Same context = same blind spots. Fresh-context reviewer, always. |
| "Research slows me down, I know this codebase" | Each layer gets 10 minutes of reading and saves a rejected PR. |
