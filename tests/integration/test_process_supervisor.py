from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from sagekit.process_supervisor import ProcessClassification, run_process


class ProcessSupervisorIntegrationTests(unittest.TestCase):
    def test_bounded_output_drains_both_pipes_without_deadlock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_process(
                stage="bounded-output",
                command=(
                    sys.executable,
                    "-B",
                    "-c",
                    "import sys; sys.stdout.write('o'*200000); sys.stderr.write('e'*200000)",
                ),
                cwd=Path(directory),
                timeout=20,
                run_id="process-bounded-output",
                max_output_bytes=4096,
                heartbeat_interval=0.1,
            )
        self.assertEqual(ProcessClassification.SUCCESS, result.classification)
        self.assertEqual(4096, len(result.stdout_tail.encode("utf-8")))
        self.assertEqual(4096, len(result.stderr_tail.encode("utf-8")))
        self.assertGreater(result.stdout_dropped_bytes, 0)
        self.assertGreater(result.stderr_dropped_bytes, 0)
        self.assertEqual(0, result.orphan_count)
        self.assertEqual("HARD" if os.name == "nt" else "MANAGED", result.containment_level)
        self.assertEqual(os.name == "nt", result.containment_complete)
        self.assertIn("job" if os.name == "nt" else "process-group", result.orphan_check)

    def test_timeout_cleans_parent_child_and_grandchild(self) -> None:
        child = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(60)']); "
            "print(p.pid, flush=True); time.sleep(60)"
        )
        parent = (
            "import subprocess,sys,time; "
            f"p=subprocess.Popen([sys.executable,'-B','-c',{child!r}]); "
            "print(p.pid, flush=True); time.sleep(60)"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = run_process(
                stage="tree-timeout",
                command=(sys.executable, "-B", "-c", parent),
                cwd=Path(directory),
                timeout=1.0,
                run_id="process-tree-timeout",
                heartbeat_interval=0.1,
                termination_grace=0.25,
            )
        self.assertEqual(ProcessClassification.TIMEOUT, result.classification)
        self.assertTrue(result.cleanup_complete, result.cleanup_error)
        self.assertEqual(0, result.orphan_count)
        self.assertEqual("HARD" if os.name == "nt" else "MANAGED", result.containment_level)
        self.assertEqual(os.name == "nt", result.containment_complete)
        self.assertGreaterEqual(result.peak_owned_processes, 1)

    @unittest.skipIf(os.name == "nt", "POSIX signal behavior")
    def test_child_ignoring_sigterm_is_force_killed(self) -> None:
        command = (
            sys.executable,
            "-B",
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)",
        )
        with tempfile.TemporaryDirectory() as directory:
            result = run_process(
                stage="ignore-term",
                command=command,
                cwd=Path(directory),
                timeout=0.5,
                run_id="process-ignore-term",
                heartbeat_interval=0.1,
                termination_grace=0.1,
            )
        self.assertEqual(ProcessClassification.TIMEOUT, result.classification)
        self.assertTrue(result.termination_escalated)
        self.assertEqual(0, result.orphan_count)

    @unittest.skipIf(os.name == "nt", "Windows gated Job adapter supplies HARD")
    def test_hard_requirement_rejects_before_target_launch_on_posix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "started"
            result = run_process(
                stage="require-hard",
                command=(
                    sys.executable,
                    "-B",
                    "-c",
                    f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')",
                ),
                cwd=Path(directory),
                timeout=5,
                run_id="require-hard",
                required_containment="HARD",
            )
            self.assertEqual(ProcessClassification.CAPABILITY, result.classification)
            self.assertFalse(marker.exists())
            self.assertEqual("MANAGED", result.containment_level)
            self.assertEqual("target-not-started", result.orphan_check)


if __name__ == "__main__":
    unittest.main()
