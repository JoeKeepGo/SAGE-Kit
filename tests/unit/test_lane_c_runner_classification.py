from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from sagekit.managed_execution import ManagedExecutionError
from sagekit.resource_governor import ResourceBusy
from scripts.run_tests import main


class RunnerClassificationTests(unittest.TestCase):
    def run_error(self, error: Exception) -> tuple[int, dict[str, object]]:
        output = StringIO()
        with patch("scripts.run_tests.execute_plan", side_effect=error), redirect_stdout(output):
            code = main(["unit", "--json"])
        return code, json.loads(output.getvalue())

    def test_capability_failure_is_not_a_handoff(self) -> None:
        code, payload = self.run_error(
            ManagedExecutionError("required containment capability unavailable")
        )

        self.assertEqual(3, code)
        self.assertEqual("CAPABILITY_LIMITATION", payload["state"])
        self.assertEqual("capability", payload["category"])

    def test_authority_failure_is_distinct(self) -> None:
        code, payload = self.run_error(
            ManagedExecutionError("workspace binding authority differs")
        )

        self.assertEqual(3, code)
        self.assertEqual("AUTHORITY_REQUIRED", payload["state"])
        self.assertEqual("authority", payload["category"])

    def test_resource_busy_preserves_resource_state_without_handoff(self) -> None:
        code, payload = self.run_error(
            ResourceBusy("cpu lease occupied", state="HANDOFF_READY")
        )

        self.assertEqual(1, code)
        self.assertEqual("RESOURCE_WAIT", payload["state"])
        self.assertEqual("HANDOFF_READY", payload["resource_state"])

    def test_unclassified_execution_failure_is_not_a_handoff(self) -> None:
        code, payload = self.run_error(ManagedExecutionError("child exited unexpectedly"))

        self.assertEqual(3, code)
        self.assertEqual("EXECUTION_FAILED", payload["state"])


if __name__ == "__main__":
    unittest.main()
