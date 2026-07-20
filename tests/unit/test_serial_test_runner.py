from __future__ import annotations

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from pathlib import Path

from sagekit.resource_governor import ResourceClass
from sagekit.test_runner import build_plan, command_for, execute_plan
from scripts.run_tests import main as runner_main


class SerialTestRunnerUnitTests(unittest.TestCase):
    def test_only_package_lane_delegates_its_shared_host_lease(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        result = SimpleNamespace(
            ok=True,
            elapsed=0.01,
            classification=SimpleNamespace(value="success"),
            peak_owned_processes=1,
            child_cpu_seconds=0.0,
            peak_rss_bytes=1,
            stdout_bytes=0,
            stderr_bytes=0,
            heartbeat_count=1,
            cleanup_complete=True,
            containment_complete=True,
            sampling_degraded=False,
            orphan_count=0,
            stdout_tail="",
            stderr_tail="",
        )

        for lane in ("unit", "package"):
            with self.subTest(lane=lane), patch(
                "sagekit.test_runner.run_managed_command", return_value=result
            ) as managed:
                code, evidence = execute_plan(
                    repository,
                    build_plan(lane, waive_high_load=False),
                )

                self.assertEqual(0, code)
                self.assertEqual(1, len(evidence))
                arguments = managed.call_args.kwargs
                if lane == "package":
                    self.assertEqual(
                        (ResourceClass.PACKAGE_BUILD,), arguments["delegated_classes"]
                    )
                    self.assertFalse(arguments["isolated_test_harness"])
                    for key in ("LOCALAPPDATA", "XDG_RUNTIME_DIR", "XDG_CACHE_HOME"):
                        self.assertNotIn(key, arguments["environment"])
                else:
                    self.assertEqual((), arguments["delegated_classes"])
                    self.assertTrue(arguments["isolated_test_harness"])

    def test_package_ci_installs_declared_build_backend_capability(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        workflow = (repository / ".github/workflows/sagekit-self-check.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("Install package build capability", workflow)
        self.assertIn('python -m pip install "setuptools>=68"', workflow)

    def test_final_plan_has_one_fixed_serial_order(self) -> None:
        plan = build_plan("final", waive_high_load=False)

        self.assertEqual(
            ("focused", "unit", "integration", "source-repo", "package"),
            tuple(node.name for node in plan),
        )
        self.assertTrue(all(not node.waived for node in plan))

    def test_high_load_waiver_is_explicit_evidence_not_a_pass(self) -> None:
        plan = build_plan("final", waive_high_load=True)
        states = {node.name: node.waived for node in plan}

        self.assertEqual(
            {
                "focused": False,
                "unit": False,
                "integration": False,
                "source-repo": True,
                "package": True,
            },
            states,
        )
        for node in plan:
            if node.waived:
                self.assertIn("limited development host", node.waiver_reason)

    def test_individual_lane_does_not_expand_to_other_nodes(self) -> None:
        for lane in ("unit", "integration", "package"):
            with self.subTest(lane=lane):
                plan = build_plan(lane, waive_high_load=False)
                self.assertEqual((lane,), tuple(node.name for node in plan))

    def test_package_lane_uses_importable_module_entrypoint(self) -> None:
        node = build_plan("package", waive_high_load=False)[0]

        self.assertEqual(
            ("-B", "-m", "scripts.wheel_smoke"),
            command_for(node, Path.cwd())[1:],
        )

    def test_json_mode_keeps_progress_on_stderr_and_final_json_on_stdout(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        def fake_execute(repository, plan, *, progress):
            progress(
                {
                    "stage": "unit",
                    "state": "RUNNING",
                    "current_test": "tests.unit.test_example",
                }
            )
            return 0, ()

        with patch("scripts.run_tests.execute_plan", side_effect=fake_execute), redirect_stdout(
            stdout
        ), redirect_stderr(stderr):
            exit_code = runner_main(["unit", "--json"])

        self.assertEqual(0, exit_code)
        self.assertIn('"current_test": "tests.unit.test_example"', stderr.getvalue())
        self.assertTrue(stdout.getvalue().lstrip().startswith("{"))


if __name__ == "__main__":
    unittest.main()
