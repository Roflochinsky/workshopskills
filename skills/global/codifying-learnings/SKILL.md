---
name: codifying-learnings
description: Use when the user corrects you, repeats an instruction they gave before, or you notice you've made the same mistake or received the same feedback more than once.
---

# Codifying Learnings

## Overview

A correction that lives only in chat history dies at the next compaction — and the user has to repeat it, more annoyed each time. Every correction gets two responses: **fix the instance, then make the rule durable**. Apology without a guardrail is apology theater.

## The loop

1. **Fix the instance** fully (including ripple effects — importers, call sites, tests). Verify, don't just claim.
2. **Sweep**: did you make the same mistake elsewhere in this session's changes? Fix those too.
3. **Pick the durability layer** — the most mechanical one that fits:

| The rule is... | Codify as | Example |
|---|---|---|
| Mechanically checkable | Linter rule / formatter / pre-commit / hook | `import/no-default-export: error` |
| A project convention or fact | Project CLAUDE.md (one line, imperative) | "Named exports only" |
| A personal preference of the user, cross-project | Memory (or user-level CLAUDE.md) | "Explain the why before the detail" |
| A multi-step procedure ("when X, do A then B") | A skill (superpowers:writing-skills) | Release steps, review loop |
| "Every time X happens, run Y" automation | settings.json hook (update-config skill) | Format on save |

   Prefer the higher row when several fit: a lint rule beats a CLAUDE.md line beats memory — machines don't forget.

4. **Propose, don't smuggle.** Adding a CLAUDE.md line or memory entry: do it and say so. Changing lint/CI/hook config: propose with the exact change and ask — config edits affect the whole team.
5. **Close the loop out loud**: "Fixed + codified in X, so it won't recur." If you only fixed, say why you didn't codify.

## Trigger discipline

- Trigger on the **first** explicit correction — don't wait for the user to be annoyed twice.
- Also trigger without a correction: if you catch yourself re-learning something you clearly derived in a past session (an env quirk, a build flag, a footgun), codify it now.
- Before writing: check the rule isn't already recorded (CLAUDE.md, memory, lint config). Update the existing entry rather than duplicating; delete entries that turned out wrong.

## Red flags

| Thought | Reality |
|---|---|
| "I'll apologize and fix it" | Fix is half the job. Where does the rule live now? |
| "I'll remember next time" | You won't. Context compacts, sessions end. |
| "Too minor to write down" | Repeated correction = by definition worth one line. |
| "I'll add the lint rule silently" | Team-visible config needs a yes. CLAUDE.md/memory doesn't — just announce it. |
