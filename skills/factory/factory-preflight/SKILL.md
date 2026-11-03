---
name: factory-preflight
description: Prepare a factory task for controller admission and implementation using current spec, ADR, test contract, reuse evidence and environment capabilities. Use before a managed worker starts or when any accepted contract or source basis changes.
---

# Factory Preflight

Work in the lead session. Prepare factual inputs for the controller; do not assign
READY_FOR_BUILD yourself. Read the current task, canonical spec/ADR/test contract,
project profile and source SHA before choosing implementation work.

## Check the contract and existing system

1. Confirm analysis has no blocking question. Check requirements/invariants → AC →
   scenarios → configured checks in both directions; flag missing or unrelated
   work. Confirm required ADRs are accepted with a real decision source.
2. Investigate affected consumers and existing implementations. Open candidates
   and compare pre/postconditions, authorization/tenant scope, errors, side effects,
   transactions and retries. Record reuse/extend/new with source evidence.
3. Check code-index revision/worktree coverage if an index is used. Fall back to
   live source/lexical evidence and available LSP; partial no-match proves nothing.
   Session knowledge is advisory and must match current code, cwd and environment.
4. Put files/symbols, steps, dependency order, verification commands and expected
   results in the existing execution plan. Keep business policy in spec and the
   architectural rationale in ADR. Carry stable IDs into any tracker issues.
5. Check that scope globs cover intended edits without broadening authority. If
   research changes a requirement or a gated choice, update the same contracts and
   repeat only affected analysis; reuse approvals whose scope still matches.

## Check the execution boundary

Confirm selected `instructions` files, the configured harness/SDK, project checks,
time/output/run budgets and sandbox capability. Workers have no shell/native task;
the controller executes commands. A binary path or version in documentation is not a
successful launch. Missing dependencies or unusable sandbox are BLOCKED. An explicit
synthetic demo mode does not establish isolation for real work.

Choose one workspace owner: Git provider, Worktrunk provider, or an existing
workspace owned by Tern/another operator. Never create or delete worktrees through a
second owner. Existing-owner mode needs distinct implementation, verification and
review paths at the required SHAs. Inspect resources before retrying interrupted
creation; never force-remove a dirty or foreign workspace.

Worktree isolation covers files only. Confirm the preview identity and isolation of
mutable data, queues, accounts and browser state. When mutable resources are shared,
use serial execution under the same environment identity and controller journal.
Identity must represent actual fixtures/version; a per-task label provisions nothing.
Do not supply production
credentials, real payments, real notifications or unrelated session transcripts.

## Admit through the host controller

Submit/reload the manifest with `create`, then ask the trusted operator/controller
to run `admit` and inspect the result. These are structural/evidence gates, not new
human approvals. A manifest's `accepted` text must represent a decision already made;
it cannot manufacture that decision. Do not call administrative commands from a
worker, edit the state database, or start native delegated workers outside the runner.

Admission binds the profile, selected instructions, spec, ADRs, test contract,
scope and source basis. An implementation worker must not edit those frozen inputs.
Any material change invalidates affected admission/evidence. After a rejected gate,
report its exact reason and continue only useful authorized discovery. Return the
plan, reuse/impact evidence, actual capability findings and controller status.
