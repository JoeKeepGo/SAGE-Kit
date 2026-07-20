from __future__ import annotations

import os
import sys
import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sagekit.execution_documents import ExecutionDocumentError, load_execution_project
from sagekit.managed_execution import (
    ManagedExecutionError,
    run_managed_command,
    run_managed_git,
)
from sagekit.process_supervisor import ProcessClassification, ProcessResult
from sagekit.process_supervisor import run_process
from sagekit.process_supervisor import _child_environment
from sagekit.resource_governor import ResourceClass
from sagekit.resource_policy import resolve_resource_policy
from sagekit.resource_policy import ResourcePolicyError
from sagekit.test_node import TEST_MODULE_LANES, validate_test_inventory
from sagekit.workspace_binding import authorize_command, required_resource_class


class CommandAuthorityCorrectiveTests(unittest.TestCase):
    @staticmethod
    def success_result(**arguments) -> ProcessResult:
        return ProcessResult(
            stage=str(arguments["stage"]),
            run_id=str(arguments["run_id"]),
            lease_id=str(arguments["lease_id"]),
            command=tuple(arguments["command"]),
            cwd=str(arguments["cwd"]),
            environment_hints={},
            classification=ProcessClassification.SUCCESS,
            exit_code=0,
            termination_reason="exit-0",
            elapsed=0.01,
            stdout_tail="",
            stderr_tail="",
            stdout_tail_bytes=b"",
            stderr_tail_bytes=b"",
            stdout_bytes=0,
            stderr_bytes=0,
            stdout_dropped_bytes=0,
            stderr_dropped_bytes=0,
            peak_owned_processes=1,
            child_cpu_seconds=0.0,
            peak_rss_bytes=1,
            temp_root=None,
            heartbeat_count=1,
            cleanup_complete=True,
            containment_complete=False,
            sampling_degraded=False,
            cleanup_error=None,
            termination_escalated=False,
            orphan_count=None,
        )

    def test_resource_policy_error_is_normalized_by_execution_loader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = SimpleNamespace(
                effective_from="M36", resource_contract="conservative-host-v1"
            )
            milestone = SimpleNamespace(phase_ids=())
            with (
                patch("sagekit.execution_documents.load_project_lock", return_value=lock),
                patch("sagekit.execution_documents.load_execution_contract", return_value=object()),
                patch("sagekit.execution_documents.load_milestone_manifest", return_value=milestone),
                patch("sagekit.execution_documents.validate_execution_project"),
                patch("sagekit.policy_resolution.resolve_policy"),
                patch(
                    "sagekit.resource_policy.resolve_resource_policy",
                    side_effect=ResourcePolicyError("invalid resource override"),
                ),
            ):
                with self.assertRaisesRegex(
                    ExecutionDocumentError, "invalid resource override"
                ):
                    load_execution_project(root, "M36")

    def test_known_commands_require_their_minimum_resource_class(self) -> None:
        self.assertIs(
            ResourceClass.PACKAGE_BUILD,
            required_resource_class((sys.executable, "-B", "-m", "build")),
        )
        self.assertIs(
            ResourceClass.SUBMIT_EXCLUSIVE,
            required_resource_class(("git", "-C", "repo", "add", "file")),
        )
        decision = authorize_command(
            (sys.executable, "-m", "build"),
            resource_class=ResourceClass.REPO_READ,
            permission_mode="ENVIRONMENT_WRITE_AUTHORIZED",
            allowed_classes=(ResourceClass.REPO_READ, ResourceClass.PACKAGE_BUILD),
            descendant=False,
        )
        self.assertFalse(decision.ok)
        self.assertIn("package-build", decision.reason)

    def test_descendant_without_explicit_delegation_cannot_start_command(self) -> None:
        decision = authorize_command(
            (sys.executable, "-c", "print('no')"),
            resource_class=ResourceClass.CPU_HEAVY,
            permission_mode="WRITE_AUTHORIZED",
            allowed_classes=(ResourceClass.CPU_HEAVY,),
            descendant=True,
            delegated=False,
        )
        self.assertFalse(decision.ok)
        self.assertIn("delegation", decision.reason)

    def test_managed_git_rejects_mutation_before_process_launch(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with patch("sagekit.managed_execution.run_process") as launch:
            with self.assertRaisesRegex(ManagedExecutionError, "mutation|submit-exclusive"):
                run_managed_git(repository, ("add", "file"), stage="unit-boundary")
        launch.assert_not_called()

    def test_managed_command_rejects_unbound_external_cwd(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory)
            with patch("sagekit.managed_execution.run_process") as launch:
                with self.assertRaisesRegex(ManagedExecutionError, "cwd|workspace|temp"):
                    run_managed_command(
                        repository,
                        (sys.executable, "-c", "print('no')"),
                        resource_class=ResourceClass.CPU_HEAVY,
                        permission_mode="WRITE_AUTHORIZED",
                        controller="root",
                        stage="unit-boundary",
                        run_id="unit-boundary",
                        timeout=1.0,
                        cwd=outside,
                    )
            launch.assert_not_called()

    def test_spoofed_descendant_environment_cannot_fall_back_to_root_acquire(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        environment = {
            "SAGEKIT_DESCENDANT": "1",
            "SAGEKIT_DELEGATION_SECRET": "x" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            with (
                patch.dict(os.environ, environment, clear=True),
                patch("sagekit.managed_execution.host_runtime_path", return_value=runtime / "host"),
                patch("sagekit.managed_execution.project_runtime_path", return_value=runtime / "project"),
                patch("sagekit.managed_execution.ResourceManager.acquire") as acquire,
                patch("sagekit.managed_execution.run_process") as launch,
            ):
                with self.assertRaisesRegex(ManagedExecutionError, "verified root delegation"):
                    run_managed_command(
                        repository,
                        (sys.executable, "-c", "print('no')"),
                        resource_class=ResourceClass.CPU_HEAVY,
                        permission_mode="WRITE_AUTHORIZED",
                        controller="root",
                        stage="spoofed-descendant",
                        run_id="spoofed-descendant",
                        timeout=1.0,
                    )
        acquire.assert_not_called()
        launch.assert_not_called()

    def test_root_managed_child_gets_no_lease_secret_without_explicit_delegation(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        captured: dict[str, str] = {}

        def launch(**arguments):
            captured.update(arguments["environment"])
            return self.success_result(**arguments)

        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("sagekit.managed_execution.host_runtime_path", return_value=runtime / "host"),
                patch("sagekit.managed_execution.project_runtime_path", return_value=runtime / "project"),
                patch("sagekit.managed_execution.run_process", side_effect=launch),
            ):
                run_managed_command(
                    repository,
                    (sys.executable, "-c", "print('managed')"),
                    resource_class=ResourceClass.CPU_HEAVY,
                    permission_mode="WRITE_AUTHORIZED",
                    controller="root",
                    stage="no-default-delegation",
                    run_id="no-default-delegation",
                    timeout=1.0,
                )
        self.assertEqual("1", captured["SAGEKIT_DESCENDANT"])
        self.assertEqual("reasoning-only", captured["SAGEKIT_ALLOWED_CLASSES"])
        inherited = {
            "SAGEKIT_LEASE_ID": "parent-lease",
            "SAGEKIT_DELEGATION_SECRET": "parent-secret",
            "SAGEKIT_AUTHORITY_DIGEST": "a" * 64,
        }
        with patch.dict(os.environ, inherited, clear=True):
            effective = _child_environment(captured)
        self.assertNotIn("SAGEKIT_LEASE_ID", effective)
        self.assertNotIn("SAGEKIT_DELEGATION_SECRET", effective)
        self.assertNotIn("SAGEKIT_AUTHORITY_DIGEST", effective)
        self.assertEqual("1", effective["GIT_CONFIG_COUNT"])
        self.assertEqual("core.autocrlf", effective["GIT_CONFIG_KEY_0"])
        self.assertEqual("input", effective["GIT_CONFIG_VALUE_0"])

    def test_workspace_is_reverified_after_lease_before_launch(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        verified = SimpleNamespace(ok=True, errors=())
        drifted = SimpleNamespace(ok=False, errors=("branch differs", "HEAD differs"))
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("sagekit.managed_execution.host_runtime_path", return_value=runtime / "host"),
                patch("sagekit.managed_execution.project_runtime_path", return_value=runtime / "project"),
                patch(
                    "sagekit.managed_execution.verify_workspace",
                    side_effect=(verified, drifted),
                ),
                patch("sagekit.managed_execution.run_process") as launch,
            ):
                with self.assertRaisesRegex(
                    ManagedExecutionError, "changed before launch"
                ):
                    run_managed_command(
                        repository,
                        (sys.executable, "-c", "print('must-not-launch')"),
                        resource_class=ResourceClass.CPU_HEAVY,
                        permission_mode="WRITE_AUTHORIZED",
                        controller="root",
                        stage="binding-drift",
                        run_id="binding-drift",
                        timeout=1.0,
                    )
            launch.assert_not_called()
            leases = runtime / "host" / "leases"
            self.assertFalse(leases.exists() and any(leases.iterdir()))

    def test_canonicalized_safe_alias_stays_within_controlled_temp_root(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "actual"
            child = actual / "child"
            child.mkdir(parents=True)
            alias = root / "alias"
            try:
                alias.symlink_to(actual, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink is unavailable: {exc}")
            from sagekit.managed_execution import _validated_cwd

            result = _validated_cwd(
                repository,
                alias / "child",
                temp_root=alias,
                resource_class=ResourceClass.CPU_HEAVY,
            )
            self.assertEqual(child.resolve(), result)


class EvidenceTruthCorrectiveTests(unittest.TestCase):
    def test_process_result_exposes_containment_truth(self) -> None:
        fields = ProcessResult.__dataclass_fields__
        self.assertIn("containment_complete", fields)
        self.assertIn("containment_level", fields)
        self.assertIn("orphan_check", fields)
        self.assertIn("platform_adapter", fields)
        self.assertIn("limitations", fields)
        self.assertIn("sampling_degraded", fields)

    def test_process_policy_and_supervisor_define_owned_tree_limit(self) -> None:
        policy = resolve_resource_policy(
            resource_contract_id=None,
            resource_profile=None,
            overrides=None,
            permission_mode="WRITE_AUTHORIZED",
            execution_profile="standard-phase@v1",
            milestone_packet=False,
        )
        limit = policy.process_policy.get("max_owned_processes")
        self.assertIsInstance(limit, int)
        self.assertGreater(limit, 1)
        self.assertIn("max_owned_processes", inspect.signature(run_process).parameters)

    def test_every_top_level_test_module_has_exactly_one_lane(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        self.assertEqual((), validate_test_inventory(repository))
        discovered = {
            path.stem for path in (repository / "tests").glob("test_*.py")
        }
        self.assertEqual(discovered, set(TEST_MODULE_LANES))
        self.assertTrue(
            all(lane in {"unit", "integration", "package"} for lane in TEST_MODULE_LANES.values())
        )


if __name__ == "__main__":
    unittest.main()
