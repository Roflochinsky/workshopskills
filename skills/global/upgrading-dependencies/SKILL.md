---
name: upgrading-dependencies
description: Use when asked to update, upgrade, or bump dependencies, fix dependency vulnerabilities, or when CI flags outdated/vulnerable packages — before running any upgrade command.
---

# Upgrading Dependencies

## Overview

"Upgrade everything" in one commit with several majors is a week of bisecting. Agents fail this task in two ways: bulk-bumping without reading changelogs, and "fixing" the resulting test failures by adapting assertions to the broken behavior. Stage the work; every stage independently verified and revertable.

## Process

1. **Ground truth**: clean tree, dedicated branch, capture `outdated` + `audit` (or the ecosystem's equivalents). Map vulnerabilities to packages — security-load-bearing upgrades get priority and define what "done" means for the CI nag.
2. **Baseline**: full test suite BEFORE touching anything. Pre-existing failures get noted, not chased later as your regressions.
3. **Patch + minor bumps in one commit.** Auto-fix tooling without force flags (`npm audit fix`, never `--force` — it silently installs breaking majors). Test, lint, build. Commit.
4. **Majors one at a time**, easiest → hardest, security-relevant first; **one commit per major**:
   - Read the migration guide / changelog BEFORE bumping — not after tests break.
   - Scope the blast radius (`grep` usage sites). A major touching 50+ files is its own tracked task — file it and say so, don't bury a framework migration at the bottom of a deps PR.
   - Fix breakages by adapting to the new API. Never by loosening assertions, mass-updating snapshots unread, or downgrading lint rules wholesale.
5. **Independent verification**: clean install from the new lockfile (`npm ci`), full suite, build, audit re-check (the original advisories must be GONE), smoke the app's main flows — router/HTTP-client changes are exactly what unit tests miss. Fresh-context reviewer over the diff for non-trivial majors (getting-second-opinion).
6. **Report**: what was bumped, what was deliberately deferred (with filed issues), audit status before/after.

## Red flags

| Thought | Reality |
|---|---|
| "I'll bump everything and see what breaks" | What breaks is your afternoon. Stage it. |
| "`audit fix --force` clears the warnings" | By installing breaking majors silently. Never. |
| "Tests fail — I'll update the assertions" | The assertion was the spec. Adapt the code to the new API, or revert the bump. |
| "Snapshots changed, regenerate them all" | Unread snapshot updates launder regressions. Eyeball the diffs. |
| "The router major fits in this PR too" | A migration guide with sections is a separate task. File it. |
