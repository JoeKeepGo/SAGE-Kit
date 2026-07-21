from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
import warnings
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sagekit.harness import (
    CandidateAssessment,
    CandidateFreezeResult,
    CompiledPacket,
    ManagedExecutionError,
    PacketError,
    ProcessResult,
    ProjectCheckResult,
    ResourceClass,
    SourceConfig,
    TaskEvidenceValidationResult,
    ValidationError,
    WorkspaceBinding,
    WorkspaceIdentity,
    WorkspaceVerification,
    assess_candidate,
    build_project_workspace_binding,
    check_project,
    discover_project_workspace,
    freeze_candidate,
    load_project_normalized_spec,
    load_project_source_config,
    run_managed_command,
    run_managed_git_command,
    run_managed_readonly_git_command,
    validate_task_and_evidence_records,
    verify_project_workspace,
    write_ephemeral_packet,
)
from sagekit import compile_ephemeral_packet
from sagekit.findings import Finding
from sagekit.packet import compile_packet
from sagekit.spec_sources import package_identity
from sagekit.workspace_binding import authorize_command
from tests.test_thin_execution_documents import create_project


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_harness_config(root: Path) -> None:
    write_json(
        root / "SAGEKIT_CONFIG.json",
        {
            "schema_version": 1,
            "project_id": "harness-synthetic-project",
            "adoption_profile": "package-bound",
            "execution_scope": "active-only",
            "active_context": "docs/ACTIVE_CONTEXT.md",
            "package": package_identity(),
            "sources": {
                "M36": {"adapter": "thin-v1", "path": "docs/M36"}
            },
        },
    )


def enable_resource_policy(root: Path, *, exclusive: list[str]) -> None:
    paths = (
        root / "SAGE_PROJECT.json",
        root / "docs/M36/MILESTONE_MANIFEST.json",
        root / "docs/M36/phases/P1.json",
        root / "docs/M36/phases/P2.json",
    )
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["sagekit_contract"] = "2026.7.20.1"
        if path.name == "SAGE_PROJECT.json":
            payload["resource_contract"] = "conservative-host-v1"
        elif path.parent.name == "phases":
            payload["resource_profile"] = "conservative-host-v1"
            payload["resource_overrides"] = (
                {"runtime_exclusive": exclusive} if path.stem == "P2" else {}
            )
        write_json(path, payload)


def valid_task_record() -> dict:
    return {
        "validation_contract": {
            "version": 2,
            "policy_id": "sagekit-task-dispatch-v2",
            "policy_sha256": "0a7c5039a1c1922dc5a2e7dabab04eae7cfa78c663bdc100779dd46a4cb8efc3",
            "scope": "active",
        },
        "id": "TASK-HARNESS",
        "type": "spec",
        "title": "Validate dispatch records in harness API",
        "priority": "P2",
        "status": "NEW",
        "runtime_shape": "documentation-only",
        "owner": "harness-test-owner",
        "authority": {
            "source": "unit-test authority",
            "grant": "WRITE_AUTHORIZED",
            "scope": "TASK-HARNESS",
        },
        "lifecycle": {
            "phase": "triage",
            "review_result": "PENDING",
            "next_action": "collect evidence",
        },
        "scope": {
            "objective": "Keep harness API checks deterministic.",
            "allowed_files": [],
            "read_only_files": [],
            "forbidden_files": [],
            "non_goals": [],
            "stop_conditions": [],
        },
        "verification": {
            "required_levels": ["L0"],
            "evidence_file": "evidence.yaml",
            "mock_allowed": False,
            "required_commands": [],
            "runtime_smoke": "N/A because this is a documentation-only validation fixture",
        },
        "dependencies": {"requires": [], "blocks": []},
        "resources": {"locks": []},
        "runs": [],
        "closure": {
            "accepted_by": None,
            "accepted_at": None,
            "closed_at": None,
            "review_result": "PENDING",
            "evidence_ref": None,
            "notes": None,
        },
    }


def valid_evidence_record() -> dict:
    levels = {
        level: {
            "status": "PENDING" if level == "L0" else "N/A",
            "evidence": [],
            "commands": [],
            "reason": "awaiting evidence",
        }
        for level in ["L0", "L1", "L2", "L3", "L4"]
    }
    return {
        "validation_contract": {
            "version": 2,
            "policy_id": "sagekit-task-dispatch-v2",
            "policy_sha256": "0a7c5039a1c1922dc5a2e7dabab04eae7cfa78c663bdc100779dd46a4cb8efc3",
            "scope": "active",
        },
        "task_id": "TASK-HARNESS",
        "objective": "Keep harness API checks deterministic.",
        "owner": "harness-test-validator",
        "authority": {
            "source": "unit-test authority",
            "grant": "WRITE_AUTHORIZED",
            "scope": "TASK-HARNESS",
        },
        "phase": "triage",
        "changed_surface": [],
        "runtime_shape": "documentation",
        "levels": levels,
        "artifacts": {
            "commands": [],
            "files_changed": [],
            "api": [],
            "sql": [],
            "browser": [],
            "logs": [],
            "screenshots": [],
            "release": [],
            "ids": [],
        },
        "runs": [],
        "skipped_checks": [],
        "blockers": [],
        "conclusion": {
            "status": "PENDING",
            "highest_level": "none",
            "review_result": "PENDING",
            "mock_used": False,
            "accepted_fallback": False,
            "mock_rationale": None,
            "mock_scope": None,
            "mock_follow_up": None,
            "mock_accepted_by": None,
            "accepted_fallback_by": None,
            "accepted_fallback_scope": None,
            "accepted_fallback_reason": None,
            "mock_acceptance_ref": None,
            "next_action": "collect evidence",
        },
    }


class HarnessAPITests(unittest.TestCase):
    def test_project_check_wrapper_preserves_gate_scope_and_external_manifest(self) -> None:
        root = Path("project-root")
        manifest = Path("external-scope.json")
        findings = [Finding("PASS", "project-contract", None, None, "valid")]
        with patch("sagekit.harness.detect_root", return_value=root), patch(
            "sagekit.harness.run_check", return_value=findings
        ) as check:
            result = check_project(
                root,
                gate_ready=True,
                mode="heavy",
                scope="history",
                scope_manifest_path=manifest,
            )

        self.assertIsInstance(result, ProjectCheckResult)
        self.assertTrue(result.ok)
        self.assertEqual(tuple(findings), result.findings)
        self.assertTrue(result.gate_ready)
        self.assertEqual("heavy", result.mode)
        self.assertEqual("history", result.scope)
        self.assertEqual(manifest.resolve(), result.scope_manifest_path)
        check.assert_called_once_with(
            root,
            gate_ready=True,
            mode="heavy",
            scope="history",
            scope_manifest_path=manifest.resolve(),
        )

    def test_project_check_result_reports_failures_unambiguously(self) -> None:
        result = ProjectCheckResult(
            Path("project-root"),
            (Finding("FAIL", "gate", None, None, "blocked"),),
            False,
            None,
            "active",
            None,
        )

        self.assertFalse(result.ok)

    def test_candidate_freeze_and_assessment_are_public_harness_entrypoints(self) -> None:
        import sagekit

        self.assertIs(sagekit.freeze_candidate, freeze_candidate)
        self.assertIs(sagekit.assess_candidate, assess_candidate)
        self.assertIs(sagekit.CandidateFreezeResult, CandidateFreezeResult)
        self.assertIs(sagekit.CandidateAssessment, CandidateAssessment)

    def test_project_source_config_and_normalized_spec_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            config = load_project_source_config(root, required=True)
            spec = load_project_normalized_spec(
                root,
                "M36",
            )

        self.assertIsNotNone(config)
        self.assertEqual("harness-synthetic-project", config.project_id)
        self.assertEqual("M36", spec.project.milestone.milestone_id)
        self.assertEqual("configured-thin-v1", spec.provenance.adapter)

    def test_compile_ephemeral_packet_from_harness_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            canonical = compile_packet(
                root,
                "M36",
                "P2",
            )
            harness = compile_ephemeral_packet(
                root,
                "M36",
                "P2",
            )

        self.assertEqual(canonical.digest, harness.digest)
        self.assertEqual(canonical.mode, harness.mode)
        self.assertEqual(canonical.payload["target"]["milestone_id"], "M36")

    def test_public_packet_compilation_rejects_contract_root_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)

            with self.assertRaises(TypeError):
                compile_ephemeral_packet(  # type: ignore[call-arg]
                    root, "M36", "P2", contract_root=contracts
                )

    def test_ephemeral_packet_write_rechecks_current_authority_and_write_grant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            milestone_packet = compile_ephemeral_packet(root, "M36")
            phase_packet = compile_ephemeral_packet(root, "M36", "P2")

            with self.assertRaisesRegex(PacketError, "repo-write runtime output"):
                write_ephemeral_packet(
                    root, ".sagekit/packets/M36.json", milestone_packet
                )
            phase = root / "docs/M36/phases/P2.json"
            payload = json.loads(phase.read_text(encoding="utf-8"))
            payload["objective"] = "Authority changed after packet compilation."
            write_json(phase, payload)
            with self.assertRaisesRegex(PacketError, "current project-owned SPEC authority"):
                write_ephemeral_packet(root, ".sagekit/packets/P2.json", phase_packet)

            self.assertFalse((root / ".sagekit/packets/P2.json").exists())

    def test_task_and_evidence_validation_wrapper(self) -> None:
        task = valid_task_record()
        evidence = valid_evidence_record()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "docs/M1/dispatch/TASK-HARNESS"
            task_file = record / "task.yaml"
            evidence_file = record / "evidence.yaml"
            write_json(task_file, task)
            write_json(evidence_file, evidence)
            result = validate_task_and_evidence_records(root, task_file, evidence_file)
            evidence["task_id"] = "TASK-MISMATCH"
            evidence_file.write_text(json.dumps(evidence), encoding="utf-8")
            mismatch = validate_task_and_evidence_records(root, task_file, evidence_file)

        self.assertIsInstance(result, TaskEvidenceValidationResult)
        self.assertTrue(result.ok)
        self.assertEqual((), result.errors)
        self.assertEqual(2, result.selection.version)
        self.assertTrue(result.active_reconciliation)
        self.assertFalse(mismatch.ok)
        self.assertTrue(
            any("does not match evidence.task_id" in error for error in mismatch.errors)
        )

    def test_unversioned_records_without_container_authority_fail_closed(self) -> None:
        task = valid_task_record()
        evidence = valid_evidence_record()
        task.pop("validation_contract")
        evidence.pop("validation_contract")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "docs/M1/dispatch/TASK-HARNESS"
            task_file = record / "task.yaml"
            evidence_file = record / "evidence.yaml"
            write_json(task_file, task)
            write_json(evidence_file, evidence)
            result = validate_task_and_evidence_records(root, task_file, evidence_file)

        self.assertFalse(result.ok)
        self.assertIsNone(result.selection)
        self.assertTrue(result.active_reconciliation)
        self.assertTrue(any("unversioned records require" in error for error in result.errors))

    def test_accepted_terminal_history_uses_frozen_contract_selector(self) -> None:
        task = valid_task_record()
        evidence = valid_evidence_record()
        task.pop("validation_contract")
        evidence.pop("validation_contract")
        task["status"] = "CLOSED"
        evidence["conclusion"]["status"] = "VERIFIED"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "docs/M1/dispatch/TASK-HARNESS"
            task_file = record / "task.yaml"
            evidence_file = record / "evidence.yaml"
            write_json(task_file, task)
            write_json(evidence_file, evidence)
            write_json(
                root / "docs/SAGE_VALIDATION_SCOPE.json",
                {
                    "schema_version": 1,
                    "active_containers": [],
                    "accepted_legacy_containers": [
                        {
                            "id": "M1",
                            "path": "docs/M1",
                            "contract_version": 1,
                            "supersedes": [],
                        }
                    ],
                    "authority": {
                        "source": "unit-test project authority",
                        "approved_by": "unit-test-owner",
                        "approved_at": "2026-01-01T00:00:00Z",
                        "baseline_head": "0123456789abcdef0123456789abcdef01234567",
                    },
                },
            )
            result = validate_task_and_evidence_records(
                root,
                task_file,
                evidence_file,
            )

        self.assertIsNotNone(result.selection)
        self.assertEqual(1, result.selection.version)
        self.assertFalse(result.active_reconciliation)

    def test_workspace_binding_verification_and_its_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = build_project_workspace_binding(
                root,
                permission_mode="READ_ONLY_REVIEW",
                controller="harness-controller",
                base_head=None,
                allowed_paths=(),
            )
            current = discover_project_workspace(root)
            identity = verify_project_workspace(binding, current=current)
            drifted_identity = replace(
                current,
                repository_root=str(current.repository_root) + "/drifted",
            )
            drifted = verify_project_workspace(binding, current=drifted_identity)

        self.assertTrue(identity.ok, identity.errors)
        self.assertFalse(drifted.ok)
        self.assertTrue(drifted.errors)

    def test_managed_execution_wrappers_forward_explicit_arguments(self) -> None:
        command_result = object()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            packet = compile_ephemeral_packet(
                root, "M36", "P2"
            )
            binding = WorkspaceBinding.from_dict(packet.payload["workspace_binding"])
            allowed = tuple(
                ResourceClass(value)
                for value in packet.payload["resolved_resource_policy"][
                    "allowed_resource_classes"
                ]
            )
            execute_patch = patch("sagekit.harness._run_managed_command")
            execute = execute_patch.start()
            self.addCleanup(execute_patch.stop)
            execute.return_value = command_result
            result = run_managed_command(
                root,
                packet,
                ("python", "-B", "-c", "print('ok')"),
                resource_class=ResourceClass.REPO_READ,
                stage="harness-run",
                run_id="run-1",
                timeout=12.0,
                delegated_classes=(ResourceClass.REPO_READ,),
                max_output_bytes=2048,
            )
            execute.assert_called_once_with(
                root,
                ("python", "-B", "-c", "print('ok')"),
                resource_class=ResourceClass.REPO_READ,
                permission_mode=binding.permission_mode,
                controller=binding.controller,
                stage="harness-run",
                run_id="run-1",
                timeout=12.0,
                delegated_classes=(ResourceClass.REPO_READ,),
                max_output_bytes=2048,
                environment=None,
                cwd=None,
                temp_root=None,
                wait_timeout=30.0,
                check=True,
                on_heartbeat=None,
                on_wait=None,
                isolated_test_harness=False,
                max_owned_processes=32,
                workspace_binding=binding,
                allowed_resource_classes=allowed,
                authority_digest=packet.digest,
            )
        self.assertIs(command_result, result)

    def test_managed_execution_does_not_accept_free_permission_or_controller(self) -> None:
        with self.assertRaises(TypeError):
            run_managed_command(  # type: ignore[call-arg]
                Path.cwd(),
                object(),
                ("python", "mutate_repo.py"),
                resource_class=ResourceClass.REPO_WRITE,
                permission_mode="WRITE_AUTHORIZED",
                controller="caller-selected",
                stage="unauthorized",
                run_id="run-unauthorized",
                timeout=1.0,
            )

    def test_managed_execution_callers_can_only_tighten_packet_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            packet = compile_ephemeral_packet(root, "M36", "P2")
            process = packet.payload["resolved_resource_policy"]["process_policy"]
            wait = packet.payload["resolved_resource_policy"]["wait_policy"]

            cases = (
                (
                    {"max_output_bytes": process["max_output_bytes"] + 1},
                    "output limit",
                ),
                (
                    {"max_owned_processes": process["max_owned_processes"] + 1},
                    "process limit",
                ),
                (
                    {"wait_timeout": wait["max_wait_seconds"] + 1},
                    "wait limit",
                ),
            )
            with patch("sagekit.harness._run_managed_command") as execute:
                for overrides, message in cases:
                    with self.subTest(message=message), self.assertRaisesRegex(
                        ManagedExecutionError, message
                    ):
                        run_managed_command(
                            root,
                            packet,
                            ("git", "status", "--short"),
                            resource_class=ResourceClass.REPO_READ,
                            stage="limit-check",
                            run_id="limit-check",
                            timeout=1.0,
                            **overrides,
                        )
                with self.assertRaises(TypeError):
                    run_managed_command(  # type: ignore[call-arg]
                        root,
                        packet,
                        ("git", "status", "--short"),
                        resource_class=ResourceClass.REPO_READ,
                        stage="isolated",
                        run_id="isolated",
                        timeout=1.0,
                        isolated_test_harness=True,
                    )
            execute.assert_not_called()

    def test_managed_execution_holds_packet_exclusive_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            enable_resource_policy(root, exclusive=["database:test-state", "port:4173"])
            packet = compile_ephemeral_packet(root, "M36", "P2")

            with patch("sagekit.harness.ResourceManager") as manager, patch(
                "sagekit.harness._run_managed_command", return_value=object()
            ):
                run_managed_command(
                    root,
                    packet,
                    ("git", "status", "--short"),
                    resource_class=ResourceClass.REPO_READ,
                    stage="exclusive-check",
                    run_id="exclusive-check",
                    timeout=1.0,
                )

            request = manager.return_value.acquire.call_args.args[0]
            self.assertEqual(
                ("database:test-state", "port:4173"), request.exclusive_resources
            )

    def test_read_only_authority_rejects_unclassified_python_script(self) -> None:
        decision = authorize_command(
            ("python", "mutate_repo.py"),
            resource_class=ResourceClass.REPO_READ,
            permission_mode="READ_ONLY_REVIEW",
            allowed_classes=(ResourceClass.REPO_READ,),
            descendant=False,
        )

        self.assertFalse(decision.ok)
        self.assertIn("unclassified", decision.reason)

    def test_managed_execution_rejects_tampered_packet_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            packet = compile_ephemeral_packet(
                root, "M36", "P2"
            )
            payload = copy.deepcopy(packet.payload)
            payload["workspace_binding"]["permission_mode"] = "SUBMIT_AUTHORIZED"
            tampered = CompiledPacket(packet.mode, payload, packet.digest, packet.provenance)
            with patch("sagekit.harness._run_managed_command") as execute:
                with self.assertRaises(PacketError):
                    run_managed_command(
                        root,
                        tampered,
                        ("git", "status", "--short"),
                        resource_class=ResourceClass.REPO_READ,
                        stage="tampered",
                        run_id="tampered",
                        timeout=1.0,
                    )
            execute.assert_not_called()

    def test_managed_execution_reuses_explicit_packet_source_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            source = root / "docs/embedded-M36"
            shutil.copytree(root / "docs/M36", source)
            packet = compile_ephemeral_packet(root, "M36", "P2", source=source)
            serialized = json.loads(packet.to_json())
            packet = CompiledPacket(
                serialized["mode"], serialized, serialized["packet_sha256"]
            )

            configured_phase = root / "docs/M36/phases/P2.json"
            configured = json.loads(configured_phase.read_text(encoding="utf-8"))
            configured["objective"] = "Configured source changed after compilation."
            write_json(configured_phase, configured)

            with patch(
                "sagekit.harness._run_managed_command", return_value=object()
            ) as execute:
                run_managed_command(
                    root,
                    packet,
                    ("git", "status", "--short"),
                    resource_class=ResourceClass.REPO_READ,
                    stage="explicit-source",
                    run_id="explicit-source",
                    timeout=1.0,
                )
                execute.assert_called_once()

                embedded_phase = source / "phases/P2.json"
                embedded = json.loads(embedded_phase.read_text(encoding="utf-8"))
                embedded["objective"] = "Embedded source changed after compilation."
                write_json(embedded_phase, embedded)
                execute.reset_mock()
                with self.assertRaisesRegex(
                    ManagedExecutionError, "current project-owned SPEC authority"
                ):
                    run_managed_command(
                        root,
                        packet,
                        ("git", "status", "--short"),
                        resource_class=ResourceClass.REPO_READ,
                        stage="stale-explicit-source",
                        run_id="stale-explicit-source",
                        timeout=1.0,
                    )
                execute.assert_not_called()

    def test_managed_execution_rejects_class_outside_packet_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            packet = compile_ephemeral_packet(
                root, "M36", "P2"
            )
            allowed = set(
                packet.payload["resolved_resource_policy"]["allowed_resource_classes"]
            )
            denied = next(item for item in ResourceClass if item.value not in allowed)
            with patch("sagekit.harness._run_managed_command") as execute:
                with self.assertRaisesRegex(
                    ManagedExecutionError, "exceeds packet authority"
                ):
                    run_managed_command(
                        root,
                        packet,
                        ("git", "status", "--short"),
                        resource_class=denied,
                        stage="denied",
                        run_id="denied",
                        timeout=1.0,
                    )
            execute.assert_not_called()

    def test_managed_readonly_git_wrapper_requires_packet_authority(self) -> None:
        git_result = object()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            packet = compile_ephemeral_packet(
                root, "M36", "P2"
            )
            git_patch = patch("sagekit.harness._run_managed_git")
            git_call = git_patch.start()
            self.addCleanup(git_patch.stop)
            git_call.return_value = git_result
            result = run_managed_readonly_git_command(
                root,
                packet,
                ("status", "--short"),
                stage="harness-git",
                run_id="run-git",
                timeout=9.0,
                max_output_bytes=1024,
            )
            git_call.assert_called_once_with(
                root,
                ("status", "--short"),
                stage="harness-git",
                run_id="run-git",
                timeout=9.0,
                max_output_bytes=1024,
            )
        self.assertIs(git_result, result)

    def test_old_managed_git_name_is_only_a_deprecated_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_harness_config(root)
            packet = compile_ephemeral_packet(
                root, "M36", "P2"
            )
            with patch(
                "sagekit.harness.run_managed_readonly_git_command",
                return_value=object(),
            ), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                run_managed_git_command(
                    root,
                    packet,
                    ("status", "--short"),
                    stage="harness-git",
                )

        self.assertTrue(any(item.category is DeprecationWarning for item in caught))

    def test_public_root_exports_signature_types_and_errors(self) -> None:
        import sagekit

        expected = {
            CompiledPacket,
            ManagedExecutionError,
            PacketError,
            ProcessResult,
            ResourceClass,
            SourceConfig,
            TaskEvidenceValidationResult,
            ValidationError,
            WorkspaceBinding,
            WorkspaceIdentity,
            WorkspaceVerification,
        }
        self.assertTrue(expected.issubset({getattr(sagekit, item.__name__) for item in expected}))


if __name__ == "__main__":
    unittest.main()
