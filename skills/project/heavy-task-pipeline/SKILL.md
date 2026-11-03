---
name: heavy-task-pipeline
description: Use for Tier 2 / heavy Workwatch tasks — a new dashboard section with its own business logic, anything spanning API + DB migrations + UI, or any ADR-gate trigger. Runs requirements analysis with grill-me and factory-system-analyst, spec readiness, the existing ADR gate, bd epic, research, plan, execution, and independent verification. Keep the process independent of the agent harness.
---

# Heavy task pipeline (Tier 2)

Run the phases in order. Do not skip requirements analysis or product discussion;
reuse an already completed discussion and recorded user decisions. The project's
ADR sign-off remains the **only human approval gate**. Readiness checks below are
evidence checks, not extra permission requests. After the applicable gate is
satisfied, proceed to completion unless a new material blocker appears.

## Runtime bindings

Load named skills through the available skill mechanism or read their canonical
`SKILL.md`. Use project artifact paths and tracker conventions; the paths below
are Workwatch defaults. Read `AGENTS.md` for ADR triggers, Mandatory verification,
environment permissions, and session completion. `factory-system-analyst` is the
single owner of completeness, traceability, and analysis-readiness rules.

Superpowers skill names below are optional adapters for the stated work, not
requirements for a particular runtime. Without those plugins, perform the stated
steps directly. Model IDs and tool names belong in harness-specific configuration.
`bd` remains required by this project's tracker policy; if unavailable, finish
useful analysis and report the tracking blocker before dispatching implementation.

Use read-only research workers where supported; otherwise research the layers
sequentially in the lead session. For implementation and review, a separately
launched agent session can replace a native sub-agent API. Preserve fresh executor
context and an independent reviewer; lack of a delegation tool never permits
self-approval or skipping mandatory verification.

## 1. Discuss and analyze — main session

- Load `factory-system-analyst`. Establish current project evidence, use `grill-me`
  for unresolved product decisions in the main session, and update the canonical
  spec (default `docs/specs/<slug>.md`). Reuse prior answers instead of restarting
  the interview. Keep layer-specific implementation research for phase 3.
- Persist the skill's readiness record. On `NEEDS_RESEARCH`, investigate the listed
  gaps read-only. On `NEEDS_DECISION`, ask the specific unresolved question while
  continuing useful investigation. Do not dispatch implementation on either state.
- If an ADR trigger applies, write/update the ADR (default `docs/ADR/`) and link
  spec ↔ ADR. Obtain the existing gate's sign-off **before any code**. A user's
  explicit decision already covering this change satisfies sign-off: record its
  source/scope and any supersession instead of requesting it again.
- Proceed with `ANALYSIS_READY` and an ADR gate that is satisfied or not triggered.
  The analyst's status alone is not permission to implement.

## 2. Epic in beads

- `bd create --type=epic` with canonical spec/ADR paths and reviewed versions in the
  description; reuse the current epic if it already exists.
- Child issues come from the Plan phase; wire them with
  `bd dep add <child> <blocker>` so `bd ready` reflects real execution order.
- Tracker readiness expresses dependencies, not spec/ADR approval. Do not use a
  `ready-for-agent` label or an empty dependency list to bypass this pipeline.

## 3. Research — read-only, by affected layer

- Research schema+migrations, sync/worker, API, frontend, export/RBAC as affected,
  in parallel where supported. Research agents read only — no edits.
- Each returns evidence-backed current state, integration points, compatible reuse
  candidates and contract differences, affected consumers, risks, and source revision.
- Append findings under `## Research` in the canonical spec. Reuse phase-1 evidence;
  investigate remaining implementation questions instead of repeating discovery.
- If findings change the contract or reveal a blocker, return the affected parts to
  `factory-system-analyst`. A new gated decision goes through the existing ADR gate;
  previously accepted decisions with unchanged scope do not need another sign-off.

## 4. Plan and pre-execution check

- Plan over spec + research, optionally with `writing-plans`. Save to
  `docs/plans/<slug>.md` (create the directory on first use).
- Map in-scope requirement/AC IDs to implementation steps, relevant design/ADR
  decisions, and verification commands or explicit manual procedures. Resolve the
  analysis-time evidence methods into executable checks, fixtures, environment and
  expected-result sources. Reuse/extend known coverage where it protects the contract;
  do not interpret one trace row as an instruction to add one test.
- Convert steps into bd child issues — independently executable subject to their
  dependencies, with spec/plan/requirement links and verification commands. Link back
  from the plan so changes and checks can be traced in both directions.
- Immediately before dispatch, the lead checks the current spec readiness record,
  applicable ADR acceptance, plan trace links, dependency readiness, and available
  execution/verification prerequisites. Record the reviewed spec/profile/ADR versions
  and code revision/relevant diff in the plan; resolve blockers before execution.
- If those sources changed, reassess affected requirements and links first. This is
  a freshness check, not a request to approve the whole task again. An external
  controller may enforce it if installed; this skill is not that controller.

## 5. Execute — one bd issue = one executor

- Claim issue → implement (TDD where it fits) → run that layer's Mandatory
  verification block → hand off for phase 6's per-issue review. Keep the issue open
  until that review passes. Use `subagent-driven-development` when available or the
  equivalent isolated executor-session workflow supported by the harness.
- Run the per-issue execute/review loop as each child becomes ready; close a reviewed
  prerequisite before dispatching its dependents. Run epic-level verification after
  all children. This keeps `bd ready` from releasing work on an unreviewed result.
- Give each executor fresh context: canonical spec/ADR/plan/issue paths and versions,
  relevant requirement/AC IDs, project instructions and verification prerequisites;
  do not substitute a retelling of the conversation. Choose models in the adapter.
- Raw-SQL / migration work inside an issue → also apply `runtime-sql-review`.
- A newly discovered contract ambiguity returns to analysis; do not invent policy
  inside code or tests. Implementation fixes within the agreed contract continue
  without reopening product approval.

## 6. Verify — independent reviewers, never the author

- Per issue, at each execution handoff: a separate reviewer/verifier checks the
  diff against spec + ADR + plan and AC/invariants/risks, optionally with
  `requesting-code-review`. Loop fix → review until clean; close the child only after
  independent review and its mandatory checks pass. Use a separate clean review
  session if native sub-agents are absent; if no independent reviewer can run,
  report BLOCKED and do not claim completion.
- Epic level: full Mandatory verification for every touched layer; required prod
  smoke for schema/sync/auth/export/formula work subject to `AGENTS.md` environment
  permissions; apply `verification-before-completion` if available. Missing optional
  plugins do not remove these checks.
- Record actual commands/output and per-AC evidence as PASS / FAIL / BLOCKED /
  NOT_RUN, tied to the checked code and contract versions. Check for unimplemented
  requirements and unrequested behavior. Reused coverage must actually apply.
- After fixes, rerun affected checks/review and all project completion gates on the
  final change. Stale evidence or an author's readiness declaration is not acceptance.
- Keep verification notes in the ADR/plan with trace links. Close the epic only once
  verification is complete, then commit & push per the session-completion protocol.

## Why this is a skill and not hooks

Phase orchestration is an advisory workflow that loads on demand. Hooks/controllers
can enforce deterministic transitions, but a Markdown status alone cannot restrict
tools or grant permissions. Keep actual enforcement in the configured runtime.
