---
name: doctor
description: Use before running heavy composite workflows (delivering-heavy-features etc.), when a required skill or tool is missing, when setting up a new machine or project for these skills, or when the user asks to check that the skill stack is healthy.
---

# Doctor

## Overview

Composite workflow skills depend on other skills and tools being installed and wired. Doctor verifies the stack, reports what's missing, and — with the user's consent — installs and wires it. Never install or edit anything without asking first.

## 1. Check — run these and build a status table

| Component | Check | Healthy when |
|---|---|---|
| Superpowers plugin | `grep -o 'superpowers' ~/.claude/plugins/installed_plugins.json` or `ls ~/.claude/plugins/cache/*/superpowers/*/skills/` (the Skill tool listing is not shell-checkable) | Plugin installed; skills dir contains brainstorming, writing-plans, subagent-driven-development, verification-before-completion |
| This collection's skills | Diff the source repo against installed: `comm -23 <(ls <repo>/skills/) <(ls ~/.claude/skills/)` where `<repo>` is your clone of this collection | Empty output — every `skills/<name>` from the repo present in `~/.claude/skills/` (symlink or copy), each with SKILL.md. grill-me/handoff count if you use them |
| beads (tracker) | `command -v bd && bd version` | Installed |
| beads in project | `test -d <project-root>/.beads` — do NOT use `bd ready` as the check: it walks up parent dirs and exits 0 against `~/.beads`, a false positive | Dir exists (only if a project is open) |
| Project CLAUDE.md routing | Project CLAUDE.md mentions task tiers / routes heavy tasks to a pipeline skill | Routing line exists; it must NAME the skill, not retell its process |
| Name collisions | `sort <(ls ~/.claude/skills/) <(ls .claude/skills/ 2>/dev/null) <(ls ~/.claude/plugins/cache/*/*/*/skills/ 2>/dev/null) \| uniq -d` | Empty — no skill name duplicated across personal / project / plugin namespaces (collisions resolve unreliably — rename) |
| Description budget | Startup warnings about skill descriptions exceeding the listing budget (session start output; `claude doctor` is an interactive TUI and does not report this) | No overflow warnings |

Report the table to the user: OK / MISSING / MISCONFIGURED per row, one line each.

## 2. Ask — before changing anything

Use one batched question round:

1. **Install missing skills + beads?** (Recommended: yes.)
2. **Wire this project's CLAUDE.md?** (Add the routing block below.) Show the exact diff before writing.

If the user declines a component, note which workflows degrade (e.g. without beads, decomposition falls back to markdown plans — worse persistence) and proceed with the rest.

## 3. Fix — only what was approved

- **Superpowers**: `claude plugin marketplace add obra/superpowers-marketplace && claude plugin install superpowers@superpowers-marketplace`
- **This collection**: clone the repo, then symlink each `skills/<name>` into `~/.claude/skills/<name>` (symlinks keep one source of truth; `cp -r` if the filesystem can't symlink).
- **beads**: install per https://github.com/steveyegge/beads#installation (check README for the current command — do not guess one). Then `bd init` in the project if the user wants project tracking.
- **CLAUDE.md routing block** (adapt tiers to the project; keep it to routing — the process lives in the skills):

```markdown
# Task dispatcher
Classify every request with the classifying-tasks skill before acting.
Heavy tasks → delivering-heavy-features skill. Shipping → shipping-a-release skill (explicit ask only).
<Project-specific gates and verification commands go here.>
```

## 4. Re-check

Re-run the checks after fixing; report the final table. Done = all approved rows healthy, not "commands executed".

## Red flags

| Thought | Reality |
|---|---|
| "I'll just install it, the user obviously wants it" | Installs and config edits get a yes first. Always. |
| "The routing text can summarize the pipeline" | Summaries get followed INSTEAD of the skill. Route by name only. |
| "Check passed last week" | Plugins update, machines change. Re-check before each heavy run is cheap. |
