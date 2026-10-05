"""Exercise checkpoint holds and pushes against disposable local repositories."""

import argparse
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("checkpoint", Path(__file__).with_name("checkpoint.py"))
checkpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="website-checkpoint-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.remote = Path(self.temporary.name) / "remote.git"
        self.root.mkdir()
        saved = {key: getattr(checkpoint, key) for key in ("ROOT", "STATE", "REVIEW", "PENDING")}
        self.addCleanup(lambda: [setattr(checkpoint, key, value) for key, value in saved.items()])
        checkpoint.ROOT = self.root
        checkpoint.STATE = self.root / ".cache/checkpoint"
        checkpoint.REVIEW = checkpoint.STATE / "review.json"
        checkpoint.PENDING = checkpoint.STATE / "pending-push.json"
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Checkpoint Test")
        self.git("config", "user.email", "checkpoint@example.test")
        self.git("config", "commit.gpgsign", "false")
        (self.root / ".gitignore").write_text(".cache/\n.tools/\n")
        for name in ("index.html", "README.md"):
            (self.root / name).write_text("initial\n")
        self.git("add", ".")
        self.git("commit", "-m", "Initial state")
        self.git("clone", "--bare", str(self.root), str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        (self.root / "scripts").mkdir()
        self.checker = self.root / "scripts/check_site.py"
        self.checker.write_text("pass\n")
        self.initial = self.git("rev-parse", "HEAD")
        (self.root / "README.md").write_text("Completed documentation update\n")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=True).stdout.strip()

    def args(self, *paths, reviewed=True):
        return argparse.Namespace(reviewed=reviewed, message="Document checkpoint workflow",
                                  paths=list(paths or ["README.md"]))

    def check(self):
        with contextlib.redirect_stdout(io.StringIO()):
            checkpoint.check()

    def unchanged(self):
        self.assertEqual(self.git("rev-parse", "HEAD"), self.initial)
        self.assertEqual(self.git("--git-dir", str(self.remote), "rev-parse", "main"), self.initial)

    def test_success_pushes_only_selected_files(self):
        (self.root / "index.html").write_text("Pre-existing user edit\n")
        self.check()
        checkpoint.ship(self.args())
        self.assertEqual(self.git("show", "--format=", "--name-only", "HEAD"), "README.md")
        self.assertEqual(self.git("--git-dir", str(self.remote), "rev-parse", "main"),
                         self.git("rev-parse", "HEAD"))
        self.assertIn("index.html", self.git("diff", "--name-only"))

    def test_missing_review_holds(self):
        self.check()
        with self.assertRaisesRegex(RuntimeError, "Review the changes"):
            checkpoint.ship(self.args(reviewed=False))
        self.unchanged()

    def test_missing_check_or_later_edit_holds(self):
        with self.assertRaisesRegex(RuntimeError, "No current successful check"):
            checkpoint.ship(self.args())
        self.check()
        (self.root / "README.md").write_text("Changed after check\n")
        with self.assertRaisesRegex(RuntimeError, "No current successful check"):
            checkpoint.ship(self.args())
        self.unchanged()

    def test_failed_check_invalidates_old_record(self):
        self.check()
        self.checker.write_text("raise SystemExit(1)\n")
        with self.assertRaises(subprocess.CalledProcessError):
            self.check()
        self.assertFalse(checkpoint.REVIEW.exists())
        self.unchanged()

    def test_source_edit_during_check_holds(self):
        self.checker.write_text("from pathlib import Path\nPath('index.html').write_text('concurrent edit')\n")
        with self.assertRaisesRegex(RuntimeError, "Files changed during checks"):
            self.check()
        self.assertFalse(checkpoint.REVIEW.exists())
        self.unchanged()

    def test_existing_staging_outside_selection_is_preserved(self):
        self.git("add", "README.md")
        (self.root / "other.txt").write_text("Independent change\n")
        self.check()
        with self.assertRaisesRegex(RuntimeError, "outside the reviewed selection"):
            checkpoint.ship(self.args("other.txt"))
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "README.md")
        self.unchanged()

    def test_selected_staged_and_unstaged_edits_are_published_together(self):
        self.git("add", "README.md")
        (self.root / "README.md").write_text("Reviewed staged and unstaged work\n")
        self.check()
        checkpoint.ship(self.args())
        self.assertEqual(self.git("show", "HEAD:README.md"), "Reviewed staged and unstaged work")
        self.assertEqual(self.git("--git-dir", str(self.remote), "rev-parse", "main"),
                         self.git("rev-parse", "HEAD"))

    def test_unpushed_prior_commit_holds(self):
        self.git("add", "README.md")
        self.git("commit", "-m", "Unrelated local work")
        local = self.git("rev-parse", "HEAD")
        (self.root / "README.md").write_text("Further work\n")
        self.check()
        with self.assertRaisesRegex(RuntimeError, "Local and remote branches differ"):
            checkpoint.ship(self.args())
        self.assertEqual(self.git("rev-parse", "HEAD"), local)
        self.assertEqual(self.git("--git-dir", str(self.remote), "rev-parse", "main"), self.initial)

    def test_rejected_push_can_retry_exact_commit(self):
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.check()
        with self.assertRaises(subprocess.CalledProcessError):
            checkpoint.ship(self.args())
        pending = self.git("rev-parse", "HEAD")
        self.assertTrue(checkpoint.PENDING.exists())
        hook.unlink()
        checkpoint.retry_push()
        self.assertEqual(self.git("--git-dir", str(self.remote), "rev-parse", "main"), pending)
        self.assertFalse(checkpoint.PENDING.exists())


if __name__ == "__main__":
    unittest.main()
