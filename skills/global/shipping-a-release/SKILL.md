---
name: shipping-a-release
description: Use when implementation is complete and the user explicitly asks to wrap up, ship, release, merge, or publish the work. Never self-initiate a release.
---

# Shipping a Release

## Overview

Completion is an agent's blind spot: work stranded on branches, versions guessed, changelogs forgotten, "shipped" claimed while CI is still running. This is a checklist pipeline — run it top to bottom, only on the user's explicit ask.

Copy this checklist and check items off as you go:

```
Ship Progress:
- [ ] 1. Verification AFTER the last edit
- [ ] 2. Diff review
- [ ] 3. Version + changelog per repo convention
- [ ] 4. Commit (explicit paths)
- [ ] 5. PR / merge through CI
- [ ] 6. Honest status report
```

## 1. Verification after the LAST edit

A green run before your latest edits proves nothing. Re-run now: full test suite, lint/typecheck, build, and the project's mandatory verification block if CLAUDE.md defines one. Then **run the actual app and observe the shipped feature working** (use the project's run skill / `verify`) — unit tests passing is not the feature working. If anything fails: stop, fix, re-run. "Ship broken fast" is never an option.

## 2. Diff review

`git diff` against the base branch, looking for: debug leftovers, accidental files, secrets, unrelated changes. If the diff is more than trivial, dispatch a fresh-context reviewer sub-agent (superpowers:requesting-code-review) — a 60-second self-skim under time pressure is how bugs ship.

## 3. Version + changelog — by convention, not by guess

Check how THIS repo versions: `git tag -l | tail`, recent release commits, CHANGELOG format, release config (semantic-release, changesets, etc.). If tooling automates versioning — don't fight it. If manual: bump per semver from the actual change type, add the changelog entry for this release only (don't backfill history silently — note it as follow-up).

## 4. Commit

Explicit paths (`git add <files>`), never `-A` blindly. Message per repo convention (check `git log`). Reference the issue it closes.

## 5. PR / merge — CI is the gate

- Push the branch; create a PR with real context: what, why, how verified, what's deferred.
- **Never bypass CI**, never force-merge, never push directly to a deploy branch to save time. If the user is leaving: arm auto-merge (`gh pr merge --auto`) so it lands when checks pass.
- Force-push or rebase of published commits — only with the user's explicit OK.

## 6. Honest status report

- CI green and merged → "shipped".
- Auto-merge armed, CI running → "queued to ship", NOT "shipped". Never claim a deploy you haven't observed.
- Report: what shipped, verification evidence, corners explicitly cut (and they must be named), follow-ups filed in the tracker.

## Red flags — you are rationalizing

| Thought | Reality |
|---|---|
| "Tests were green 10 minutes ago" | Before your last edits = unknown state. Re-run. |
| "User leaves in 10 min, skip the smoke run" | A feature nobody watched working is unverified. Say "queued", verify after, or do it now. |
| "Minor bump, obviously" | The repo's convention decides, not your intuition. Check tags first. |
| "I'll merge directly, CI is slow" | CI is the only verification beyond your machine. Auto-merge exists for exactly this. |
| "I'll quietly skip the changelog" | Skipping is fine only when said out loud and filed as follow-up. |
