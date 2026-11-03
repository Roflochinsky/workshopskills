# AGENTS.md

Shared agent rules for Workwatch: behavioral guidelines + project rules + verification protocol. This is the **single source of truth** for agent-agnostic project rules — Claude Code imports this file from `CLAUDE.md` (which adds only its Claude-specific dispatcher/skills layer), Codex reads it natively. When project rules change, change them HERE, not in both files. If rules conflict, prefer the safer interpretation and surface the tradeoff before coding.

---

# Behavioral guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# Workwatch project rules

## Execution posture
- The user is the product owner and source of truth for Workwatch decisions in this repository.
- **When the user asks for something, implement it to completion — no extra approval cycles, no re-litigating decisions the user has already made.** The user's request is the authorization.
- **The only approval gate is the ADR.** If a task requires creating a new ADR or changing an existing one (see _ADR gates_ below), stop, agree the decision with the user, then implement. Nothing else is gated.
- When the user confirms a product/metric/rollout/scope decision, treat it as approval to supersede older ADRs, plans, and docs that conflict. Record the supersession in the relevant ADR/plan/docs, then execute. Update or replace the conflicting older ADR rather than preserving legacy logic for compatibility.
- Safety reflexes still apply automatically: never commit or expose secrets; never use production data, resources, or URLs unless the user explicitly says `prod` (and never reach for external/other production systems the user has not pointed you to — see _Environment and safety_); before a destructive database or deployment action, state the exact target and command. These are reflexes, not approval gates — the user's explicit instruction is enough to proceed.
- Git: **auto-push is enabled.** Commit and push to `release` at the end of a work session, but only after the _Mandatory verification_ checks below are green. Normal pushes only — force-push or rebasing already-published commits still needs the user's explicit OK.

## Mandatory verification after writing code

**Rule:** After ANY code change, before reporting the work as done, run the checks for every layer you touched and paste the real command output. Never claim completion on green checks you did not run. If a check fails, fix it and re-run — do not report a partial pass.

### Backend — `backend/` (pip + venv baseline)

Runtime baseline is **pip + venv** (Python 3.12+). `requirements*.txt` are the canonical lock artifacts. **Do not use `uv` / `uv run`** — `backend/uv.lock` is not the source of truth and must not come back without a new ADR.

```bash
cd backend
source .venv/bin/activate
python -m ruff check .            # lint: E, F, I, B, UP (line-length 100)
python -m ruff format --check .   # formatting gate (pre-commit enforces ruff-format)
python -m mypy app                # static types
python -m pytest                  # full backend suite (testpaths = tests)
```

While iterating you may narrow (`python -m pytest -m <marker>` — auth, rbac, migration, formula, export, sync, data_quality, integration — or `tests/test_<domain>.py`), but the full run above is the completion gate.

### Frontend — `frontend/` (Node >= 24, npm >= 10)

```bash
cd frontend
npm run typecheck   # tsc --noEmit (strict)
npm run lint        # eslint .
npm run test        # orchestrates typecheck + lint + all contract gates
```

`npm run test` already chains: typecheck, lint, `test:p0-release-gate`, `test:static-route`, `test:login-assets-layout`, `test:s04-copy`, `test:s05-traceability`, `test:s06-grouping`, `test:settings-api-contract`. For auth / login / employee / group-status / KPI / norm-save changes also run `npm run test:e2e` (Playwright smoke).

### Which block to run
- Backend-only change → backend block. Frontend-only → frontend block.
- API contract touched on both sides → **both**, and regenerate OpenAPI/types if the contract changed.
- Schema / sync / auth / export / formula change → also record **prod smoke** notes (see _Environment and safety_).

## Workflow & skill routing (Codex / omx only — Claude Code uses the dispatcher in `CLAUDE.md` instead)
- This section applies when the session runs under **oh my codex (omx)** — it is launched with its own overlays (e.g. `omx --madmax --high`) and does built-in prompt routing. Don't try to "invoke omx"; it is the runtime. Your job here is the next layer: route each task to the right flow/skill.
- Per task, pick the flow/skill that matches the task type: discussion/research before unclear product or ADR decisions, planning for non-trivial implementation, quick execution for small scoped changes, debug for defects, UI review for visual/UX work, and code review before judging implementation quality.
- If the selected flow/skill requires user approval or business clarification, stop implementation and wait for the answer before changing code.
- **Default: every task runs through beads + the oh-my-codex flow** — open a `bd` issue, then plan → implement → independent review (write → review → ok? proceed : fix → review again). The ONLY exception is trivial cosmetic changes — e.g. editing KPI-card text/a label, adding a button to the frontend menu, a single-spot copy/style tweak — which may be done directly, no `bd` issue and no review pass. When unsure whether a task is trivial, treat it as non-trivial and use the full flow.

## Runtime-/live-only bug fixes — mandatory write→review loop (all agents)
When the failure only manifests at runtime and the repo's tests can't catch it (raw SQL via SQLAlchemy `text()` / asyncpg, migrations, queries, any live-DB path — backend tests are mostly SQL-text/mocks, no live DB), a green author run is NOT "done": loop write → independent review (separate reviewer/verifier subagent) → fix → review until clean, and always add a unit guard that catches the failure class without a live DB. Full procedure and the known SQL footguns: `.claude/skills/runtime-sql-review/SKILL.md` (Claude invokes it as the `runtime-sql-review` skill; Codex reads the file).

## Read before non-trivial work
1. `docs/PRD_Workwatch_Dashboard_v2.3_Codex.md`
2. `docs/PROJECT_PLAN_ADR_STAGES.md`
3. `docs/ARCHITECTURE.md`
4. `docs/STAGE_NEON.md` (historical — Neon no longer used; see _Environment and safety_)
5. `docs/ADR_INDEX.md`
6. Relevant ADR files in `docs/ADR/`
7. `PLANS.md`

## Product and architecture invariants
- Product: Workwatch Dashboard for monitoring activity and idle time of production staff.
- Architecture: modular monolith.
- Deployables: `web`, `api`, `worker`.
- Data store: a single local PostgreSQL instance on the host (no-docker; processes run under supervisor). This is the production database (`stage = prod`); Neon is no longer used (`docs/STAGE_NEON.md` is historical).
- FastAPI owns business APIs, metric formulas, filtering, RBAC scope, and authoritative exports.
- Next.js owns UI composition, routes, layouts, filters, tables, and charts.
- Do not add a generic Next.js proxy/BFF by default.
- Do not duplicate metric formulas in the frontend.
- Data flow is `Workwatch source -> raw/staging -> curated tables -> aggregates/views -> FastAPI -> Next.js`.
- The online request path must never query the external Workwatch source database.
- MVP is batch-oriented, not realtime.
- Export is required on every core screen and must respect filters and RBAC.
- Settings and access-control changes must be audited.
- Risky user-visible features should be behind feature flags.

## Environment and safety
- There is a single environment, and it is **production** (`stage = prod`): a local PostgreSQL instance on the host, with `web` / `api` / `worker` run under **supervisor** (no-docker setup). Neon is no longer used; `docs/STAGE_NEON.md` is historical only.
- Product-owner operating decision (2026-05-29, supersedes the 2026-05-21 "stage is a prod-like sandbox" decision): this local-Postgres / supervisor environment holds **real production data**. Treat it as prod for code, architecture, migrations, sync, worker runtime, and all safety gates. There is no separate sandbox — verification runs against this prod environment, so act accordingly.
- Push project changes to `release` by default for the current GitLab release flow unless the user explicitly asks for another branch. The older `develop` default is superseded for this GitLab release flow.
- Our branch is `release` — we build, verify, and run prod from it. There is no `master` promotion step in this flow; do not push to or treat `master` specially without the user's explicit instruction.
- Never reach for external/other production secrets, databases, or URLs the user has not pointed you to; this local prod environment is the only target unless the user explicitly says otherwise.
- Never hardcode connection strings, passwords, API keys, service-role keys, or tokens.
- Schema, sync, auth, export, and formula changes require verification notes captured against this prod environment.
- Because there is no separate stage, **destructive migrations are especially dangerous**: they require an explicit plan, a rollback path, and a rehearsal on a disposable throwaway copy of the database (never against live prod data) before running on prod.
- If a change requires a host/runtime action — a **supervisor** service restart, a DB migration, an environment-variable change, etc. — explicitly notify the user and provide the exact target, service, and commands. (Docker/compose is no longer the deployment mechanism.)

## ADR gates
Write or update an ADR before changing:
- auth/session model
- RBAC or organizational visibility semantics
- metric formulas or status semantics
- ranking formula or ranking weights
- database schema strategy
- Workwatch source sync strategy
- export architecture
- service boundaries
- queue/broker usage
- observability baseline
- feature flag or rollout strategy with production impact
- dependency that enters the request path

## Business approval gates
Do not implement the following until the corresponding blocked ADR is accepted:
- final rating score formula and `W1/W2` weights
- any ranking/compare UI that depends on the final score formula
- broadened role visibility beyond the conservative RBAC matrix
- map integration format and optional route/Sankey flows
- any customer-facing semantic change to activity, idle, long-idle, status, or KPI definitions

## Default delivery style
- Plan first for any non-trivial task.
- Implement the smallest vertical slice that proves user value end-to-end.
- Prefer tests for formulas, RBAC, filters, sync idempotency, exports, and settings audit.
- Use prod smoke checks before declaring schema, sync, auth, export, or formula work done.
- Report changed files, verification commands, unresolved risks, and rollback path.

## Avoid by default
- microservices
- Kafka/RabbitMQ/event buses
- additional datastores
- realtime streaming
- broad refactors unrelated to the task
- speculative abstractions
- frontend-owned authoritative XLSX generation
- localStorage/sessionStorage tokens

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for durable task/issue tracking and backlog (with dependencies) — prefer it over markdown TODO lists for anything that outlives the current turn
- Run `bd prime` for detailed command reference and session close protocol
- `bd` (incl. `bd remember`) is for issue/task tracking. The Claude Code memory system (`MEMORY.md` + `memory/`) stays in use for durable user/project preferences. Keep both; do not migrate one into the other.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

When wrapping up a work session:

1. **File issues for remaining work** with `bd` — anything that needs follow-up.
2. **Run the quality gates** (Mandatory verification above) if code changed.
3. **Update issue status** — close finished work, update in-progress items.
4. **Commit and push** (auto-push enabled) — only after the quality gates are green:
   `git pull --rebase && git push && git status` (must end up-to-date with origin).
   Normal push only; never force-push or rebase published commits without the user's
   explicit OK.
5. **Mirror beads to Linear**: `bd linear sync --push` (push-only mirror, Linear team
   «green_dash»; needs `LINEAR_API_KEY` in the shell env — see
   `docs/superpowers/specs/2026-06-10-beads-linear-mirror-design.md`). Linear is
   read-only for humans; bd/Dolt stays the source of truth.
   **Epics → Linear Projects** (convention since 2026-06-12): `bd linear sync` pushes
   a bd epic as a plain issue; when creating a NEW bd epic, additionally create a
   Linear **Project** in team green_dash (via the Linear MCP `save_project`, name =
   epic title, description links the bd id) and attach the epic's mirrored issues to
   it (`save_issue` with `project`). The sync does not touch the project field, so
   the assignment survives subsequent pushes.
6. **Hand off** — summarize what changed, what's verified, and what's left.
<!-- END BEADS INTEGRATION -->
