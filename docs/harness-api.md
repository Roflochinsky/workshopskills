# Pi and OMP worker adapters

The factory launches one SDK process per worker. The controller owns admission,
worktrees, process deadlines, OS isolation, evidence capture and integration. These
adapters own a small boundary: deterministic model selection, the permitted SDK
tools, a fresh reviewer session and a machine-readable result.

## Supported API baselines

| Adapter | Package pinned by the adapter | Interpreter | Source checked |
| --- | --- | --- | --- |
| `adapters/pi.mjs` | `@earendil-works/pi-coding-agent@1.5.0` | Node.js >=22.19.0 | Pi upstream, 2026-11-03 |
| `adapters/omp.mjs` | `@oh-my-pi/pi-coding-agent@18.16.0` | Bun >=1.4.4 | OMP commit `83de60ad992d12e572ec3ed6fe2dd9e160cdc4a2` |

The version pins are the implementation baseline, not a claim that a live model
was exercised in the development environment. OMP's package `engines.bun` is
stricter than the minimum on its SDK overview page; the adapter uses the package
requirement. OMP is a Bun SDK and cannot be loaded by a Node process.

The controller profile supplies the **absolute root import entry of an already
installed SDK**, plus the trusted interpreter path. The adapter resolves that
file, reads its enclosing `package.json`, checks the package name and version,
and checks that the file is the package's root import entry. It never runs a
package installer, guesses a global installation directory, falls back to a CLI,
or accepts a different version silently. Package metadata is not a signature:
the operator must trust the installed package and its dependency lock.

Resolve the root import entry in the environment where the pinned package was
installed. For a local Node installation, `import.meta.resolve` or
`require.resolve` can identify Pi's installed root entry. For OMP, use Bun's
resolver in the installation environment. Record the resulting absolute path in
the profile; copying only the entry file without its dependency tree does not
make an installation.

Primary sources:

- [Pi package and runtime requirement](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/package.json)
- [Pi full-control SDK example](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/12-full-control.ts)
- [Pi model selection](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/02-custom-model.ts)
- [Pi SDK lifecycle](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sdk.md)
- [OMP package at the checked commit](https://github.com/can1357/oh-my-pi/blob/83de60ad992d12e572ec3ed6fe2dd9e160cdc4a2/packages/coding-agent/package.json)
- [OMP SDK public contract](https://omp.sh/docs/sdk)
- [OMP SDK implementation at the checked commit](https://github.com/can1357/oh-my-pi/blob/83de60ad992d12e572ec3ed6fe2dd9e160cdc4a2/packages/coding-agent/src/sdk.ts)

## Launch and input

The controller invokes an argv array, with the worker worktree as the process
working directory. Shell interpolation is unnecessary.

```text
<trusted-node> <absolute-factory-path>/adapters/pi.mjs <absolute-input-json>
<trusted-bun> --no-env-file --no-install --config <controller-owned-bunfig.toml> <absolute-factory-path>/adapters/omp.mjs <absolute-input-json>
```

The controller creates the trusted Bun configuration outside worker-writable
directories, with `preload = []`, and mounts it read-only. `--no-env-file` disables
Bun's automatic environment files; `--no-install` prevents dependency installation
during module resolution. An absolute adapter file selects a file execution, so
project package scripts and their lifecycle hooks are not invoked.

These flags are only part of startup isolation. OMP's utility module also reads
environment files itself during SDK import, independently of Bun's flag. The
controller masks existing project `.env*` and `bunfig.toml` files before starting
the interpreter, gives it private `HOME` and `XDG_CONFIG_HOME` directories, and
rejects runtime-control environment variables, including all `BUN_*` variables,
`NODE_OPTIONS` and `NODE_PATH`. This prevents an inherited `BUN_OPTIONS` or
`BUN_INSPECT_PRELOAD` from selecting code that runs before the adapter can enforce
its tool policy. The adapter sets its private `PI_CODING_AGENT_DIR` before SDK
import. Startup protection belongs in the launcher: checking after import cannot
undo a preload that has already executed.

Startup sources: [Bun runtime flags and script execution](https://bun.com/docs/runtime),
[Bun configuration and preloads](https://bun.com/docs/runtime/bunfig),
[Bun environment-file loading](https://bun.com/docs/runtime/environment-variables),
[Bun startup environment options](https://bun.com/blog/bun-v1.3), and
[OMP's independent environment loader](https://github.com/can1357/oh-my-pi/blob/83de60ad992d12e572ec3ed6fe2dd9e160cdc4a2/packages/utils/src/env.ts).

Input schema version 1:

```json
{
  "schema_version": 1,
  "role": "review",
  "prompt": "Controller-assembled handoff: approved spec, test contract, candidate and evidence references.",
  "output_dir": "/isolated-worker-output",
  "session_path": null,
  "provider": "explicit-provider-id",
  "model": "exact-model-id",
  "sdk_module": "/operator-selected-installation/root-import-entry.js",
  "tools": ["read", "grep", "find"]
}
```

`auth_file` is optional and must be an absolute path to an operator-provisioned
credential snapshot. `role` is `implement`, `analyze` or `review`. Provider and
model are exact identifiers: no model-role alias, fuzzy match or automatic
fallback is accepted. A model absent from the pinned built-in catalog causes
`BLOCKED`; arbitrary project `models.json`/`models.yml` files are not loaded.

The controller supplies the approved project instructions and selected skill
bodies/references in the prompt. It must preserve their source paths and digests
in its manifest. There is no ambient skill lookup in these workers, so a local
skill with the same name cannot shadow the controller's selected skill.

## Tool policy and discovery

| Role | Pi tools available for an explicit request | OMP tools available for an explicit request |
| --- | --- | --- |
| `analyze` | `read`, `grep`, `find`, `ls` | `read`, `grep`, `find` |
| `review` | `read`, `grep`, `find`, `ls` | `read`, `grep`, `find` |
| `implement` | The above plus `write`, `edit` | The above plus `write`, `edit` |

OMP has no built-in `ls` tool at this baseline. The requested list must be a
nonempty subset of the role's fixed list. Unknown tools, wildcards, native
`task`, arbitrary custom tools and any request for `bash` are rejected.
The adapter also checks the SDK's actual active tool names before prompting and
after settlement. A missing requested capability or an extra capability blocks
the run.

**Pi:** a host-owned `ResourceLoader` returns no extensions, skills, prompt
templates, themes or discovered `AGENTS.md` files. The SDK receives in-memory
settings, an explicit model runtime, exact tool names and an MCP deny pattern.
Pi's CLI built-in MCP/codemode extensions are not installed into this SDK session.
The model runtime uses `modelsPath: null`, disables catalog networking, and
receives a host-owned immutable in-memory `CredentialStore` instead of a mutable
`auth.json` backend.

**OMP:** `Settings.isolated()` avoids ambient settings. `restrictToolNames: true`
is the enforced SDK allowlist; `toolNames` alone is insufficient. Discovered
extensions, MCP, LSP, IRC, custom tools, skills, rules, context files and prompt
templates are explicitly disabled or replaced with empty lists. Native advisor
execution is disabled with `advisor.enabled: false`; automatic prewalk and model
fallbacks are disabled. The registry uses only the bundled/offline catalog, not
local model configuration. `autoApprove: true` applies to the already granted
worker tools within the controller's OS sandbox, avoiding an unimplemented
interactive approval exchange.

These settings enforce the SDK capability boundary; they do not replace OS
isolation. Version 1 gives no worker a shell or evaluator, including implementers.
Workers inspect and edit source; the controller runs configured command arrays
and checks with a separate environment containing no model credentials. This
removes the ordinary native-task and shell routes to unmanaged delegation. It
is not a proof against an SDK exploit. Worker processes must remain unable to
write controller state or another worktree, reach production credentials, or
perform an unauthorized external effect. Network permissions and mutable test
data isolation belong to the controller's environment policy. The reviewer also
has no edit or write capability and receives controller-owned execution evidence.

OMP's CLI accepts `--tools`, but that option alone does not remove discovered
custom/plugin tools or MCP. This is why the factory uses the SDK rather than
claiming that a CLI allowlist or a prompt enforces isolation.

## Authentication and sessions

The preferred credential route is the controller's allowlisted provider API-key
environment. The adapter never logs configuration objects or credential values;
it redacts known secret environment values and snapshot keys from its JSON
output. SDK stderr and all artifacts still belong in access-controlled evidence
storage. A raw event stream can contain repository data and model output.

An optional `auth_file` must contain literal API-key credentials for **only the
selected provider**. Pi accepts its `auth.json` format. OMP accepts a consistent
SQLite credential snapshot, with no live `-wal` or `-shm` sidecars. The adapter
copies the snapshot into a private temporary directory before reading it,
validates it, and transfers the literal keys to in-memory storage. Pi uses an
immutable `CredentialStore`; OMP uses an in-memory SQLite `AuthStorage`. The
temporary snapshot is removed before the agent turn. A worker cannot change the
active credentials by rewriting an auth file into an executable helper. The
original read-only file is never opened for writing. No global auth directory or
implicit login session is discovered.

Read-only OAuth refresh credentials and executable credential helpers are
rejected. Copying a rotating refresh token, refreshing it and deleting the copy
would lose the new credential and can invalidate the original. Supporting that
flow requires a separate host-owned credential refresh integration. Do not put
credentials in prompts, CLI arguments or committed profiles.

`session_path: null` creates an in-memory session. Review and analysis reject any
non-null session path. Every review therefore starts with the explicit handoff,
not the implementer's transcript.

For `implement`, an absolute `session_path` selects a dedicated session file. A
missing file starts a new persistent session; an existing file resumes that
session. The adapter verifies the recorded working directory against the current
worktree and refuses a symlink in place of the session file. The controller must
own the session path, bind it to the task and harness, serialize access and mount
its directory outside the product checkout. Changing the task/spec boundary is
the controller's decision; the adapter does not discover the most recent session
or import transcripts automatically.

Sources for persistence and auth:

- [Pi SessionManager](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/session-manager.ts)
- [Pi ModelRuntime](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/model-runtime.ts)
- [Pi CredentialStore interface](https://github.com/earendil-works/pi/blob/main/packages/ai/src/auth/types.ts)
- [OMP SessionManager](https://github.com/can1357/oh-my-pi/blob/83de60ad992d12e572ec3ed6fe2dd9e160cdc4a2/packages/coding-agent/src/session/session-manager.ts)
- [OMP AuthStorage](https://github.com/can1357/oh-my-pi/blob/83de60ad992d12e572ec3ed6fe2dd9e160cdc4a2/packages/ai/src/auth-storage.ts)

## Events, result and failure semantics

Stdout is JSONL. SDK session events retain their shape inside one envelope:

```json
{"type":"event","event":{"type":"message_end","message":{}}}
```

The controller continuously drains stdout and stderr separately. It records the
raw streams, interpreter/SDK versions, exit status, process deadline, input/spec
digests, role, candidate SHA and worktree identity. Missing/truncated streams,
timeout, a crashed process or absent final result cannot become a passing review.
Adapter output is evidence from a worker, not permission to advance state.

The SDK call is awaited through `prompt()` and `waitForIdle()`. Pi's low-level
`agent_end` can precede automatic continuation; an RPC implementation would need
`agent_settled`. OMP RPC instead uses `agent_end` with `isTerminal !== false`.
Neither protocol's prompt acknowledgement means completion. The SDK adapters
avoid confusing these harness-specific wire conditions.

A reviewer must return one JSON object with exactly four fields:

```json
{
  "status": "PASS",
  "covered_ac": ["AC-1", "AC-2"],
  "lenses": ["spec", "correctness", "tests"],
  "findings": []
}
```

`PASS` requires nonempty unique acceptance identifiers, all three known lenses
and no unresolved findings. Markdown fences, explanatory prose, unknown fields,
malformed JSON or incomplete passing claims yield `BLOCKED`. `FAIL` and `BLOCKED`
can carry findings. The controller must still compare coverage to the actual
spec, check required evidence and verify that the result refers to the current
candidate. A syntactically valid verdict does not prove its claims.

The adapter writes `output_dir/result.json` and emits one final frame:

```json
{"type":"result","status":"PASS","role":"review","covered_ac":["AC-1"],"lenses":["spec","correctness","tests"],"findings":[]}
```

For implementation and analysis, a successful completed turn has `status: PASS`
and a `text` field, with empty review coverage/lenses. It means the turn completed;
it grants no readiness, verification, merge or release authority. A terminal SDK
error, abort, empty answer, incompatible API or failed cleanup produces `BLOCKED`.
Exit codes are `0` for `PASS`, `1` for `FAIL`, and `2` for `BLOCKED`.

## Worktrunk boundary

The checked Worktrunk documentation is v0.81.0. Use explicit cwd, branch, base and
absolute destination. The controller remains the single lifecycle owner:

```text
wt -C REPO switch --create BRANCH --base BASE_SHA --path ABS_PATH --no-cd --no-hooks --format=json
wt -C REPO remove --foreground --no-hooks --no-delete-branch --format=json BRANCH
```

`--no-hooks` avoids configured lifecycle commands. `--foreground` waits for
removal; removal otherwise runs in the background. Retaining the branch avoids
implicit branch deletion. Do not add `--force`, `--clobber` or `--reap` to routine
cleanup. Inspect switch stdout even on a nonzero exit: the worktree may already
have been created. Reconcile the result against `git worktree list --porcelain`.

An externally managed Tern worktree must use the factory's external workspace
mode; the factory must not create/remove that worktree with Worktrunk as well.
Separate worktrees do not isolate a shared database, queue or browser state.

Sources: [wt switch](https://worktrunk.dev/switch/),
[wt remove](https://worktrunk.dev/remove/),
[base ref resolution](https://github.com/max-sixty/worktrunk/blob/0162047ee32ac4acbb67e51d252a89e2d8b88a09/src/commands/worktree/switch.rs).

## Source-search baseline

`factory/intelligence.py` is a standard-library implementation with three public
functions: `health(repo)`, `search(repo, query, limit=20)` and
`symbol(repo, name, limit=20)`. Each call reads the current Git-tracked and
nonignored untracked source. There is no persistent index to confuse with a
different worktree. `symbol` identifies Python class/function definitions through
AST parsing and labels every other hit as a lexical occurrence. It does not
claim a references, call or impact graph.

Responses include a manifest with a repository identity, explicit worktree,
HEAD SHA, extractor version, searched-content digest, path inventory and
worktree-change fingerprint. The latter combines Git raw change records with
the searched bytes and skipped-file metadata; it is not a byte-level commitment
to omitted binary or oversized files. Every hit also names its path, line,
column, file digest and snapshot identities.

The default scope is UTF-8 regular files, excluding `.git` and `.factory`.
Symlinks are never followed, including symlinks in parent path components. Binary,
non-UTF-8, oversized and over-budget files are reported as omitted. Source reads,
result count and excerpts are bounded. A host without safe directory-relative
nofollow opens reports `unavailable`, rather than weakening the boundary.

Status is `ok`, `partial`, `stale` or `unavailable`. A concurrent change detected
during collection produces `stale`; the observation is not an atomic snapshot.
An empty result is explicitly `no_matches_in_observed_scope`, never “no reusable
implementation exists.” The analyst must read candidates and compare contracts.
Semantic retrieval, other-language symbol graphs and authorized session mining
remain later work in the supplied architecture, not hidden capabilities of this
baseline.

## Validation boundary

Offline validation checks JavaScript syntax, fixed role capabilities, exact
review JSON, failure/cleanup behavior and the options passed into fake SDKs.
`runPi` and `runOmp` are exported for those dependency-injected contract tests.
The executable entry points have no test-mode version bypass and do not accept
an arbitrary fake module through a production flag.

Run the committed adapter tests with `node --test tests/test_adapters.mjs`.
Run the source-search regressions with
`python -m unittest discover -s tests -p test_intelligence.py -v`; they use real,
disposable Git repositories and worktrees, including changes, renames, deletions,
symlinks, partial coverage and changes during an observation.

Those tests do not prove that a provider, account, pinned SDK installation,
native dependency or OS sandbox works on the target machine. Before enabling a
real project profile, run its configured adapter in the actual sandbox with an
authorized low-cost prompt, inspect the final result and SDK tool inventory, and
exercise the controller's negative cases. No live model smoke test or package
installation is implied by the offline test result.
