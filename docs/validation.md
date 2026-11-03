# Implementation and validation — 2026-11-03

## Design input and scope

The user-supplied [full architecture](software-factory-architecture-full.md) is
preserved as design input. Its old sandbox download links refer to the original
conversation, not installable dependencies. This implementation replaces the
earlier instructions-only analyst iteration with the first executable factory
contour described in section 10 of that document.

| Architecture area | Implemented behavior | Verification boundary |
| --- | --- | --- |
| Requirements and decisions | Six phase skills, selected project instructions, canonical spec/ADR/test contract, complete requirement/invariant → AC → scenario → check links | Controller validates structure and freshness; the leading agent/user and independent reviewer assess meaning. An `accepted` field is not cryptographic proof of consent. |
| Non-LLM controller | SQLite transactions, task/environment leases, revision-bound admission, execution budgets, immutable completed run records, finalization | Unit/integration tests use real temporary Git repositories and worktrees. Trusted host/operator remains the root of authority. |
| Workspace ownership | Git and Worktrunk providers; existing-owner attachment; separate implementation, verification and review snapshots | Git lifecycle exercised. Worktrunk command shape checked against its official API; installed `wt` and a real Tern instance were unavailable. |
| Pi and OMP | Separate pinned SDK adapters, explicit tools, isolated discovery/auth/session setup, strict structured results | Offline fake-SDK contract tests and primary-source API review passed. Live SDK/provider calls were not run. |
| Verification | Captured stdout/stderr with hashes, actual check argv, clean committed verification worktree, distinct reviewer process, final SHA/contract/environment gate | Full synthetic example passes; no real target application, database, browser or RBAC fixtures were supplied. Project drivers must provide those checks. |
| Isolation and recovery | Fail-closed Bubblewrap launcher, protected Git metadata/config, no worker shell/native delegation, task locks, startup handshake and PID identity, cancel/recover without replay | Negative tests verify gate and launch policy. Successful OS namespace isolation was not available on this host; no live worker was downgraded to an unsandboxed run. |
| Code intelligence | Live lexical search, Python AST definitions, repository/SHA/diff/content provenance, bounded partial/stale results | Nine source-inspection regressions. No semantic index, session mining or inferred current-code graph from transcripts. |

The document's later contours—distributed workers, remote environment pools,
semantic retrieval measured against baseline, session mining and a TokenEconomizer
integration—are not represented as implemented capabilities. Native Codex/Cursor
workers, a Tern plugin, OAuth-refresh ownership, project-specific preview/RBAC
fixtures and automatic forge publishing are also outside this runtime version.

## Reproduce the checks

From the repository root, using Python 3.11+, Git and Node:

```bash
python3 -m unittest discover -s tests -v
node --test tests/test_adapters.mjs
node --check adapters/common.mjs
node --check adapters/pi.mjs
node --check adapters/omp.mjs
python3 bin/factory demo /tmp/law-factory-validation
```

Use a new destination for each demo. The command refuses to overwrite an existing
directory. It creates a local Git repository containing a deliberate billing
rounding defect and an independent table of expected public behavior.

Observed result: **41 Python tests and 5 Node tests PASS**. All six factory skills
passed the skill format validator. These counts include meaningful refusal and
recovery cases; they are not a product test-count target.

## End-to-end synthetic result

The demo observed the seeded implementation failing its actual regression check,
then ran this sequence:

1. Register the canonical task, pass admission and create an owned worktree.
2. A deterministic fixture process repairs the arithmetic implementation.
3. The controller checks scope and commits the candidate.
4. The configured Python test command passes in a separate clean verification
   worktree at that candidate SHA.
5. A different fixture process reviews the candidate in another worktree.
6. Finalization validates current check/review evidence and records `VERIFIED`.
7. `pr-body` produces a description without publishing or merging anything.

The result explicitly records `synthetic: true`, `live_model: NOT_RUN` and
`sandbox: NOT_RUN`. The synthetic worker is a deterministic test fixture, not a
model or a simulation presented as a live Pi/OMP integration result.

## Negative cases exercised

The suite rejects implementation without admission; pending decisions; broken
trace links; changed spec, project instruction, SHA or environment; repeated
review by the implementation actor; missing/changed raw evidence; incomplete
review; stale results after readmission; concurrent task/environment runs;
malformed worker output; out-of-scope rename; modified contract files; and missing
sandbox or harness configuration. It verifies cancellation, timeout after closed
pipes, output limits on the final chunk, startup crash before process release,
recovery locking, and refusal to recover an unidentifiable live process.

Additional cases cover disabled host Git filters, read-only `.git` and runtime
configuration mount construction, SDK tool-policy rejection, secret/helper
credential restrictions, worker skill discovery isolation, separate verification
source unaffected by ignored implementation output, and lexical-search freshness
across worktrees, rename/delete and partial source coverage.

## What remains unverified on this host

`doctor` returned `BLOCKED`: Bubblewrap namespace startup was unavailable, and
trusted Pi/OMP installations, Bun and Worktrunk were absent. Consequently a real
model run, working OS isolation, Worktrunk execution and Tern UI integration have
status **NOT_RUN**, not PASS. The launcher's default remains fail-closed.

For a real project, configure the actual SDK/runtime/provider/model, explicit
credential names, dependency roots and check commands in the profile, then run
`doctor` and the full documented task cycle. Environment IDs must describe the
actual versioned fixture/backend; naming a shared database differently does not
isolate it. See [runtime-contract.md](runtime-contract.md) for the exact boundary.
