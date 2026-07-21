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
        self.assertIn("needs: focused", unit)
        self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", unit)
        self.assertIn('python-version: ["3.10", "3.11", "3.12"]', unit)
        self.assertIn("python -B scripts/run_tests.py unit --repository .", unit)

    def test_focused_matrix_runs_before_the_unit_lane(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        focused = self.job(text, "focused", "unit")
        self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", focused)
        self.assertIn('python-version: ["3.10", "3.11", "3.12"]', focused)
        self.assertIn("python -B scripts/run_tests.py focused --repository .", focused)

    def test_each_job_fetches_history_for_frozen_base_comparison(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(4, text.count("fetch-depth: 0"))

    def test_jobs_use_governed_runner_lanes(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        unit = self.job(text, "unit", "integration")
        integration = self.job(text, "integration", "package-process-resource-smoke")
        package = self.job(text, "package-process-resource-smoke", None)

        self.assertIn("python -B scripts/run_tests.py unit --repository .", unit)
        self.assertIn("needs: unit", integration)
        self.assertIn("python -B scripts/run_tests.py integration --repository .", integration)
        self.assertIn("needs: integration", package)
        self.assertIn("python -B scripts/run_tests.py package --repository .", package)
        for job in (unit, integration, package):
            self.assertNotIn("sagekit.test_node", job)
            self.assertNotIn("scripts/wheel_smoke.py", job)

    def test_integration_and_package_use_one_python_per_platform(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        integration = self.job(text, "integration", "package-process-resource-smoke")
        package = self.job(text, "package-process-resource-smoke", None)
        for job in (integration, package):
            self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", job)
            self.assertNotIn('python-version: ["3.10", "3.11", "3.12"]', job)
            self.assertIn("python-version: \"3.12\"", job)
        self.assertIn("python -B scripts/run_tests.py integration --repository .", integration)
        self.assertIn("python -B scripts/run_tests.py package --repository .", package)

    def test_package_jobs_use_internal_source_check_and_wheel_smoke(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(1, text.count("python -B scripts/run_tests.py package --repository ."))
        self.assertEqual(1, text.count("python -B scripts/run_tests.py source-repo --repository ."))
        self.assertNotIn("python -B -m sagekit check --source-repo", text)

    @staticmethod
    def job(text: str, name: str, next_name: str | None) -> str:
        start = text.index(f"  {name}:\n")
        end = len(text) if next_name is None else text.index(f"  {next_name}:\n", start)
        return text[start:end]
