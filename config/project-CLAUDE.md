# CLAUDE.md

Claude Code instructions for Workwatch. All shared project rules — behavioral
guidelines, execution posture, **Mandatory verification commands**, product/architecture
invariants, environment & safety, ADR gates, beads — live in `AGENTS.md` (single source
of truth) and are imported below. This file adds only the Claude-specific layer:
the task dispatcher, skills, and sub-agent rules. When shared rules change, edit
`AGENTS.md`, not this file.

@AGENTS.md

---

# Task dispatcher (Claude Code)

Classify every request top-down — **first match wins**. When genuinely unsure between
tiers, treat it as the higher tier or ask one question. The omx routing section in
`AGENTS.md` is Codex-only; this dispatcher is the Claude Code equivalent.

**Signals to check before classifying:**
- ADR-gate trigger touched (`AGENTS.md` → _ADR gates_)? Formulas / status semantics,
  RBAC / visibility, ranking, schema strategy, sync, export architecture, auth/session,
  service boundaries, queue/broker, observability, rollout flags, request-path deps.
- New DB tables / columns / migrations? New endpoints? New dashboard section or route?
- How many layers touched: DB / sync / API / frontend / export?
- Real behavior change, or text/style only?

## Tier 2 — Heavy → `heavy-task-pipeline` skill

Triggers (any one): an ADR-gate trigger; a new dashboard section or feature with its
own business logic; ≥2 layers with a new or changed contract (e.g. new endpoints +
migrations + UI); a bug whose fix changes a formula or contract.

→ Invoke the **`heavy-task-pipeline`** skill: discuss (`grill-me`) → spec in
`docs/specs/` (+ ADR sign-off if gated — the only approval gate) → bd epic → research
(read-only sub-agents per layer) → plan (`writing-plans` → bd child issues) → execute
(one executor sub-agent per issue, TDD) → verify (independent reviewer sub-agents).

## Tier 1 — Standard (real behavior change, no gate; one layer or a thin slice)

Examples: a UI filter, a table column, a new endpoint that doesn't change
formulas/contracts.

1. 1–3 clarifying questions only if genuinely ambiguous (Superpowers `brainstorming`, brief).
2. bd issue: `bd create … -p <n>` → `bd update <id> --claim`.
3. Short plan for anything non-obvious (`writing-plans`); skip for the truly small.
4. Implement, tests-first where it fits (`test-driven-development`); sub-agents
   optional — direct for small, `subagent-driven-development` for larger.
5. Verify: the touched layer's Mandatory verification block + relevant contract tests
   + `verification-before-completion`. Close the bd issue.

## Tier 0 — Trivial (copy / label / locale / single-spot style or cosmetic tweak)

Apply directly per Karpathy guidelines (surgical, minimal diff). Verify only what's
relevant (`npm run typecheck && npm run lint`, or `test:s04-copy` for locale text).
bd issue optional (only if part of a tracked effort).

## Debugging — any tier

Superpowers `systematic-debugging` (reproduce → isolate → fix → prove). A fix that
changes a formula or contract becomes Tier 2. Runtime-/live-only failures (raw SQL via
SQLAlchemy `text()` / asyncpg, migrations, live-DB paths) → invoke the
**`runtime-sql-review`** skill (mandatory write→review loop; never self-approve).

# Skills map

| Situation | Skill |
|---|---|
| Tier 2 / heavy task | `heavy-task-pipeline` (project) |
| Deep design interview before code | `grill-me` (global) |
| Brief requirement clarification | `superpowers:brainstorming` |
| Implementation plan | `superpowers:writing-plans` |
| Executing a plan with sub-agents | `superpowers:subagent-driven-development` |
| Any bug / unexpected behavior | `superpowers:systematic-debugging` |
| Feature/bugfix implementation | `superpowers:test-driven-development` |
| Runtime-only SQL / migration fixes | `runtime-sql-review` (project) |
| Before claiming "done" | `superpowers:verification-before-completion` |
| Context handoff to a fresh session | `handoff` (global) |
| Coding hygiene (always) | `andrej-karpathy-skills:karpathy-guidelines` |
| Laziest-solution mode (every executor) | `ponytail` (plugin) |

# Sub-agent rules

- **Research / explore:** read-only sub-agents, parallel by layer; findings go into the
  spec or bd issue notes, not just the conversation.
- **Execute:** one bd issue = one sub-agent with a fresh context — pass spec/plan/issue
  paths, not a retelling of the conversation.
- **Verify:** always a separate reviewer/verifier sub-agent; the author never approves
  their own work in the same pass.
- **Models:** Opus by default; high effort for research, planning, and review agents.
  Executor sub-agents (one bd issue = one executor) run on **Opus 4.8, medium effort**
  (`model: opus 4.8`).
- **Ponytail (executors):** every executor sub-agent prompt MUST require the agent to
  invoke the `ponytail` skill as its first action and stay in it for the whole task —
  the laziest solution that works (YAGNI, stdlib first, shortest working diff). Plugin
  hooks don't reach Task-tool sub-agents, so this is enforced in the dispatched prompt,
  not by a hook. Reinforces Karpathy/Simplicity-First; does not relax TDD or the
  Mandatory verification gates. (Main-session Claude gets ponytail automatically via the
  plugin's SessionStart hook.)

# Claude-specific notes

- **Memory split:** `bd` (incl. `bd remember`) is for issues/tasks/backlog. The Claude
  Code memory system (`MEMORY.md` + `memory/`) stays in use for durable user/project
  preferences. Keep both; do not migrate one into the other.
- **Hooks:** SessionStart runs `bd prime`. Pipeline phases are NOT hooks — orchestration
  belongs to skills; hooks are reserved for deterministic enforcement.
- **Commits:** messages in Russian; push to `release` only after verification is green
  (see _Execution posture_ and _Session Completion_ in `AGENTS.md`).
