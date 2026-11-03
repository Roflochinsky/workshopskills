# Factory workflow instructions

Merge this routing into the target project's effective `AGENTS.md` when selecting
the factory runtime. Keep the project's domain policies and mandatory verification
commands as their existing source of truth. This file is not an application profile
and does not supply Workwatch, database, production or credential configuration.

## One workflow owner

Use the external `bin/factory` controller for admission, managed runs and evidence.
Do not run the legacy heavy-task-pipeline as a second controller. Implementation
workers have read/grep/find/write/edit; reviewers have only read/grep/find. Workers
have no shell or native task tool. The controller alone executes configured
commands, snapshots candidates and starts separate review sessions.

Keep one lead session for discussion, analysis, design and implementation context.
Load only the applicable `factory-*` skill. Use separate contexts for independent
review; no separate analyst/architect agent is required merely to follow a phase.

| Need | Skill |
|---|---|
| Resolve product intent and system behavior | `factory-system-analyst` |
| Choose sufficient, nonduplicative evidence | `factory-test-design` |
| Check reuse, plan, prerequisites and admission inputs | `factory-preflight` |
| Run the real project's verification procedure | `factory-runtime-verification` |
| Verify affected authorization boundaries | `factory-rbac-audit` |
| Review requirements, correctness and tests independently | `factory-independent-review` |

## Contracts and authority

Preserve canonical spec/ADR/plan locations. `.factory/project.json` binds the real
harness, workspace, verification and budget settings. Its `instructions` list
selects canonical Markdown domain rules; the controller hashes and embeds them.
Ambient harness instruction/skill discovery is off. Task/test JSON links the
contracts and check IDs; it does not replace the human-readable domain spec.
Workers must not edit frozen spec/ADR/profile/instruction/test-contract files or
the task manifest, even when a broad scope glob would otherwise match them.

Facts need current source evidence. Policy needs an accepted decision. Reuse the
user's decisions already made for this scope; do not ask for duplicate approvals.
A newly triggered ADR choice uses the existing project gate. Missing mandatory
behavior, dependencies or acceptance remain blockers, not guessed assumptions.

Only the trusted controller/operator admits execution and registers evidence.
`ANALYSIS_READY` is an analysis conclusion; only the controller issues
`READY_FOR_BUILD`. Only controller finalization issues `VERIFIED`. Never edit its
SQLite database, log records, hashes or state from a worker.

## Execution and completion

Use exactly one worktree owner: configured Git/Worktrunk provider or an existing
workspace owned by the operator/Tern. Existing-owner mode requires separate
implementation, verification and review paths at their required SHAs; only that
owner manages their lifecycle. Keep source commits, contract versions and preview
identity attached to results. No production data, payments, sends or
credentials enter a synthetic verification run. A separate worktree alone does
not isolate databases, queues, accounts or browser state.

Checks use a separate clean source snapshot mounted read-only. The project driver
owns dependencies, temporary application/DB fixtures and output in FACTORY_RUN_DIR;
it must not depend on ignored artifacts from implementation. Shared resources use
the same real environment identity and controller journal; a per-task label does
not provision isolated resources. Run configured argv and collect actual evidence.
Mark missing/unrun checks BLOCKED/NOT_RUN. Preserve failure evidence; fix through
the implementer and recheck the current candidate. The author cannot review its
own result. Do not close tracked work until its independent review and mandatory
checks pass. A prepared PR body does not authorize push, merge or deployment.
