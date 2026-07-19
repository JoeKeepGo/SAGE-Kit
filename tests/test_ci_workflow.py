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

    def test_matrix_keeps_all_supported_os_and_python_versions(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", text)
        self.assertIn('python-version: ["3.10", "3.11", "3.12"]', text)

    def test_every_matrix_job_runs_fresh_venv_wheel_smoke(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(1, text.count("python -B scripts/wheel_smoke.py"))
        wheel_step = re.search(
            r"(?ms)^      - name: Run wheel install smoke\s*$\n"
            r"(?P<body>.*?)(?=^      - name:|\Z)",
            text,
        )
        self.assertIsNotNone(wheel_step, text)
        self.assertNotIn("if:", wheel_step.group("body"))
