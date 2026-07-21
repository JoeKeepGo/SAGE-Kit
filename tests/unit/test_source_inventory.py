from __future__ import annotations

import unittest
from pathlib import Path

from sagekit.check import (
    SOURCE_REQUIRED_FILES,
    check_source_resource_governance_mirrors,
)


class SourceInventoryUnitTests(unittest.TestCase):
    def test_resource_governance_source_and_package_mirrors_are_byte_identical(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        findings = check_source_resource_governance_mirrors(repository)

        self.assertTrue(findings)
        self.assertFalse(
            [finding for finding in findings if finding.level == "FAIL"], findings
        )

    def test_resource_workspace_process_and_runner_files_are_source_required(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        required = {
            "sagekit/harness.py",
            "sagekit/managed_execution.py",
            "sagekit/process_supervisor.py",
            "sagekit/resource_governor.py",
            "sagekit/resource_policy.py",
            "sagekit/test_runner.py",
            "sagekit/workspace_binding.py",
            "sagekit/resources/resource_governance/conservative-host-v1.json",
            "scripts/run_tests.py",
        }

        self.assertEqual(set(), required - set(SOURCE_REQUIRED_FILES))
        self.assertEqual(
            set(),
            {relative for relative in required if not (repository / relative).is_file()},
        )


if __name__ == "__main__":
    unittest.main()
