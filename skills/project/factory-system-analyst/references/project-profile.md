# Project profile source map

Use this reference when first adapting the analyst to a project or when conventions
have changed. Keep the general method in `factory-system-analyst`; keep project
facts in the project's existing documents. No new profile file is required.

## Discover before adding

1. Read the effective project instructions and identify which ones actually loaded
   in the current harness. Record the source paths and relevant versions.
2. Locate the existing glossary, spec/ADR conventions, domain rules, contracts,
   execution/verification documentation, tracker, and environment constraints.
3. Build a short map of pointers. Keep it in the existing project guide or the
   current spec's context section. Extract a reusable profile only when duplication
   across tasks makes that useful; follow the project's location convention.
4. Mark missing information as unknown. Validate factual entries against current
   source; obtain business decisions through the existing discussion/ADR process.

## Suggested map (adapt names, not obligations)

| Profile entry | Point to authoritative existing material |
|---|---|
| Domain and vocabulary | Product/problem context, actors, glossary, ambiguous terms. |
| Invariants and policies | Formula/units/time rules, states, access/tenant matrix, data ownership. |
| System boundaries | Modules, deployables, public APIs/events, external consumers and dependencies. |
| Sources of truth | Which source defines intended behavior; which source shows current behavior; authority for supersession. |
| Artifact conventions | Canonical spec/ADR/plan locations, formats, IDs, indexes, and versioning. |
| Decision process | ADR triggers, existing sign-off evidence, unresolved blocked decisions. |
| Verification | Mandatory commands, observable boundaries, fixtures, real environment/access constraints. |
| Delivery | Tracker and dependency conventions, release/rollout/rollback rules. |
| Available tooling | Confirmed search/LSP/index capabilities and freshness; harness skill discovery and reviewer mechanism. |

Load only relevant linked sections for the current task. Preserve links and source
versions rather than copying the entire knowledge base into the skill or prompt.
Do not introduce roles, commands, SLA, or environment access from a template.

## Workwatch mapping in this bundle

`config/project-AGENTS.md` is a distributable project template, not instructions to
operate the `workshopskills` repository as the Workwatch production application.
After installation, the target project's effective `AGENTS.md` is authoritative.
For Workwatch, its existing sections provide the initial profile:

- **Read before non-trivial work** → product/architecture/spec/ADR sources.
- **Product and architecture invariants** → business and system boundaries.
- **ADR gates / Business approval gates** → triggers and blocked decisions.
- **Mandatory verification / Environment and safety** → commands and actual access.
- **Beads Issue Tracker / Session Completion** → tracking and delivery conventions.

Use `docs/specs/`, `docs/ADR/`, and `docs/plans/` only as the current Workwatch defaults;
prefer a target project's established paths when adapting. For affected Workwatch
behavior inspect DB, sync/worker, API, frontend, export, and RBAC as applicable.
Do not copy Workwatch-specific production rules into an unrelated project.

## Updating a profile

Update an existing source where the fact belongs, then refresh its pointer/version.
Changes are versioned and reviewed with normal repository changes. This is not a
new user approval gate. A new gated architectural decision still follows the
project's ADR process; an already authorized decision is recorded without asking again.
A project profile may add domain checks, but cannot silently relax mandatory checks,
independent review, authority boundaries, or the analyst's readiness criteria.
