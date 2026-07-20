from __future__ import annotations

import tempfile
import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sagekit.managed_execution import run_managed_git
from sagekit.cli import main


class ExecutionAdmissionTests(unittest.TestCase):
    def test_cli_help_and_version_do_not_enter_managed_execution(self) -> None:
        with patch("sagekit.managed_execution.ResourceManager.acquire") as acquire, patch(
            "sagekit.managed_execution.run_process"
        ) as managed, redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["--help"]))
            self.assertEqual(0, main(["--version"]))

        acquire.assert_not_called()
        managed.assert_not_called()

    def test_trivial_read_only_git_bypasses_lease_and_managed_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("sagekit.managed_execution.ResourceManager.acquire") as acquire, patch(
                "sagekit.managed_execution.run_process"
            ) as managed, patch(
                "sagekit.managed_execution._run_bounded_readonly_git"
            ) as direct:
                direct.return_value.ok = True
                for arguments in (
                    ("status", "--short"),
                    ("rev-parse", "HEAD"),
                    ("diff", "--name-only"),
                    ("ls-files", "-z"),
                ):
                    with self.subTest(arguments=arguments):
                        run_managed_git(root, arguments, stage="cheap-read")

        self.assertEqual(4, direct.call_count)
        acquire.assert_not_called()
        managed.assert_not_called()

    def test_mutating_and_unbounded_git_stays_managed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("sagekit.managed_execution.run_managed_command") as managed, patch(
                "sagekit.managed_execution._run_bounded_readonly_git"
            ) as direct:
                managed.return_value.ok = True
                run_managed_git(root, ("add", "file.py"), stage="write")
                run_managed_git(root, ("log", "--all"), stage="unbounded")
                run_managed_git(
                    root,
                    ("diff", "--name-only", "--ext-diff"),
                    stage="external-diff",
                )
                run_managed_git(
                    root,
                    ("diff", "--name-only", "--textconv"),
                    stage="textconv",
                )
                run_managed_git(
                    root,
                    ("diff", "--name-only", "--output=leak.txt"),
                    stage="output-file",
                )

        self.assertEqual(5, managed.call_count)
        direct.assert_not_called()


if __name__ == "__main__":
    unittest.main()
