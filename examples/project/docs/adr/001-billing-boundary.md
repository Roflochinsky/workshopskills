# ADR-001: retain the public billing function

Status: accepted, as part of the synthetic example policy.

The defect is a local arithmetic rule. Keep `billed_minutes(seconds)` and its
existing input validation. A new billing engine or abstraction would add no
behavior required by REQ-1, REQ-2 or INV-1. Verify through the public function.
No additional user approval is required for the already accepted decision.
