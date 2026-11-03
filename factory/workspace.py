"""Controller-owned Git/Worktrunk workspaces. Never force-remove user changes."""
from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

from .safegit import GitError, git as safe_git


class WorkspaceError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> str:
    try:
        return safe_git(repo, *args)
    except GitError as exc:
        raise WorkspaceError(str(exc)) from exc


def inventory(repo: Path) -> dict[str, dict]:
    records = {}
    for block in git(repo, "worktree", "list", "--porcelain").split("\n\n"):
        entry = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            entry[key] = value
        if "worktree" in entry:
            records[str(Path(entry["worktree"]).resolve())] = entry
    return records


def create(repo: Path, path: Path, branch: str, base: str, provider: str) -> Path:
    path = path.resolve()
    current = inventory(repo).get(str(path))
    if current:
        # Crash recovery may find the completed worktree. Never repeat its creation.
        if current.get("HEAD") != base or current.get("branch") != "refs/heads/" + branch:
            raise WorkspaceError("Existing worktree does not match the requested branch/base")
        if git(path, "status", "--porcelain"):
            raise WorkspaceError("Existing worktree is dirty; inspect it before recovery")
        return path
    if path.exists():
        raise WorkspaceError("Unregistered workspace path already exists: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if provider == "git":
        git(repo, "worktree", "add", "-b", branch, str(path), base)
    elif provider == "worktrunk":
        result = subprocess.run([
            "wt", "-C", str(repo), "switch", "--create", branch, "--base", base,
            "--path", str(path), "--no-cd", "--no-hooks", "--format=json",
        ], capture_output=True, text=True, check=False)
        # wt may create a worktree before a later failure; inspect the durable result.
        if str(path) not in inventory(repo):
            raise WorkspaceError("Worktrunk did not create the workspace: " + result.stderr)
    else:
        raise WorkspaceError("Provider cannot create worktrees: " + provider)
    entry = inventory(repo).get(str(path), {})
    if entry.get("HEAD") != base or entry.get("branch") != "refs/heads/" + branch:
        raise WorkspaceError("Workspace creation produced an unexpected branch or revision")
    return path


def attach(repo: Path, path: Path, base: str) -> Path:
    path = path.resolve()
    entry = inventory(repo).get(str(path))
    if not entry or entry.get("HEAD") != base:
        raise WorkspaceError("External owner must supply a registered worktree at the required SHA")
    if git(path, "status", "--porcelain"):
        raise WorkspaceError("External worktree must be clean")
    return path


def remove(repo: Path, path: Path, provider: str) -> None:
    if provider == "existing":
        raise WorkspaceError("The external workspace owner alone may remove this worktree")
    if git(path, "status", "--porcelain"):
        raise WorkspaceError("Refusing to remove a dirty worktree")
    if provider == "git":
        git(repo, "worktree", "remove", str(path))
    elif provider == "worktrunk":
        result = subprocess.run([
            "wt", "-C", str(repo), "remove", "--foreground", "--no-hooks",
            "--no-delete-branch", "--format=json", str(path),
        ], capture_output=True, text=True, check=False)
        if str(path.resolve()) in inventory(repo):
            raise WorkspaceError("Worktrunk did not remove the worktree: " + result.stderr)
    else:
        raise WorkspaceError("Unknown workspace provider")


def snapshot(path: Path, scope: list[str], task_id: str) -> str:
    """Commit only an in-scope candidate, leaving failed/out-of-scope edits for inspection."""
    changed = git(path, "diff", "--no-renames", "--name-only", "-z", "HEAD").split("\0")
    untracked = git(path, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    paths = sorted(set(changed + untracked) - {""})
    forbidden = [p for p in paths if not any(fnmatch.fnmatchcase(p, pat) for pat in scope)]
    if forbidden:
        raise WorkspaceError("Out-of-scope edits: " + ", ".join(forbidden))
    if any(p == ".git" or p.startswith(".git/") for p in paths):
        raise WorkspaceError("Git metadata is not implementation scope")
    if paths:
        git(path, "add", "--all", "--", *paths)
        git(path, "-c", "user.name=LAW Factory", "-c", "user.email=factory@localhost",
            "commit", "--no-gpg-sign", "-m", "factory(" + task_id + "): implementation candidate")
    return git(path, "rev-parse", "HEAD")
