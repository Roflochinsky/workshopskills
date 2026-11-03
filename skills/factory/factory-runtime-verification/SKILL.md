---
name: factory-runtime-verification
description: Define and execute project-specific runtime verification with real commands, isolated fixtures and revision-bound evidence. Use after implementation and after fixes for LAW Verification & Review; missing or failed checks must never become a completion claim.
---

# Factory Runtime Verification

Use the candidate SHA, accepted task/test contract, actual project profile and a
permitted preview. Run checks through the trusted controller's `check` path. While
acting as verifier, do not edit product code or decide new product policy. An
implementation worker prepares the handoff; only the controller runs commands.

## Establish the project driver

Keep one project-specific procedure for:

- **Launch:** real commands, cwd, dependencies and preview service identity.
- **Doctor:** observable health checks proving required services/fixtures exist.
- **Drive:** actual public API/CLI/UI operations tied to AC and test scenarios.
- **Evidence:** raw command output, return codes and relevant artifacts at the
  candidate SHA, contract fingerprint and environment identity.
- **Cleanup:** bounded removal of this run's synthetic fixtures/resources only.

Discover those facts in the project. Register actual argv arrays and check IDs in
the verification profile. A generated driver remains unverified until it has run
on a real permitted feature; do not invent selectors, credentials or successful
commands. Existing mandatory project checks remain required.

Checks read a separate clean verification snapshot. Put writable outputs and any
temporary application copy under FACTORY_RUN_DIR. The driver supplies dependencies
and isolated fixtures using FACTORY_TASK_ID, FACTORY_SOURCE_SHA and
FACTORY_ENVIRONMENT_ID; the factory does not infer or provision the application.

## Execute and diagnose

1. Confirm the candidate and contract still match the registered task. Check the
   environment identity and current health before interpreting test results.
2. Run required checks, including runtime/RBAC checks required by the test contract.
   Keep mutable state isolated per run, or serialize shared resources. Never use
   another run's fixture state or credentials as an implicit dependency.
3. Preserve the controller's raw status. Separate a reproduced defect from a
   failed prerequisite: nonzero exit alone does not establish a product bug.
   Report missing/unexecuted observations as BLOCKED/NOT_RUN, never PASS.
   Process exit alone is not UI evidence.
4. For a finding, retain expected behavior, actual behavior, reproduction inputs,
   source revision and evidence. Separate infrastructure failure from a product
   failure; deduplicate reports that have the same cause.
5. Send required fixes to the lead/implementer. Preserve the failing evidence;
   execute affected checks again on the new candidate and satisfy final project
   gates before completion. Old-SHA output cannot pass the new candidate.

The controller owns run registration, immutable evidence records and finalization.
Use its result; do not write PASS into its ledger or supply fabricated log hashes.
A lost worker, timeout, missing fixture or failed cleanup needs an explicit result,
not an empty success report. Recovery must inspect prior side effects before retry.

## Finish the verification handoff

Return check IDs, actual status, raw evidence references, affected AC, environment
identity and remaining blockers. Independent review still examines spec alignment,
correctness and test usefulness. Only controller `finalize` can mark VERIFIED.
PR body preparation is a later operation; it does not publish, merge or deploy.
