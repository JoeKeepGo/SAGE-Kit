from __future__ import annotations

import unittest

from sagekit.cli import build_parser
from sagekit.process_supervisor import ProcessClassification
from sagekit.resource_cli import _resource_process_exit_code


class ResourceCliDefaultTests(unittest.TestCase):
    def test_process_classification_maps_to_cli_contract(self) -> None:
        self.assertEqual(
            0,
            _resource_process_exit_code(
                ProcessClassification.SUCCESS,
                cleanup_complete=True,
                release_error=None,
            ),
        )
        for classification in (
            ProcessClassification.NONZERO,
            ProcessClassification.TIMEOUT,
            ProcessClassification.INTERRUPTED,
            ProcessClassification.CAPABILITY,
        ):
            with self.subTest(classification=classification):
                self.assertEqual(
                    1,
                    _resource_process_exit_code(
                        classification,
                        cleanup_complete=True,
                        release_error=None,
                    ),
                )
        self.assertEqual(
            3,
            _resource_process_exit_code(
                ProcessClassification.INTERNAL,
                cleanup_complete=False,
                release_error="cleanup failed",
            ),
        )

    def test_resource_run_automatically_uses_bounded_profile_wait(self) -> None:
        args = build_parser().parse_args(
            [
                "resource",
                "run",
                "--class",
                "repo-read",
                "--run-id",
                "run-1",
                "--timeout",
                "10",
                "--",
                "git",
                "status",
            ]
        )

        self.assertEqual(300.0, args.wait_seconds)


if __name__ == "__main__":
    unittest.main()
