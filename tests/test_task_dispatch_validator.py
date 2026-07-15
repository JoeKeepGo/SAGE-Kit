import json
import tempfile
import unittest
from pathlib import Path

from sagekit.task_dispatch_validator import load_record, parse_yaml_subset, validate_records


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs/profiles/task-dispatch/schemas"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "docs/profiles/task-dispatch/templates"


def valid_task():
    return {
        "id": "TASK-001",
        "type": "spec",
        "title": "Validate dispatch records",
        "priority": "P2",
        "status": "NEW",
        "lifecycle": {
            "phase": "triage",
            "review_result": "PENDING",
            "next_action": "collect evidence",
        },
        "scope": {
            "objective": "Reject inconsistent dispatch records.",
            "allowed_files": ["src/app.py"],
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


def valid_evidence():
    levels = {
        level: {
            "status": "PENDING" if level == "L0" else "N/A",
            "evidence": [],
            "commands": [],
            "reason": "not required" if level != "L0" else "awaiting evidence",
        }
        for level in ["L0", "L1", "L2", "L3", "L4"]
    }
    return {
        "task_id": "TASK-001",
        "phase": "triage",
        "changed_surface": [],
        "runtime_shape": "static validation",
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
            "next_action": "collect evidence",
        },
    }


def verified_records():
    task = valid_task()
    evidence = valid_evidence()
    task["status"] = "VERIFIED"
    task["closure"].update(
        {
            "accepted_by": "project-owner",
            "accepted_at": "2026-07-15T10:00:00Z",
            "review_result": "ACCEPTABLE",
            "evidence_ref": "evidence.yaml",
        }
    )
    task["lifecycle"].update(
        {"phase": "review", "review_result": "ACCEPTABLE", "next_action": "close task"}
    )
    evidence["phase"] = "review"
    evidence["levels"]["L0"].update(
        {"status": "PASS", "evidence": ["diff reviewed"], "reason": None}
    )
    evidence["conclusion"].update(
        {
            "status": "VERIFIED",
            "highest_level": "L0",
            "review_result": "ACCEPTABLE",
            "next_action": "close task",
        }
    )
    return task, evidence


class FallbackYamlParserTests(unittest.TestCase):
    def test_windows_path_in_sequence_is_a_scalar(self):
        record = parse_yaml_subset(
            """
scope:
  allowed_files:
    - C:\\repo\\src\\app.py
"""
        )

        self.assertEqual(record["scope"]["allowed_files"], [r"C:\repo\src\app.py"])

    def test_empty_and_simple_flow_mappings_are_parsed(self):
        record = parse_yaml_subset(
            r"""
closure: {}
commands:
  - {command: python -m unittest, source: local, cwd: C:\repo\src}
"""
        )

        self.assertEqual(record["closure"], {})
        self.assertEqual(
            record["commands"],
            [{"command": "python -m unittest", "source": "local", "cwd": r"C:\repo\src"}],
        )


class StructuralValidationTests(unittest.TestCase):
    def test_rejects_wrong_element_types_in_file_and_command_lists(self):
        cases = [
            ("task.scope.allowed_files", lambda task, evidence: task["scope"].update(allowed_files=[{}])),
            (
                "task.verification.required_commands",
                lambda task, evidence: task["verification"].update(required_commands=[42]),
            ),
            (
                "evidence.artifacts.files_changed",
                lambda task, evidence: evidence["artifacts"].update(files_changed=[{}]),
            ),
            (
                "evidence.artifacts.commands",
                lambda task, evidence: evidence["artifacts"].update(commands=[42]),
            ),
        ]
        for label, mutate in cases:
            with self.subTest(label=label):
                task, evidence = valid_task(), valid_evidence()
                mutate(task, evidence)
                errors = validate_records(task, evidence, None)
                self.assertTrue(any(label in error and "element" in error for error in errors), errors)

    def test_rejects_empty_core_fields_and_invalid_evidence_id(self):
        task, evidence = valid_task(), valid_evidence()
        task.update(id="", title="")
        task["scope"]["objective"] = ""
        evidence.update(task_id="wrong-id", runtime_shape="")

        errors = validate_records(task, evidence, None)

        for field in ["task.id", "task.title", "task.scope.objective", "evidence.task_id", "evidence.runtime_shape"]:
            self.assertTrue(any(field in error for error in errors), (field, errors))

    def test_rejects_invalid_run_attempt_lease_and_lock_values(self):
        task, evidence = valid_task(), valid_evidence()
        task["runs"] = [{"id": "run-1", "attempt": 0, "status": "RUNNIG"}]
        evidence["runs"] = [{"id": "run-1", "attempt": 1, "status": "RUNNIG"}]
        task["resources"]["locks"] = [
            {"resource": "db", "owner": "worker", "mode": "exclusive", "status": "HLOD"}
        ]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("task.runs[0].attempt" in error for error in errors), errors)
        self.assertTrue(any("task.runs[0].status" in error for error in errors), errors)
        self.assertTrue(any("evidence.runs[0].status" in error for error in errors), errors)
        self.assertTrue(any("task.resources.locks[0].status" in error for error in errors), errors)

    def test_custom_schema_directory_validates_records(self):
        task, evidence = valid_task(), valid_evidence()
        with tempfile.TemporaryDirectory() as tmp:
            schema_dir = Path(tmp)
            (schema_dir / "task.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": ["review_ticket"],
                        "properties": {"review_ticket": {"type": "string", "minLength": 1}},
                    }
                ),
                encoding="utf-8",
            )
            (schema_dir / "evidence.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": ["audit_tag"],
                        "properties": {"audit_tag": {"enum": ["reviewed"]}},
                    }
                ),
                encoding="utf-8",
            )

            errors = validate_records(task, evidence, schema_dir)

        self.assertTrue(any("task.review_ticket is required by schema" in error for error in errors), errors)
        self.assertTrue(any("evidence.audit_tag is required by schema" in error for error in errors), errors)

    def test_custom_schema_enforces_composition_and_conditionals(self):
        task, evidence = valid_task(), valid_evidence()
        task["review_ticket"] = "REVIEW-2"
        evidence["audit_tag"] = "draft"
        with tempfile.TemporaryDirectory() as tmp:
            schema_dir = Path(tmp)
            (schema_dir / "task.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "allOf": [
                            {"properties": {"review_ticket": {"const": "REVIEW-1"}}}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (schema_dir / "evidence.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "if": {"properties": {"audit_tag": {"const": "draft"}}},
                        "then": {"required": ["reviewed_by"]},
                    }
                ),
                encoding="utf-8",
            )

            errors = validate_records(task, evidence, schema_dir)

        self.assertTrue(any("task.review_ticket" in error and "constant" in error for error in errors), errors)
        self.assertTrue(any("evidence.reviewed_by is required by schema" in error for error in errors), errors)

    def test_schema_validation_does_not_inject_shared_resource_flag(self):
        task, evidence = valid_task(), valid_evidence()
        task["runs"] = [
            {
                "id": "run-1",
                "attempt": 1,
                "status": "RUNNING",
                "lease": {
                    "resource": "test-db",
                    "owner": "worker-1",
                    "mode": "exclusive",
                    "status": "ACTIVE",
                    "release_rule": "after tests",
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            schema_dir = Path(tmp)
            (schema_dir / "task.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "runs": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["uses_shared_resource"],
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (schema_dir / "evidence.schema.json").write_text(
                json.dumps({"type": "object"}), encoding="utf-8"
            )

            errors = validate_records(task, evidence, schema_dir)

        self.assertTrue(any("uses_shared_resource is required by schema" in error for error in errors), errors)

    def test_repository_templates_validate_against_actual_schemas(self):
        task = load_record(TEMPLATE_DIR / "TASK_RECORD_TEMPLATE.yaml")
        evidence = load_record(TEMPLATE_DIR / "EVIDENCE_RECORD_TEMPLATE.yaml")

        errors = validate_records(task, evidence, SCHEMA_DIR)

        self.assertEqual(errors, [])


class LifecycleValidationTests(unittest.TestCase):
    def test_authority_fields_must_match_in_all_validation_modes(self):
        authority = {
            "source": "milestone entry gate",
            "grant": "WRITE_AUTHORIZED",
            "scope": "TASK-001 and its allowed files and evidence",
        }
        mismatches = {
            "source": "execution packet",
            "grant": "CORRECTIVE_AUTHORIZED",
            "scope": "TASK-001 evidence only",
        }
        for gate_ready in [False, True]:
            for field, mismatch in mismatches.items():
                with self.subTest(gate_ready=gate_ready, field=field):
                    task, evidence = verified_records() if gate_ready else (valid_task(), valid_evidence())
                    task["authority"] = authority.copy()
                    evidence["authority"] = authority.copy()
                    evidence["authority"][field] = mismatch

                    errors = validate_records(task, evidence, None, gate_ready=gate_ready)

                    self.assertTrue(
                        any(
                            f"task.authority.{field}" in error
                            and f"evidence.authority.{field}" in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_terminal_task_and_evidence_states_must_agree(self):
        task, evidence = valid_task(), valid_evidence()
        task["status"] = "VERIFIED"

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("task.status VERIFIED" in error for error in errors), errors)

        task, evidence = verified_records()
        task["status"] = "IN_PROGRESS"
        errors = validate_records(task, evidence, None)
        self.assertTrue(any("task.status IN_PROGRESS" in error for error in errors), errors)

    def test_verified_and_closed_tasks_require_closure_metadata(self):
        task, evidence = verified_records()
        task["closure"].update(
            accepted_by=None,
            accepted_at=None,
            review_result=None,
            evidence_ref=None,
        )

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("task.closure.accepted_by" in error for error in errors), errors)
        self.assertTrue(any("task.closure.accepted_at" in error for error in errors), errors)
        self.assertTrue(any("task.closure.review_result" in error for error in errors), errors)
        self.assertTrue(any("task.closure.evidence_ref" in error for error in errors), errors)

        task, evidence = verified_records()
        task["status"] = "CLOSED"
        errors = validate_records(task, evidence, None)
        self.assertTrue(any("task.closure.closed_at" in error for error in errors), errors)

    def test_status_reconciliation_uses_top_level_status_and_lifecycle_truth(self):
        task, evidence = valid_task(), valid_evidence()
        task["status"] = "BLOCKED"
        evidence["conclusion"]["status"] = "PENDING"
        task["lifecycle"].update(
            phase="implementation", review_result="BLOCKED", next_action="resolve blocker"
        )
        evidence["phase"] = "review"
        evidence["conclusion"].update(review_result="PENDING", next_action="collect evidence")

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("task.status BLOCKED" in error for error in errors), errors)
        self.assertTrue(any("task.lifecycle.phase" in error for error in errors), errors)
        self.assertTrue(any("task.lifecycle.review_result" in error for error in errors), errors)
        self.assertTrue(any("task.lifecycle.next_action" in error for error in errors), errors)

    def test_run_sets_must_match_after_execution_starts(self):
        task, evidence = valid_task(), valid_evidence()
        task["status"] = "IN_PROGRESS"
        task["runs"] = [
            {
                "id": "run-1",
                "attempt": 1,
                "status": "RUNNING",
                "uses_shared_resource": False,
            }
        ]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("run run-1 is missing from evidence.runs" in error for error in errors), errors)

    def test_active_run_requires_matching_run_even_when_task_is_new(self):
        task, evidence = valid_task(), valid_evidence()
        task["runs"] = [
            {
                "id": "run-active",
                "attempt": 1,
                "status": "RUNNING",
                "uses_shared_resource": False,
            }
        ]

        errors = validate_records(task, evidence, None)

        self.assertTrue(
            any("run run-active is missing from evidence.runs" in error for error in errors),
            errors,
        )

    def test_same_run_id_requires_equal_canonical_statuses(self):
        canonical = ["PENDING", "RUNNING", "PASSED", "FAILED", "BLOCKED", "ABORTED"]
        for task_status in canonical:
            for evidence_status in canonical:
                if task_status == evidence_status:
                    continue
                with self.subTest(task_status=task_status, evidence_status=evidence_status):
                    task, evidence = valid_task(), valid_evidence()
                    task["runs"] = [
                        {
                            "id": "run-1",
                            "attempt": 1,
                            "status": task_status,
                            "uses_shared_resource": False,
                        }
                    ]
                    evidence["runs"] = [
                        {"id": "run-1", "attempt": 1, "status": evidence_status}
                    ]

                    errors = validate_records(task, evidence, None)

                    self.assertTrue(
                        any(
                            "task/evidence run run-1 status mismatch" in error
                            and task_status in error
                            and evidence_status in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_lifecycle_status_is_not_required_or_used(self):
        task, evidence = valid_task(), valid_evidence()
        task["lifecycle"]["status"] = "CLOSED"

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("lifecycle.status" in error for error in errors), errors)

    def test_active_run_cannot_use_released_lease(self):
        task, evidence = valid_task(), valid_evidence()
        task["runs"] = [
            {
                "id": "run-1",
                "attempt": 1,
                "status": "RUNNING",
                "uses_shared_resource": True,
                "lease": {
                    "resource": "test-db",
                    "owner": "worker-1",
                    "mode": "exclusive",
                    "status": "RELEASED",
                    "release_rule": "after tests",
                },
            }
        ]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("active run" in error and "released lease" in error for error in errors), errors)

    def test_gate_ready_rejects_active_runs_and_locks(self):
        task, evidence = verified_records()
        task["runs"] = [
            {"id": "run-1", "attempt": 1, "status": "RUNNING", "uses_shared_resource": False}
        ]
        evidence["runs"] = [{"id": "run-1", "attempt": 1, "status": "RUNNING"}]
        task["resources"]["locks"] = [
            {
                "resource": "test-db",
                "owner": "worker-1",
                "mode": "exclusive",
                "status": "ACTIVE",
                "release_rule": "after tests",
            }
        ]

        errors = validate_records(task, evidence, None, gate_ready=True)

        self.assertTrue(any("gate-ready" in error and "active run" in error for error in errors), errors)
        self.assertTrue(any("gate-ready" in error and "active lock" in error for error in errors), errors)


class ResourceValidationTests(unittest.TestCase):
    def test_active_run_without_shared_resource_does_not_require_lease(self):
        task, evidence = valid_task(), valid_evidence()
        task["runs"] = [
            {"id": "run-1", "attempt": 1, "status": "RUNNING", "uses_shared_resource": False}
        ]

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("lease" in error for error in errors), errors)

    def test_existing_lease_infers_shared_resource_for_compatibility(self):
        task, evidence = valid_task(), valid_evidence()
        task["runs"] = [
            {
                "id": "run-1",
                "attempt": 1,
                "status": "RUNNING",
                "lease": {
                    "resource": "test-db",
                    "owner": "worker-1",
                    "mode": "exclusive",
                    "status": "ACTIVE",
                    "release_rule": "after tests",
                },
            }
        ]

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("lease" in error for error in errors), errors)

    def test_run_statuses_accept_only_canonical_enum_values(self):
        canonical = ["PENDING", "RUNNING", "PASSED", "FAILED", "BLOCKED", "ABORTED"]
        for status in canonical:
            with self.subTest(status=status):
                task, evidence = valid_task(), valid_evidence()
                task["runs"] = [
                    {
                        "id": "run-1",
                        "attempt": 1,
                        "status": status,
                        "uses_shared_resource": False,
                    }
                ]
                errors = validate_records(task, evidence, None)
                self.assertFalse(any("task.runs[0].status" in error for error in errors), errors)

        for alias in ["ACTIVE", "IN_PROGRESS", "PASSED_WITH_WARNINGS", "DONE"]:
            with self.subTest(alias=alias):
                task, evidence = valid_task(), valid_evidence()
                task["runs"] = [
                    {
                        "id": "run-1",
                        "attempt": 1,
                        "status": alias,
                        "uses_shared_resource": False,
                    }
                ]
                errors = validate_records(task, evidence, None)
                self.assertTrue(any("task.runs[0].status" in error for error in errors), errors)


class EvidenceValidationTests(unittest.TestCase):
    @staticmethod
    def required_command(command_id="CMD-unit", source="local"):
        return {
            "id": command_id,
            "command": "python -m unittest tests.test_widget",
            "purpose": "verify widget behavior",
            "source": source,
            "expected_result": "tests pass",
        }

    @staticmethod
    def command_evidence(command_id="CMD-unit", source="local"):
        return {
            "command_id": command_id,
            "command": "python -m unittest tests.test_widget",
            "status": "PASS",
            "source": source,
            "runner": "local-shell",
            "cwd": ".",
            "observed_at": "2026-07-15T10:00:00Z",
            "output_ref": "test-output.txt",
        }

    def test_required_command_needs_exact_command_evidence(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = ["python -m unittest tests.test_widget"]
        evidence["artifacts"]["commands"] = ["python -m unittest tests.test_other"]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("required command has no matching evidence" in error for error in errors), errors)

    def test_required_command_matches_normalized_structured_evidence(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = [
            self.required_command()
        ]
        command = self.command_evidence()
        command["command"] = " python   -m unittest  tests.test_widget "
        evidence["artifacts"]["commands"] = [command]

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("required command" in error for error in errors), errors)

    def test_required_command_rejects_wrong_provenance(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = [self.required_command(source="ci")]
        evidence["artifacts"]["commands"] = [self.command_evidence(source="local")]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("required command has no matching evidence" in error for error in errors), errors)

    def test_required_command_uses_canonical_source_not_provenance_alias(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = [self.required_command(source="local")]
        command = self.command_evidence(source="ci")
        command["provenance"] = "local"
        evidence["artifacts"]["commands"] = [command]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("required command has no matching evidence" in error for error in errors), errors)

    def test_failed_command_evidence_does_not_satisfy_requirement(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = [self.required_command()]
        command = self.command_evidence()
        command["status"] = "FAIL"
        evidence["artifacts"]["commands"] = [command]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("CMD-unit" in error and "pass-like" in error for error in errors), errors)

    def test_required_command_rejects_matching_command_with_different_id(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = [self.required_command("CMD-required")]
        evidence["artifacts"]["commands"] = [self.command_evidence("CMD-other")]

        errors = validate_records(task, evidence, None)

        self.assertTrue(any("CMD-required" in error and "no matching evidence" in error for error in errors), errors)

    def test_required_command_matches_id_command_and_provenance(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = [self.required_command()]
        command = self.command_evidence()
        command["command"] = " python   -m unittest  tests.test_widget "
        evidence["artifacts"]["commands"] = [command]

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("required command" in error for error in errors), errors)

    def test_skipped_required_command_is_classified_instead_of_missing(self):
        task, evidence = verified_records()
        task["verification"]["required_commands"] = [self.required_command()]
        evidence["skipped_checks"] = [
            {
                "id": "CMD-unit",
                "check": "python -m unittest tests.test_widget",
                "reason": "runtime unavailable",
                "owner": "worker-1",
                "follow_up": "run when runtime returns",
                "blocking": True,
            }
        ]

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("no matching evidence" in error for error in errors), errors)
        self.assertTrue(any("CMD-unit" in error and "skipped" in error and "blocking" in error for error in errors), errors)

        evidence["skipped_checks"][0].update(
            blocking=False,
            status="WAIVED",
            waived_by="project-owner",
            waiver_scope="unit command only",
        )
        errors = validate_records(task, evidence, None)
        self.assertFalse(any("required command" in error for error in errors), errors)

    def test_mock_use_always_requires_complete_fallback_metadata(self):
        task, evidence = verified_records()
        task["verification"]["mock_allowed"] = True
        evidence["conclusion"].update(mock_used=True, accepted_fallback=False, next_action="")

        errors = validate_records(task, evidence, None)

        for field in ["rationale", "scope", "follow-up", "accepted-by"]:
            self.assertTrue(any("mock_used" in error and field in error for error in errors), (field, errors))

        evidence["conclusion"].update(
            accepted_fallback_reason="runtime unavailable",
            accepted_fallback_scope="unit verification only",
            accepted_fallback_by="project-owner",
            next_action="run live smoke when runtime returns",
        )
        errors = validate_records(task, evidence, None)
        self.assertFalse(any("mock_used requires" in error for error in errors), errors)

    def test_mock_acceptance_actor_is_recognized(self):
        task, evidence = verified_records()
        task["verification"]["mock_allowed"] = True
        evidence["conclusion"].update(
            mock_used=True,
            mock_rationale="runtime unavailable",
            mock_scope="unit verification only",
            mock_follow_up="run live smoke later",
            mock_acceptance_actor="project-owner",
            mock_acceptance_ref="DECISION-1",
        )

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("accepted-by/authority metadata" in error for error in errors), errors)

    def test_path_like_changed_surfaces_require_matching_artifacts(self):
        cases = [
            ("src/api/users.py", "artifacts.api"),
            ("db/migrations/001.sql", "artifacts.sql"),
            ("frontend/components/App.tsx", "artifacts.browser"),
            ("deploy/release.yaml", "artifacts.release"),
        ]
        for surface, expected in cases:
            with self.subTest(surface=surface):
                task, evidence = verified_records()
                evidence["changed_surface"] = [surface]
                errors = validate_records(task, evidence, None)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_documentation_path_does_not_imply_heavy_surface_evidence(self):
        task, evidence = verified_records()
        evidence["changed_surface"] = ["docs/api-notes.md"]

        errors = validate_records(task, evidence, None)

        self.assertFalse(any("verified evidence for surface" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
