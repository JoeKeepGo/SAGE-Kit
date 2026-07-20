from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from sagekit.managed_execution import run_managed_git
from sagekit.resource_cli import manager_for_target


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
    def test_managed_git_binds_workspace_acquires_repo_read_and_releases(self) -> None:
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
            self.assertEqual(0, result.orphan_count)
            self.assertTrue(result.cleanup_complete)
            manager, _ = manager_for_target(root)
            self.assertEqual((), manager.status())


if __name__ == "__main__":
    unittest.main()
