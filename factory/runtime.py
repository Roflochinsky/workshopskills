"""Trusted launcher. Workers cannot access the controller database or grant a phase."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterator

from .controller import Controller, ControllerError
from . import process, workspace

ROOT = Path(__file__).resolve().parent.parent
ROLE_SKILLS = {
    "implement": ["factory-preflight", "factory-test-design", "factory-runtime-verification"],
    "review": ["factory-independent-review", "factory-test-design", "factory-rbac-audit"],
}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Runtime:
    def __init__(self, controller: Controller, *, synthetic: bool = False):
        self.controller = controller
        self.repo = controller.repo
        self.state = controller.state_dir
        # This internal option is used only by the deterministic demo/tests. No
        # run/check/review CLI flag can downgrade the real sandbox requirement.
        self.synthetic = synthetic

    @contextlib.contextmanager
    def lock(self, task_id: str) -> Iterator[None]:
        # Acquire before begin_run, preventing recover from racing process setup.
        self.controller.status(task_id)  # validates existence; ID originated in schema
        directory = self.state / "locks"
        directory.mkdir(exist_ok=True)
        with (directory / (task_id + ".lock")).open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ControllerError("A launcher is active for this task") from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def workspaces(self) -> Path:
        return self.state.parent / (self.state.name + "-workspaces")

    def prepare_workspace(self, task_id: str) -> dict:
        with self.lock(task_id):
            status = self.controller.status(task_id)
            registered = status["workspace"]
            if registered["path"]:
                self._identity(status, Path(registered["path"]))
                return registered
            if status["state"] != "READY_FOR_BUILD":
                raise ControllerError("Workspace creation requires READY_FOR_BUILD")
            config = status["profile"]["workspace"]
            provider = config["provider"]
            base = status["admitted_source_sha"]
            if provider == "existing":
                raw = config.get("path")
                if not raw or not Path(raw).is_absolute():
                    raise ControllerError("existing provider requires an absolute workspace.path")
                path = workspace.attach(self.repo, Path(raw), base)
                branch = workspace.git(path, "symbolic-ref", "--short", "HEAD")
            else:
                path = self.workspaces() / task_id
                branch = "factory/" + task_id
                path = workspace.create(self.repo, path, branch, base, provider)
            return self.controller.set_workspace(task_id, path, branch, provider)["workspace"]

    def _identity(self, status: dict, path: Path) -> None:
        expected = status["workspace"]
        if Path(expected["path"]).resolve() != path.resolve():
            raise ControllerError("Workspace identity changed")
        common = workspace.git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        original = workspace.git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        branch = workspace.git(path, "symbolic-ref", "--short", "HEAD")
        if Path(common).resolve() != Path(original).resolve() or branch != expected["branch"]:
            raise ControllerError("Workspace Git ownership or branch changed")

    def _sources(self, status: dict, path: Path) -> None:
        # A code worker may never rewrite its own specification, grants, checks,
        # or selected project policies, even if the product scope is broad.
        for name, expected in status["sources"].items():
            file = path / name
            if file.is_symlink() or not file.resolve().is_relative_to(path.resolve()) or not file.is_file() or digest(file) != expected:
                raise ControllerError("Workspace contract differs from admission: " + name)
        manifest = path / status["manifest_path"]
        if manifest.is_symlink() or not manifest.resolve().is_relative_to(path.resolve()):
            raise ControllerError("Task manifest escaped the workspace")
        if json.loads(manifest.read_text()) != status["task"]:
            raise ControllerError("Worker changed the task manifest")

    def environment(self, status: dict) -> str:
        preview = status["profile"].get("preview", {})
        if not isinstance(preview, dict):
            raise ControllerError("preview must be an object")
        identity = preview.get("environment_id", status["profile"]["project_id"] + ":local")
        isolation = preview.get("isolation", "serial")
        if not isinstance(identity, str) or not identity.strip() or isolation not in ("serial", "per-task"):
            raise ControllerError("Declare a stable preview.environment_id and serial/per-task isolation")
        if isolation == "per-task":
            # This label does not provision isolation. Project check commands must
            # use FACTORY_TASK_ID to allocate separate database/queue/fixtures.
            identity += ":" + status["task_id"]
        return identity

    def _run_directory(self, run_id: str) -> Path:
        path = self.state / "runs" / run_id
        path.mkdir(parents=True, exist_ok=False)
        path.chmod(0o700)
        (path / "worker").mkdir(mode=0o700)
        return path

    def _evidence_workspace(self, status: dict, kind: str) -> Path:
        config = status["profile"]["workspace"]
        source = status["candidate_sha"]
        if config["provider"] == "existing":
            key = "review_path" if kind == "review" else "verification_path"
            raw = config.get(key)
            if not raw or not Path(raw).is_absolute() or Path(raw).resolve() == Path(status["workspace"]["path"]).resolve():
                raise ControllerError("External owner must supply a separate absolute workspace." + key + " at candidate SHA")
            other_key = "verification_path" if kind == "review" else "review_path"
            if config.get(other_key) and Path(raw).resolve() == Path(config[other_key]).resolve():
                raise ControllerError("Verification and independent review require separate workspaces")
            return workspace.attach(self.repo, Path(raw), source)
        name = status["task_id"] + "-" + kind + "-" + source[:12]
        return workspace.create(self.repo, self.workspaces() / name, "factory/" + name,
                                source, config["provider"])

    def _prompt(self, status: dict, role: str) -> str:
        sections = [(ROOT / "config/factory-AGENTS.md").read_text()]
        for skill in ROLE_SKILLS[role]:
            sections.append((ROOT / "skills/factory" / skill / "SKILL.md").read_text())
        sections.append("# Controller handoff\n" + json.dumps({
            "task": status["task"], "contract_hash": status["contract_hash"],
            "source_sha": status["candidate_sha"] if role == "review" else status["admitted_source_sha"],
            "scope": status["task"]["scope"], "environment_id": self.environment(status),
        }, ensure_ascii=False, indent=2))
        for name, expected in status["sources"].items():
            file = self.repo / name
            if digest(file) != expected:
                raise ControllerError("Canonical source changed while preparing handoff: " + name)
            sections.append("# Frozen artifact: " + name + "\n" + file.read_text())
        if role == "review":
            # Bounded copies, not direct access to trusted state. The controller
            # validates the original hashes again at finalization.
            sections.append("# Registered check evidence\n")
            for run in status["runs"]:
                if run["generation"] != status["generation"] or not run["role"].startswith("check:"):
                    continue
                sections.append(json.dumps({k: run.get(k) for k in (
                    "run_id", "role", "status", "source_sha", "result_sha", "contract_hash", "environment_id")}, ensure_ascii=False))
                for item in run["evidence"].get("files", []):
                    file = Path(item["path"])
                    if not file.resolve().is_relative_to(self.state) or digest(file) != item["sha256"]:
                        raise ControllerError("Check evidence changed before review")
                    data = file.read_bytes()
                    sections.append("Evidence " + file.name + " (sha256 " + item["sha256"] + "):\n" + data[:32768].decode("utf-8", "replace") +
                                    ("\n[TRUNCATED: do not infer coverage from omitted content]" if len(data) > 32768 else ""))
            sections.append("Review the source diff from base " + status["base_sha"] +
                            ". You have read-only tools; report BLOCKED if supplied evidence is insufficient. "
                            "Return exactly {status,covered_ac,lenses,findings} as JSON. "
                            "PASS requires every acceptance ID, all spec/correctness/tests lenses and no findings.")
            sections.append("# Source diff\n" + workspace.git(Path(status["workspace"]["path"]),
                "diff", "--no-ext-diff", "--no-textconv", status["base_sha"], status["candidate_sha"], "--"))
        else:
            sections.append("Implement the admitted behavior within scope. Do not edit frozen artifacts, "
                            "Git metadata, branches, or project runtime configuration. Do not delegate to other agents. "
                            "The controller commits the candidate and executes checks after you return. "
                            "Your final answer is implementation output, never acceptance or gate approval.")
        prompt = "\n\n".join(sections)
        if len(prompt.encode()) > 2 * 1024 * 1024:
            raise ControllerError("Handoff exceeds 2 MiB; narrow the task/evidence before running")
        return prompt

    def _harness(self, profile: dict, harness: str) -> tuple[dict, list[Path]]:
        if harness not in ("pi", "omp"):
            raise ControllerError("Harness must be pi or omp")
        configured = profile.get("harnesses", {})
        if not isinstance(configured, dict) or not isinstance(configured.get(harness, {}), dict):
            raise ControllerError("harnesses and each harness profile must be objects")
        config = configured.get(harness, {})
        for name in ("runtime", "sdk_module", "provider", "model"):
            if not isinstance(config.get(name), str) or not config[name].strip():
                raise ControllerError(f"Configure harnesses.{harness}.{name}")
        for name in ("runtime", "sdk_module"):
            path = Path(config[name])
            if not path.is_absolute() or not path.is_file():
                raise ControllerError(f"{harness}.{name} must be an existing absolute file")
            if path.resolve().is_relative_to(self.repo) or path.resolve().is_relative_to(self.workspaces()):
                raise ControllerError("Harness installation must be trusted and outside task workspaces")
        if not os.access(config["runtime"], os.X_OK):
            raise ControllerError("Harness runtime is not executable")
        readonly = [ROOT / "adapters", Path(config["runtime"]).resolve().parent]
        # Dependencies may sit at a higher installation root (e.g. node_modules).
        # The operator chooses that exact trusted root; never mount a whole home.
        roots = config.get("read_only_paths", [])
        if not isinstance(roots, list) or any(not isinstance(p, str) or not Path(p).is_absolute() for p in roots):
            raise ControllerError("harness read_only_paths must be absolute paths")
        readonly += [Path(p) for p in roots]
        readonly.append(Path(config["sdk_module"]).resolve().parent)
        if config.get("auth_file"):
            auth = Path(config["auth_file"])
            if not auth.is_absolute() or not auth.is_file():
                raise ControllerError("auth_file must be an existing absolute snapshot")
            readonly.append(auth)
        return config, readonly

    def _execute(self, status: dict, argv: list[str], cwd: Path, source: Path,
                 directory: Path, names: list[str], extra: list[Path], *, readonly: bool,
                 timeout: int, network: bool) -> dict:
        output = directory / "worker"
        if not readonly and ROOT.is_relative_to(source.resolve()):
            raise ControllerError("Install the trusted factory outside the writable worker checkout")
        env = process.clean_environment(names, output)
        env.update({"FACTORY_TASK_ID": status["task_id"], "FACTORY_SOURCE_SHA": workspace.git(source, "rev-parse", "HEAD"),
                    "FACTORY_ENVIRONMENT_ID": self.environment(status)})
        if self.synthetic:
            if status["profile"].get("project_id") != "law-factory-demo" or not status["profile"].get("preview", {}).get("synthetic"):
                raise ControllerError("Trusted-local execution is reserved for the built-in synthetic demo")
        else:
            if status["profile"]["runtime"].get("sandbox", "bubblewrap") != "bubblewrap":
                raise ControllerError("Only bubblewrap is implemented; no silent isolation downgrade")
            roots = status["profile"]["runtime"].get("read_only_paths", [])
            if not isinstance(roots, list) or any(not isinstance(p, str) or not Path(p).is_absolute() for p in roots):
                raise ControllerError("runtime.read_only_paths must be absolute paths")
            argv = process.sandbox_command(argv, cwd, source, output, readonly,
                                           extra + [Path(p) for p in roots], self.state, network)
        return process.run(argv, cwd, env, directory / "logs", timeout,
                           status["profile"]["runtime"]["output_limit_bytes"],
                           lambda: self.controller.status(status["task_id"])["cancelled"])

    def worker(self, task_id: str, role: str, harness: str) -> dict:
        if role not in ROLE_SKILLS:
            raise ControllerError("Unknown worker role")
        with self.lock(task_id):
            status = self.controller.status(task_id)
            source = Path(status["workspace"]["path"] or self.repo)
            sha = workspace.git(source, "rev-parse", "HEAD")
            # Actor identity is a fresh process/session identity, not a model name.
            actor = role + ":" + harness + ":" + os.urandom(12).hex()
            run = self.controller.begin_run(task_id, role, sha, actor, self.environment(status))
            evidence: dict = {}
            result_status = "BLOCKED"
            result_sha = sha
            try:
                if run["contract_hash"] != status["contract_hash"]:
                    raise ControllerError("Contract changed between handoff and run admission")
                directory = self._run_directory(run["run_id"])
                self._identity(status, source)
                self._sources(status, source)
                work = self._evidence_workspace(status, "review") if role == "review" else source
                self._sources(status, work)
                prompt = self._prompt(status, role)
                output = directory / "worker"
                if self.synthetic:
                    config = {"env": []}
                    argv = [sys.executable, str(ROOT / "examples/fixture_worker.py"), role, str(output)]
                    write_json(output / "handoff.json", {"task": status["task"], "prompt": prompt})
                    extra = []
                else:
                    config, extra = self._harness(status["profile"], harness)
                    session = None
                    if role == "implement":
                        session = output / "session.jsonl"
                        # Only same contract/workspace/harness may resume. Review is
                        # always fresh, and never receives this session transcript.
                        for previous in reversed(status["runs"]):
                            candidate = self.state / "runs" / previous["run_id"] / "worker/session.jsonl"
                            if (previous["role"] == role and previous["contract_hash"] == status["contract_hash"]
                                    and previous["actor_id"].startswith("implement:" + harness + ":")
                                    and candidate.is_file() and not candidate.is_symlink()):
                                shutil.copyfile(candidate, session)
                                break
                    input_path = directory / "input.json"
                    tools = ["read", "grep", "find"] + (["write", "edit"] if role == "implement" else [])
                    write_json(input_path, {"schema_version": 1, "role": role, "prompt": prompt,
                        "output_dir": str(output), "provider": config["provider"], "model": config["model"],
                        "sdk_module": config["sdk_module"], "tools": tools,
                        "session_path": str(session) if session else None,
                        **({"auth_file": config["auth_file"]} if config.get("auth_file") else {})})
                    flags = []
                    if harness == "omp":
                        bunfig = directory / "trusted-bunfig.toml"
                        bunfig.write_text("# No project preload or auto installation\npreload = []\n")
                        flags = ["--no-env-file", "--no-install", "--config", str(bunfig)]
                        extra.append(bunfig)
                    argv = [config["runtime"], *flags, str(ROOT / "adapters" / (harness + ".mjs")), str(input_path)]
                    extra.append(input_path)
                evidence = self._execute(status, argv, work, work, directory, config.get("env", []), extra,
                    readonly=role == "review", timeout=status["profile"]["runtime"]["timeout_seconds"], network=not self.synthetic)
                result_status = evidence["status"]
                file = output / "result.json"
                if evidence["status"] == "PASS":
                    if file.is_symlink() or not file.is_file() or file.stat().st_size > 1024 * 1024:
                        raise ControllerError("Missing or invalid structured worker result")
                    result = json.loads(file.read_text())
                    if not isinstance(result, dict):
                        raise ControllerError("Worker result must be a JSON object")
                    if result.get("role") != role or result.get("status") not in ("PASS", "FAIL", "BLOCKED"):
                        raise ControllerError("Worker result role/status does not match its launch")
                    result_status = result["status"]
                    evidence.update({k: result[k] for k in ("covered_ac", "lenses", "findings", "text") if k in result})
                    # Copy the verdict out of the worker-writable output tree.
                    receipt = directory / "result.json"
                    write_json(receipt, result)
                    evidence["files"].append({"path": str(receipt), "sha256": digest(receipt)})
                    if result_status == "PASS":
                        self._identity(status, source)
                        self._sources(status, source)
                        if role == "implement":
                            result_sha = workspace.snapshot(source, status["task"]["scope"], task_id)
                        elif workspace.git(work, "rev-parse", "HEAD") != sha or workspace.git(work, "status", "--porcelain", "--untracked-files=all"):
                            raise ControllerError("Reviewer changed its source snapshot")
                evidence["synthetic"] = self.synthetic
                evidence["harness"] = "fixture" if self.synthetic else harness
            except (ControllerError, workspace.WorkspaceError, process.ExecutionError, OSError, ValueError) as exc:
                result_status = "BLOCKED"
                evidence["reason"] = str(exc)
            return self.controller.finish_run(run["run_id"], result_status, result_sha, evidence)

    def check(self, task_id: str, check_id: str | None = None) -> list[dict]:
        results = []
        with self.lock(task_id):
            initial = self.controller.status(task_id)
            checks = initial["profile"]["verification"]["checks"]
            if check_id is not None:
                checks = [check for check in checks if check["id"] == check_id]
                if not checks:
                    raise ControllerError("Unknown check: " + check_id)
            for check in checks:
                status = self.controller.status(task_id)
                source = Path(status["workspace"]["path"] or self.repo)
                sha = workspace.git(source, "rev-parse", "HEAD")
                run = self.controller.begin_run(task_id, "check:" + check["id"], sha,
                    "check:" + check["id"] + ":" + os.urandom(8).hex(), self.environment(status))
                evidence: dict = {}
                try:
                    if run["contract_hash"] != status["contract_hash"]:
                        raise ControllerError("Contract changed between check selection and run admission")
                    directory = self._run_directory(run["run_id"])
                    self._identity(status, source)
                    self._sources(status, source)
                    # Ignored or uncommitted implementation artifacts must not
                    # influence verification of a committed candidate.
                    work = self._evidence_workspace(status, "verify")
                    self._sources(status, work)
                    cwd = (work / check.get("cwd", ".")).resolve()
                    if not cwd.is_relative_to(work) or not cwd.is_dir():
                        raise ControllerError("Verification cwd escaped or is missing")
                    evidence = self._execute(status, check["argv"], cwd, work, directory,
                        check.get("env", []), [], readonly=True,
                        timeout=min(check["timeout_seconds"], status["profile"]["runtime"]["timeout_seconds"]),
                        network=check.get("network") is True)
                    evidence.update({"argv": check["argv"], "synthetic": self.synthetic})
                    self._identity(status, source)
                    self._sources(status, source)
                    if workspace.git(work, "rev-parse", "HEAD") != sha or workspace.git(work, "status", "--porcelain", "--untracked-files=all"):
                        raise ControllerError("Verification command changed its source snapshot")
                except (ControllerError, workspace.WorkspaceError, process.ExecutionError, OSError, ValueError) as exc:
                    evidence.update({"status": "BLOCKED", "reason": str(exc)})
                results.append(self.controller.finish_run(run["run_id"], evidence["status"], sha, evidence))
        return results

    def finalize(self, task_id: str) -> dict:
        with self.lock(task_id):
            status = self.controller.status(task_id)
            work = Path(status["workspace"]["path"] or self.repo)
            self._identity(status, work)
            self._sources(status, work)
            return self.controller.finalize(task_id, workspace.git(work, "rev-parse", "HEAD"), self.environment(status))

    def cancel(self, task_id: str) -> dict:
        status = self.controller.cancel(task_id)
        for run in status["runs"]:
            if run["status"] == "RUNNING":
                record = self.state / "runs" / run["run_id"] / "logs/process.json"
                if record.is_file():
                    process.stop(json.loads(record.read_text()))
        return self.controller.status(task_id)

    def recover(self, task_id: str) -> dict:
        with self.lock(task_id):
            status = self.controller.status(task_id)
            for run in status["runs"]:
                if run["status"] == "RUNNING":
                    record = self.state / "runs" / run["run_id"] / "logs/process.json"
                    if record.is_file():
                        identity = json.loads(record.read_text())
                        if identity.get("identity_unavailable") and not identity.get("completed"):
                            raise ControllerError("Cannot prove the abandoned process stopped on this host; inspect it before recovery")
                        if process.alive(identity):
                            raise ControllerError("Worker is still alive; cancel it and inspect effects before recovery")
            return self.controller.recover(task_id)

    def pr_body(self, task_id: str) -> str:
        # Always re-evaluate evidence against current bytes/SHA, even if a past
        # invocation already recorded VERIFIED.
        status = self.finalize(task_id)
        task = status["task"]
        lines = ["## Change", "", "Implements " + task["spec"] + ".", "", "## Evidence", "",
                 "- Candidate: `" + status["candidate_sha"] + "`",
                 "- Contract: `" + status["contract_hash"] + "`",
                 "- Environment: `" + self.environment(status) + "`"]
        for run in status["runs"]:
            if run["generation"] == status["generation"] and run["source_sha"] == status["candidate_sha"]:
                lines.append("- " + run["role"] + ": " + run["status"] + " (`" + run["run_id"] + "`)")
        lines += ["", "## Scope and decisions", "", "- Scope: " + ", ".join(task["scope"]),
                  "- ADRs: " + (", ".join(adr["path"] for adr in task["adrs"]) or "none triggered"),
                  "", "## Merge risk", "", "Review the residual risks and rollout constraints in the spec. "
                  "VERIFIED covers the recorded contract/SHA/environment; it does not authorize merge or deployment."]
        if self.synthetic:
            lines += ["", "**Synthetic fixture run: no live model/provider or OS sandbox was exercised.**"]
        return "\n".join(lines) + "\n"
