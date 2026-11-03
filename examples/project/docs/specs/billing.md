# Synthetic task: bill each started minute

## Goal and observed system

This deliberately small example has no customer or production data. `billing.py`
exposes `billed_minutes(seconds)`. It currently floors partial minutes, violating
the accepted example policy. The test suite contains the necessary regression
checks and must fail on that baseline. Successful repair makes the public API
consistent with the policy; adding more tests is not itself the goal.

## Contract and acceptance

| ID | Rule | Acceptance |
| --- | --- | --- |
| REQ-1 | Every started minute is billed. | AC-1: 1 and 59 seconds cost 1 minute; 61 costs 2. |
| REQ-2 | The input is a nonnegative integer; booleans are not durations. | AC-2: -1, 1.5, True and "60" raise ValueError. |
| INV-1 | Zero remains free and exact minute boundaries do not gain a minute. | AC-3: 0 → 0, 60 → 1, 120 → 2. |

The independent oracle is this table. `docs/adr/001-billing-boundary.md` keeps the
public function as the boundary. `docs/test-contracts/billing.json` maps every
requirement and invariant to its acceptance and executable check.

## Scope, constraints and exclusions

Change `billing.py`; extend existing tests only if a distinct failure mode is
uncovered. Preserve the public name, exception class and integer result. No UI,
database, tenancy, concurrency or external service exists; RBAC is inapplicable.
There is no clock, network or nondeterministic dependency. Python integers have no
fixed-width overflow. No architectural decision remains open.

## Risk and readiness

The material risk is an off-by-one error at zero or exact multiples of 60. The
listed boundaries distinguish it from the original floor error. This synthetic
fixture is ready for analysis handoff. Controller admission and independent
verification are still required; this prose does not grant either state.
