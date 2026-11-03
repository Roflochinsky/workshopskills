"""Git metadata operations without hooks, fsmonitor, or content-filter programs.

The controller preserves raw repository bytes. Git LFS and other clean/smudge
transformations need a separate trusted integration; they are never executed on
the host as a side effect of inspecting or committing a worker's changes.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess


class GitError(RuntimeError):
    pass


def git(path: Path, *args: str, timeout: float = 30) -> str:
    # Explicit -C must not be redirected by an ambient Git hook's environment.
    redirects = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                 "GIT_NAMESPACE", "GIT_CONFIG", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS"}
    env = {k: v for k, v in os.environ.items()
           if k not in redirects and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    base = ["git", "--literal-pathspecs", "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false", "-C", str(path)]
    try:
        # Reading config does not run the programs it names. Names only + NUL
        # keeps embedded newlines in subsection names unambiguous.
        config = subprocess.run(
            [*base, "config", "--null", "--name-only", "--get-regexp",
             r"^filter\..*\.(clean|smudge|process|required)$"],
            capture_output=True, text=True, check=False, timeout=timeout, env=env,
        )
        if config.returncode not in (0, 1):
            raise GitError(config.stderr.strip() or "Cannot inspect Git filter configuration")
        drivers = {key.rsplit(".", 1)[0] for key in config.stdout.split("\0") if key}
        overrides = []
        for driver in sorted(drivers):
            for setting in ("clean=", "smudge=", "process=", "required=false"):
                overrides += ["-c", driver + "." + setting]
        arguments = list(args)
        if arguments and arguments[0] == "diff":
            arguments[1:1] = ["--no-ext-diff", "--no-textconv"]
        result = subprocess.run(
            [*base, *overrides, *arguments], capture_output=True, text=True,
            check=False, timeout=timeout, env=env,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise GitError(f"Git operation failed ({' '.join(args[:2])}): {exc}") from exc
    if result.returncode:
        raise GitError(result.stderr.strip() or result.stdout.strip() or
                       f"Git operation failed ({' '.join(args[:2])}): exit {result.returncode}")
    # NUL-delimited path lists must retain all filename whitespace.
    return result.stdout if "-z" in arguments else result.stdout.strip()
