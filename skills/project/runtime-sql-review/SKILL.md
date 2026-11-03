---
name: runtime-sql-review
description: Mandatory write→review loop for runtime-/live-only fixes the test suite cannot catch — raw SQL via SQLAlchemy text() / asyncpg, migrations, queries, any live-DB path. Use BEFORE declaring such a fix done; a green author run is NOT done.
---

# Runtime-only SQL/migration fixes — write→review loop

Our backend tests are mostly SQL-text/mocks with no live DB, so failures in raw SQL
(SQLAlchemy `text()` / asyncpg), migrations, and live-DB query paths only manifest at
runtime. For these fixes a green author run is NOT "done".

## The loop (author never self-approves)

1. Track via `bd` (issue or child issue of the current epic).
2. **Write** the fix.
3. **Independent review pass**: a separate reviewer/verifier agent or clean reviewer
   session reviews the diff specifically for runtime SQL hazards (bind params, casts,
   transaction scope, migration reversibility). Select the model and delegation tools
   in the harness adapter; if no independent reviewer is available, report BLOCKED
   rather than substituting author self-review.
4. Approved? proceed. Rejected? fix → review again. Loop until the reviewer is clean.
5. The author never approves their own pass, and never in the same context as the write.

## Mandatory unit guard

Always add a unit test that catches the failure class WITHOUT a live DB:

- Compile `text(SQL)` and assert the **exact bind-parameter set** the statement exposes.
- Assert null-guarded params are **explicitly cast** to their type.

## Known footguns (caught in this repo)

- SQLAlchemy `text()` parses `:name` **anywhere** — including inside `--` comments.
  A stray `:name` / `::` in a comment becomes an unbound bind and fails at execute time
  with `A value is required for bind parameter ...`.
- asyncpg raises `AmbiguousParameterError` on a bare `:param is null` — cast the param
  to its type (`:param::int is null` / `CAST(:param AS int) IS NULL`).
- Prod smoke is required before declaring schema/sync/migration work done (see
  _Environment and safety_ in `AGENTS.md`): single prod environment, no separate stage.
