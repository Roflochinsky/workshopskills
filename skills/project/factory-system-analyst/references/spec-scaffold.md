# Optional spec scaffold

Use this only when a project has no adequate spec format. Merge missing information
into an existing spec instead of creating another document. Bracketed values below
are placeholders to replace or explicitly mark unknown, never claims of readiness.
Keep small tasks short; combine sections/tables and use references and grouped
N/A reasons. Do not fill every heading with prose or repeat a rule across sections.

## Context and authority

- Spec identity/version: [path and revision/document version; keep any content
  digest only in the Analysis readiness record below].
- Request and accepted decisions: [source, desired change, scope of authorization].
- Project profile/source map: [links and versions].
- System examined: [repository, HEAD SHA, relevant dirty diff reference/digest].
- Current behavior and evidence: [facts vs inference vs unknowns].

## Problem, outcome, and scope

[Actor/process, current difficulty, intended observable improvement, included and
excluded behavior, priority, constraints, dependencies/owners and their disposition.]

## Behavior and applicable dimensions

[Requirements, invariants, actors/access, transitions, data/API/UI behavior, negative
and boundary cases, NFR, compatibility, observability, and material risks as relevant.]

| Dimension from the skill | DECIDED / OPEN / N/A | Evidence, gap/impact, or reason |
|---|---|---|
| [Each dimension, possibly grouped where the same reason applies] | [Status] | [Reference or concrete explanation] |

## Acceptance and traceability

For each AC: [preconditions/input/state] → [action/event] → [observable outcome and
forbidden effects]; expected-result source: [decision/policy/example/invariant];
verification: [boundary/method, fixtures/environment/access dependencies].

| Requirement / invariant / risk + source | AC | Decision / ADR and status | Planned evidence |
|---|---|---|---|
| [Stable ID] | [AC IDs] | [Decision/ADR, or no-trigger reason] | [Method, oracle, existing coverage candidate, prerequisite] |

Do not copy the implementation into expected results. Existing tests are coverage
candidates until their actual relevance is inspected; a planned run has no PASS status.

## Research and implementation handoff

[Evidence-linked current behavior, affected consumers/layers, reuse/extend/new
candidates and their contract differences, limitations of search, unresolved impact.]

[Link the execution plan and tracker issues when created. Keep symbol/file/command
mapping there, with the reviewed revision; no duplicate task backlog in this spec.]

## Open items

| ID / source | Gap and affected requirement IDs | Impact | Blocking? + reason | Resolver / next action |
|---|---|---|---|---|
| [Question] | [Concrete missing evidence or choice] | [Consequence] | [yes/no; why] | [Investigation or decision owner] |

## Analysis readiness

- Outcome: [ANALYSIS_READY / NEEDS_RESEARCH / NEEDS_DECISION].
- Basis: [spec/profile/ADR revisions and source SHA + relevant diff; if hashing the
  spec contract, exclude this readiness record from the digest].
- Checks: [completeness, consistency, verifiability, feasibility, handoff — result
  and evidence link for each; record failures rather than ticking empty headings].
- Blocking items: [IDs or none, with evidence].
- Nonblocking items: [IDs, reasons, and disposition].
- ADR gate: [not_triggered + reason / satisfied + acceptance source / pending + choice].
- Next action: [investigate, resolve a specific decision, or hand off to the pipeline].

ANALYSIS_READY does not release work to an executor. The pipeline checks the ADR gate
and plan before implementation. Revalidate affected parts after material changes.

## Small illustrative trace (not a domain policy)

Assume the user has already decided that members may read only their own drafts,
and the project has accepted an ADR covering server-side ownership enforcement.

| Contract item | Acceptance | Decision / architecture | Planned evidence |
|---|---|---|---|
| REQ-1: a member can read their own draft; INV-1: a different member cannot read it | AC-1: owner reads the saved content; AC-2: another member's direct request yields the policy-defined denial with no content disclosure | Existing user decision + accepted ownership ADR; reuse current server enforcement if source inspection confirms its contract | Public API check with two synthetic identities and one draft; oracle is the accepted policy, not the authorization implementation |

AC-2 does not invent whether denial means 403 or 404. Resolve that from the accepted
API contract; if it is missing and observable semantics matter, record a blocker.
The actual test count, test code, and execution evidence belong to later phases.
