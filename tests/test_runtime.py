from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from factory import process, workspace
from factory.cli import default_state, demo, init
from factory.controller import Controller, ControllerError
from factory.runtime import ROOT, Runtime, digest, write_json


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        shutil.copytree(ROOT / "examples/project", self.repo,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        workspace.git(self.repo, "init", "-b", "main")
        workspace.git(self.repo, "add", "--all")
        workspace.git(self.repo, "-c", "user.name=Test", "-c", "user.email=test@localhost",
                      "commit", "--no-gpg-sign", "-m", "fixture")
        self.controller = Controller(self.repo, self.root / "state")
        self.runtime = Runtime(self.controller, synthetic=True)
        self.task = "billing-rounding"
        self.controller.create(".factory/tasks/billing.json")

    def prepare(self):
        self.controller.admit(self.task)
        return Path(self.runtime.prepare_workspace(self.task)["path"])

    def fake_completion(self, *args, result=None, mutate=None, **kwargs):
        source, directory = args[3], args[4]
        if mutate:
            mutate(source)
        output = directory / "worker"
        file = directory / "log"
        file.write_text("captured synthetic output")
        write_json(output / "result.json", result if result is not None else {
            "role": "implement", "status": "PASS", "covered_ac": [], "lenses": [], "findings": []})
        return {"status": "PASS", "files": [{"path": str(file), "sha256": digest(file)}]}

    def test_full_demo_observes_defect_then_verifies_real_candidate(self):
        result = demo(self.root / "complete")
        self.assertEqual(result["baseline"], "FAIL")
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["live_model"], "NOT_RUN")
        controller = Controller(result["repo"], result["state_dir"])
        status = controller.status(self.task)
        self.assertEqual(len(status["runs"]), 3)
        self.assertNotEqual(status["runs"][0]["actor_id"], status["runs"][2]["actor_id"])
        self.assertTrue(all(Path(f["path"]).is_file() for r in status["runs"] for f in r["evidence"]["files"]))
        self.assertIn("Synthetic fixture", Path(result["pr_body"]).read_text())

    def test_workspace_cannot_launch_before_admission_and_creation_is_idempotent(self):
        with self.assertRaises(ControllerError):
            self.runtime.prepare_workspace(self.task)
        first = self.prepare()
        second = Path(self.runtime.prepare_workspace(self.task)["path"])
        self.assertEqual(first, second)
        self.assertEqual(len(workspace.inventory(self.repo)), 2)

    def test_malformed_worker_result_is_blocked_without_stranded_lease(self):
        self.prepare()
        with patch.object(self.runtime, "_execute", side_effect=lambda *a, **k: self.fake_completion(*a, result=[], **k)):
            result = self.runtime.worker(self.task, "implement", "fixture")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("JSON object", result["evidence"]["reason"])
        self.assertFalse(any(r["status"] == "RUNNING" for r in self.controller.status(self.task)["runs"]))

    def test_worker_cannot_rewrite_contract_even_inside_broad_scope(self):
        work = self.prepare()
        def mutation(path):
            (path / "docs/specs/billing.md").write_text("All output is acceptable")
        with patch.object(self.runtime, "_execute", side_effect=lambda *a, **k: self.fake_completion(*a, mutate=mutation, **k)):
            result = self.runtime.worker(self.task, "implement", "fixture")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("contract differs", result["evidence"]["reason"])
        self.assertNotEqual((work / "docs/specs/billing.md").read_text(), (self.repo / "docs/specs/billing.md").read_text())

    def test_out_of_scope_rename_preserves_dirty_work_for_inspection(self):
        work = self.prepare()
        (work / "billing.py").rename(work / "replacement.py")
        with self.assertRaisesRegex(workspace.WorkspaceError, "Out-of-scope"):
            workspace.snapshot(work, ["replacement.py"], self.task)
        self.assertTrue((work / "replacement.py").is_file())
        self.assertTrue(workspace.git(work, "status", "--porcelain"))

    def test_real_launcher_does_not_fallback_when_sandbox_unavailable(self):
        work = self.prepare()
        status = self.controller.status(self.task)
        directory = self.root / "state/probe"
        (directory / "worker").mkdir(parents=True)
        with patch("factory.process.sandbox_probe", return_value={"ready": False, "reason": "userns disabled"}), patch("factory.process.run") as launch:
            with self.assertRaisesRegex(process.ExecutionError, "execution blocked"):
                Runtime(self.controller)._execute(status, ["python3", "-V"], work, work, directory,
                    [], [], readonly=True, timeout=1, network=False)
        launch.assert_not_called()

    def test_missing_real_harness_configuration_is_recorded_blocked(self):
        self.prepare()
        result = Runtime(self.controller).worker(self.task, "implement", "pi")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Configure harnesses.pi.runtime", result["evidence"]["reason"])

    def test_recovery_cannot_race_active_launcher_or_replay_work(self):
        self.prepare()
        with self.runtime.lock(self.task):
            with self.assertRaisesRegex(ControllerError, "launcher is active"):
                self.runtime.recover(self.task)
        sha = workspace.git(Path(self.controller.status(self.task)["workspace"]["path"]), "rev-parse", "HEAD")
        self.controller.begin_run(self.task, "implement", sha, "crashed", "synthetic-billing")
        recovered = self.runtime.recover(self.task)
        self.assertEqual(recovered["state"], "BLOCKED")
        self.assertEqual(len(recovered["runs"]), 1)
        self.assertEqual(self.runtime.recover(self.task)["runs"], recovered["runs"])

    def test_unknown_live_process_identity_blocks_recovery(self):
        work = self.prepare()
        run = self.controller.begin_run(self.task, "implement", workspace.git(work, "rev-parse", "HEAD"), "crashed", "synthetic-billing")
        write_json(self.root / "state/runs" / run["run_id"] / "logs/process.json",
                   {"pid": 999999, "identity_unavailable": True})
        with self.assertRaisesRegex(ControllerError, "Cannot prove"):
            self.runtime.recover(self.task)

    def test_external_workspace_never_deleted_by_controller(self):
        work = self.prepare()
        with self.assertRaisesRegex(workspace.WorkspaceError, "external workspace owner"):
            workspace.remove(self.repo, work, "existing")
        self.assertTrue(work.is_dir())

    def test_default_journal_identity_is_shared_across_worktrees(self):
        work = self.prepare()
        self.assertEqual(default_state(self.repo), default_state(work))

    def test_verification_cannot_see_ignored_implementation_outputs(self):
        work = self.prepare()
        implementation = self.runtime.worker(self.task, "implement", "fixture")
        self.assertEqual(implementation["status"], "PASS")
        artifact = work / "__pycache__/untrusted.pyc"
        artifact.parent.mkdir()
        artifact.write_bytes(b"not part of the committed candidate")
        seen = []
        original = self.runtime._execute
        def inspect(*args, **kwargs):
            seen.append(args[3])
            self.assertNotEqual(args[3], work)
            self.assertFalse((args[3] / "__pycache__/untrusted.pyc").exists())
            return original(*args, **kwargs)
        with patch.object(self.runtime, "_execute", side_effect=inspect):
            results = self.runtime.check(self.task)
        self.assertEqual(results[0]["status"], "PASS")
        self.assertEqual(len(seen), 1)

    def test_sandbox_masks_dotenv_bunfig_and_git_pointer_before_runtime_start(self):
        work = self.prepare()
        (work / ".env").write_text("FAKE_SECRET=synthetic-only\n")
        (work / "bunfig.toml").write_text('preload = ["./unexpected.ts"]\n')
        output = self.root / "state/probe/worker"
        output.mkdir(parents=True)
        with patch("factory.process.sandbox_probe", return_value={"ready": True}):
            argv = process.sandbox_command(["/usr/bin/true"], work, work, output,
                False, [], self.root / "state", False)
        for target in (work / ".env", work / "bunfig.toml", work / ".git"):
            index = argv.index(str(target))
            # .git is also the source of its own mount, configuration files are
            # mounted from a trusted empty file outside worker-writable output.
            self.assertIn("--ro-bind", argv[max(0, index - 2):index])
        self.assertIn("--unshare-net", argv)
        self.assertEqual((work / ".env").read_text(), "FAKE_SECRET=synthetic-only\n")

    def test_init_never_overwrites_existing_profile(self):
        before = (self.repo / ".factory/project.json").read_bytes()
        with self.assertRaises(ControllerError):
            init(self.repo)
        self.assertEqual((self.repo / ".factory/project.json").read_bytes(), before)


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def invoke(self, code, *, timeout=1, limit=1024, cancelled=lambda: False):
        output = self.root / "logs"
        return process.run([sys.executable, "-c", code], self.root,
            process.clean_environment([], self.root / "worker"), output, timeout, limit, cancelled)

    def test_closed_pipes_do_not_escape_time_budget(self):
        result = self.invoke("import os,time; os.close(1); os.close(2); time.sleep(2)", timeout=0.15)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "timeout")
        self.assertLess(result["seconds"], 1.5)

    def test_last_chunk_cannot_escape_output_budget(self):
        result = self.invoke("print('x' * 20000)", limit=128)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "output_limit")
        self.assertLessEqual(sum(Path(f["path"]).stat().st_size for f in result["files"]), 128)

    def test_cancellation_stops_the_owned_process(self):
        result = self.invoke("import time; time.sleep(2)", cancelled=lambda: True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "cancelled")

    def test_startup_crash_cannot_release_unrecorded_external_effect(self):
        read_fd, write_fd = os.pipe()
        marker = self.root / "effect"
        child = subprocess.Popen([sys.executable, str(ROOT / "factory/child_guard.py"), str(read_fd),
            sys.executable, "-c", "from pathlib import Path; Path('effect').write_text('sent')"],
            cwd=self.root, pass_fds=(read_fd,))
        os.close(read_fd)
        os.close(write_fd)  # Parent died without publishing PID and releasing GO.
        self.assertEqual(child.wait(timeout=3), 125)
        self.assertFalse(marker.exists())

    def test_control_environment_variables_cannot_be_inherited(self):
        for name in ("NODE_OPTIONS", "BUN_OPTIONS", "BUN_INSPECT_PRELOAD", "PI_CODING_AGENT_DIR"):
            with self.subTest(name=name), self.assertRaises(process.ExecutionError):
                process.clean_environment([name], self.root)
        with self.assertRaises(process.ExecutionError):
            process.clean_environment(None, self.root)


if __name__ == "__main__":
    unittest.main()
