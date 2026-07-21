from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.managed_execution import (
    ManagedExecutionError,
    _identity_digest,
    run_managed_git,
)
from sagekit.resource_governor import ResourceManager, host_runtime_path, project_runtime_path
from sagekit.workspace_binding import discover_workspace


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PAGER": "cat",
        }
    )
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


class ManagedExecutionIntegrationTests(unittest.TestCase):
    def test_bounded_git_late_success_is_still_a_timeout(self) -> None:
        class LateSuccessGit:
            def poll(self) -> int:
                time.sleep(0.01)
                return 0

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "--initial-branch=main")
            with patch("sagekit.managed_execution.subprocess.Popen", return_value=LateSuccessGit()):
                with self.assertRaisesRegex(ManagedExecutionError, "timed out during late-success"):
                    run_managed_git(
                        root,
                        ("rev-parse", "HEAD"),
                        stage="late-success",
                        timeout=0.001,
                    )

    def test_bounded_git_timeout_remains_a_timeout_after_kill_and_reap(self) -> None:
        class HangingGit:
            def __init__(self) -> None:
                self.killed = False

            def poll(self) -> int | None:
                return -9 if self.killed else None

            def kill(self) -> None:
                self.killed = True

            def wait(self, timeout: float | None = None) -> int:
                return -9

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "--initial-branch=main")
            process = HangingGit()
            with patch("sagekit.managed_execution.subprocess.Popen", return_value=process):
                with self.assertRaisesRegex(ManagedExecutionError, "timed out during timeout-case"):
                    run_managed_git(
                        root,
                        ("rev-parse", "HEAD"),
                        stage="timeout-case",
                        timeout=0.001,
                    )

        self.assertTrue(process.killed)

    def test_bounded_readonly_git_is_direct_and_makes_no_orphan_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "--initial-branch=main")
            (root / "tracked.txt").write_text("managed\n", encoding="utf-8")
            git(root, "add", "tracked.txt")
            git(
                root,
                "-c",
                "user.name=SAGE-Kit Tests",
                "-c",
                "user.email=sagekit@example.invalid",
                "-c",
                "commit.gpgSign=false",
                "-c",
                f"core.hooksPath={os.devnull}",
                "commit",
                "-m",
                "baseline",
            )
            expected = git(root, "rev-parse", "HEAD").stdout.strip()

            result = run_managed_git(
                root,
                ("rev-parse", "HEAD"),
                stage="managed-git-integration",
                run_id="managed-git-integration",
            )

            self.assertEqual(expected, result.stdout.strip())
            self.assertIsNone(result.lease_id)
            self.assertIsNone(result.orphan_count)
            self.assertEqual("not-performed", result.orphan_check)
            self.assertEqual("SOFT", result.containment_level)
            self.assertFalse(result.containment_complete)
            self.assertTrue(result.cleanup_complete)
            identity = discover_workspace(root)
            manager = ResourceManager(
                host_runtime=host_runtime_path(),
                project_runtime=project_runtime_path(
                    Path(identity.project_root),
                    Path(identity.git_common_dir) if identity.git_common_dir else None,
                ),
            )
            project_identity = _identity_digest(
                identity.git_common_dir or identity.repository_root
            )
            worktree_identity = _identity_digest(identity.worktree_root)
            active = tuple(
                lease
                for lease in manager.status()
                if lease.project_identity == project_identity
                and lease.worktree_identity == worktree_identity
            )
            self.assertEqual((), active)


if __name__ == "__main__":
    unittest.main()
