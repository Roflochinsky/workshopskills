---
name: factory-independent-review
description: Independently review a factory candidate against its accepted requirements, architecture and test contract using fresh context and read-only source. Use after implementation and after corrections; the implementation author cannot accept its own work.
---

# Factory Independent Review

Start in a separate reviewer process/session with only canonical contracts,
candidate source/diff and evidence references. Do not inherit the author's private
conversation as proof. Do not edit product files, start implementation workers,
run arbitrary shell commands, change controller state or approve work you authored.
The runner supplies the permitted read-only tools and output channel.

## Inspect three lenses

- **spec:** trace every in-scope requirement/invariant and AC to delivered behavior;
  inspect omissions, extra scope, negative cases, accepted ADRs and source versions.
  Current code and an author's summary do not redefine expected behavior.
- **correctness:** inspect changed paths, consumers, states, data integrity,
  access/tenant boundaries, retries/concurrency and plausible failure cases. Verify
  reuse compatibility and architecture within the diff; unrelated improvements
  belong in backlog, not mandatory broad refactoring.
- **tests:** inspect the test contract, independent oracles, relevant actual
  coverage and evidence. Ask what distinct defect each new scenario detects,
  whether existing coverage already protects it, and whether it survives a
  refactor. Do not reward test count or a green mock-only result.

Source review does not execute a runtime check. Inspect raw registered results
where provided; flag missing/stale evidence and ask the controller/operator to run
necessary checks. An unavailable fixture or tool is BLOCKED, not a clean review.
Do not infer a successful browser or live authorization check from source alone.

## Findings and decision

For each material finding state the affected AC, source location, expected and
actual behavior, reproduction/evidence and impact. Distinguish a source-supported
defect from a hypothesis requiring runtime reproduction. A missing required check
is a blocker even if no implementation defect has yet been demonstrated.

Return FAIL for an actionable defect, BLOCKED when required review evidence or
capability is missing, and PASS only after all three lenses and all AC are covered
with no unresolved findings. The lead sends fixes to the implementer; a new
candidate needs new review/evidence. Do not turn review into another human approval
for a product decision that is already accepted.

## Output protocol

Return exactly one JSON object, with no Markdown fences or surrounding prose:

```json
{
  "status": "PASS",
  "covered_ac": ["AC-ID-FROM-THE-TASK"],
  "lenses": ["spec", "correctness", "tests"],
  "findings": []
}
```

The example is a shape, not a ready-made verdict. Replace IDs with actual reviewed
AC; select the actual status. For FAIL/BLOCKED put concrete findings or blockers in
`findings`; never output PASS with unresolved findings. Keep secret values out of
output. The controller checks the run's independent identity, contract/SHA,
environment, coverage and evidence before finalization; this JSON alone is not
VERIFIED or authorization to publish/merge/deploy.
