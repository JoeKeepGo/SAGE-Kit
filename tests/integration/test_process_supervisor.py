from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sagekit.process_supervisor import (
    ProcessClassification,
    _MandatoryHeartbeatDispatcher,
    _WindowsBackend,
    run_process,
)


class ProcessSupervisorIntegrationTests(unittest.TestCase):
    def test_immediate_success_with_hung_renewal_obeys_command_timeout(self) -> None:
        renewal_started = threading.Event()
        allow_renewal = threading.Event()
        renewal_finished = threading.Event()

        def renewal(_heartbeat) -> None:
            renewal_started.set()
            allow_renewal.wait(2)
            renewal_finished.set()

        with tempfile.TemporaryDirectory() as directory:
            with patch("sagekit.process_supervisor._MANDATORY_RENEWAL_MAX_AGE", 0.6):
                started = time.monotonic()
                try:
                    result = run_process(
                        stage="immediate-success-hung-renewal",
                        command=(sys.executable, "-B", "-c", "pass"),
                        cwd=Path(directory),
                        timeout=0.25,
                        run_id="immediate-success-hung-renewal",
                        heartbeat_interval=0.01,
                        termination_grace=0.05,
                        on_mandatory_heartbeat=renewal,
                    )
                finally:
                    allow_renewal.set()
                    renewal_finished.wait(1)
                elapsed = time.monotonic() - started

        self.assertTrue(renewal_started.is_set())
        self.assertEqual(ProcessClassification.TIMEOUT, result.classification)
        self.assertEqual("timeout", result.termination_reason)
        self.assertTrue(result.cleanup_complete, result.cleanup_error)
        self.assertLess(elapsed, 1.0)

    def test_renewal_failure_racing_child_exit_cannot_report_success(self) -> None:
        allow_failure = threading.Event()

        class RacingMandatoryDispatcher(_MandatoryHeartbeatDispatcher):
            def state(self) -> tuple[BaseException | None, float | None]:
                super().state()
                return None, None

            def close(self) -> None:
                allow_failure.set()
                super().close()

            def close_and_drain(
                self, deadline: float
            ) -> tuple[BaseException | None, bool]:
                allow_failure.set()
                return super().close_and_drain(deadline)

        def renewal(_heartbeat) -> None:
            self.assertTrue(allow_failure.wait(1))
            raise OSError("renewal lost at child exit")

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "sagekit.process_supervisor._MandatoryHeartbeatDispatcher",
                RacingMandatoryDispatcher,
            ):
                result = run_process(
                    stage="renewal-child-exit-race",
                    command=(sys.executable, "-B", "-c", "pass"),
                    cwd=Path(directory),
                    timeout=1,
                    run_id="renewal-child-exit-race",
                    heartbeat_interval=0.01,
                    on_mandatory_heartbeat=renewal,
                )

        self.assertEqual(ProcessClassification.INTERNAL, result.classification)
        self.assertIn(
            "mandatory-heartbeat:OSError:renewal lost at child exit",
            result.termination_reason,
        )

    def test_fast_child_waits_for_submitted_mandatory_renewal(self) -> None:
        renewal_started = threading.Event()
        allow_renewal = threading.Event()
        renewal_completed = threading.Event()

        def renewal(_heartbeat) -> None:
            renewal_started.set()
            self.assertTrue(allow_renewal.wait(1))
            renewal_completed.set()

        with tempfile.TemporaryDirectory() as directory:
            release = threading.Timer(0.1, allow_renewal.set)
            release.start()
            try:
                result = run_process(
                    stage="fast-child-renewal-barrier",
                    command=(sys.executable, "-B", "-c", "pass"),
                    cwd=Path(directory),
                    timeout=1,
                    run_id="fast-child-renewal-barrier",
                    heartbeat_interval=0.01,
                    on_mandatory_heartbeat=renewal,
                )
            finally:
                release.cancel()
                allow_renewal.set()

        self.assertTrue(renewal_started.is_set())
        self.assertTrue(renewal_completed.is_set())
        self.assertEqual(ProcessClassification.SUCCESS, result.classification)

    def test_mandatory_renewal_failure_after_fast_child_exit_surfaces(self) -> None:
        renewal_started = threading.Event()
        allow_failure = threading.Event()

        def renewal(_heartbeat) -> None:
            renewal_started.set()
            self.assertTrue(allow_failure.wait(1))
            raise OSError("lease store unavailable")

        with tempfile.TemporaryDirectory() as directory:
            release = threading.Timer(0.1, allow_failure.set)
            release.start()
            try:
                result = run_process(
                    stage="fast-child-renewal-failure",
                    command=(sys.executable, "-B", "-c", "pass"),
                    cwd=Path(directory),
                    timeout=1,
                    run_id="fast-child-renewal-failure",
                    heartbeat_interval=0.01,
                    on_mandatory_heartbeat=renewal,
                )
            finally:
                release.cancel()
                allow_failure.set()

        self.assertTrue(renewal_started.is_set())
        self.assertEqual(ProcessClassification.INTERNAL, result.classification)
        self.assertIn("mandatory-heartbeat:OSError:lease store unavailable", result.termination_reason)

    def test_stalled_mandatory_renewal_is_bounded_before_lease_ttl(self) -> None:
        renewal_started = threading.Event()
        allow_renewal = threading.Event()

        def renewal(_heartbeat) -> None:
            renewal_started.set()
            self.assertTrue(allow_renewal.wait(1))

        with tempfile.TemporaryDirectory() as directory:
            with patch("sagekit.process_supervisor._MANDATORY_RENEWAL_MAX_AGE", 0.1):
                try:
                    result = run_process(
                        stage="stalled-mandatory-renewal",
                        command=(sys.executable, "-B", "-c", "import time; time.sleep(5)"),
                        cwd=Path(directory),
                        timeout=5,
                        run_id="stalled-mandatory-renewal",
                        heartbeat_interval=0.01,
                        termination_grace=0.05,
                        on_mandatory_heartbeat=renewal,
                    )
                finally:
                    allow_renewal.set()

        self.assertTrue(renewal_started.is_set())
        self.assertEqual(ProcessClassification.INTERNAL, result.classification)
        self.assertIn("mandatory-heartbeat:timeout", result.termination_reason)
        self.assertLess(result.elapsed, 1.5)

    def test_blocked_heartbeat_callback_cannot_delay_process_timeout(self) -> None:
        def blocked_callback(_heartbeat) -> None:
            time.sleep(2)

        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            result = run_process(
                stage="blocked-heartbeat",
                command=(sys.executable, "-B", "-c", "import time; time.sleep(5)"),
                cwd=Path(directory),
                timeout=0.25,
                run_id="blocked-heartbeat-timeout",
                heartbeat_interval=0.05,
                termination_grace=0.25,
                on_heartbeat=blocked_callback,
            )
            elapsed = time.monotonic() - started

        self.assertEqual(ProcessClassification.TIMEOUT, result.classification)
        self.assertLess(elapsed, 1.5)
        self.assertTrue(result.cleanup_complete, result.cleanup_error)

    def test_mandatory_renewal_runs_despite_blocked_progress_callback(self) -> None:
        renewals: list[float] = []

        def blocked_progress(_heartbeat) -> None:
            time.sleep(2)

        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            result = run_process(
                stage="mandatory-heartbeat",
                command=(sys.executable, "-B", "-c", "import time; time.sleep(5)"),
                cwd=Path(directory),
                timeout=0.25,
                run_id="mandatory-heartbeat-progress",
                heartbeat_interval=0.05,
                termination_grace=0.25,
                on_heartbeat=blocked_progress,
                on_mandatory_heartbeat=lambda _heartbeat: renewals.append(time.monotonic()),
            )
            elapsed = time.monotonic() - started

        self.assertEqual(ProcessClassification.TIMEOUT, result.classification)
        self.assertGreaterEqual(len(renewals), 2)
        self.assertLess(elapsed, 1.5)

    def test_blocked_mandatory_renewal_cannot_delay_process_timeout(self) -> None:
        def blocked_renewal(_heartbeat) -> None:
            time.sleep(2)

        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            result = run_process(
                stage="blocked-mandatory-heartbeat",
                command=(sys.executable, "-B", "-c", "import time; time.sleep(5)"),
                cwd=Path(directory),
                timeout=0.25,
                run_id="blocked-mandatory-heartbeat-timeout",
                heartbeat_interval=0.05,
                termination_grace=0.25,
                on_mandatory_heartbeat=blocked_renewal,
            )
            elapsed = time.monotonic() - started

        self.assertEqual(ProcessClassification.TIMEOUT, result.classification)
        self.assertLess(elapsed, 1.5)
        self.assertTrue(result.cleanup_complete, result.cleanup_error)

    def test_mandatory_renewal_failure_stops_and_surfaces_safely(self) -> None:
        def failed_renewal(_heartbeat) -> None:
            raise OSError("lease store unavailable")

        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            result = run_process(
                stage="failed-mandatory-heartbeat",
                command=(sys.executable, "-B", "-c", "import time; time.sleep(5)"),
                cwd=Path(directory),
                timeout=5,
                run_id="failed-mandatory-heartbeat",
                heartbeat_interval=0.05,
                termination_grace=0.25,
                on_mandatory_heartbeat=failed_renewal,
            )
            elapsed = time.monotonic() - started

        self.assertEqual(ProcessClassification.INTERNAL, result.classification)
        self.assertIn("mandatory-heartbeat:OSError:lease store unavailable", result.termination_reason)
        self.assertTrue(result.cleanup_complete, result.cleanup_error)
        self.assertLess(elapsed, 1.5)

    def test_windows_final_job_query_failure_does_not_claim_containment(self) -> None:
        class FinalQueryFailureJob:
            def __init__(self) -> None:
                self.samples = 0

            def sample(self) -> tuple[int, int, float, int]:
                self.samples += 1
                if self.samples == 1:
                    return 0, 1, 0.0, 0
                raise OSError("final Job Object query failed")

            def terminate(self) -> None:
                raise AssertionError("an empty Job Object must not be terminated")

            def close(self) -> None:
                return

        process = SimpleNamespace(poll=lambda: 0)
        with patch(
            "sagekit.process_supervisor._WindowsJob", FinalQueryFailureJob
        ):
            cleanup = _WindowsBackend().cleanup(process, grace=0.01)

        self.assertFalse(cleanup.complete)
        self.assertFalse(cleanup.containment_complete)
        self.assertIsNone(cleanup.orphan_count)
        self.assertIn("final Job Object query failed", cleanup.error or "")

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
