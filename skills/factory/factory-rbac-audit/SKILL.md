---
name: factory-rbac-audit
description: Verify authorization and tenant/ownership boundaries for a factory candidate against accepted policy. Use when changed APIs, UI, lists, exports or state transitions affect who may access or modify resources, and when the test contract requires an RBAC check.
---

# Factory RBAC Audit

Take expected policy from the accepted spec/ADR, never from the authorization code
under examination. Work in a permitted synthetic preview with a fixed candidate
SHA and contract fingerprint. Do not modify product code or invent missing policy.
In a read-only review, inspect registered RBAC evidence and report gaps; the
controller/project driver performs the active probes described below.

## Build the relevant matrix

Enumerate meaningful actor × action × resource ownership × tenant × resource state
classes. Name concrete synthetic identities and objects and their expected allow/
deny outcomes. Two users with the same role can have different object permissions.

Cover the applicable boundaries: permitted operation, forbidden operation, another
owner, another tenant, direct API request, list/detail visibility, export, and
changed or stale resource state. A hidden button does not demonstrate server denial.
Resolve ambiguous error/disclosure and partial-batch policy before treating it as
an oracle. Use N/A with a reason for dimensions genuinely outside this change.

Link the matrix to AC and test-contract scenarios. Set `rbac.required: true` and
`rbac.check_id` to the actual configured check for an affected access boundary.
Reuse existing suitable coverage after confirming the new path cannot bypass it;
do not create a full Cartesian suite without distinct failure classes.

## Execute under bounded authority

1. Verify the declared environment, candidate SHA, fixtures, permitted domains and
   budget. Use separate mutable accounts/data/browser state or serialize the runs.
2. Run the deterministic accepted matrix through real authorization boundaries.
   Do not mock the policy being tested or call production systems.
3. Add a bounded adversarial pass only for a concrete remaining risk: alternate
   entry points, parameter changes, ordering or state races. It complements the
   matrix; it cannot prove the absence of every authorization defect.
4. Record reproducible findings with expected policy, actual outcome, identities,
   resource state, steps and evidence. Ask the lead/coordinator to reproduce a
   finding before treating it as confirmed; group duplicate causes.
5. Send fixes to the implementer. Recheck affected cases on the new candidate;
   checks from the previous SHA or environment are stale.

Report PASS / FAIL / BLOCKED / NOT_RUN per relevant scenario. Missing identities,
browser failure, unclear policy or an absent worker must not count as PASS. Include
prohibited side effects in denial assertions; successful HTTP denial alone may not
prove that a write or notification did not happen.

Keep exploratory probes temporary. Promote a confirmed distinct defect into the
smallest useful regression check through `factory-test-design`. Return evidence to
the controller; never assign VERIFIED, approve your own implementation or broaden
permissions to get the checks running.
