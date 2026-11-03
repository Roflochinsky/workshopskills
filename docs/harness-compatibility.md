# LAW skill compatibility

Checked against official documentation on **2026-11-03**.

## Scope and evidence

This guide covers `factory-system-analyst` and the portable procedure in
`heavy-task-pipeline`, with `grill-me` and the project's SQL review flow.
It does not certify every other skill or configuration in this repository.

The shared format is a directory with `SKILL.md`, YAML `name` and `description`,
and Markdown instructions. Supporting files remain relative to that directory.
The workflow does not depend on a particular model, slash command, delegation
tool, UI, or orchestration plugin. Host permissions still apply.

| Host | Compatibility evidence | Execution in the real application |
| --- | --- | --- |
| Codex CLI / IDE | Documented local skill format and discovery | `NOT_RUN` |
| Cursor Agent | Documented Agent Skills and project instructions | `NOT_RUN` |
| OMP | Documented skill format, compatible directories and context files | `NOT_RUN` |
| Tern | Documented agent hosting; skill behavior belongs to its selected harness | `NOT_RUN` |

Documentation and structural inspection establish an integration path. They do
not establish that a particular installed version loaded the intended files or
followed the workflow. Complete the smoke check below in the target environment.

## One canonical installation

Keep one maintained copy of each skill in the target project's `.agents/skills/`.
Install whole skill directories, including `references/` and any other bundled
resources. The `global/` and `project/` directories organize this source bundle;
they are not additional levels to retain below the installed skill root.

| Source in this repository | Destination in the target project |
| --- | --- |
| `skills/project/factory-system-analyst/` | `.agents/skills/factory-system-analyst/` |
| `skills/project/heavy-task-pipeline/` | `.agents/skills/heavy-task-pipeline/` |
| `skills/global/grill-me/` | `.agents/skills/grill-me/` |
| `skills/project/runtime-sql-review/` | `.agents/skills/runtime-sql-review/` |

The first three skills are required for this workflow. Install `runtime-sql-review`
for the project's SQL/migration flow. Preserve any other required project skills.
Do not overwrite existing copies without comparing their contents and ownership.
Avoid parallel copies with the same name in user, native, or compatibility roots.

Merge the relevant routing from `config/project-AGENTS.md` into the target's
existing `AGENTS.md`; adapt project-specific facts instead of overwriting local
instructions. Keep analysis rules in the analyst skill and orchestration in the
pipeline. An explicit instruction to read a file is portable; `@path` import
semantics are not identical across hosts.

## Discovery and explicit invocation

| Host | Project discovery | Explicit invocation and inspection |
| --- | --- | --- |
| Codex | Scans `.agents/skills` from the working directory to the repository root; follows skill-directory symlinks. | Use `$factory-system-analyst` or select through `/skills`. Inspect the resolved file path. |
| Cursor | Supports `.agents/skills/` and `.cursor/skills/`, plus compatible Claude/Codex locations; supports nested skill directories. | Type `/` in Agent chat and select `factory-system-analyst`. Check the loaded source. |
| OMP | Supports `.agents/skills/`; native locations are `.omp/skills/` and `~/.omp/agent/skills/`. Discovery is one skill-directory level deep. | Use `/skill:factory-system-analyst`; inspect Skills in `/extensions`. Run `/reload-plugins` after skill edits. |

Codex requires `name` and `description`; Cursor also requires the name to match
the containing directory. Supplying both fields with matching names works for
OMP as well. Do not depend on implicit description matching to run a mandatory
pipeline stage: explicitly load the skill through the host or read its file.
See [Codex skills][codex-skills], [Cursor skills][cursor-skills], and
[OMP skills][omp-skills].

Codex does not merge same-name skills; both can appear in selectors. Cursor's
local user skills are not automatically present in every remote/cloud environment.
Ensure the canonical project files exist in the actual checkout or worktree.

### OMP shadowing and project instructions

OMP does not merge same-name skills. Explicit custom directories override default
discovery; otherwise provider priority and project proximity select a copy.
Use `/extensions` to confirm the active path and identify shadowed copies.
Name filters and disabled providers can also make an installed skill unavailable.

Context files have separate precedence. At the same directory depth,
`.omp/AGENTS.md` can shadow the standalone `AGENTS.md`; other providers can also
win. Inspect Context Files in `/extensions`, not merely the filesystem.
After context-file changes, start a new OMP session and recheck the active source.
Do not create a second full policy file to work around discovery.
See [OMP context files][omp-context].

Codex reads applicable `AGENTS.md` files, but `AGENTS.override.md` wins at the same
directory level. Cursor supports root and nested `AGENTS.md`. Confirm that the
effective instructions point to the same LAW workflow in either host.
See [Codex project instructions][codex-agents] and [Cursor rules][cursor-rules].

## Tern is the host, not a separate skill contract

The name refers to two different products in the architecture discussion:

- [Tern from Stencil][tern-stencil] runs agent blocks using `agent-command`, whose
  documented default is `omp`. With that command, apply the OMP setup above.
- [Tern at tern.build][tern-build] starts a selected installed CLI agent in a
  worktree or the current workspace. Apply that agent's skill discovery rules.

For either product, identify the actual agent command, working directory, and
version. Do not infer a separate Tern skill loader, universal slash command,
automatic skill synchronization, or equal support for every agent UI feature.

## Orchestration adapters and required gates

Superpowers may supply `writing-plans`, `subagent-driven-development`,
`requesting-code-review`, and `verification-before-completion` where installed.
Treat these as optional execution adapters to the pipeline's required outcomes.
Their absence does not remove analysis, ADR, planning, or verification gates.

Use available delegation APIs without hard-coded tool or model identifiers.
Research can be sequential when parallel workers are unavailable. Independent
verification must still use a separate reviewer agent/session with fresh context
from the artifacts. If none is available, record the review as blocked; do not
replace it with author self-review or claim completion.

If the project's instructions require Beads, `bd` remains required. Missing `bd`
blocks the dependent tracking stage; it does not authorize a substitute tracker.
Continue useful analysis that does not depend on it and report the exact blocker.

## Minimal smoke check in the target environment

1. Start the chosen harness in the target project. Record its version and working
   directory, then inspect the active instruction and skill source paths.
2. Explicitly apply `factory-system-analyst` to a small task with one documented,
   already accepted decision. Confirm it reads the canonical spec/profile and
   does not ask for that decision again.
3. Include a material unanswered business rule. Confirm the analysis reports the
   gap, traces requirements to observable acceptance criteria, and blocks the
   affected implementation instead of inventing the rule.
4. Resolve that gap in the fixture. Confirm analysis readiness remains distinct
   from implementation admission, and existing ADR requirements still apply.
5. Check the pipeline handoff: spec/version and requirement IDs reach the plan,
   Beads issues, and an independent reviewer. Record unavailable capabilities.

Save the observed paths, versions, results and remaining blockers with the task's
existing evidence. Replace `NOT_RUN` only for environments actually exercised.

[codex-skills]: https://learn.chatgpt.com/docs/build-skills
[codex-agents]: https://learn.chatgpt.com/docs/agent-configuration/agents-md
[cursor-skills]: https://cursor.com/docs/skills
[cursor-rules]: https://cursor.com/docs/rules
[omp-skills]: https://omp.sh/docs/skills
[omp-context]: https://omp.sh/docs/context-files
[tern-stencil]: https://docs.stencil.so/tern/scripts/sessions.html
[tern-build]: https://tern.build/docs
