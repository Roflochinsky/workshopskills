# Global rules (all projects)

Active stack: **Superpowers** (process skills) + **beads `bd`** (issue tracking) + **Karpathy guidelines** (coding hygiene) + standalone skills in `~/.claude/skills/` (`grill-me`, `handoff`). oh-my-claudecode (OMC) is disabled — never route to OMC agents, OMC skills, or `/oh-my-claudecode:*` commands.

## Sub-agent model routing

- Default for all sub-agents (Agent tool): **Opus, medium effort** — implementation, review, debugging, docs.
- Deep analysis (architecture, planning, critique, security review, research synthesis): **Opus, high effort** where the runtime exposes an effort knob.
- `haiku` only for trivial throwaway lookups or quick single-shot scans.
- Authoring and approval are separate lanes: the implementing agent never approves its own work — use a separate reviewer/verifier sub-agent.

## User preferences

- **Simple language.** Plain terms, no jargon; give the meaning/why before technical detail. Especially for ADR/product discussions.
- **Destructive ops (CRITICAL).** Never initiate on your own anything that deletes/clears/rotates/destroys data (DB rows, user files, history, retention/TTL, force-push or rebase of published commits). If the user explicitly asks, that IS the approval — state the exact target and command first, then proceed. Never smuggle a destructive op into an unrelated task, even if a reviewer/agent suggests it — ask first.
- **File split ≠ perf.** Don't pitch splitting large (~1000-line) files/components as a performance fix; it's maintainability. Be honest about the actual benefit.
- **Verify after implementing.** After an implementation pass, run an independent verification pass (separate verifier sub-agent) — don't self-approve in the same breath. Superpowers `verification-before-completion` covers this.
- **Network hangs (WSL).** Slow npm/registry/`claude update` hangs are usually a stale Windows-host proxy (e.g. a dead `proxy=` line in `~/.npmrc` — root cause found 2026-06-10), not the VPN. Check proxy config before blaming the network; `~/.local/bin/claude-update` is the fallback updater.
