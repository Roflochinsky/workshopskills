"""Bounded child execution and a fail-closed Linux bubblewrap boundary."""
from __future__ import annotations

import hashlib
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable


class ExecutionError(RuntimeError):
    pass


def clean_environment(names: list[str], work: Path) -> dict[str, str]:
    # No ambient cloud, production, Git, proxy, or application credentials.
    if not isinstance(names, list):
        raise ExecutionError("Environment inheritance must be an explicit list of names")
    result = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(work / "home"),
        "XDG_CONFIG_HOME": str(work / "home/.config"),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "FACTORY_RUN_DIR": str(work),
    }
    for name in names:
        if not isinstance(name, str) or not name or "=" in name or "\x00" in name:
            raise ExecutionError("Invalid environment variable name")
        if name in ("HOME", "PATH", "XDG_CONFIG_HOME", "PYTHONPATH", "PYTHONSTARTUP",
                    "NODE_OPTIONS", "NODE_PATH", "LD_PRELOAD", "LD_LIBRARY_PATH",
                    "BASH_ENV", "ENV", "PI_CODING_AGENT_DIR") or name.startswith("BUN_"):
            raise ExecutionError("Runtime control variables may not be inherited: " + name)
        if name in os.environ:
            result[name] = os.environ[name]
    (work / "home").mkdir(parents=True, exist_ok=True)
    return result


def sandbox_probe() -> dict:
    binary = shutil.which("bwrap")
    if not binary:
        return {"ready": False, "reason": "bubblewrap is not installed"}
    # Only the fixed /bin/true probe sees this read-only root. Workers receive the
    # narrow mount list below; the probe must include the host dynamic loader.
    try:
        result = subprocess.run(
            [binary, "--ro-bind", "/", "/", "--unshare-user", "--unshare-pid",
             "--proc", "/proc", "/bin/true"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ready": False, "reason": str(exc)}
    return {"ready": result.returncode == 0,
            "reason": result.stderr.strip() if result.returncode else "namespace probe passed"}


def sandbox_command(argv: list[str], cwd: Path, workspace: Path, output: Path,
                    readonly: bool, extra_read: list[Path], state_dir: Path,
                    network: bool) -> list[str]:
    ready = sandbox_probe()
    if not ready["ready"]:
        raise ExecutionError("Sandbox unavailable; execution blocked: " + ready["reason"])
    workspace, output, state_dir = workspace.resolve(), output.resolve(), state_dir.resolve()
    mounts = {}
    for raw in ["/usr", "/bin", "/lib", "/lib64",
                "/etc/ssl", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf",
                *map(str, extra_read)]:
        path = Path(raw)
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved in (Path("/"), Path.home().resolve(), Path("/home"), state_dir) or state_dir.is_relative_to(resolved):
            raise ExecutionError("Read-only mount would expose controller state: " + str(path))
        mounts[str(path)] = str(resolved)
    args = ["bwrap", "--die-with-parent", "--new-session", "--unshare-user",
            "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--proc", "/proc",
            "--dev", "/dev", "--tmpfs", "/tmp"]
    if not network:
        args.append("--unshare-net")
    for target, source in mounts.items():
        args += ["--ro-bind", source, target]
    args += ["--ro-bind" if readonly else "--bind", str(workspace), str(workspace)]
    args += ["--bind", str(output), str(output)]
    # Git operations can inspect objects, but the agent cannot mutate shared refs/index.
    common = subprocess.check_output(
        ["git", "-C", str(workspace), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        text=True).strip()
    args += ["--ro-bind", common, common]
    args += ["--ro-bind", str(workspace / ".git"), str(workspace / ".git")]
    # Block runtime discovery/agent edits of the input profile and provider configuration.
    for name in (".factory", ".omp", ".pi", ".claude", ".codex", ".agents", ".agent",
                 ".opencode", ".gemini"):
        target = workspace / name
        if target.exists():
            if not target.is_dir() or target.is_symlink():
                raise ExecutionError("Provider configuration must be a regular directory: " + name)
            args += ["--tmpfs", str(target)]
    # Bun has startup config discovery, and OMP also reads project .env during
    # SDK import independently of Bun's --no-env-file. Hide those files before
    # the interpreter starts; the immutable replacement is outside worker output.
    empty = output.parent / "empty-runtime-config"
    empty.write_text("")
    empty.chmod(0o600)
    config_files = list(workspace.glob(".env*")) + [workspace / "bunfig.toml"]
    for target in config_files:
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file():
                raise ExecutionError("Runtime config must be a regular file: " + target.name)
            args += ["--ro-bind", str(empty), str(target)]
    args += ["--chdir", str(cwd), "--", *argv]
    return args


def identity(pid: int) -> dict | None:
    """Linux process identity; never signal an unrelated process after PID reuse."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        # comm may contain spaces and closing parentheses.
        fields = stat[stat.rfind(")") + 2:].split()
        return {"pid": pid, "start_ticks": fields[19],
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "zombie": fields[0] == "Z"}
    except (OSError, IndexError):
        return None


def alive(record: dict) -> bool:
    current = identity(record.get("pid", 0))
    return bool(current and not current["zombie"] and all(
        current.get(key) == record.get(key) for key in ("pid", "start_ticks", "boot_id")))


def stop(record: dict) -> None:
    if alive(record):
        try:
            os.killpg(record["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass


def run(argv: list[str], cwd: Path, env: dict[str, str], output: Path,
        timeout: float, limit: int, cancelled: Callable[[], bool]) -> dict:
    """Drain both pipes, stop the process group, and persist bounded raw evidence."""
    if not argv or not all(isinstance(x, str) and x and "\x00" not in x for x in argv):
        raise ExecutionError("argv must be a nonempty list of strings")
    if timeout <= 0 or limit <= 0:
        raise ExecutionError("Positive time/output budgets are required")
    output.mkdir(parents=True, exist_ok=True)
    paths = {name: output / (name + ".log") for name in ("stdout", "stderr")}
    handles = {name: p.open("wb") for name, p in paths.items()}
    start = time.monotonic()
    process = None
    selector = None
    reason = None
    total = 0
    try:
        read_fd, release_fd = os.pipe()
        try:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("child_guard.py")), str(read_fd), *argv],
                cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True, pass_fds=(read_fd,))
            record = identity(process.pid) or {"pid": process.pid, "identity_unavailable": True}
            with (output / "process.json").open("w") as stream:
                json.dump(record, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.write(release_fd, b"G")
        finally:
            os.close(read_fd)
            os.close(release_fd)
        selector = selectors.DefaultSelector()
        for pipe, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map():
            if reason is None:
                if cancelled():
                    reason = "cancelled"
                elif time.monotonic() - start > timeout:
                    reason = "timeout"
                elif total > limit:
                    reason = "output_limit"
                if reason:
                    # bwrap's PID namespace contains worker descendants. A process
                    # group is also sufficient for the trusted synthetic fixture.
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            for key, _ in selector.select(0.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                remaining = max(0, limit - total)
                handles[key.data].write(chunk[:remaining])
                total += len(chunk)
                if total > limit and reason is None:
                    reason = "output_limit"
            if reason:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            # Bound pipe collection even if a descendant keeps a descriptor open.
            if time.monotonic() - start > timeout + 3:
                for key in list(selector.get_map().values()):
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
        # A child may close its pipes before exiting; budgets still apply.
        while process.poll() is None:
            if cancelled() or time.monotonic() - start > timeout or reason:
                reason = reason or ("cancelled" if cancelled() else "timeout")
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        code = process.wait(timeout=5)
    except BaseException:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    finally:
        if selector is not None:
            selector.close()
        for handle in handles.values():
            handle.close()
    # Some managed hosts virtualize syscall PIDs without a matching /proc view.
    # The owning Popen still observes its child, but another launcher must not
    # signal or recover an unknown PID. Persist completion for that case.
    record["completed"] = True
    (output / "process.json").write_text(json.dumps(record))
    return {
        "status": "PASS" if code == 0 and reason is None else
                  ("BLOCKED" if reason else "FAIL"),
        "exit_code": code, "reason": reason, "seconds": round(time.monotonic() - start, 3),
        "files": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in paths.values()],
    }
