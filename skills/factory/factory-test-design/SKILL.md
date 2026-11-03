---
name: factory-test-design
description: Design the minimum sufficient evidence for an accepted factory contract before implementation, and review test changes for distinct failure coverage. Use for LAW Verification & Review planning, excessive test generation, or changed risks and acceptance criteria.
---

# Factory Test Design

Work with the lead's canonical spec, accepted decisions, existing tests and project
mandatory checks. Define evidence; do not set admission state or certify unrun tests.
A small count is not a quality target. Every retained scenario must protect a
requirement, invariant or material risk with a distinguishable failure mode.
The lead may update the contract; a read-only reviewer reports gaps without editing.

## Choose evidence before writing tests

1. Inspect actual existing coverage and public interfaces. Identify which checks
   already protect each AC and whether the new path can bypass that boundary.
2. For each distinct behavior/failure class, choose the most stable boundary that
   provides an adequate, timely signal: a pure function, service/API integration,
   or a user interaction. Do not duplicate one fact at every layer by default.
3. Define the expected result from an accepted policy, independent example or
   mathematical invariant. Copying the implementation into `expected` is not an
   independent oracle. A mocked authorization decision cannot prove real access.
4. Select reuse, extension or new coverage. Explain a new scenario's difference
   from existing ones and its execution/maintenance cost. Keep several related
   assertions together when they describe one behavior.
5. Preserve mandatory project checks even if a narrower scenario would also pass.
   Resolve unavailable fixtures/access explicitly; absence is BLOCKED, not PASS.

## Persist the test contract

Use the JSON file referenced by the task's `test_contract`, without duplicating the
spec. Set `schema_version: 1`; each `scenarios` entry contains:

| Field | Required meaning |
|---|---|
| `id`, `requirements`, `acceptance` | Stable scenario ID, task requirement/invariant IDs and AC IDs. |
| `behavior`, `distinct_failure_mode` | Observable behavior and the separate defect it detects; link material risk IDs from the spec here. |
| `public_boundary`, `oracle_source` | Observation boundary and independent expected-result source. |
| `existing_coverage` | Inspected relevant check or a specific coverage gap. |
| `disposition` | `reuse`, `extend`, or `new`; explain the choice in `existing_coverage` or `cost`. |
| `cost` | Relevant runtime, reliability or maintenance tradeoff. |
| `checks` | IDs of actual commands configured in the project verification profile. |

Set `rbac.required` from the affected access boundary. Give a reason when false;
when true, link `rbac.check_id` to an actual configured check and use
`factory-rbac-audit`. Do not invent a command merely to satisfy schema validation.

## Keep regression coverage useful

Reject private-call/order assertions, self-mocked use cases, broad incidental DOM
snapshots and CSS-class checks unless an explicit contract needs that signal.
Combine repeated scenarios when they catch the same failure at the same boundary.
Never remove a required denial case just to reduce count. Do not enumerate every
input × role × layer combination without distinct risks.

For a bugfix, show the expected behavioral failure before the fix and a pass after
it when feasible. A missing database or broken fixture is not that red result.
For critical invariants, select a small sensitivity check in a disposable managed
workspace; do not mandate a whole-suite mutation score or mutate production data.

Exploratory checks stay temporary. Promote only a confirmed new failure class or
an uncovered invariant to the permanent suite. During review ask: what defect,
which oracle, what existing overlap, why this boundary, and will it survive a
refactor? Return the contract and unresolved evidence gaps; controller and
independent review decide whether the evidence satisfies the task.
