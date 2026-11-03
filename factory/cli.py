"""Harness-independent operator CLI. No hidden install, push, merge or deployment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path

from .controller import Controller, ControllerError
from .runtime import Runtime, ROOT, write_json
from . import process, workspace


def default_state(repo: Path) -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    common = workspace.git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return root / "law-factory" / hashlib.sha256(str(Path(common).resolve()).encode()).hexdigest()[:16]


def init(repo: Path) -> dict:
    workspace.git(repo, "rev-parse", "--show-toplevel")
    file = repo / ".factory/project.json"
    if file.exists():
        raise ControllerError("Project profile already exists; edit it explicitly")
    harness = {"runtime": "", "sdk_module": "", "provider": "", "model": "", "env": [], "read_only_paths": []}
    write_json(file, {"schema_version": 1, "project_id": repo.name,
        "instructions": [], "workspace": {"provider": "git"},
        "preview": {"environment_id": repo.name + ":local", "isolation": "serial"},
        "verification": {"checks": []},
        "runtime": {"max_runs": 8, "timeout_seconds": 900, "output_limit_bytes": 1048576, "sandbox": "bubblewrap"},
        "harnesses": {"pi": dict(harness), "omp": dict(harness)}})
    return {"status": "DRAFT", "profile": str(file),
            "next": "Set actual check argv, selected project instructions and trusted harness installation/model; create a spec, ADR records, test contract and task manifest. Commit the canonical input before admission."}


def doctor(repo: Path, state: Path) -> dict:
    sandbox = process.sandbox_probe()
    profile_file = repo / ".factory/project.json"
    profile = json.loads(profile_file.read_text()) if profile_file.is_file() else {}
    configured = {}
    for harness in ("pi", "omp"):
        config = profile.get("harnesses", {}).get(harness, {})
        configured[harness] = {
            "runtime_exists": bool(config.get("runtime") and Path(config["runtime"]).is_file()),
            "sdk_exists": bool(config.get("sdk_module") and Path(config["sdk_module"]).is_file()),
            "model_configured": bool(config.get("provider") and config.get("model")),
            "live_provider": "NOT_RUN",
        }
    outside = not state.resolve().is_relative_to(repo.resolve()) and not repo.resolve().is_relative_to(state.resolve())
    installed = any(all(item[k] for k in ("runtime_exists", "sdk_exists", "model_configured")) for item in configured.values())
    return {"status": "PASS" if sandbox["ready"] and outside and installed and shutil.which("git") else "BLOCKED",
            "python": platform.python_version(), "platform": sys.platform,
            "sandbox": sandbox, "state_outside_checkout": outside,
            "git": shutil.which("git"), "worktrunk": shutil.which("wt"),
            "harnesses": configured,
            "note": "Doctor checks local prerequisites only; admission validates contracts and a real run validates the pinned SDK and provider. Worktree is not a sandbox."}


def demo(destination: Path) -> dict:
    destination = destination.resolve()
    if destination.exists():
        raise ControllerError("Demo destination already exists; choose a new directory")
    destination.mkdir(parents=True, mode=0o700)
    repo, state = destination / "repo", destination / "state"
    shutil.copytree(ROOT / "examples/project", repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    workspace.git(repo, "init", "-b", "main")
    workspace.git(repo, "add", "--all")
    workspace.git(repo, "-c", "user.name=LAW Demo", "-c", "user.email=demo@localhost",
                  "commit", "--no-gpg-sign", "-m", "Seed the synthetic billing contract and defect")
    control = Controller(repo, state)
    runner = Runtime(control, synthetic=True)
    task_id = "billing-rounding"
    # A defect-catching check is observed red on the actual baseline before repair.
    before_dir = state / "baseline"
    before_dir.mkdir()
    baseline = process.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        repo, process.clean_environment([], before_dir), before_dir, 10, 262144, lambda: False)
    if baseline["status"] != "FAIL":
        raise ControllerError("The seeded defect was not detected by the independent contract checks")
    control.create(".factory/tasks/billing.json")
    control.admit(task_id)
    runner.prepare_workspace(task_id)
    implementation = runner.worker(task_id, "implement", "fixture")
    if implementation["status"] != "PASS":
        raise ControllerError("Demo implementation failed: " + json.dumps(implementation["evidence"]))
    checks = runner.check(task_id)
    review = runner.worker(task_id, "review", "fixture")
    final = runner.finalize(task_id)
    body = destination / "PR_BODY.md"
    body.write_text(runner.pr_body(task_id))
    result = {"status": final["state"], "synthetic": True, "live_model": "NOT_RUN",
        "sandbox": "NOT_RUN: explicitly trusted-local deterministic fixture",
        "baseline": baseline["status"], "implementation": implementation["status"],
        "checks": [{"role": run["role"], "status": run["status"]} for run in checks],
        "review": review["status"], "source_sha": final["candidate_sha"],
        "contract_hash": final["contract_hash"], "repo": str(repo), "state_dir": str(state), "pr_body": str(body)}
    write_json(destination / "result.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="LAW factory controller and controlled Pi/OMP launcher")
    value.add_argument("--repo", type=Path, default=Path.cwd())
    value.add_argument("--state-dir", type=Path)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create an incomplete project profile; never guess commands or models")
    commands.add_parser("doctor", help="Check local execution prerequisites")
    item = commands.add_parser("create", help="Register or update the canonical task contract")
    item.add_argument("manifest", type=Path)
    for command in ("admit", "workspace", "status", "finalize", "cancel", "recover", "pr-body"):
        item = commands.add_parser(command)
        item.add_argument("task_id")
    for command in ("run", "review"):
        item = commands.add_parser(command)
        item.add_argument("task_id")
        item.add_argument("--harness", required=True, choices=["pi", "omp"])
    item = commands.add_parser("check")
    item.add_argument("task_id")
    item.add_argument("--check", dest="check_id")
    item = commands.add_parser("demo", help="Execute a synthetic fixture, with real Git/SQLite/checks but no model or sandbox")
    item.add_argument("destination", type=Path)
    for command in ("search", "symbol"):
        item = commands.add_parser(command)
        item.add_argument("query")
        item.add_argument("--limit", type=int, default=20)
    commands.add_parser("index-health")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        repo = args.repo.resolve()
        if args.command == "demo":
            result = demo(args.destination)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        repo = Path(workspace.git(repo, "rev-parse", "--show-toplevel")).resolve()
        state = (args.state_dir or default_state(repo)).resolve()
        if args.command == "init":
            result = init(repo)
        elif args.command == "doctor":
            result = doctor(repo, state)
        elif args.command in ("search", "symbol", "index-health"):
            from . import intelligence
            result = intelligence.health(repo) if args.command == "index-health" else getattr(intelligence, args.command)(repo, args.query, limit=args.limit)
        else:
            controller = Controller(repo, state)
            runner = Runtime(controller)
            command = args.command
            if command == "create":
                result = controller.create(args.manifest)
            elif command in ("admit", "status"):
                result = getattr(controller, command)(args.task_id)
            elif command == "workspace":
                result = runner.prepare_workspace(args.task_id)
            elif command in ("run", "review"):
                result = runner.worker(args.task_id, "implement" if command == "run" else "review", args.harness)
            elif command == "check":
                result = runner.check(args.task_id, args.check_id)
            elif command == "pr-body":
                print(runner.pr_body(args.task_id), end="")
                return 0
            else:
                result = getattr(runner, command)(args.task_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if isinstance(result, list):
            return 0 if all(item.get("status") == "PASS" for item in result) else 2
        return 2 if result.get("status", result.get("state")) in ("BLOCKED", "FAIL", "CANCELLED", "NOT_RUN", "unavailable", "stale") else 0
    except (ControllerError, workspace.WorkspaceError, process.ExecutionError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
