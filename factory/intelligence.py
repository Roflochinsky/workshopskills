"""Bounded, live source search. No semantic retrieval, session mining, or cached index.

All results describe an observed Git worktree and identify both its HEAD and the
bytes actually searched. Absence of a lexical match is never proof that reusable
behavior does not exist. The controller must freeze/recheck the candidate when
using this observation for an admission decision.
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any


EXTRACTION_VERSION = "law-live-source-v1"
MAX_FILE_BYTES = 1_000_000
MAX_CORPUS_BYTES = 32_000_000
MAX_FILES = 10_000
MAX_GIT_BYTES = 16_000_000
MAX_RESULTS = 100
MAX_EXCERPT_CHARS = 300
EXCLUDED_ROOTS = frozenset({".git", ".factory"})


class IntelligenceError(ValueError):
    """The source observation could not be established safely."""


@dataclass
class _Source:
    path: str
    text: str
    sha256: str
    metadata: tuple[int, ...]


@dataclass
class _Snapshot:
    root: Path
    manifest: dict[str, Any]
    sources: list[_Source]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(repo: Path, *arguments: str) -> bytes:
    # No hooks, external diff drivers, textconv, pager, interactive prompts or
    # optional index writes are needed to inspect source.
    command = [
        "git", "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
        "-c", "core.hooksPath=/dev/null", "-C", os.fspath(repo), *arguments,
    ]
    try:
        completed = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=20, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise IntelligenceError("Git source inspection is unavailable or timed out.") from error
    if completed.returncode:
        raise IntelligenceError("Git could not inspect the requested worktree.")
    if len(completed.stdout) > MAX_GIT_BYTES:
        raise IntelligenceError("Git source inventory exceeds the bounded inspection limit.")
    return completed.stdout


def _state(root: Path) -> tuple[str, bytes, bytes]:
    head = _git(root, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise IntelligenceError("Git returned an invalid HEAD identity.")
    inventory = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    # Raw Git change records are combined with the searched-content digest below.
    # A raw record alone does not distinguish two unstaged edits to the same file.
    raw_diff = _git(root, "diff", "--no-ext-diff", "--no-textconv", "--raw", "-z", "--no-abbrev", "HEAD", "--")
    return head, inventory, raw_diff


def _metadata(value: os.stat_result) -> tuple[int, ...]:
    return value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_ino, value.st_dev


def _scoped_open(root_fd: int, relative: str) -> int:
    """Walk from an already opened root; never follow a symlink in any component."""
    parsed = PurePosixPath(relative)
    parts = parsed.parts
    if parsed.is_absolute() or not parts or any(part in {".", ".."} for part in parts):
        raise IntelligenceError("Git reported a path outside the source scope.")
    current = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
    finally:
        os.close(current)


def _read_source(root_fd: int, name: str, remaining_bytes: int) -> tuple[_Source | None, str, tuple[int, ...] | None]:
    descriptor: int | None = None
    try:
        descriptor = _scoped_open(root_fd, name)
        before = os.fstat(descriptor)
        metadata = _metadata(before)
        if not stat.S_ISREG(before.st_mode):
            return None, "not_regular", metadata
        if before.st_size > MAX_FILE_BYTES:
            return None, "too_large", metadata
        if before.st_size > remaining_bytes:
            return None, "corpus_budget", metadata
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(min(MAX_FILE_BYTES, remaining_bytes) + 1)
            after = os.fstat(stream.fileno())
        if metadata != _metadata(after):
            return None, "changed_during_read", metadata
        if len(data) > MAX_FILE_BYTES or len(data) > remaining_bytes:
            return None, "grew_over_budget", metadata
        if b"\0" in data:
            return None, "binary", metadata
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return None, "non_utf8", metadata
        return _Source(name, text, _sha(data), metadata), "indexed", metadata
    except FileNotFoundError:
        return None, "deleted", None
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            return None, "symlink_or_replaced_parent", None
        return None, "unreadable", None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _still_same(root_fd: int, source: _Source) -> bool:
    descriptor: int | None = None
    try:
        descriptor = _scoped_open(root_fd, source.path)
        return _metadata(os.fstat(descriptor)) == source.metadata
    except (OSError, IntelligenceError):
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _observe(repo: os.PathLike[str] | str) -> _Snapshot:
    requested = Path(repo).resolve(strict=True)
    root = Path(os.fsdecode(_git(requested, "rev-parse", "--show-toplevel").removesuffix(b"\n"))).resolve(strict=True)
    if requested != root:
        raise IntelligenceError("Pass the worktree root explicitly; source search does not widen a subdirectory scope.")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY") or os.open not in os.supports_dir_fd:
        raise IntelligenceError("This host cannot safely open source paths without following symlinks.")
    common = Path(os.fsdecode(_git(root, "rev-parse", "--git-common-dir").removesuffix(b"\n")))
    if not common.is_absolute():
        common = root / common
    repository_id = _sha(os.fsencode(common.resolve(strict=True)))
    start_head, start_inventory, start_diff = _state(root)
    paths = sorted({os.fsdecode(item) for item in start_inventory.split(b"\0") if item})
    counts: Counter[str] = Counter()
    counts["inventory_paths"] = len(paths)
    sources: list[_Source] = []
    skipped: list[dict[str, str]] = []
    content = hashlib.sha256(EXTRACTION_VERSION.encode())
    scope = hashlib.sha256()
    total_bytes = 0
    opened_files = 0
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in paths:
            parts = PurePosixPath(name).parts
            if not parts or parts[0] in EXCLUDED_ROOTS:
                counts["excluded_root"] += 1
                continue
            if opened_files >= MAX_FILES:
                counts["file_budget"] += 1
                scope.update(os.fsencode(name) + b"\0file_budget\0")
                continue
            opened_files += 1
            source, reason, metadata = _read_source(root_fd, name, MAX_CORPUS_BYTES - total_bytes)
            counts[reason] += 1
            scope.update(os.fsencode(name) + b"\0" + reason.encode() + b"\0")
            if source is None:
                if metadata is not None:
                    scope.update(repr(metadata).encode() + b"\0")
                if len(skipped) < 30:
                    skipped.append({"path": name, "reason": reason})
                continue
            sources.append(source)
            total_bytes += len(source.text.encode("utf-8"))
            content.update(os.fsencode(name) + b"\0" + source.sha256.encode() + b"\0")
        metadata_stable = all(_still_same(root_fd, source) for source in sources)
        end_head, end_inventory, end_diff = _state(root)
    finally:
        os.close(root_fd)
    stable = metadata_stable and (start_head, start_inventory, start_diff) == (end_head, end_inventory, end_diff)
    stable = stable and not counts["changed_during_read"] and not counts["grew_over_budget"]
    content_digest = content.hexdigest()
    inventory_digest = _sha(start_inventory)
    scope_digest = scope.hexdigest()
    diff_digest = _sha(start_diff + b"\0" + content_digest.encode() + b"\0" + inventory_digest.encode() + b"\0" + scope_digest.encode())
    partial = any(counts[reason] for reason in ["file_budget", "corpus_budget", "too_large", "unreadable", "changed_during_read", "grew_over_budget"])
    manifest: dict[str, Any] = {
        "repository_id": repository_id,
        "worktree": os.fspath(root),
        "head_sha": start_head,
        "worktree_diff_digest": diff_digest,
        "content_digest": content_digest,
        "path_inventory_digest": inventory_digest,
        "scope_digest": scope_digest,
        "extraction_version": EXTRACTION_VERSION,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "stable_observation": stable,
        "partial": partial,
        "scope": "Git tracked and nonignored untracked UTF-8 regular files, excluding .git and .factory",
        "diff_digest_basis": "Git raw HEAD change records + searched content + path inventory + skipped-file metadata",
        "line_convention": "LF-separated UTF-8 source; columns count Unicode code points",
        "counts": dict(counts),
        "indexed_bytes": total_bytes,
        "skipped_examples": skipped,
        "limits": {"file_bytes": MAX_FILE_BYTES, "corpus_bytes": MAX_CORPUS_BYTES, "files": MAX_FILES, "results": MAX_RESULTS},
        "limitations": [
            "Live observation is not an atomic snapshot; freeze or recheck the worktree before a gate.",
            "Binary, non-UTF-8, symlink, excluded and over-budget file contents are not searched or content-hashed.",
            "Literal matches do not establish semantic equivalence, safe reuse, references or impact completeness.",
            "No match means no literal match in this observed scope; it never proves reusable behavior is absent.",
            "There is no vector index, language-server graph or session-derived knowledge in this baseline.",
        ],
    }
    return _Snapshot(root, manifest, sources)


def _base_result(snapshot: _Snapshot) -> dict[str, Any]:
    manifest = snapshot.manifest
    status = "stale" if not manifest["stable_observation"] else "partial" if manifest["partial"] else "ok"
    return {"status": status, "mode": "live-lexical", "manifest": manifest}


def _unavailable(error: Exception) -> dict[str, Any]:
    return {"status": "unavailable", "mode": "live-lexical", "manifest": None,
            "error": str(error), "results": [], "truncated": False}


def _arguments(query: str, limit: int) -> tuple[str, int]:
    if not isinstance(query, str) or not query.strip() or len(query) > 256:
        raise IntelligenceError("Provide a nonempty literal query of at most 256 characters.")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_RESULTS:
        raise IntelligenceError(f"limit must be an integer from 1 to {MAX_RESULTS}.")
    return query.strip(), limit


def _attribution(snapshot: _Snapshot, source: _Source) -> dict[str, str]:
    manifest = snapshot.manifest
    return {key: manifest[key] for key in [
        "repository_id", "worktree", "head_sha", "worktree_diff_digest", "content_digest", "extraction_version",
    ]} | {"file_sha256": source.sha256}


def _item(snapshot: _Snapshot, source: _Source, line: int, column: int, text: str, kind: str, **extra: Any) -> dict[str, Any]:
    start = max(0, column - 1 - 80)
    excerpt = text[start:start + MAX_EXCERPT_CHARS]
    return {
        "path": source.path, "line": line, "column": column,
        "text": excerpt, "text_start_column": start + 1,
        "text_truncated": start > 0 or start + len(excerpt) < len(text),
        "match_kind": kind, "source": _attribution(snapshot, source), **extra,
    }


def _literal_results(snapshot: _Snapshot, query: str, limit: int, excluded: set[tuple[str, int]] | None = None) -> tuple[list[dict[str, Any]], bool]:
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results: list[dict[str, Any]] = []
    for source in snapshot.sources:
        for number, line in enumerate(source.text.split("\n"), start=1):
            if excluded and (source.path, number) in excluded:
                continue
            match = pattern.search(line)
            if match is None:
                continue
            if len(results) >= limit:
                return results, True
            results.append(_item(snapshot, source, number, match.start() + 1, line, "literal_case_insensitive"))
    return results, False


def health(repo: os.PathLike[str] | str) -> dict[str, Any]:
    """Report the live source scope, fingerprints, coverage and observation limits."""
    try:
        snapshot = _observe(repo)
        return _base_result(snapshot) | {"index": "none; source is read on each request"}
    except (IntelligenceError, OSError) as error:
        return _unavailable(error)


def search(repo: os.PathLike[str] | str, query: str, limit: int = 20) -> dict[str, Any]:
    """Case-insensitive literal line search; each hit includes its source identity."""
    try:
        query, limit = _arguments(query, limit)
        snapshot = _observe(repo)
        results, truncated = _literal_results(snapshot, query, limit)
        return _base_result(snapshot) | {
            "query": query, "query_outcome": "matches" if results else "no_matches_in_observed_scope",
            "results": results, "truncated": truncated,
        }
    except (IntelligenceError, OSError) as error:
        return _unavailable(error)


def symbol(repo: os.PathLike[str] | str, name: str, limit: int = 20) -> dict[str, Any]:
    """Exact Python class/function definitions plus explicitly labeled lexical hits.

    Other languages and call sites receive no semantic reference/definition claim.
    """
    try:
        name, limit = _arguments(name, limit)
        snapshot = _observe(repo)
        definitions: list[dict[str, Any]] = []
        definition_lines: set[tuple[str, int]] = set()
        parse_errors: list[str] = []
        python_files = 0
        for source in snapshot.sources:
            if not source.path.endswith((".py", ".pyi")):
                continue
            python_files += 1
            try:
                tree = ast.parse(source.text, filename=source.path)
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                if len(parse_errors) < 30:
                    parse_errors.append(source.path)
                continue
            lines = source.text.split("\n")

            class Definitions(ast.NodeVisitor):
                def __init__(self) -> None:
                    self.parents: list[str] = []

                def definition(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                    qualified = ".".join([*self.parents, node.name])
                    if node.name == name or qualified == name:
                        definition_lines.add((source.path, node.lineno))
                        if len(definitions) <= limit:
                            line = lines[node.lineno - 1]
                            # AST columns are UTF-8 byte offsets, unlike search's Unicode columns.
                            column = len(line.encode("utf-8")[:node.col_offset].decode("utf-8")) + 1
                            definitions.append(_item(
                                snapshot, source, node.lineno, column, line, "python_ast_definition",
                                symbol=node.name, qualified_name=qualified,
                                definition_kind=type(node).__name__, end_line=getattr(node, "end_lineno", node.lineno),
                            ))
                    self.parents.append(node.name)
                    self.generic_visit(node)
                    self.parents.pop()

                visit_ClassDef = definition
                visit_FunctionDef = definition
                visit_AsyncFunctionDef = definition

            try:
                Definitions().visit(tree)
            except RecursionError:
                if len(parse_errors) < 30:
                    parse_errors.append(source.path)
        truncated = len(definitions) > limit
        results = definitions[:limit]
        if len(results) < limit:
            lexical, lexical_truncated = _literal_results(snapshot, name, limit - len(results), definition_lines)
            results.extend(lexical)
            truncated = truncated or lexical_truncated
        else:
            lexical, lexical_truncated = _literal_results(snapshot, name, 1, definition_lines)
            truncated = truncated or bool(lexical) or lexical_truncated
        return _base_result(snapshot) | {
            "query": name, "query_outcome": "matches" if results else "no_matches_in_observed_scope",
            "results": results, "truncated": truncated,
            "symbol_coverage": {"python_files": python_files, "parse_error_examples": parse_errors,
                                "other_languages": "literal occurrences only; no semantic symbol graph"},
        }
    except (IntelligenceError, OSError) as error:
        return _unavailable(error)
