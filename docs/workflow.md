# Operating the factory workflow

This runtime follows the supplied Software Factory architecture's first working
loop: one lead, versioned contracts, controlled execution, independent review and
revision-bound evidence. The legacy workshop skills remain separate. Select one
workflow for a task rather than loading two competing heavy pipelines.

## Contents

- [Responsibilities](#responsibilities)
- [Project setup](#project-setup)
- [Task contracts](#task-contracts)
- [Execution loop](#execution-loop)
- [Evidence and recovery](#evidence-and-recovery)
- [Boundaries](#boundaries)

## Responsibilities

| Component | Responsibility |
|---|---|
| Lead session | Investigate the product, clarify decisions, maintain canonical spec/ADR and the plan, prepare the machine contracts. |
| Six `factory-*` skills | Procedures for analysis, test design, preflight, runtime verification, RBAC audit and independent review. Skills do not mutate controller state by declaring a status. |
| Python controller | Validate structural prerequisites, bind contract versions, serialize admitted runs, preserve evidence and decide whether the recorded gate conditions are met. |
| Pi / OMP adapter | Run the selected harness with the role's actual permitted capabilities; avoid ambient competing skills and uncontrolled native delegation. |
| Workspace provider | Create/adopt and inspect exactly the workspaces it owns. |
| Independent reviewer | Review the candidate in a fresh context without editing it; report structured findings against actual AC. |
| Project verification driver | Run actual configured checks against permitted fixtures/environment; collect raw results. |

The controller cannot prove a business policy is correct or that a string saying
`accepted` represents a real human decision. Those claims need their cited source
and semantic review. Its gate ensures that the declared contract is complete in
structure, current, and supported by the required registered results.

## Project setup

Use `bin/factory --help` for the actual CLI interface. Command names below describe
the workflow; repository paths, model IDs and credentials are project-specific.

1. Run `init` for the target repository and inspect the generated draft
   `.factory/project.json`. It is not an admitted project: check lists and harness
   settings need actual values. Fill SDK/runtime paths, model/provider, workspace
   owner, budgets and verification check argv. Keep secret values out of files;
   `harnesses.<name>.env` and `verification.checks[].env` list explicitly permitted
   environment variable names rather than their values. See the exact fields in
   [runtime-contract.md](runtime-contract.md).
2. Merge the routing in [factory-AGENTS.md](../config/factory-AGENTS.md) into the
   effective project instructions. Preserve existing domain rules and mandatory
   checks. Add the selected Markdown domain-rule paths to `instructions` in the
   profile. They are hashed and embedded in the handoff; ambient instruction and
   skill discovery is disabled. Do not load the legacy heavy pipeline in parallel.
3. Run `doctor` for local prerequisites and sandbox availability. Its report does
   not certify the installed SDK/provider: the real worker validates those. Resolve
   missing paths, commands and unusable sandbox before attempting a real worker.
4. Establish the actual synthetic preview and verification procedure: Launch,
   Doctor, Drive, Evidence and Cleanup. Register check IDs only for real commands.
   A generated procedure without an executed example remains unverified.
5. Commit the profile and canonical task/spec/ADR/test-contract files. Admission
   and revision-bound evidence require a clean committed source snapshot. The
   controller's mutable state belongs outside every checkout/worktree.

The active workspace owner is `git`, `worktrunk`, or `existing`. Checks and review
use separate clean worktrees at the candidate SHA, so ignored implementation
artifacts do not become verification inputs. For `existing`, Tern/operator supplies
absolute `path`, `verification_path` and `review_path` at the required revisions;
the factory neither creates nor removes those resources. The owner prepares new
candidate snapshots after a fix. Never force-remove dirty or foreign worktrees.

A worktree separates files; database schemas, queues, test identities and browser
state need their own isolation. When those resources are shared, use the same
`preview.environment_id` and `preview.isolation: "serial"`. Select `per-task` only
when the project fixture actually provides separate mutable backend resources;
the setting alone does not create them. Environment identity must encode the real
fixture and its relevant revision. Leases coordinate runs only in one controller
journal: all operators/hosts in this contour must use the same canonical repository
and state directory. Independent journals do not serialize a shared database.

## Task contracts

Keep business behavior in the project's canonical spec, architectural rationale in
ADR, and symbols/steps in the existing plan. The task JSON is the controller's link
map. [Runtime contracts](runtime-contract.md#task-manifest) define the schema and
[examples/project](../examples/project/) supplies a coherent synthetic example.
The lead maintains these canonical inputs; workers cannot rewrite their spec,
ADR, profile, selected instructions, task manifest or test contract to pass a gate.

The test-contract JSON contains `schema_version: 1`, `scenarios`, and `rbac`.
Each scenario names its requirement/invariant IDs, AC IDs, behavior, distinct
failure mode, public boundary, independent oracle source, inspected existing
coverage, reuse/extend/new disposition, cost and configured check IDs. Material
risk IDs remain linked from the spec and the scenario's failure description.
`rbac.required` has an explicit reason; when required, `rbac.check_id` identifies
the actual configured check. See the
[test-design skill](../skills/factory/factory-test-design/SKILL.md) for selection rules.

Do not create a scenario per implementation method or a test per trace-table row.
Reuse suitable coverage; preserve project-mandated checks. Expected values come
from policy/examples/invariants, not the algorithm or policy function under test.

## Execution loop

| Step | Action and expected result |
|---|---|
| Analyze | The lead uses `factory-system-analyst`, including the grill-me method for unresolved product choices. A prior accepted decision is reused. |
| Design evidence | `factory-test-design` connects each AC to sufficient, distinct evidence and actual check IDs. |
| Preflight | `factory-preflight` checks scope, dependencies, reuse, the plan and environment. New material questions return to the relevant decision; settled decisions are not reopened. |
| Register | `create` records/reloads the task and the canonical inputs. Inspect `status` rather than assuming creation admitted implementation. |
| Admit | `admit` checks current analysis, ADR, trace and contract prerequisites. Only a successful controller result establishes READY_FOR_BUILD. |
| Workspace | `workspace` creates or adopts the configured task workspace and reconciles its recorded identity. |
| Implement | `run` launches the chosen Pi/OMP worker with read/grep/find/write/edit, admitted scope and budgets. No shell or native task tool is available; the controller snapshots the candidate. |
| Check | `check` runs configured argv in a separate verification worktree with source mounted read-only. Include required runtime and RBAC evidence. |
| Review | `review` starts a separate fresh reviewer with the candidate and available check evidence. The author cannot supply that independent result. |
| Finalize | `finalize` requires current contract/SHA/environment and all mandatory results; only then is the task VERIFIED. |
| Prepare PR | `pr-body` formats the verified change and evidence. Publication/merge/deployment remain separately authorized operations. |

Typical states are DRAFT, READY_FOR_BUILD, IMPLEMENTING, READY_FOR_REVIEW,
VERIFYING and VERIFIED. Failures or unavailable prerequisites produce BLOCKED;
explicit cancellation produces CANCELLED. Read actual status after a command.
A Markdown claim, an empty tracker dependency list or a green author run does not
replace an admission/finalization result.

If a fix changes implementation only, keep accepted business decisions, admit the
new implementation attempt as required, and regenerate evidence for the new
candidate. If spec/ADR/test contract/profile/scope changes, update the canonical
inputs and revalidate affected contract/admission. Do not silently reuse old hashes.

## Evidence and recovery

Each registered result distinguishes PASS, FAIL, BLOCKED and NOT_RUN. Retain raw
stdout/stderr and relevant evidence with their actual hashes, source commit,
contract fingerprint, reviewer/run identity and environment identity. A timeout,
missing worker, invalid review JSON or unavailable fixture is not success.

The independent review protocol is a single JSON object with `status`, actual
`covered_ac`, the `spec`, `correctness`, `tests` lenses and `findings`. PASS requires
complete review and no unresolved findings. The controller still checks who ran
it and which candidate/contract/evidence it belongs to. Runtime checks are separate
observations; source review cannot invent their results.

Verification source is read-only. The project driver creates dependencies,
temporary application copies and isolated DB/queue/browser fixtures in permitted
locations and writes artifacts under `FACTORY_RUN_DIR`. It receives task, source
and environment identifiers; see the [driver contract](runtime-contract.md#project-driver).
The factory does not guess a working application setup from a generated command.

Use `cancel` to stop requested work and inspect the resulting process/task state.
After interruption use `recover` to mark stranded work explicitly and reconcile
resources. Recovery does not automatically replay a possibly completed external
side effect. A per-task `flock` and a startup pipe handshake protect the gap between
registration and process launch. Recovery refuses an active launcher or an
unverifiable live process instead of killing an arbitrary PID. Inspect existing
resources and effects before retrying; never force-remove dirty work.

Keep the controller state and raw evidence outside worker-controlled checkouts.
The default state path is derived from the common Git directory, sharing one
journal across local worktrees; an explicit shared `--state-dir` is recommended.
The operator should not edit evidence to turn a failure green. Retain failing logs
through correction, then attach fresh evidence to the current candidate.

## Boundaries

Real worker/check runs require Linux and usable Bubblewrap. The runtime blocks
when that boundary is unavailable; no run/check/review flag silently downgrades it.
The built-in trusted-local synthetic demo does not prove OS isolation or grant
production access. Tool allowlists complement the sandbox. Host Git operations
disable hooks, fsmonitor and content filters. LFS/submodules need a future explicit
driver and are not claimed as supported by this version.

Pi and OMP are distinct SDK integrations; OMP needs its supported Bun runtime.
Check [harness-api.md](harness-api.md) for the pinned API basis and run `doctor` for
local capabilities. A documented command or passing fake-SDK test is not a live
provider smoke result. Real model, preview and platform evidence must be recorded
in the target environment before claiming those integrations were exercised.

`search`, `symbol` and `index-health` inspect live source with worktree/SHA/content
identity. Symbol extraction recognizes Python AST definitions; other occurrences
are lexical, not a semantic reference graph. Coverage/observation limits are part
of each result. Semantic indexing, session mining, TokenEconomizer and remote
worker pools remain outside this first working contour. A future service must be
evaluated against the live-source baseline and versioned by repo/worktree/revision.
Do not treat a
no-match from an incomplete index, an old successful command or repeated agent
speculation as an architectural fact or an instruction to execute. Do not promote
session lessons into LAW without reviewing the underlying evidence.
