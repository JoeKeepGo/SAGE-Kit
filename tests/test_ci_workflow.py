import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/sagekit-self-check.yml"


class SelfCheckWorkflowTests(unittest.TestCase):
    def test_feature_push_does_not_duplicate_pull_request_matrix(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertRegex(
            text,
            re.compile(
                r"(?m)^on:\s*$\n"
                r"^  pull_request:\s*$\n"
                r"^  push:\s*$\n"
                r"^    branches:\s*$\n"
                r"^      - main\s*$"
            ),
        )

    def test_concurrency_cancels_superseded_matrix_for_same_pr_or_ref(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "group: sagekit-self-check-${{ github.event.pull_request.number || github.ref }}",
            text,
        )
        self.assertIn("cancel-in-progress: true", text)

    def test_unit_matrix_keeps_all_supported_os_and_python_versions(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        unit = self.job(text, "unit", "integration")
        self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", unit)
        self.assertIn('python-version: ["3.10", "3.11", "3.12"]', unit)
        self.assertIn("python -B -m scripts.run_tests unit --json", unit)

    def test_each_job_fetches_history_for_frozen_base_comparison(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(3, text.count("fetch-depth: 0"))

    def test_integration_and_package_use_one_python_per_platform(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        integration = self.job(text, "integration", "package-process-resource-smoke")
        package = self.job(text, "package-process-resource-smoke", None)
        for job in (integration, package):
            self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", job)
            self.assertNotIn('python-version: ["3.10", "3.11", "3.12"]', job)
            self.assertIn("python-version: \"3.12\"", job)
        self.assertIn("python -B -m scripts.run_tests integration --json", integration)
        self.assertIn("python -B -m scripts.run_tests package --json", package)

    def test_expensive_package_flow_is_not_repeated_in_other_jobs(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(1, text.count("scripts.run_tests package --json"))
        self.assertNotIn("python -B scripts/wheel_smoke.py", text)
        self.assertEqual(1, text.count("scripts.run_tests integration --json"))

    @staticmethod
    def job(text: str, name: str, next_name: str | None) -> str:
        start = text.index(f"  {name}:\n")
        end = len(text) if next_name is None else text.index(f"  {next_name}:\n", start)
        return text[start:end]
