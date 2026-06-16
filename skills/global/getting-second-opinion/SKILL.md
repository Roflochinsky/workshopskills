---
name: getting-second-opinion
description: Use when about to approve, merge, or sign off on non-trivial work you authored yourself — especially when feeling confident, when the user says "I trust your judgment", or when your own tests pass.
---

# Getting a Second Opinion

## Overview

The context that wrote the solution cannot see its defects — the same blind spots authored the code AND the tests. Confidence is not evidence; "the user trusts me" raises the cost of being wrong, it doesn't lower the bar. Authoring and approval are separate lanes, always.

## When it fires

Non-trivial work you wrote, about to be merged/shipped/signed off: code, but equally plans, specs, ADRs, migration strategies. Trivial diffs (copy, single-spot tweaks) don't need it.

## How

1. **Fresh context, hostile brief.** Dispatch a reviewer sub-agent that did NOT author the work (superpowers:requesting-code-review). The brief names the specific failure modes of THIS kind of artifact — "try to refute that this sliding-window limiter is atomic under concurrent instances", not "review this code". A reviewer told what to attack finds what a polite one compliments.
2. **Distinct lenses, not N identical passes.** For bigger work, 2–3 reviewers with different angles: correctness/races, simplicity (did the author overbuild?), conventions/security. Diversity catches what redundancy can't.
3. **Cross-model or cross-tool opinion** where available (a different model, a linter/analyzer pass) — different training = different blind spots.
4. **Surface the product decisions.** A reviewer can't approve what is actually the user's call (fail-open vs fail-closed, defaults, data backfills). Extract those into one yes/no message to the user instead of burying them in an "approved" verdict.
5. **Loop: fix → re-verify → re-review.** A fix without a re-run is just confidence again. Repeat until the reviewer is out of findings, then report WITH the evidence: test counts, reviewer verdict, decisions confirmed.

## Red flags

| Thought | Reality |
|---|---|
| "My tests pass and I'm confident" | Your tests share your blind spots. That's why they pass. |
| "The user said they trust me" | Trust delegates the work, not the verification. |
| "A review will take too long" | Ten minutes of hostile review vs a production incident in your proudest feature. |
| "I'll review it myself carefully" | Same context = same blind spots, however careful. |
| "The reviewer approved, ship it" | Did the reviewer see the product decisions, or did you decide those silently? |
