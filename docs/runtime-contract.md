# Runtime configuration and task contracts

This is the operator contract for schema version 1. The implementation lives in
[cli.py](../factory/cli.py), [controller.py](../factory/controller.py),
[runtime.py](../factory/runtime.py) and [process.py](../factory/process.py).
[workflow.md](workflow.md) describes the process; the skills describe analysis and
review methods. The coherent [synthetic example](../examples/project/) can be run
with `bin/factory demo NEW_DIRECTORY` without installing a model SDK.

## Project profile

`init` writes only a draft `.factory/project.json` in an existing Git repository.
Empty checks and harness settings require project-specific configuration. Do not
copy synthetic business policy or mark an unexecuted project driver as working.
Python 3.11+ and Git are required; real execution requires Linux and Bubblewrap.

| Field | Value and behavior |
|---|---|
| `schema_version` | Integer `1`. |
| `project_id` | Nonempty project identifier. |
| `instructions` | Array of repository-relative Markdown paths. These selected domain rules are hashed, frozen and embedded in worker handoffs. Empty means no additional project instructions. |
| `workspace.provider` | Exactly one of `git`, `worktrunk`, `existing`. |
| `workspace.path` | For `existing`: absolute implementation worktree path, registered in this repository and initially at the admitted SHA. |
| `workspace.verification_path` | For `existing`: a separate absolute clean worktree at the candidate SHA for checks. |
| `workspace.review_path` | For `existing`: a separate absolute clean worktree at the candidate SHA for review. |
| `preview.environment_id` | Stable identity of the actual fixture/environment, including the relevant fixture revision. Results with a different identity cannot complete the same gate. |
| `preview.isolation` | `serial` by default, or `per-task`. The latter appends the task ID to the identity; it does not create isolated data or services. |
| `verification.checks` | Nonempty array of configured command objects; see below. |
| `runtime.max_runs` | Positive integer cap on all registered runs for the task, including retries, checks and reviews. |
| `runtime.timeout_seconds` | Positive integer worker deadline and upper bound on a check deadline. |
| `runtime.output_limit_bytes` | Positive integer bound for captured stdout and stderr together. Exceeding it blocks a successful result. |
| `runtime.sandbox` | `bubblewrap`. Other values cannot launch real work. |
| `runtime.read_only_paths` | Optional absolute, narrowly scoped dependency paths mounted read-only for execution. No controller-state or whole-home mounts. |
| `harnesses.pi`, `harnesses.omp` | Configure the selected harness; unused entries may remain empty. See the next table. |

For `existing`, the external owner prepares and updates the three worktrees; the
factory validates their identity and does not create, reset or remove them. Git
and Worktrunk modes create a managed implementation worktree and distinct clean
verification/review worktrees for each candidate SHA. They preserve branches and
refuse foreign or dirty destinations rather than replacing them.

### Harness settings

| Field under `harnesses.<name>` | Meaning |
|---|---|
| `runtime` | Existing executable absolute path to Node for Pi or Bun for OMP. |
| `sdk_module` | Absolute root import entry of the pinned installed SDK, outside task workspaces. |
| `provider`, `model` | Exact nonempty provider/model identifiers from that SDK's catalog; no implicit fallback. |
| `env` | Array of environment variable names explicitly allowed from the operator process, usually the selected provider's API key. Values never go in the profile. |
| `read_only_paths` | Optional absolute trusted installation/dependency roots needed by the SDK. Mount the specific dependency tree, not a home directory. |
| `auth_file` | Optional absolute API-key snapshot for the selected provider; the supported formats and restrictions are in [harness-api.md](harness-api.md#authentication-and-sessions). |

Pinned package versions and interpreter requirements belong to
[harness-api.md](harness-api.md#supported-api-baselines). `doctor` reports local
paths/configuration and a sandbox probe, with live provider status `NOT_RUN`.
Only an actual worker run validates the installed SDK and provider together.
Ambient settings, skills, instruction discovery and native delegation are disabled.
The controller requests `read/grep/find/write/edit` for implementation and
`read/grep/find` for review. Neither role has shell/evaluator/native task access;
configured commands execute through the controller.

## Verification checks

Each `verification.checks` object has:

| Field | Type and constraint |
|---|---|
| `id` | Unique 1–64 character slug using letters, digits, `_`, `-`; first character alphanumeric. |
| `argv` | Nonempty array of nonempty strings passed directly to process execution. No implicit shell interpolation. |
| `cwd` | Repository-relative directory, default `.`; interpreted in the verification worktree. |
| `timeout_seconds` | Positive integer, capped by `runtime.timeout_seconds`. |
| `required` | Explicit boolean. Required checks always participate in finalization. |
| `env` | Optional explicit array of inherited environment names; independent from harness credentials. |
| `network` | Optional boolean; networking is disabled unless this is exactly `true`. |

`check TASK` runs configured checks; `check TASK --check ID` selects one.
Finalization requires the union of checks marked `required`, checks referenced by
test scenarios, and the required RBAC check. Running only a convenient subset does
not satisfy the gate. A shell script is possible only as an explicitly configured
trusted argv program; a worker cannot invent and execute a new command itself.

### Project driver

Checks execute in a separate clean verification worktree, with source mounted
read-only and no model credentials inherited. Writable output is a dedicated run
directory; `/tmp` is ephemeral. The controller supplies:

| Environment variable | Meaning |
|---|---|
| `FACTORY_RUN_DIR` | Writable run output directory. Put build artifacts, temporary application copies and relevant evidence here. |
| `FACTORY_TASK_ID` | Current task identifier; use it when provisioning genuinely separate task fixtures. |
| `FACTORY_SOURCE_SHA` | Full candidate commit SHA of the mounted source. |
| `FACTORY_ENVIRONMENT_ID` | Controller-selected environment identity used to bind evidence. |

The project driver supplies permitted dependencies, a temporary runnable app,
synthetic DB/queue/browser fixtures, actual operations and cleanup. It must not
rely on ignored build output or local state left in the implementation worktree.
For tools that insist on writing in the source tree, build a controlled temporary
copy under `FACTORY_RUN_DIR` and verify that candidate. A generated argv or a
successful process exit is not proof of a working UI/authorization check: the
command must assert the declared observable behavior and retain useful output.

The current runner automatically registers stdout/stderr and structured worker
receipts. Other files under `FACTORY_RUN_DIR` are retained outputs, not automatically
hashed gate evidence or reviewer inputs. Emit essential assertions/measurements to
captured output; do not claim that an unregistered screenshot/report was reviewed.
A nonzero command exit records FAIL; a deadline/output limit or unavailable launch
records BLOCKED. Diagnose infrastructure separately: nonzero exit alone does not
establish a product defect.

Shared mutable resources use one environment identity and one controller journal.
Every operator/host participating in this contour must use the same canonical
repository and state directory. Independent journals cannot lease each other's
resources. `per-task` is appropriate only when the driver actually separates the
backend state; adding the label does not provision or verify that separation.

## Task manifest

`create` accepts a JSON file within the canonical repository. Its location is a
project convention; `.factory/tasks/TASK.json` is a useful example, not a required
layout. The spec and ADR keep their existing canonical locations.

| Field | Type and constraint |
|---|---|
| `schema_version` | Integer `1`. |
| `task_id` | Stable 1–64 character safe slug, with the same character rules as check IDs. |
| `spec` | Repository-relative nonempty canonical spec file. |
| `adrs` | Array of `{path, status, decision_source}`. Empty when no ADR is triggered; admission requires all listed statuses `accepted` and nonempty actual decision sources. |
| `test_contract` | Repository-relative test-contract JSON file. |
| `scope` | Nonempty array of relative implementation globs; no absolute paths or parent traversal. |
| `requirements` | Nonempty array of unique stable IDs defined in the spec. |
| `invariants` | Array of stable IDs, empty when no separate invariant is needed; IDs must not overlap requirements. |
| `acceptance` | Nonempty array of `{id, requirements: [IDs]}` with unique AC IDs. Links can name requirements and invariants. Every declared requirement/invariant needs an AC. |
| `analysis` | `{status, blocking_questions}`. The lead uses `ANALYSIS_READY`, `NEEDS_RESEARCH` or `NEEDS_DECISION`; admission requires `ANALYSIS_READY` and an explicit empty blocking-question list. |

These are structural checks. A nonempty decision source is not proof that approval
occurred, and an ID link is not proof that behavior is correct. The lead and
independent review establish those meanings from actual evidence and decisions.

Admission binds the manifest meaning, profile, selected instructions, spec, ADR,
test contract and source basis. Commit these inputs before admission and keep the
worktree clean. Implementation workers may edit only their product scope; changing
frozen contracts, grants, instructions or profile is rejected even if a broad glob
matches the file. A material contract update goes through `create` and admission;
it does not require repeating an unchanged, previously accepted user decision.
When canonical input changes after a worktree already exists, the trusted operator
must also bring those approved artifacts into the implementation worktree and
commit them before the next run. The launcher compares their bytes with the new
admission; it does not silently overwrite a task branch or cherry-pick decisions.

## Test contract

The file has `schema_version: 1`, a nonempty `scenarios` array and `rbac`.
Each scenario has a unique `id`; nonempty ID arrays `requirements`, `acceptance`
and `checks`; nonempty strings `behavior`, `distinct_failure_mode`,
`public_boundary`, `oracle_source`, `existing_coverage` and `cost`; and
`disposition` equal to `reuse`, `extend` or `new`.

Scenario links must resolve to task IDs and configured checks, without orphan
requirements. Together they must cover every declared requirement-to-AC link.
`rbac` contains an explicit boolean `required` and nonempty `reason`. When required,
`check_id` names a configured real command. Material risks remain in the spec and
can be linked from `distinct_failure_mode`; there is no separate machine risk table.
The [test-design skill](../skills/factory/factory-test-design/SKILL.md) defines useful
coverage and independent oracles; a table row is not a reason to add another test.

## State, evidence and recovery

Global `--repo` and `--state-dir` precede the CLI command. Keep the state directory
outside the canonical checkout and every worktree. The default is
`$XDG_STATE_HOME/law-factory/<common-git-directory-hash>`, falling back to
`~/.local/state` when XDG_STATE_HOME is absent. Prefer one explicit team path to
accidentally starting independent journals. Managed workspaces are siblings of
that state directory.

The controller owns DRAFT → READY_FOR_BUILD → IMPLEMENTING → READY_FOR_REVIEW /
VERIFYING → VERIFIED, with BLOCKED and CANCELLED outcomes. `status` exposes recorded
runs/events. Skills never assign these states. A successful implementation turn
means only that the worker completed; acceptance needs current checks and an
independent review at the exact SHA, contract fingerprint and environment identity.

Raw stdout/stderr, process identity and structured result receipts are stored
outside worker-controlled source. Finalization rechecks registered evidence hashes. Review
receives bounded copies of registered evidence, marked when truncated, and must
return BLOCKED if the available evidence is insufficient. Author summaries and
synthetic fixture results do not stand in for live platform evidence.

Launcher/recovery serialize through a per-task `flock`; a child waits for a startup
pipe release after its identity record is saved. `recover` does not replay work or
external side effects. It refuses an active launcher and live/unverifiable abandoned
process; `cancel` only signals a matching recorded process identity. Inspect effects
and existing resources before retrying. There is no distributed worker-pool or
cross-journal recovery protocol in this version.

Real execution fails closed when Bubblewrap is missing or unusable. The built-in
demo's trusted-local fixture path is explicit and internal; `run`, `check` and
`review` have no option that turns off the sandbox. Git host operations disable
hooks, fsmonitor and content filters; LFS/submodules need an explicit future driver.
