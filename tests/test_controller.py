"""State/evidence boundary tests using real temporary Git repositories."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from factory.controller import Controller, ControllerError
from factory import workspace
from factory.cli import default_state


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q", "-b", "main")
        self.git(self.repo, "config", "user.name", "Factory fixture")
        self.git(self.repo, "config", "user.email", "fixture@example.invalid")
        self.profile = {
            "schema_version": 1, "project_id": "sample",
            "workspace": {"provider": "git"},
            "runtime": {"max_runs": 12, "timeout_seconds": 60, "output_limit_bytes": 10000},
            "verification": {"checks": [{"id": "unit", "argv": ["python3", "-m", "unittest"],
                                            "cwd": ".", "timeout_seconds": 20, "required": True}]},
        }
        self.task = {
            "schema_version": 1, "task_id": "change", "spec": "docs/spec.md",
            "adrs": [{"path": "docs/adr.md", "status": "accepted", "decision_source": "User decision R-1"}],
            "test_contract": "docs/tests.json", "scope": ["src/**", "tests/**"],
            "requirements": ["REQ-1"], "invariants": ["INV-1"],
            "acceptance": [{"id": "AC-1", "requirements": ["REQ-1", "INV-1"]}],
            "analysis": {"status": "ANALYSIS_READY", "blocking_questions": []},
        }
        self.test_plan = {
            "schema_version": 1,
            "scenarios": [{"id": "S-1", "requirements": ["REQ-1", "INV-1"], "acceptance": ["AC-1"],
                           "behavior": "Return an exact result", "distinct_failure_mode": "Wrong boundary",
                           "public_boundary": "public function", "oracle_source": "docs/spec.md example",
                           "existing_coverage": "No existing boundary case", "disposition": "new",
                           "cost": "One local deterministic case", "checks": ["unit"]}],
            "rbac": {"required": False, "reason": "Local pure function has no identities"},
        }
        self.write_json(".factory/project.json", self.profile)
        self.write_json(".factory/tasks/change.json", self.task)
        self.write_json("docs/tests.json", self.test_plan)
        self.write("docs/spec.md", "REQ-1 / INV-1: exact output. AC-1: known independent example.\n")
        self.write("docs/adr.md", "Accepted by user decision R-1.\n")
        self.write("src/result.py", "RESULT = 1\n")
        self.commit(self.repo, "baseline")
        self.state = self.root / "state"
        self.controller = Controller(self.repo, self.state)
        self.controller.create(".factory/tasks/change.json")
        self.worktree = self.workspace("change")
        self.environment = "local-preview-change"

    @staticmethod
    def git(path, *args):
        return subprocess.check_output(["git", "-C", str(path), *args], stderr=subprocess.PIPE).decode().strip()

    def write(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def write_json(self, name, value):
        self.write(name, json.dumps(value, indent=2) + "\n")

    def commit(self, path, message):
        self.git(path, "add", "--all")
        self.git(path, "commit", "-q", "-m", message)
        return self.git(path, "rev-parse", "HEAD")

    def workspace(self, task_id):
        path = self.root / "worktrees" / task_id
        self.git(self.repo, "worktree", "add", "-b", "factory/" + task_id, str(path), "HEAD")
        self.controller.set_workspace(task_id, path, "factory/" + task_id, "git")
        return path

    def evidence(self, run, **extra):
        path = self.state / "logs" / (run["run_id"] + ".log")
        path.parent.mkdir(exist_ok=True)
        data = (run["role"] + " fixture output\n").encode()
        path.write_bytes(data)
        return {"files": [{"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}], **extra}

    def implement(self):
        self.controller.admit("change")
        run = self.controller.begin_run("change", "implement", self.git(self.worktree, "rev-parse", "HEAD"), "lead", self.environment)
        (self.worktree / "src/result.py").write_text("RESULT = 2\n")
        sha = self.commit(self.worktree, "implementation")
        done = self.controller.finish_run(run["run_id"], "PASS", sha, self.evidence(run))
        self.assertEqual(done["status"], "PASS")
        return sha

    def review(self, sha, **changes):
        run = self.controller.begin_run("change", "review", sha, "independent-reviewer", self.environment)
        payload = {"covered_ac": ["AC-1"], "lenses": ["spec", "correctness", "tests"], "findings": []}
        payload.update(changes)
        evidence = self.evidence(run, **payload)
        self.controller.finish_run(run["run_id"], "PASS", sha, evidence)
        return evidence

    def check(self, sha, status="PASS"):
        run = self.controller.begin_run("change", "check:unit", sha, "check-runner", self.environment)
        return self.controller.finish_run(run["run_id"], status, sha, self.evidence(run))

    def test_complete_gate_needs_independent_review_and_every_required_check(self):
        source = self.git(self.worktree, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ControllerError, "admission"):
            self.controller.begin_run("change", "implement", source, "lead", self.environment)
        sha = self.implement()
        with self.assertRaisesRegex(ControllerError, "different actor"):
            self.controller.begin_run("change", "review", sha, "lead", self.environment)
        self.review(sha)
        with self.assertRaisesRegex(ControllerError, "check:unit"):
            self.controller.finalize("change", sha, self.environment)
        self.check(sha, "FAIL")
        with self.assertRaisesRegex(ControllerError, "check:unit"):
            self.controller.finalize("change", sha, self.environment)
        self.check(sha)
        result = self.controller.finalize("change", sha, self.environment)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertTrue(all(r["contract_hash"] == result["contract_hash"] for r in result["runs"]))

    def test_admission_rejects_decision_and_trace_gaps_without_new_approval(self):
        variants = []
        pending = copy.deepcopy(self.task)
        pending["adrs"][0]["status"] = "pending"
        variants.append((pending, self.test_plan, "ADR gate"))
        questions = copy.deepcopy(self.task)
        questions["analysis"]["blocking_questions"] = ["Who may see another tenant?"]
        variants.append((questions, self.test_plan, "blocking"))
        uncovered = copy.deepcopy(self.test_plan)
        uncovered["scenarios"][0]["requirements"] = ["REQ-1"]
        variants.append((self.task, uncovered, "requirement-to-AC"))
        rbac = copy.deepcopy(self.test_plan)
        rbac["rbac"] = {"required": True, "reason": "Tenant-sensitive change", "check_id": "absent"}
        variants.append((self.task, rbac, "RBAC"))
        for task, plan, error in variants:
            with self.subTest(error=error):
                self.write_json(".factory/tasks/change.json", task)
                self.write_json("docs/tests.json", plan)
                self.controller.create(".factory/tasks/change.json")
                with self.assertRaisesRegex(ControllerError, error):
                    self.controller.admit("change")
        self.write_json(".factory/tasks/change.json", self.task)
        self.write_json("docs/tests.json", self.test_plan)
        self.controller.create(".factory/tasks/change.json")
        self.assertEqual(self.controller.admit("change")["state"], "READY_FOR_BUILD")

    def test_changed_contract_requires_explicit_refresh_and_readmission(self):
        self.controller.admit("change")
        self.write("docs/spec.md", "A materially changed acceptance contract.\n")
        source = self.git(self.worktree, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ControllerError, "stale"):
            self.controller.begin_run("change", "implement", source, "lead", self.environment)
        self.assertEqual(self.controller.create(".factory/tasks/change.json")["state"], "DRAFT")
        with self.assertRaisesRegex(ControllerError, "admission"):
            self.controller.begin_run("change", "implement", source, "lead", self.environment)
        self.assertEqual(self.controller.admit("change")["state"], "READY_FOR_BUILD")

    def test_explicit_project_instructions_are_part_of_contract(self):
        self.profile["instructions"] = ["docs/conventions.md"]
        self.write_json(".factory/project.json", self.profile)
        self.write("docs/conventions.md", "Use the project's established error types.\n")
        created = self.controller.create(".factory/tasks/change.json")
        self.assertIn("docs/conventions.md", created["sources"])
        self.controller.admit("change")
        self.write("docs/conventions.md", "Changed project behavior requires new analysis.\n")
        with self.assertRaisesRegex(ControllerError, "stale"):
            self.controller.begin_run("change", "implement", self.git(self.worktree, "rev-parse", "HEAD"), "lead", self.environment)

    def test_readmission_invalidates_previous_candidate_before_another_run(self):
        sha = self.implement()
        self.review(sha)
        self.check(sha)
        self.assertEqual(self.controller.finalize("change", sha, self.environment)["state"], "VERIFIED")
        readmitted = self.controller.admit("change")
        self.assertEqual(readmitted["state"], "READY_FOR_BUILD")
        self.assertIsNone(readmitted["candidate_sha"])
        with self.assertRaisesRegex(ControllerError, "candidate"):
            self.controller.finalize("change", sha, self.environment)

    def test_task_and_environment_leases_and_recovery_do_not_replay(self):
        self.controller.admit("change")
        sha = self.git(self.worktree, "rev-parse", "HEAD")
        run = self.controller.begin_run("change", "implement", sha, "lead", self.environment)
        second = Controller(self.repo, self.state)
        with self.assertRaisesRegex(ControllerError, "active run"):
            second.begin_run("change", "implement", sha, "other", self.environment)
        other_task = copy.deepcopy(self.task)
        other_task["task_id"] = "other"
        self.write_json(".factory/tasks/other.json", other_task)
        self.commit(self.repo, "second task")
        self.controller.create(".factory/tasks/other.json")
        other_workspace = self.workspace("other")
        self.controller.admit("other")
        with self.assertRaisesRegex(ControllerError, "environment is already leased"):
            second.begin_run("other", "implement", self.git(other_workspace, "rev-parse", "HEAD"), "other", self.environment)
        recovered = self.controller.recover("change")
        self.assertEqual(recovered["state"], "BLOCKED")
        self.assertEqual(len(recovered["runs"]), 1)
        self.assertEqual(recovered["runs"][0]["status"], "BLOCKED")
        with self.assertRaisesRegex(ControllerError, "immutable"):
            self.controller.finish_run(run["run_id"], "PASS", sha, self.evidence(run))

    def test_worktree_invocation_uses_existing_canonical_repository_inputs(self):
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "shared-state")}):
            canonical = Controller(self.repo, default_state(self.repo))
            original = canonical.create(".factory/tasks/change.json")
            (self.worktree / "docs/spec.md").write_text("Different unadmitted worktree contract.\n")
            from_worktree = Controller(self.worktree, default_state(self.worktree))
            self.assertEqual(from_worktree.repo, self.repo)
            self.assertEqual(from_worktree.create(".factory/tasks/change.json")["contract_hash"], original["contract_hash"])
            unrelated = self.root / "unrelated"
            unrelated.mkdir()
            self.git(unrelated, "init", "-q")
            with self.assertRaisesRegex(ControllerError, "different repository"):
                Controller(unrelated, default_state(self.repo))

    def test_cancellation_prevents_late_success(self):
        self.controller.admit("change")
        sha = self.git(self.worktree, "rev-parse", "HEAD")
        run = self.controller.begin_run("change", "implement", sha, "lead", self.environment)
        self.controller.cancel("change")
        result = self.controller.finish_run(run["run_id"], "PASS", sha, self.evidence(run))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(self.controller.status("change")["state"], "CANCELLED")

    def test_source_and_environment_changes_invalidate_evidence(self):
        sha = self.implement()
        self.review(sha)
        self.check(sha)
        with self.assertRaisesRegex(ControllerError, "environment"):
            self.controller.finalize("change", sha, "different-preview")
        (self.worktree / "src/result.py").write_text("RESULT = 3\n")
        with self.assertRaisesRegex(ControllerError, "dirty"):
            self.controller.finalize("change", sha, self.environment)
        new_sha = self.commit(self.worktree, "unreviewed edit")
        with self.assertRaisesRegex(ControllerError, "candidate"):
            self.controller.finalize("change", new_sha, self.environment)

    def test_tampered_evidence_and_incomplete_review_cannot_verify(self):
        sha = self.implement()
        self.review(sha, covered_ac=[{"AC-1": "malformed external report"}])
        self.check(sha)
        with self.assertRaisesRegex(ControllerError, "cover every AC"):
            self.controller.finalize("change", sha, self.environment)
        evidence = self.review(sha)
        self.controller.finalize("change", sha, self.environment)
        Path(evidence["files"][0]["path"]).write_text("tampered\n")
        with self.assertRaisesRegex(ControllerError, "changed"):
            self.controller.finalize("change", sha, self.environment)

    def test_missing_raw_evidence_blocks_and_finished_results_are_immutable(self):
        self.controller.admit("change")
        sha = self.git(self.worktree, "rev-parse", "HEAD")
        run = self.controller.begin_run("change", "implement", sha, "lead", self.environment)
        finished = self.controller.finish_run(run["run_id"], "PASS", sha, {})
        self.assertEqual(finished["status"], "BLOCKED")
        with self.assertRaisesRegex(ControllerError, "immutable"):
            self.controller.finish_run(run["run_id"], "PASS", sha, self.evidence(run))
        with self.assertRaisesRegex(ControllerError, "unregistered"):
            self.controller.finish_run("not-a-run", "PASS", sha, {})

    def test_paths_do_not_escape_the_project_or_expose_controller_state(self):
        with self.assertRaisesRegex(ControllerError, "outside"):
            Controller(self.repo, self.repo / "state")
        outside = self.root / "outside.md"
        outside.write_text("not authorized project material")
        (self.repo / "docs/escape.md").symlink_to(outside)
        bad = copy.deepcopy(self.task)
        bad["spec"] = "docs/escape.md"
        self.write_json(".factory/tasks/change.json", bad)
        with self.assertRaisesRegex(ControllerError, "escapes"):
            self.controller.create(".factory/tasks/change.json")

    def test_host_git_filters_do_not_execute_during_status_or_snapshot(self):
        marker = self.root / "host-side-effect"
        self.git(self.repo, "config", "filter.example.clean", "touch " + str(marker) + "; cat")
        self.git(self.repo, "config", "filter.example.process", "touch " + str(marker) + "; cat")
        self.git(self.repo, "config", "filter.example.required", "true")
        (self.worktree / ".gitattributes").write_text("src/*.py filter=example\n")
        (self.worktree / "src/result.py").write_text("RESULT = 7\n")
        self.controller._git_at(self.worktree, "status", "--porcelain")
        self.assertFalse(marker.exists(), "Inspecting worker files ran a host-side filter")
        sha = workspace.snapshot(self.worktree, ["src/**", ".gitattributes"], "change")
        self.assertFalse(marker.exists(), "Committing worker files ran a host-side filter")
        self.assertEqual(self.git(self.repo, "show", sha + ":src/result.py"), "RESULT = 7")


if __name__ == "__main__":
    unittest.main()
