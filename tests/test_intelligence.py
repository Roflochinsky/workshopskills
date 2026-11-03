"""Behavioral tests for live source search, using disposable real Git worktrees."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from factory import intelligence


@unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd, "safe source opening requires dirfd/nofollow")
class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="law-source-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "module.py").write_text("def existing():\n    return 'needle'\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Factory tests", "-c", "user.email=factory-tests@example.invalid", "commit", "-qm", "baseline")

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(self.repo), *args],
            check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout

    def test_fingerprints_change_between_unstaged_edits_and_hits_have_attribution(self):
        before = intelligence.health(self.repo)
        self.assertEqual(before["status"], "ok")
        self.assertEqual(before["manifest"]["head_sha"], self.git("rev-parse", "HEAD").decode().strip())
        (self.repo / "module.py").write_text("def existing():\n    return 'needle one'\n", encoding="utf-8")
        first_edit = intelligence.health(self.repo)
        (self.repo / "module.py").write_text("def existing():\n    return 'needle two'\n", encoding="utf-8")
        second_edit = intelligence.health(self.repo)
        self.assertEqual(first_edit["manifest"]["head_sha"], second_edit["manifest"]["head_sha"])
        self.assertNotEqual(first_edit["manifest"]["content_digest"], second_edit["manifest"]["content_digest"])
        self.assertNotEqual(first_edit["manifest"]["worktree_diff_digest"], second_edit["manifest"]["worktree_diff_digest"])
        hit = intelligence.search(self.repo, "NEEDLE TWO")["results"][0]
        self.assertEqual((hit["path"], hit["line"], hit["column"]), ("module.py", 2, 13))
        self.assertEqual(hit["source"]["content_digest"], second_edit["manifest"]["content_digest"])
        self.assertEqual(len(hit["source"]["file_sha256"]), 64)

    def test_untracked_rename_delete_and_ignored_scope(self):
        self.git("mv", "module.py", "renamed.py")
        (self.repo / "new.py").write_text("value = 'new-candidate'\n", encoding="utf-8")
        ignored = self.repo / "ignored"
        ignored.mkdir()
        (ignored / "private.py").write_text("private-scope-needle\n", encoding="utf-8")
        self.assertEqual(intelligence.search(self.repo, "needle")["results"][0]["path"], "renamed.py")
        self.assertEqual(intelligence.search(self.repo, "new-candidate")["results"][0]["path"], "new.py")
        self.assertEqual(intelligence.search(self.repo, "private-scope-needle")["results"], [])
        (self.repo / "renamed.py").unlink()
        deleted = intelligence.search(self.repo, "needle")
        self.assertEqual(deleted["results"], [])
        self.assertEqual(deleted["query_outcome"], "no_matches_in_observed_scope")
        self.assertIn("never proves", " ".join(deleted["manifest"]["limitations"]))

    def test_symlink_files_and_symlink_parents_never_expose_external_source(self):
        package = self.repo / "pkg"
        package.mkdir()
        (package / "inside.py").write_text("ordinary = 1\n", encoding="utf-8")
        self.git("add", "pkg")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "inside.py").write_text("outside-only-secret\n", encoding="utf-8")
        shutil.rmtree(package)
        package.symlink_to(outside, target_is_directory=True)
        (self.repo / "alias.py").symlink_to(outside / "inside.py")
        result = intelligence.search(self.repo, "outside-only-secret")
        self.assertEqual(result["results"], [])
        self.assertGreaterEqual(result["manifest"]["counts"]["symlink_or_replaced_parent"], 2)

    def test_binary_and_huge_sources_are_skipped_with_partial_coverage(self):
        (self.repo / "binary.dat").write_bytes(b"\0binary-only-needle")
        (self.repo / "huge.txt").write_text("huge-only-needle" * 100, encoding="utf-8")
        with patch.object(intelligence, "MAX_FILE_BYTES", 100):
            result = intelligence.search(self.repo, "only-needle")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["manifest"]["counts"]["binary"], 1)
        self.assertEqual(result["manifest"]["counts"]["too_large"], 1)

    def test_worktrees_have_common_repository_identity_and_distinct_source(self):
        other = self.root / "candidate"
        self.git("worktree", "add", "--detach", str(other), "HEAD")
        (other / "module.py").write_text("def candidate_only():\n    return 2\n", encoding="utf-8")
        base = intelligence.search(self.repo, "candidate_only")
        candidate = intelligence.search(other, "candidate_only")
        self.assertEqual(base["results"], [])
        self.assertEqual(candidate["results"][0]["source"]["worktree"], str(other))
        self.assertEqual(base["manifest"]["repository_id"], candidate["manifest"]["repository_id"])
        self.assertNotEqual(base["manifest"]["content_digest"], candidate["manifest"]["content_digest"])

    def test_python_definitions_and_other_language_hits_have_distinct_claims(self):
        (self.repo / "service.py").write_text("class Service:\n    async def run(self):\n        pass\n", encoding="utf-8")
        (self.repo / "other.js").write_text("function run() {}\n", encoding="utf-8")
        (self.repo / "invalid.py").write_text("def broken(:\n    run()\n", encoding="utf-8")
        qualified = intelligence.symbol(self.repo, "Service.run")
        self.assertEqual(qualified["results"][0]["qualified_name"], "Service.run")
        self.assertEqual(qualified["results"][0]["definition_kind"], "AsyncFunctionDef")
        unqualified = intelligence.symbol(self.repo, "run")
        self.assertEqual(unqualified["results"][0]["match_kind"], "python_ast_definition")
        javascript = next(item for item in unqualified["results"] if item["path"] == "other.js")
        self.assertEqual(javascript["match_kind"], "literal_case_insensitive")
        self.assertIn("invalid.py", unqualified["symbol_coverage"]["parse_error_examples"])

    def test_bounded_literal_results_and_physical_line_attribution(self):
        (self.repo / "many.txt").write_text("match\n" * 150, encoding="utf-8")
        result = intelligence.search(self.repo, "match", limit=2)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(result["truncated"])
        (self.repo / "unicode.txt").write_text("first\u2028same physical line\nneedle.after\n", encoding="utf-8")
        hit = intelligence.search(self.repo, "needle.after")["results"][0]
        self.assertEqual(hit["line"], 2)
        self.assertEqual(intelligence.search(self.repo, "needleXafter")["results"], [])
        self.assertEqual(intelligence.search(self.repo, "match", limit=101)["status"], "unavailable")

    def test_mutation_during_observation_is_stale(self):
        original = intelligence._read_source
        changed = False

        def mutate_after_read(root_fd, name, budget):
            nonlocal changed
            result = original(root_fd, name, budget)
            if name == "module.py" and not changed:
                (self.repo / name).write_text("def changed():\n    return 7\n", encoding="utf-8")
                changed = True
            return result

        with patch.object(intelligence, "_read_source", side_effect=mutate_after_read):
            result = intelligence.search(self.repo, "existing")
        self.assertEqual(result["status"], "stale")
        self.assertFalse(result["manifest"]["stable_observation"])

    def test_subdirectory_does_not_silently_widen_scope_and_nonrepo_is_unavailable(self):
        nested = self.repo / "nested"
        nested.mkdir()
        self.assertEqual(intelligence.health(nested)["status"], "unavailable")
        self.assertEqual(intelligence.health(self.root)["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
