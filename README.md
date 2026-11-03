# Workshopskills — LAW Software Factory для Pi / OMP

Исполняемый контур LAW: ведущий агент уточняет задачу и поддерживает spec/ADR,
Python-контроллер допускает реализацию и хранит evidence, Pi или OMP выполняет
ограниченную роль, отдельный reviewer проверяет результат. Готовность зависит от
актуального контракта, конкретного Git SHA, среды и фактически выполненных проверок.

Методика навыков не зависит от модели или агентного харнесса. Исполняемые адаптеры
этого контура — Pi и OMP; правила проекта и навыки можно использовать из Tern ADE,
Codex и Cursor с внешним контроллером. Нативных адаптеров Codex/Cursor здесь нет.

## Что входит

| Компонент | Назначение |
|---|---|
| [`bin/factory`](bin/factory), [`factory/`](factory/) | CLI, admission/finalization gates, SQLite-состояние, workspaces, бюджеты, остановка и evidence. |
| [`adapters/`](adapters/) | Раздельные Pi/OMP SDK-адаптеры исполнителя и reviewer без нативного запуска дополнительных работников. |
| [`skills/factory/`](skills/factory/) | Шесть процедур: анализ, test design, preflight, runtime verification, RBAC audit и independent review. |
| [`config/factory-AGENTS.md`](config/factory-AGENTS.md) | Подключение одного factory-процесса к правилам конкретного проекта. |
| [`examples/project/`](examples/project/) | Синтетический проект с согласованными spec, ADR, task/test contract и исполняемой проверкой. |
| [`docs/workflow.md`](docs/workflow.md) | Роли, контракты, проход задачи, evidence и восстановление. |
| [`docs/runtime-contract.md`](docs/runtime-contract.md) | Поля профиля и manifest, границы workspace, запуск checks и контракт среды. |
| [`docs/harness-api.md`](docs/harness-api.md) | Точные версии пакетов Pi/OMP, используемые API и границы проведённой проверки. |
| [`docs/validation.md`](docs/validation.md) | Связь с исходной архитектурой, результаты выполненных проверок и явные NOT_RUN. |

## Быстрый запуск синтетического примера

Из корня этого репозитория, с Python 3.11+ и Git:

```bash
bin/factory demo /tmp/workshopskills-factory-demo
```

Команда создаёт отдельный учебный репозиторий, внешнее состояние и managed
workspaces и проходит цикл допуска, реализации, проверки и завершения на явных
синтетических исполнителях. Этот пример не обращается к реальной модели. Его PASS
проверяет работу фабрики на fixtures; он не подтверждает запуск провайдера Pi/OMP,
доступность приложения пользователя или изоляцию production-среды.

## Подключение реального проекта

Для реальных worker runs требуется Linux-среда с работающим Bubblewrap, а также
SDK и runtime выбранного харнесса: Node для Pi, поддерживаемый Bun для OMP.
Зависимости и API зафиксированы в [harness-api.md](docs/harness-api.md). `doctor`
проверяет локальные предпосылки и доступность sandbox; совместимость установленного
SDK и реального провайдера подтверждает фактический запуск.

В командах ниже задайте собственные абсолютные пути. Состояние обязано находиться
вне проектного checkout и всех его worktrees. Все операторы одного контура
используют общий canonical repo и `state-dir`: leases разных журналов не связаны.
Default state вычисляется по общему Git directory; явный путь удобнее для команды.

```bash
FACTORY_PROJECT=/absolute/path/to/project
FACTORY_STATE=/absolute/path/outside/project/factory-state
FACTORY_TASK=task-001

bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" init
```

`init` создаёт только черновой `.factory/project.json`. Далее:

1. Задайте фактические SDK/runtime paths, provider/model, бюджеты, допустимые имена
   переменных окружения и реальные verification argv. Пустой список checks не
   допускает реализацию; секреты в профиль не записываются.
2. Подключите [factory-AGENTS.md](config/factory-AGENTS.md), сохранив предметные
   правила, обязательные проверки и существующий ADR-гейт проекта. Используйте
   `skills/factory/` как единый набор процедур. В `instructions` профиля укажите
   выбранные Markdown-файлы предметных правил: контроллер хеширует и передаёт их
   worker. Автоматическое обнаружение местных skills/configs отключено.
3. Выберите одного владельца workspace: `git`, `worktrunk` или `existing`.
   Последний используется, когда жизненным циклом worktree управляет Tern/operator.
   БД, очереди, аккаунты и browser state требуют отдельной изоляции. По умолчанию
   preview выполняется последовательно; `per-task` допустим при реально
   разделённых ресурсах. Для `existing` владелец предоставляет отдельные абсолютные
   `path`, `verification_path` и `review_path` на соответствующих SHA; фабрика их
   не создаёт и не удаляет.
4. Ведущий агент исследует систему, применяет grilling для нерешённых вопросов,
   готовит канонические spec/ADR, task manifest и test contract. Используйте
   [пример](examples/project/) как форму, адаптируя поведение, роли и команды.
   `init` не создаёт за вас `.factory/tasks/task-001.json`.
5. Зафиксируйте профиль и контракты в Git. Admission требует чистого committed
   snapshot; ранее принятые решения пользователя повторно согласовывать не нужно.

Проверьте возможности среды и зарегистрируйте подготовленную задачу:

```bash
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" doctor
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" create ".factory/tasks/$FACTORY_TASK.json"
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" admit "$FACTORY_TASK"
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" workspace "$FACTORY_TASK"
```

Только успешный `admit` устанавливает `READY_FOR_BUILD`. Заключение навыка
`ANALYSIS_READY` само по себе не запускает исполнителя. ADR с новым существенным
решением проходит существующий проектный гейт; строка `accepted` должна ссылаться
на реальное решение.

Выполните задачу выбранным харнессом; для OMP замените `pi` на `omp`:

```bash
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" run "$FACTORY_TASK" --harness pi
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" check "$FACTORY_TASK"
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" review "$FACTORY_TASK" --harness pi
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" finalize "$FACTORY_TASK"
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" pr-body "$FACTORY_TASK"
```

Исполнитель получает `read/grep/find/write/edit`; shell и native `task` отсутствуют.
Команды выполняет контроллер. Checks используют отдельный чистый verification
worktree с исходниками на чтение; driver пишет временные результаты в
`FACTORY_RUN_DIR` и сам готовит разрешённые зависимости, приложение и fixtures.
Reviewer получает отдельную сессию, snapshot на чтение и зарегистрированное
evidence. Контроллер проверяет независимость, trace до AC и актуальность результатов.
После исправления кода нужны проверки на новом SHA. `pr-body` оформляет описание;
публикация PR, merge и deployment требуют своего действующего разрешения.

## Состояние, остановка и восстановление

```bash
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" status "$FACTORY_TASK"
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" cancel "$FACTORY_TASK"
bin/factory --repo "$FACTORY_PROJECT" --state-dir "$FACTORY_STATE" recover "$FACTORY_TASK"
```

Это отдельные управляющие действия: `cancel` останавливает текущую работу, `recover`
обрабатывает прерванные runs и требует проверки уже созданных ресурсов. Не
повторяйте внешний побочный эффект вслепую и не удаляйте чужой или dirty worktree.
Если принадлежность живого процесса нельзя доказать, восстановление блокируется;
произвольный PID не уничтожается. Startup handshake и lock защищают запуск от
гонки с recovery, но не разрешают повтор внешних действий.
FAIL, BLOCKED и NOT_RUN сохраняются явно; отсутствие результата не становится PASS.

По умолчанию sandbox — Bubblewrap и **при недоступности блокирует запуск**.
Trusted-local используется только явно для синтетического demo; он не обеспечивает
OS-изоляцию. Allowlist инструментов и hooks дополняют, но не заменяют sandbox.

## Поиск и локальная проверка фабрики

```bash
bin/factory --repo "$FACTORY_PROJECT" search "billing"
bin/factory --repo "$FACTORY_PROJECT" symbol billed_minutes
bin/factory --repo "$FACTORY_PROJECT" index-health
python3 -m unittest discover -s tests -v
node --test tests/test_adapters.mjs
```

Поиск читает текущие исходники: literal matches и Python AST definitions с SHA,
digest и ограничениями покрытия. Это не semantic index, LSP graph или session
mining. Тесты адаптеров используют fake SDK; live model, Bun SDK и production
preview этим не подтверждаются.

Реализован первый рабочий контур из архитектурного md. Remote worker pools,
semantic/session mining и TokenEconomizer остаются вне этой версии. Git hooks,
fsmonitor и filters отключены; Git LFS и submodules требуют отдельного явного
driver и сейчас не заявлены как поддерживаемые.

## Legacy workshop bundle

Исходные `skills/global/`, `skills/project/`, `config/project-AGENTS.md` и
`config/*CLAUDE*` сохранены как отдельный режим. В нём остаются прежние
`heavy-task-pipeline`, `runtime-sql-review` и зависимости от Claude/Superpowers/Beads.
Выбирайте один процесс для задачи: не загружайте legacy heavy pipeline вместе с
factory-контроллером как второго владельца допуска и выполнения.

Legacy-конфиги содержат соглашения конкретного проекта и машины; адаптируйте их
перед применением. Новый factory-профиль не наследует от них production-окружение,
модели, пути и полномочия автоматически.
