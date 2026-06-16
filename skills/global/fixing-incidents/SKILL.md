---
name: fixing-incidents
description: Use when production is down or degraded, users are reporting errors, or the user demands an urgent fix ("prod is down", "fix it now", "clients are calling") — before taking any recovery action.
---

# Fixing Incidents

## Overview

Panic mode is where agents cause the second incident: destructive commands justified by urgency, restarts that erase the evidence, "fixed" claimed while the root cause reloads. The order below is non-negotiable. "I don't care how" from a panicking user authorizes speed — it does NOT authorize destructive or irreversible actions.

```
Incident Progress:
- [ ] 1. Confirm symptom (30s)
- [ ] 2. Snapshot evidence BEFORE mitigating
- [ ] 3. Mitigate: smallest reversible action
- [ ] 4. Verify recovery + watch for recurrence
- [ ] 5. Root cause + follow-ups (now, not "later")
```

## 1. Confirm the symptom (~30 seconds)

Service status, a real request to the failing endpoint, the current error in the logs (not stale ones). You're verifying the incident is what the user says it is — pattern-matching a symptom to a remembered failure is how the wrong service gets restarted.

## 2. Snapshot evidence BEFORE mitigating

Restarts destroy the bad state you need for diagnosis, and an undiagnosed incident repeats within hours. Spend 30–60 seconds capturing to a file (`/tmp/incident-<date>.txt`): relevant process/connection/queue state, the failing components' logs, resource usage. Then mitigate.

## 3. Mitigate: smallest reversible action first

- Escalation ladder: restart your own app processes → terminate specifically identified stuck resources (with the user told what and why) → config change with a noted rollback. Each rung only if the previous one didn't restore service.
- **Never, regardless of pressure**: drop/truncate data, blanket-kill all DB sessions, restart the database when the app is the problem, push code changes straight to prod unreviewed, disable auth/safety checks "temporarily".
- Before any action from the middle of the ladder: one line to the user — exact target and command. Urgency makes this one line, it doesn't delete it.

## 4. Verify recovery — separately from "the command succeeded"

Real requests through the real ingress, watch logs/metrics for 1–2 minutes for recurrence. A climbing resource counter means you bought minutes, not a fix — say so.

## 5. Root cause + follow-ups, immediately

The evidence snapshot from step 2 points at the cause. Investigate now (superpowers:systematic-debugging); the code fix goes through normal review — a hotfix branch, not vim-on-the-server. File follow-ups: the fix, the missing alert that would have caught this earlier, the postmortem note. Report: what restored service, what the root cause is (or the concrete next diagnostic step), what was deliberately NOT done.

## Red flags

| Thought | Reality |
|---|---|
| "User said 'I don't care how'" | They care tomorrow. Speed yes, destruction no. |
| "Restart first, look later" | Restart erases the diagnosis. 60 seconds of snapshot first. |
| "I'll kill all DB connections to be sure" | Blanket kills roll back live transactions. Target the specific stuck ones. |
| "Service is back, incident over" | Without root cause it's an intermission. Investigate now. |
| "I'll hotfix the code right on the box" | Unreviewed prod edits are the next incident. Branch + fast review. |
