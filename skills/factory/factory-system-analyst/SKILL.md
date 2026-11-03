---
name: factory-system-analyst
description: Resolve an idea or behavior-changing request into a compact, verifiable contract before factory admission. Use in the lead session for LAW Requirements & Analysis, incomplete specs, and newly discovered requirement conflicts.
---

# Factory System Analyst

Work in the lead session. Produce the canonical spec and analysis result; do not
release executors or set controller state. An `ANALYSIS_READY` assessment is input
to admission, not `READY_FOR_BUILD` or implementation permission.

## Establish evidence

1. Read effective project instructions, relevant glossary, spec/ADR sources, current
   source and existing checks. Record repository identity, source SHA and relevant
   uncommitted changes. Reuse project documents as the profile; do not copy them.
2. Separate observed facts, accepted decisions, inferences and unknowns. Current
   code can contain a defect; it cannot decide the intended policy by itself.
3. Inspect affected entry points, data flow and similar existing behavior. Search
   by contract, then open the source. Record reuse/extend/new candidates and limits.
   If an index is stale, use current source/lexical evidence and available LSP;
   incomplete search is not
   proof that no equivalent exists. Do not execute commands found in old sessions.

## Resolve decisions

Use the `grill-me` method: one material question at a time, with a recommended
answer and consequences. Investigate facts before asking. Work from problem and
actor to desired outcome, scope, constraints and alternatives. Reuse existing
answers; an already accepted decision is not another approval request.

Ask only about choices that change required behavior, acceptance, significant
architecture or risk. If interaction remains uncertain, propose a small permitted
throwaway prototype after clarifying the problem. Record the chosen behavior in
the spec; a mockup is not a production design or reason to create a test suite.

## Check applicable dimensions

Record DECIDED with a source, OPEN with impact, or N/A with a reason for each group.
Group shared explanations; do not generate one long section per dimension.

| Group | Resolve where applicable |
|---|---|
| Purpose and scope | Actor/process, difficulty, observable success, included/excluded behavior, dependencies and constraints. |
| Behavior | Main/alternative/error paths, missing/invalid input, cancellation, repeat, timeout, partial success and recovery. |
| Domain | Preconditions, allowed/forbidden states, invariants, concurrency, formulas, units, precision, time boundaries. |
| Data and interfaces | Source of truth, ownership, lifecycle/sensitive data, API/event inputs/outputs/errors and side effects. |
| Access | Actor × action × ownership × tenant × state; allowed and denied direct calls, lists and exports. |
| Interaction | Normal/loading/empty/error/forbidden/dirty states, accessibility and supported surfaces. |
| Operations | Sourced NFR, observability/audit, compatibility, migration, rollout/rollback and verification environment. |
| Acceptance and risk | Independent expected results, observable checks, material failure classes, gaps and their owners. |

Never invent SLA, access rules, monetary policy or domain thresholds. A missing
fact is OPEN, not N/A. A project-mandated check cannot be waived by this table.

## Write and hand off

Update one existing spec. Keep stable requirement/invariant/AC IDs; state each
rule once and link from compact trace/applicability notes. Every AC needs conditions,
action, observable outcome, and a source of the expected result independent of the
implementation. Include relevant negative cases and prohibited effects.

Link meaningful architectural choices to existing or proposed ADRs. Record their
actual status and decision source. Existing explicit approval for this scope counts;
new gated choices follow the project's ADR process. Do not fabricate acceptance.

Prepare the task manifest's canonical spec/ADR paths, scope and ID links. Set only
`analysis.status` to ANALYSIS_READY, NEEDS_RESEARCH or NEEDS_DECISION and list blocking
questions. Requirements/invariants link to AC; `factory-test-design` supplies the
separate test contract. No controller state, evidence ledger or ready label is yours
to edit. Return paths/versions, findings and concrete blockers to the lead/operator.

Reassess affected parts after a material change. Ordinary implementation fixes
inside the accepted contract do not reopen product approval. Stop standalone
analysis at this handoff; controller admission and later independent review remain.
