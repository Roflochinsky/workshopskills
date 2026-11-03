"""Trusted operator-side state machine and evidence gate.

This module does not launch agents or provide an OS sandbox. The launcher must keep
this state directory outside agent mounts. The host owner can always edit local
state; SQLite supplies transactional consistency, not an identity boundary.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
from typing import Any, Iterator
import uuid

from .safegit import GitError, git as safe_git


class ControllerError(RuntimeError):
    """The requested transition or contract is not admissible."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControllerError(f"{label} must be a nonempty string")
    return value


def _ids(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not empty and not value):
        raise ControllerError(f"{label} must be a {'possibly empty ' if empty else ''}list")
    result = [_text(item, label) for item in value]
    if len(set(result)) != len(result):
        raise ControllerError(f"{label} contains duplicate IDs")
    return result


class Controller:
    """One repository, one durable journal, serialized execution environments."""

    def __init__(self, repo: Path | str, state_dir: Path | str):
        requested = Path(repo).expanduser().resolve()
        self.repo = Path(self._git_at(requested, "rev-parse", "--show-toplevel")).resolve()
        self.state_dir = Path(state_dir).expanduser().resolve()
        self._check_state_location()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.state_dir / "controller.sqlite3"
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, manifest_path TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL, snapshot TEXT NOT NULL, contract_hash TEXT NOT NULL,
                    base_sha TEXT NOT NULL, admitted_hash TEXT, admitted_source_sha TEXT,
                    candidate_sha TEXT, generation INTEGER NOT NULL DEFAULT 0,
                    workspace_path TEXT, branch TEXT, provider TEXT,
                    cancelled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    role TEXT NOT NULL, status TEXT NOT NULL, generation INTEGER NOT NULL,
                    contract_hash TEXT NOT NULL, source_sha TEXT NOT NULL, result_sha TEXT,
                    actor_id TEXT NOT NULL, environment_id TEXT NOT NULL,
                    started_at TEXT NOT NULL, finished_at TEXT, evidence TEXT NOT NULL DEFAULT '{}'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_task
                    ON runs(task_id) WHERE status = 'RUNNING';
                CREATE UNIQUE INDEX IF NOT EXISTS active_environment
                    ON runs(environment_id) WHERE status = 'RUNNING';
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL, at TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL
                );
            """)
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1')")
            version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
            if version != "1":
                raise ControllerError(f"Unsupported controller schema: {version}")
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('repository', ?)", (str(self.repo),))
            registered = db.execute("SELECT value FROM metadata WHERE key='repository'").fetchone()[0]
            if registered != str(self.repo):
                canonical = Path(registered)
                if not canonical.is_dir():
                    raise ControllerError("Registered canonical repository is unavailable")
                try:
                    actual_common = Path(self._git_at(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
                    canonical_common = Path(self._git_at(canonical, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
                except ControllerError as exc:
                    raise ControllerError("Cannot establish registered canonical repository identity") from exc
                if actual_common != canonical_common:
                    raise ControllerError("State directory belongs to a different repository")
                # Commands invoked from another worktree share the same journal
                # and the already selected canonical input artifacts.
                self.repo = canonical.resolve()
                self._check_state_location()

    @staticmethod
    def _git_at(path: Path, *args: str) -> str:
        try:
            return safe_git(path, *args)
        except GitError as exc:
            raise ControllerError(str(exc)) from exc

    def _check_state_location(self) -> None:
        worktrees = self._git_at(self.repo, "worktree", "list", "--porcelain")
        roots = [self.repo]
        roots.extend(Path(line[9:]).resolve() for line in worktrees.splitlines() if line.startswith("worktree "))
        if any(_inside(self.state_dir, root) for root in roots):
            raise ControllerError("Controller state must be outside the repository and its worktrees")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            else:
                db.commit()

    @staticmethod
    def _task(db: sqlite3.Connection, task_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise ControllerError(f"Unknown task: {task_id}")
        return row

    @staticmethod
    def _event(db: sqlite3.Connection, task_id: str, kind: str, data: Any) -> None:
        db.execute("INSERT INTO events(task_id,at,kind,data) VALUES(?,?,?,?)", (task_id, _now(), kind, _json(data)))

    @staticmethod
    def _active(db: sqlite3.Connection, task_id: str) -> None:
        if db.execute("SELECT 1 FROM runs WHERE task_id=? AND status='RUNNING'", (task_id,)).fetchone():
            raise ControllerError("Task has an active run; cancel/recover it before changing the contract")

    def _file(self, relative: str) -> Path:
        _text(relative, "artifact path")
        posix = PurePosixPath(relative)
        if posix.is_absolute() or ".." in posix.parts or "\\" in relative:
            raise ControllerError(f"Artifact path must be repository-relative: {relative}")
        path = (self.repo / relative).resolve()
        if not _inside(path, self.repo) or not path.is_file():
            raise ControllerError(f"Artifact missing or escapes repository: {relative}")
        return path

    def _read_contract(self, path: Path | str) -> tuple[dict[str, Any], str, str]:
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                relative = candidate.resolve().relative_to(self.repo).as_posix()
            except ValueError as exc:
                raise ControllerError("Task manifest must be within the repository") from exc
        else:
            relative = candidate.as_posix()
        manifest = self._file(relative)
        sources: dict[str, str] = {}

        def read(name: str, *, structured: bool = False) -> Any:
            file = self._file(name)
            if file.stat().st_size > 8 * 1024 * 1024:
                raise ControllerError(f"Contract artifact exceeds 8 MiB: {name}")
            try:
                data = file.read_bytes()
            except OSError as exc:
                raise ControllerError(f"Cannot read contract artifact: {name}") from exc
            sources[name] = _sha(data)
            if not data.strip():
                raise ControllerError(f"Empty contract artifact: {name}")
            if not structured:
                return None
            try:
                value = json.loads(data)
            except (ValueError, UnicodeError) as exc:
                raise ControllerError(f"Invalid JSON: {name}") from exc
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise ControllerError(f"Expected schema_version=1 object: {name}")
            return value

        task = read(relative, structured=True)
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", task_id):
            raise ControllerError("task_id must be a safe 1–64 character slug")
        profile = read(".factory/project.json", structured=True)
        _text(profile.get("project_id"), "profile.project_id")
        for instruction in _ids(profile.get("instructions", []), "profile.instructions", empty=True):
            if PurePosixPath(instruction).suffix.lower() != ".md":
                raise ControllerError("Explicit project instructions must be Markdown files")
            read(instruction)
        read(_text(task.get("spec"), "task.spec"))
        test_contract = read(_text(task.get("test_contract"), "task.test_contract"), structured=True)
        adrs = task.get("adrs")
        if not isinstance(adrs, list):
            raise ControllerError("task.adrs must list the triggered decision records (or be empty)")
        seen_adrs: set[str] = set()
        for adr in adrs:
            if not isinstance(adr, dict):
                raise ControllerError("Each ADR must be an object")
            name = _text(adr.get("path"), "ADR path")
            if name in seen_adrs:
                raise ControllerError(f"Duplicate ADR: {name}")
            seen_adrs.add(name)
            read(name)
        # Formatting-only edits to the manifest do not change its semantic identity.
        sources.pop(relative)
        snapshot = {"task": task, "profile": profile, "test_contract": test_contract,
                    "sources": sources, "manifest_path": relative}
        return snapshot, _sha(_json(snapshot).encode()), relative

    def _validate(self, snapshot: dict[str, Any]) -> list[str]:
        task, profile, test_plan = (snapshot[k] for k in ("task", "profile", "test_contract"))
        analysis = task.get("analysis", {})
        if not isinstance(analysis, dict) or analysis.get("status") != "ANALYSIS_READY":
            raise ControllerError("Analysis is not ANALYSIS_READY")
        if analysis.get("blocking_questions") != []:
            raise ControllerError("Analysis has unresolved or undeclared blocking questions")
        for adr in task["adrs"]:
            if adr.get("status") != "accepted":
                raise ControllerError(f"ADR gate is pending: {adr['path']}")
            _text(adr.get("decision_source"), f"ADR acceptance source: {adr['path']}")
        scope = _ids(task.get("scope"), "task.scope")
        for pattern in scope:
            path = PurePosixPath(pattern)
            if path.is_absolute() or ".." in path.parts or "\\" in pattern or pattern in (".", ""):
                raise ControllerError(f"Unsafe scope pattern: {pattern}")
        requirements = _ids(task.get("requirements"), "requirements")
        invariants = _ids(task.get("invariants", []), "invariants", empty=True)
        all_ids = set(requirements + invariants)
        if len(all_ids) != len(requirements) + len(invariants):
            raise ControllerError("Requirement and invariant IDs overlap")
        acceptance = task.get("acceptance")
        if not isinstance(acceptance, list) or not acceptance:
            raise ControllerError("Acceptance criteria are required")
        ac_map: dict[str, set[str]] = {}
        for ac in acceptance:
            if not isinstance(ac, dict):
                raise ControllerError("Acceptance criteria must be objects")
            ac_id = _text(ac.get("id"), "AC ID")
            linked = set(_ids(ac.get("requirements"), f"{ac_id}.requirements"))
            if ac_id in ac_map or not linked <= all_ids:
                raise ControllerError(f"Duplicate AC or unknown requirement in {ac_id}")
            ac_map[ac_id] = linked
        if set().union(*ac_map.values()) != all_ids:
            raise ControllerError("Every requirement/invariant needs an acceptance criterion")
        verification = profile.get("verification", {})
        checks = verification.get("checks") if isinstance(verification, dict) else None
        if not isinstance(checks, list) or not checks:
            raise ControllerError("Configure executable verification checks before admission")
        check_map: dict[str, dict[str, Any]] = {}
        for check in checks:
            if not isinstance(check, dict):
                raise ControllerError("Verification checks must be objects")
            check_id = _text(check.get("id"), "check ID")
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", check_id) or check_id in check_map:
                raise ControllerError(f"Invalid or duplicate check ID: {check_id}")
            argv = check.get("argv")
            if not isinstance(argv, list) or not argv or any(not isinstance(v, str) or not v for v in argv):
                raise ControllerError(f"{check_id}.argv must be a nonempty argv array")
            cwd = check.get("cwd", ".")
            if not isinstance(cwd, str) or PurePosixPath(cwd).is_absolute() or ".." in PurePosixPath(cwd).parts or "\\" in cwd:
                raise ControllerError(f"{check_id}.cwd must be relative")
            cwd_path = (self.repo / cwd).resolve()
            if not _inside(cwd_path, self.repo) or not cwd_path.is_dir():
                raise ControllerError(f"{check_id}.cwd is missing or outside repository")
            if type(check.get("timeout_seconds")) is not int or check["timeout_seconds"] <= 0:
                raise ControllerError(f"{check_id}.timeout_seconds must be positive")
            if type(check.get("required")) is not bool:
                raise ControllerError(f"{check_id}.required must be explicit")
            check_map[check_id] = check
        runtime = profile.get("runtime", {})
        if not isinstance(runtime, dict):
            raise ControllerError("runtime must be an object")
        for key in ("max_runs", "timeout_seconds", "output_limit_bytes"):
            if type(runtime.get(key)) is not int or runtime[key] <= 0:
                raise ControllerError(f"runtime.{key} must be a positive integer")
        workspace = profile.get("workspace", {})
        if not isinstance(workspace, dict) or workspace.get("provider") not in ("git", "worktrunk", "existing"):
            raise ControllerError("Select exactly one workspace provider")
        scenarios = test_plan.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            raise ControllerError("A behavioral test contract is required")
        scenario_ids: set[str] = set()
        covered_links: set[tuple[str, str]] = set()
        required_checks = {name for name, c in check_map.items() if c["required"]}
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                raise ControllerError("Test scenarios must be objects")
            name = _text(scenario.get("id"), "scenario ID")
            if name in scenario_ids:
                raise ControllerError(f"Duplicate scenario: {name}")
            scenario_ids.add(name)
            for field in ("behavior", "distinct_failure_mode", "public_boundary", "oracle_source", "existing_coverage", "cost"):
                _text(scenario.get(field), f"{name}.{field}")
            if scenario.get("disposition") not in ("reuse", "extend", "new"):
                raise ControllerError(f"{name}.disposition must be reuse, extend, or new")
            req = set(_ids(scenario.get("requirements"), f"{name}.requirements"))
            acs = set(_ids(scenario.get("acceptance"), f"{name}.acceptance"))
            if not req <= all_ids or not acs <= ac_map.keys():
                raise ControllerError(f"Unknown trace reference in {name}")
            for ac_id in acs:
                intersection = req & ac_map[ac_id]
                if not intersection:
                    raise ControllerError(f"{name} does not protect a requirement of {ac_id}")
                covered_links.update((ac_id, r) for r in intersection)
            if not req <= set().union(*(ac_map[ac_id] for ac_id in acs)):
                raise ControllerError(f"{name} has orphan requirement references")
            selected = set(_ids(scenario.get("checks"), f"{name}.checks"))
            if not selected <= check_map.keys():
                raise ControllerError(f"{name} refers to an unknown verification check")
            required_checks.update(selected)
        if covered_links != {(a, r) for a, reqs in ac_map.items() for r in reqs}:
            raise ControllerError("Test contract must cover every requirement-to-AC link")
        rbac = test_plan.get("rbac")
        if not isinstance(rbac, dict) or type(rbac.get("required")) is not bool:
            raise ControllerError("Test contract must classify RBAC applicability")
        _text(rbac.get("reason"), "RBAC applicability reason")
        if rbac["required"]:
            check_id = _text(rbac.get("check_id"), "RBAC check_id")
            if check_id not in check_map:
                raise ControllerError("RBAC requires a configured executable check")
            required_checks.add(check_id)
        return sorted(required_checks)

    def _fresh(self, row: sqlite3.Row) -> dict[str, Any]:
        snapshot, digest, _ = self._read_contract(row["manifest_path"])
        if digest != row["contract_hash"]:
            raise ControllerError("Contract is stale; run create/update explicitly and admit again")
        if row["admitted_hash"] != digest:
            raise ControllerError("Task has no current implementation admission")
        self._validate(snapshot)
        return snapshot

    def _workspace(self, row: sqlite3.Row) -> Path:
        return Path(row["workspace_path"]) if row["workspace_path"] else self.repo

    def _source(self, row: sqlite3.Row, sha: str, *, clean: bool = True) -> None:
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
            raise ControllerError("An exact full Git commit SHA is required")
        workspace = self._workspace(row)
        if self._git_at(workspace, "rev-parse", "HEAD") != sha:
            raise ControllerError("Evidence source SHA does not match the task workspace HEAD")
        if clean and self._git_at(workspace, "status", "--porcelain", "--untracked-files=all"):
            raise ControllerError("Workspace is dirty; evidence requires a clean committed snapshot")

    def create(self, path: Path | str) -> dict[str, Any]:
        snapshot, digest, relative = self._read_contract(path)
        task_id = snapshot["task"]["task_id"]
        base_sha = self._git_at(self.repo, "rev-parse", "HEAD")
        with self._transaction() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is not None:
                self._active(db, task_id)
                if row["manifest_path"] != relative:
                    raise ControllerError("Task ID is already bound to a different manifest path")
                if row["contract_hash"] == digest:
                    return self._status(db, task_id)
                db.execute("""UPDATE tasks SET state='DRAFT', snapshot=?, contract_hash=?,
                    admitted_hash=NULL, admitted_source_sha=NULL, candidate_sha=NULL,
                    cancelled=0, updated_at=? WHERE task_id=?""", (_json(snapshot), digest, _now(), task_id))
                self._event(db, task_id, "contract_updated", {"from": row["contract_hash"], "to": digest})
            else:
                when = _now()
                try:
                    db.execute("""INSERT INTO tasks(task_id,manifest_path,state,snapshot,contract_hash,
                        base_sha,created_at,updated_at) VALUES(?,?,'DRAFT',?,?,?,?,?)""",
                        (task_id, relative, _json(snapshot), digest, base_sha, when, when))
                except sqlite3.IntegrityError as exc:
                    raise ControllerError("Manifest path is already bound to another task") from exc
                self._event(db, task_id, "created", {"contract_hash": digest, "base_sha": base_sha})
            return self._status(db, task_id)

    def _status(self, db: sqlite3.Connection, task_id: str) -> dict[str, Any]:
        row = dict(self._task(db, task_id))
        snapshot = json.loads(row.pop("snapshot"))
        row.update(snapshot)
        row["workspace"] = {"path": row["workspace_path"], "branch": row["branch"], "provider": row["provider"]}
        row["cancelled"] = bool(row["cancelled"])
        row["runs"] = [self._run_value(r) for r in db.execute("SELECT * FROM runs WHERE task_id=? ORDER BY rowid", (task_id,))]
        row["events"] = [{**dict(e), "data": json.loads(e["data"])} for e in db.execute("SELECT * FROM events WHERE task_id=? ORDER BY sequence", (task_id,))]
        return row

    @staticmethod
    def _run_value(row: sqlite3.Row) -> dict[str, Any]:
        return {**dict(row), "evidence": json.loads(row["evidence"])}

    def status(self, task_id: str) -> dict[str, Any]:
        with self._connection() as db:
            # A status report must not combine task, runs and events from
            # different concurrent transactions.
            db.execute("BEGIN")
            return self._status(db, task_id)

    def admit(self, task_id: str) -> dict[str, Any]:
        with self._transaction() as db:
            row = self._task(db, task_id)
            self._active(db, task_id)
            snapshot, digest, _ = self._read_contract(row["manifest_path"])
            if digest != row["contract_hash"]:
                raise ControllerError("Contract changed; explicitly create/update the task before admission")
            self._validate(snapshot)
            source = self._git_at(self._workspace(row), "rev-parse", "HEAD")
            self._source(row, source)
            db.execute("""UPDATE tasks SET state='READY_FOR_BUILD', admitted_hash=?,
                admitted_source_sha=?, candidate_sha=NULL, cancelled=0,updated_at=? WHERE task_id=?""",
                (digest, source, _now(), task_id))
            self._event(db, task_id, "admitted", {"contract_hash": digest, "source_sha": source})
            return self._status(db, task_id)

    def set_workspace(self, task_id: str, path: Path | str, branch: str, provider: str) -> dict[str, Any]:
        _text(branch, "workspace branch")
        workspace = Path(path).resolve()
        if _inside(self.state_dir, workspace) or _inside(workspace, self.state_dir):
            raise ControllerError("Agent workspace and trusted controller state must not contain one another")
        with self._transaction() as db:
            row = self._task(db, task_id)
            self._active(db, task_id)
            configuration = json.loads(row["snapshot"])["profile"].get("workspace", {})
            if not isinstance(configuration, dict) or configuration.get("provider") not in ("git", "worktrunk", "existing"):
                raise ControllerError("Select a valid workspace provider before registration")
            expected = configuration["provider"]
            if provider != expected:
                raise ControllerError("Workspace provider differs from the project profile")
            if workspace == self.repo and provider != "existing":
                raise ControllerError("Managed execution requires a separate worktree")
            if Path(self._git_at(workspace, "rev-parse", "--show-toplevel")).resolve() != workspace:
                raise ControllerError("Workspace must identify its exact Git worktree root")
            common = Path(self._git_at(workspace, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
            own_common = Path(self._git_at(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
            if common != own_common:
                raise ControllerError("Workspace does not belong to this repository")
            if row["workspace_path"] and (row["workspace_path"] != str(workspace) or row["provider"] != provider or row["branch"] != branch):
                raise ControllerError("Workspace ownership is immutable for a task")
            db.execute("UPDATE tasks SET workspace_path=?,branch=?,provider=?,updated_at=? WHERE task_id=?",
                       (str(workspace), branch, provider, _now(), task_id))
            self._event(db, task_id, "workspace_registered", {"path": str(workspace), "branch": branch, "provider": provider})
            return self._status(db, task_id)

    def begin_run(self, task_id: str, role: str, source_sha: str, actor_id: str, environment_id: str) -> dict[str, Any]:
        _text(role, "role")
        _text(actor_id, "actor_id")
        _text(environment_id, "environment_id")
        with self._transaction() as db:
            row = self._task(db, task_id)
            self._active(db, task_id)
            snapshot = self._fresh(row)
            if row["cancelled"]:
                raise ControllerError("Task is cancelled; explicit admission is needed to resume")
            if not row["workspace_path"]:
                raise ControllerError("Register the task workspace before starting a run")
            self._source(row, source_sha)
            runs = db.execute("SELECT COUNT(*) FROM runs WHERE task_id=?", (task_id,)).fetchone()[0]
            if runs >= snapshot["profile"]["runtime"]["max_runs"]:
                raise ControllerError("Task run budget exhausted")
            generation = row["generation"]
            if role == "implement":
                if row["state"] != "READY_FOR_BUILD" or source_sha != row["admitted_source_sha"]:
                    raise ControllerError("Implementation requires current READY_FOR_BUILD admission and source")
                generation += 1
                db.execute("UPDATE tasks SET generation=?,candidate_sha=NULL,state='IMPLEMENTING',updated_at=? WHERE task_id=?",
                           (generation, _now(), task_id))
            elif role == "review" or role.startswith("check:"):
                if not row["candidate_sha"] or source_sha != row["candidate_sha"]:
                    raise ControllerError("Verification requires the completed implementation candidate SHA")
                if row["state"] not in ("READY_FOR_REVIEW", "VERIFYING", "BLOCKED"):
                    raise ControllerError("Task is not awaiting verification")
                if role == "review" and db.execute("SELECT 1 FROM runs WHERE task_id=? AND role='implement' AND actor_id=?", (task_id, actor_id)).fetchone():
                    raise ControllerError("Reviewer must use a different actor/session from every implementer")
                if role.startswith("check:") and role[6:] not in {c["id"] for c in snapshot["profile"]["verification"]["checks"]}:
                    raise ControllerError("Unknown verification check")
                db.execute("UPDATE tasks SET state='VERIFYING',updated_at=? WHERE task_id=?", (_now(), task_id))
            else:
                raise ControllerError(f"Unknown run role: {role}")
            run_id = uuid.uuid4().hex
            try:
                db.execute("""INSERT INTO runs(run_id,task_id,role,status,generation,contract_hash,source_sha,
                    actor_id,environment_id,started_at) VALUES(?,?,?,'RUNNING',?,?,?,?,?,?)""",
                    (run_id, task_id, role, generation, row["contract_hash"], source_sha, actor_id, environment_id, _now()))
            except sqlite3.IntegrityError as exc:
                raise ControllerError("Execution environment is already leased by another active run") from exc
            self._event(db, task_id, "run_started", {"run_id": run_id, "role": role, "source_sha": source_sha, "generation": generation})
            return self._run_value(db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())

    def _evidence_files(self, evidence: dict[str, Any], *, required: bool) -> None:
        files = evidence.get("files", [])
        if not isinstance(files, list) or (required and not files):
            raise ControllerError("PASS requires raw evidence.files with paths and SHA-256 digests")
        for item in files:
            if not isinstance(item, dict):
                raise ControllerError("Evidence files must be objects")
            original = Path(_text(item.get("path"), "evidence path"))
            path = original.resolve()
            if not original.is_absolute() or original.is_symlink() or not _inside(path, self.state_dir) or not path.is_file() or path == self.db_path:
                raise ControllerError("Raw evidence must be an ordinary file inside the controller state directory")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
                raise ControllerError("Evidence requires a SHA-256 digest")
            try:
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
            except OSError as exc:
                raise ControllerError("Raw evidence is unreadable") from exc
            if digest != item["sha256"]:
                raise ControllerError("Raw evidence is missing or changed")

    def finish_run(self, run_id: str, status: str, source_sha: str, evidence: dict[str, Any]) -> dict[str, Any]:
        if status not in ("PASS", "FAIL", "BLOCKED", "NOT_RUN") or not isinstance(evidence, dict):
            raise ControllerError("Run result requires PASS/FAIL/BLOCKED/NOT_RUN and an evidence object")
        encoded = _json(evidence)
        with self._transaction() as db:
            run = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise ControllerError("Cannot finish an unregistered run")
            if run["status"] != "RUNNING":
                if (run["status"], run["result_sha"], run["evidence"]) == (status, source_sha, encoded):
                    return self._run_value(run)
                raise ControllerError("Finished run evidence is immutable; create a new run")
            task = self._task(db, run["task_id"])
            effective, issue = status, None
            try:
                self._fresh(task)
                if task["cancelled"]:
                    raise ControllerError("Task was cancelled while the run was active")
                if status == "PASS":
                    self._source(task, source_sha)
                    if run["role"] != "implement" and source_sha != run["source_sha"]:
                        raise ControllerError("Verifier changed its source snapshot")
                    if run["role"] == "implement":
                        self._git_at(self._workspace(task), "merge-base", "--is-ancestor", run["source_sha"], source_sha)
                    self._evidence_files(evidence, required=True)
                else:
                    self._evidence_files(evidence, required=False)
            except ControllerError as exc:
                effective, issue = "BLOCKED", str(exc)
                evidence = {**evidence, "gate_error": issue, "claimed_status": status}
            db.execute("UPDATE runs SET status=?,result_sha=?,finished_at=?,evidence=? WHERE run_id=?",
                       (effective, source_sha, _now(), _json(evidence), run_id))
            if task["cancelled"]:
                state = "CANCELLED"
            elif effective != "PASS":
                state = "BLOCKED"
            elif run["role"] == "implement":
                state = "READY_FOR_REVIEW"
                db.execute("UPDATE tasks SET candidate_sha=? WHERE task_id=?", (source_sha, task["task_id"]))
            else:
                state = "READY_FOR_REVIEW"
            db.execute("UPDATE tasks SET state=?,updated_at=? WHERE task_id=?", (state, _now(), task["task_id"]))
            self._event(db, task["task_id"], "run_finished", {"run_id": run_id, "status": effective, "source_sha": source_sha, "gate_error": issue})
            return self._run_value(db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())

    def finalize(self, task_id: str, current_sha: str, environment_id: str) -> dict[str, Any]:
        problem = None
        with self._transaction() as db:
            row = self._task(db, task_id)
            self._active(db, task_id)
            try:
                snapshot = self._fresh(row)
                if row["cancelled"] or current_sha != row["candidate_sha"]:
                    raise ControllerError("No current completed implementation candidate")
                self._source(row, current_sha)
                required = self._validate(snapshot)
                latest: dict[str, sqlite3.Row] = {}
                for run in db.execute("SELECT * FROM runs WHERE task_id=? AND generation=? ORDER BY rowid", (task_id, row["generation"])):
                    latest[run["role"]] = run
                for role in ["review", *("check:" + check for check in required)]:
                    run = latest.get(role)
                    if run is None or run["status"] != "PASS":
                        raise ControllerError(f"Missing current PASS for {role}")
                    if (run["contract_hash"], run["source_sha"], run["result_sha"], run["environment_id"]) != (row["contract_hash"], current_sha, current_sha, environment_id):
                        raise ControllerError(f"Stale contract/source/environment evidence for {role}")
                    self._evidence_files(json.loads(run["evidence"]), required=True)
                review = json.loads(latest["review"]["evidence"])
                acs = {a["id"] for a in snapshot["task"]["acceptance"]}
                covered = review.get("covered_ac")
                if not isinstance(covered, list) or any(not isinstance(ac, str) for ac in covered) or set(covered) != acs:
                    raise ControllerError("Independent review must cover every AC and no unknown AC")
                lenses = review.get("lenses")
                if not isinstance(lenses, list) or any(not isinstance(lens, str) for lens in lenses) or not {"spec", "correctness", "tests"} <= set(lenses):
                    raise ControllerError("Independent review requires spec, correctness, and test-design lenses")
                if review.get("findings") != []:
                    raise ControllerError("Independent review has unresolved or undeclared findings")
            except ControllerError as exc:
                problem = str(exc)
                db.execute("UPDATE tasks SET state='BLOCKED',updated_at=? WHERE task_id=?", (_now(), task_id))
                self._event(db, task_id, "finalization_blocked", {"reason": problem})
            else:
                db.execute("UPDATE tasks SET state='VERIFIED',updated_at=? WHERE task_id=?", (_now(), task_id))
                self._event(db, task_id, "verified", {"source_sha": current_sha, "contract_hash": row["contract_hash"], "environment_id": environment_id})
            result = self._status(db, task_id)
        if problem:
            raise ControllerError(problem)
        return result

    def cancel(self, task_id: str) -> dict[str, Any]:
        with self._transaction() as db:
            self._task(db, task_id)
            db.execute("UPDATE tasks SET cancelled=1,state='CANCELLED',updated_at=? WHERE task_id=?", (_now(), task_id))
            self._event(db, task_id, "cancel_requested", {})
            return self._status(db, task_id)

    def recover(self, task_id: str) -> dict[str, Any]:
        """After the launcher establishes processes stopped, abandon, never replay."""
        with self._transaction() as db:
            task = self._task(db, task_id)
            runs = db.execute("SELECT * FROM runs WHERE task_id=? AND status='RUNNING'", (task_id,)).fetchall()
            for run in runs:
                evidence = {"reason": "Abandoned run recovered; external effects are unknown and were not replayed"}
                db.execute("UPDATE runs SET status='BLOCKED',finished_at=?,evidence=? WHERE run_id=?", (_now(), _json(evidence), run["run_id"]))
            if runs:
                db.execute("UPDATE tasks SET state=?,updated_at=? WHERE task_id=?", ("CANCELLED" if task["cancelled"] else "BLOCKED", _now(), task_id))
                self._event(db, task_id, "recovered", {"abandoned_runs": [r["run_id"] for r in runs], "replayed": False})
            return self._status(db, task_id)
