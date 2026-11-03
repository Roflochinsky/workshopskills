# Claude Code — воркшоп-бандл (конфиги + self-hosted скиллы)

Набор для коллег: правила поведения агентов (CLAUDE.md / AGENTS.md) + мои
self-hosted скиллы. Проектные конфиги содержат соглашения Workwatch; перед
установкой в другой проект адаптируйте их к его фактическим правилам.

## Что внутри

```
config/
  global-CLAUDE.md          # глобальные правила (все проекты) → ~/.claude/CLAUDE.md
  project-CLAUDE.md         # правила проекта (Claude-слой: диспетчер + скиллы) → <repo>/CLAUDE.md
  project-AGENTS.md         # единый источник правил проекта (agent-agnostic) → <repo>/AGENTS.md
  home-CLAUDE.md.optional   # доп.: beads-шаблон, лежал в $HOME (по желанию)
skills/
  global/                   # мои self-hosted скиллы (ставятся для всех проектов) → ~/.claude/skills/
  project/                  # скиллы конкретного проекта → <repo>/.claude/skills/
```

## Куда класть на машине коллеги

| Файл из бандла | Назначение |
|---|---|
| `config/global-CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `config/project-CLAUDE.md` | `<repo>/CLAUDE.md` |
| `config/project-AGENTS.md` | `<repo>/AGENTS.md` |
| `skills/global/*` | `~/.claude/skills/*` (каждый скилл — своя папка с `SKILL.md`) |
| `skills/project/*` | `<repo>/.claude/skills/*` |

Скиллы Claude Code подхватывает из этих папок при старте сессии (перезапустить
`claude` после копирования).

## Как устроены правила

- **AGENTS.md** — единый источник agent-agnostic правил проекта (поведение,
  verification-гейты, ADR-гейты, beads, безопасность). Claude импортирует его из
  `CLAUDE.md` через `@AGENTS.md`; Codex читает напрямую.
- **project-CLAUDE.md** — только Claude-слой поверх AGENTS.md: диспетчер задач
  (Tier 0/1/2), карта скиллов, правила сабагентов.
- **global-CLAUDE.md** — личные правила для всех проектов (стек, предпочтения,
  роутинг моделей сабагентов).

## Self-hosted скиллы (что это и зачем)

Каждый скилл — папка с `SKILL.md` (frontmatter `name`/`description` + инструкция).
Claude вызывает их по описанию через Skill-tool.

**Глобальные (`skills/global/`)** — переиспользуемый процессный набор:
`classifying-tasks`, `delivering-heavy-features`, `decomposing-to-issues`,
`grill-me` (design-интервью), `handoff`, `onboarding-codebase`,
`getting-second-opinion`, `fixing-incidents`, `shipping-a-release`,
`upgrading-dependencies`, `codifying-learnings`, `doctor`.

**Проектные (`skills/project/`)**:

- `factory-system-analyst` — LAW: Requirements & Analysis: исследование системы,
  полнота и согласованность требований, инварианты, негативные сценарии,
  критерии приёмки, прослеживаемость и оценка готовности spec.
- `heavy-task-pipeline` — Tier-2 конвейер; использует аналитика и `grill-me`,
  сохраняет ADR-гейт, Beads, планирование, реализацию и независимую верификацию.
- `runtime-sql-review` — write→review цикл для runtime-only SQL/миграций.

### LAW в Tern ADE, Codex, Cursor и OMP

Ядро аналитика и `heavy-task-pipeline` не требуют определённой модели или API
субагентов. Подключайте отдельные каталоги навыков в `.agents/skills/<name>/`,
сохраняя `references/`, и загружайте действующие инструкции проекта. Не переносите
уровни `global/` и `project/` внутрь каталога discovery. Для Claude Code остаются
пути установки из таблицы выше.

[Подключение и ограничения совместимости](docs/harness-compatibility.md) описывают
конкретные пути, команды, два продукта с названием Tern и проверку перекрытия
навыков/инструкций в OMP. Переносимость этого LAW-контура не означает, что весь
исторический бандл перестал содержать Claude-specific настройки.

[Навык аналитика](skills/project/factory-system-analyst/SKILL.md) владеет правилами
готовности. `ANALYSIS_READY` означает завершённый анализ; допуск к реализации
проверяет pipeline с учётом ADR и плана. Это не новое согласование пользователя.
Профиль проекта — ссылки на существующие соглашения; отдельный профиль и новый
формат spec не обязательны. Опциональные примеры находятся в `references/` навыка.

## Внешние зависимости (в бандл НЕ входят — это маркетплейс-плагины, не self-hosted)

Конфиги ссылаются на плагины, которые ставятся отдельно через
`claude plugin marketplace add` + `claude plugin install`:
- **Superpowers** (`brainstorming`, `writing-plans`, `subagent-driven-development`,
  `test-driven-development`, `verification-before-completion`, …)
- **beads** (`bd`) — issue-трекер
- **andrej-karpathy-skills** (`karpathy-guidelines`)
- **ponytail** (laziest-solution mode) — опционально

В переносимом LAW-конвейере Superpowers — необязательные адаптеры: при их отсутствии
агент выполняет описанные действия доступными средствами. Это не отменяет
обязательные проверки и независимое review. `bd` остаётся обязательным там, где
его требует проект. Остальные исторические навыки могут иметь собственные
зависимости; их совместимость нужно проверять отдельно.

## ⚠️ Перед шерингом просмотри

- `config/global-CLAUDE.md` — содержит мои машинно-специфичные заметки
  (WSL/прокси/пути памяти). Не секреты, но стоит вычистить личное.
- `config/project-AGENTS.md` — содержит внутренние правила проекта (ветка
  `release`, GitLab-флоу, prod-окружение). Убери, если делишься вне команды.
- В бандле нет секретов (токены/коннекшн-строки правилами запрещены), но
  пробегись глазами перед отправкой.
