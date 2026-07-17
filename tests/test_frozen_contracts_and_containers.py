import hashlib
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from sagekit.check import check_task_dispatch, discover_task_dispatch_records
from sagekit.compatibility import select_validation_contract, validate_compatible_records
from sagekit.milestone_scope import (
    MilestoneScope,
    MilestoneScopeKind,
    RepositoryScopeResolver,
)
from sagekit.task_dispatch_validator import load_record
from sagekit.validation_contracts import contract_resource
from sagekit.validation_contracts import v0 as v0_contract
from sagekit.validation_contracts.v0 import (
    contract_metadata as v0_metadata,
    validate_records as validate_v0,
)
from sagekit.validation_contracts.v1 import (
    FROZEN_VALIDATOR_REGISTRY_SHA256,
    contract_metadata as v1_metadata,
    validate_records as validate_v1,
)
from sagekit.validation_contracts.v2 import validate_records as validate_v2
from sagekit.validation_scope_manifest import load_validation_scope_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "docs/profiles/task-dispatch/templates"
BASELINE_HEAD = "0123456789abcdef0123456789abcdef01234567"
V0_SOURCE_COMMIT = "e6fe28061d600bfb7164c5cf40448f2d2f5d620c"
V0_POLICY_SHA256 = "443c99d1eecd13adef9e2960e1ca56e3f9267b1eac026ad19dd790c1111aa5cb"
V1_VALIDATOR_REGISTRY_SHA256 = (
    "287760d3ccf9f3f752ee42377753ca0195d54fd32e18b957c3ca2e41a6985ca7"
)
V0_VALIDATOR_REGISTRY_SHA256 = (
    "8186472ccaf641eb4f45d87f9637a69e153506f0c0e6b6fb7b25d325b38e7821"
)
V0_SOURCE_SCHEMA_SHA256 = {
    "task.schema.json": "7fe569c103e1cfbd81ed1304f130603c4223bd405dda398d6bff453538071ae5",
    "evidence.schema.json": "1c1d7fe983f830b5dd2be7d9eadf4ccd184fc4c4f762dc3dd7eb75852003f9f3",
}
V0_PACKAGED_SCHEMA_SHA256 = {
    "task.schema.json": "6d213c9a06617aec61e83e24615865333a62e01f7d5159e6072e0fe9f9cb54ca",
    "evidence.schema.json": "207e44ec2bad0ed14e9f37135ff103be58a0b5c5e6c6736dbcfee1c39f503ee1",
}
V0_SEMANTIC_SCHEMA_SHA256 = {
    "task.schema.json": "d692c739bad4c49e301cdf97a10c9f358978ec34492af21939f345a8c2b47a4d",
    "evidence.schema.json": "71470bdd4295f5134936da17480c24b6a9daeadf78698af29222304eb52445f0",
}


def canonical_digest(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def semantic_schema_digest(payload):
    semantic = dict(payload)
    semantic.pop("$id", None)
    semantic.pop("title", None)
    return canonical_digest(semantic)


def early_records(*, task_status="VERIFIED", evidence_status="VERIFIED"):
    task = {
        "id": "TASK-EARLY",
        "type": "chore",
        "title": "Anonymous early record",
        "priority": "P2",
        "status": task_status,
        "scope": {
            "objective": "Preserve historical evidence.",
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
        },
        "dependencies": {"requires": [], "blocks": []},
        "resources": {"locks": []},
        "runs": [],
        "closure": {},
    }
    evidence = {
        "task_id": "TASK-EARLY",
        "changed_surface": [],
        "runtime_shape": "historical",
        "levels": {
            "L0": {
                "status": "PASS",
                "evidence": ["accepted historical evidence"],
                "commands": [],
                "reason": None,
                "waived_by": None,
                "waiver_scope": None,
            },
            **{
                level: {
                    "status": "N/A",
                    "evidence": [],
                    "commands": [],
                    "reason": "not required by the task",
                    "waived_by": None,
                    "waiver_scope": None,
                }
                for level in ("L1", "L2", "L3", "L4")
            },
        },
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
        "blockers": [],
        "conclusion": {
            "status": evidence_status,
            "highest_level": "L0",
            "mock_used": False,
            "accepted_fallback": False,
            "next_action": "none",
        },
    }
    return task, evidence


def hardened_records():
    task = load_record(TEMPLATE_ROOT / "TASK_RECORD_TEMPLATE.yaml")
    evidence = load_record(TEMPLATE_ROOT / "EVIDENCE_RECORD_TEMPLATE.yaml")
    task.pop("validation_contract")
    evidence.pop("validation_contract")
    task["id"] = "TASK-HARDENED"
    evidence["task_id"] = task["id"]
    task["status"] = "CLOSED"
    task["lifecycle"].update(
        {
            "phase": "closed",
            "review_result": "ACCEPTABLE",
            "next_action": "No further action required.",
        }
    )
    task["closure"].update(
        {
            "accepted_by": "reviewer",
            "accepted_at": "2025-01-01T00:00:00Z",
            "closed_at": "2025-01-01T00:00:00Z",
            "review_result": "ACCEPTABLE",
            "evidence_ref": "evidence.yaml",
        }
    )
    evidence["phase"] = "closed"
    evidence["levels"]["L0"].update(
        {"status": "PASS", "evidence": ["accepted"], "reason": None}
    )
    evidence["conclusion"].update(
        {
            "status": "VERIFIED",
            "highest_level": "L0",
            "review_result": "ACCEPTABLE",
            "next_action": "No further action required.",
        }
    )
    return task, evidence


def history_scope(version, *, container_id="C1", path="docs/C1"):
    return MilestoneScope(
        container_id,
        MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
        (f"validation scope manifest accepted {path} with frozen v{version}",),
        "explicit accepted legacy container authority",
        contract_version=version,
        container_path=path,
    )


def manifest_payload(*, active=(), legacy=()):
    return {
        "schema_version": 1,
        "active_containers": [
            {"id": container_id, "path": path}
            for container_id, path in active
        ],
        "accepted_legacy_containers": [
            {
                "id": container_id,
                "path": path,
                "contract_version": version,
                "supersedes": list(supersedes),
            }
            for container_id, path, version, supersedes in legacy
        ],
        "authority": {
            "source": "project-owner migration acceptance",
            "approved_by": "project-owner",
            "approved_at": "2026-01-01T00:00:00Z",
            "baseline_head": BASELINE_HEAD,
        },
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_pair(root, container, name, task, evidence):
    record = root / container / "dispatch" / name
    record.mkdir(parents=True, exist_ok=True)
    write_json(record / "task.yaml", task)
    write_json(record / "evidence.yaml", evidence)
    board = root / container / "dispatch" / "DISPATCH_BOARD.md"
    board.write_text("## Active Tasks\n\n| Task |\n|---|\n", encoding="utf-8")
    return record


@contextmanager
def replace_contract_resource(version, name, replacement):
    original = contract_resource

    def resolve(requested_version, requested_name):
        if requested_version == version and requested_name == name:
            return replacement
        return original(requested_version, requested_name)

    with patch("sagekit.validation_contracts.contract_resource", side_effect=resolve), patch(
        "sagekit.validation_contracts.frozen_validator.contract_resource",
        side_effect=resolve,
    ):
        yield


class FrozenV0ProvenanceTests(unittest.TestCase):
    def test_frozen_sidecar_and_rules_corruption_is_a_validation_failure(self):
        for version, validate in ((0, validate_v0), (1, validate_v1)):
            task, evidence = early_records() if version == 0 else hardened_records()
            cases = (
                ("policy.json", None, "frozen artifact missing"),
                ("policy.json", "{not-json", "frozen artifact is not valid JSON"),
                ("validator.json", None, "frozen artifact missing"),
                ("rules.json", "{not-json", "frozen artifact is not valid JSON"),
                ("validator.json", "[]", "frozen artifact must contain a JSON object"),
            )
            for name, content, expected in cases:
                with self.subTest(version=version, name=name, content=content):
                    with tempfile.TemporaryDirectory() as temp_dir:
                        replacement = Path(temp_dir) / name
                        if content is not None:
                            replacement.write_text(content, encoding="utf-8")
                        with replace_contract_resource(version, name, replacement):
                            errors = validate(task, evidence)

                    self.assertTrue(any(expected in error for error in errors), errors)

    def test_frozen_policy_corruption_fails_selection_without_internal_error(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "policy.json"
            with replace_contract_resource(0, "policy.json", missing):
                result = validate_compatible_records(
                    task,
                    evidence,
                    container_scope=history_scope(0),
                )

        self.assertIsNone(result.selection)
        self.assertTrue(any("policy artifact" in error for error in result.errors))

    def test_v0_missing_schema_artifact_is_a_validation_failure(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing-task.schema.json"
            with replace_contract_resource(0, "task.schema.json", missing):
                errors = validate_v0(task, evidence)

        self.assertTrue(any("schema file missing" in error for error in errors), errors)

    def test_v0_invalid_json_schema_artifact_is_a_validation_failure(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid = Path(temp_dir) / "task.schema.json"
            invalid.write_text("{not-json", encoding="utf-8")
            with replace_contract_resource(0, "task.schema.json", invalid):
                errors = validate_v0(task, evidence)

        self.assertTrue(any("not valid JSON" in error for error in errors), errors)

    def test_v0_schema_artifact_digest_mismatch_is_a_validation_failure(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as temp_dir:
            changed = Path(temp_dir) / "task.schema.json"
            payload = json.loads(
                contract_resource(0, "task.schema.json").read_text(encoding="utf-8")
            )
            payload["description"] = "digest mismatch fixture"
            changed.write_text(json.dumps(payload), encoding="utf-8")
            with replace_contract_resource(0, "task.schema.json", changed):
                errors = validate_v0(task, evidence)

        self.assertTrue(any("digest" in error for error in errors), errors)

    def test_v0_resources_bind_source_and_normalized_packaged_digests(self):
        policy = json.loads(contract_resource(0, "policy.json").read_text(encoding="utf-8"))

        self.assertEqual(V0_POLICY_SHA256, canonical_digest(policy))
        self.assertEqual(V0_SOURCE_COMMIT, policy["frozen_from_base_sha"])
        self.assertEqual(V0_SOURCE_SCHEMA_SHA256, policy["source_schema_sha256"])
        self.assertEqual(V0_PACKAGED_SCHEMA_SHA256, policy["schema_sha256"])
        self.assertEqual(
            "metadata-only $id/title replacement",
            policy["normalization"]["kind"],
        )
        for name in ("task.schema.json", "evidence.schema.json"):
            packaged = json.loads(contract_resource(0, name).read_text(encoding="utf-8"))
            self.assertEqual(V0_PACKAGED_SCHEMA_SHA256[name], canonical_digest(packaged))
            self.assertEqual(V0_SEMANTIC_SCHEMA_SHA256[name], semantic_schema_digest(packaged))
            self.assertTrue(packaged["$id"].startswith("https://example.invalid/sage-kit/"))
            self.assertTrue(packaged["title"].startswith("SAGE-Kit "))

    def test_frozen_contract_sidecars_bind_rules_engine_and_runtime_schema_behavior(self):
        for version in (0, 1):
            policy = json.loads(
                contract_resource(version, "policy.json").read_text(encoding="utf-8")
            )
            rules = json.loads(
                contract_resource(version, "rules.json").read_text(encoding="utf-8")
            )
            binding = json.loads(
                contract_resource(version, "validator.json").read_text(
                    encoding="utf-8"
                )
            )
            if version == 0:
                self.assertEqual(
                    V0_VALIDATOR_REGISTRY_SHA256,
                    canonical_digest(binding),
                )
                self.assertEqual(
                    V0_VALIDATOR_REGISTRY_SHA256,
                    getattr(v0_contract, "FROZEN_VALIDATOR_REGISTRY_SHA256", None),
                )
                self.assertFalse(binding["record_schema_enforced"])
                self.assertEqual(
                    ["presence", "valid_json", "canonical_digest"],
                    binding["schema_artifacts_checked"],
                )
                self.assertEqual(
                    "frozen_python_semantics",
                    binding["record_validation"],
                )
            else:
                self.assertEqual(
                    V1_VALIDATOR_REGISTRY_SHA256,
                    canonical_digest(binding),
                )
                self.assertEqual(
                    V1_VALIDATOR_REGISTRY_SHA256,
                    FROZEN_VALIDATOR_REGISTRY_SHA256,
                )
                self.assertTrue(binding["record_schema_enforced"])
                self.assertEqual(
                    "frozen_schema_and_python_semantics",
                    binding["record_validation"],
                )
            self.assertEqual(canonical_digest(policy), binding["policy_sha256"])
            self.assertEqual(canonical_digest(rules), binding["validator_rules_sha256"])
            self.assertRegex(binding["validator_engine_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(binding["source_validator_sha256"], r"^[0-9a-f]{64}$")

    def test_v0_required_enums_and_absent_conditionals_match_early_boundary(self):
        task_schema = json.loads(
            contract_resource(0, "task.schema.json").read_text(encoding="utf-8")
        )
        evidence_schema = json.loads(
            contract_resource(0, "evidence.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [
                "id",
                "type",
                "title",
                "priority",
                "status",
                "scope",
                "verification",
                "dependencies",
                "resources",
                "runs",
                "closure",
            ],
            task_schema["required"],
        )
        self.assertEqual(
            [
                "task_id",
                "changed_surface",
                "runtime_shape",
                "levels",
                "artifacts",
                "runs",
                "blockers",
                "conclusion",
            ],
            evidence_schema["required"],
        )
        self.assertEqual(
            [
                "NEW",
                "TRIAGED",
                "READY",
                "IN_PROGRESS",
                "READY_FOR_REVIEW",
                "VERIFIED",
                "PARTIAL",
                "BLOCKED",
                "CLOSED",
            ],
            task_schema["properties"]["status"]["enum"],
        )
        serialized = json.dumps([task_schema, evidence_schema])
        for keyword in ('"if"', '"then"', '"else"'):
            self.assertNotIn(keyword, serialized)

    def test_frozen_validators_do_not_call_current_validator(self):
        early_task, early_evidence = early_records()
        hardened_task, hardened_evidence = hardened_records()

        with patch(
            "sagekit.task_dispatch_validator.validate_records",
            side_effect=AssertionError("mutable current validator called"),
        ):
            self.assertEqual([], validate_v0(early_task, early_evidence))
            self.assertEqual([], validate_v1(hardened_task, hardened_evidence))

    def test_v2_remains_bound_to_current_validator(self):
        task, evidence = hardened_records()
        metadata = {
            "version": 2,
            "policy_id": "sagekit-task-dispatch-v2",
            "policy_sha256": "placeholder",
            "scope": "active",
        }
        task["validation_contract"] = dict(metadata)
        evidence["validation_contract"] = dict(metadata)

        with patch(
            "sagekit.task_dispatch_validator.validate_records",
            side_effect=RuntimeError("current sentinel"),
        ):
            with self.assertRaisesRegex(RuntimeError, "current sentinel"):
                validate_v2(task, evidence)


class FrozenHistoricalShapeTests(unittest.TestCase):
    def test_v0_scope_objective_remains_a_python_required_field(self):
        task, evidence = early_records()
        task["scope"].pop("objective")

        errors = validate_v0(task, evidence)

        self.assertIn("task.scope.objective is required", errors)

    def test_historical_nonempty_predicate_rejects_sentinel_strings(self):
        task, evidence = hardened_records()
        task["lifecycle"]["next_action"] = "none"
        evidence["conclusion"]["next_action"] = "none"

        errors = validate_v1(task, evidence)

        self.assertIn("task.lifecycle.next_action must be a non-empty string", errors)
        self.assertIn("evidence.conclusion.next_action must be a non-empty string", errors)

    def test_v0_oracle_allows_case_normalized_enums_and_schema_only_item_mismatch(self):
        cases = (
            ("uppercase task type", "SPEC", []),
            ("mixed-case task type", "Spec", []),
            ("schema-only changed-surface item", "chore", [{"kind": "documentation"}]),
        )
        for label, task_type, changed_surface in cases:
            with self.subTest(label=label):
                task, evidence = early_records()
                task["type"] = task_type
                evidence["changed_surface"] = changed_surface

                self.assertEqual([], validate_v0(task, evidence))

    def test_v0_oracle_rejects_invalid_enum_and_missing_python_required_run_attempt(self):
        task, evidence = early_records()
        task["type"] = "unknown"
        task["runs"] = [{"id": "RUN-1", "status": "PASSED"}]
        evidence["runs"] = [{"id": "RUN-1", "status": "PASSED"}]

        errors = validate_v0(task, evidence)

        self.assertTrue(any("task.type" in error for error in errors), errors)
        self.assertTrue(any("task.runs[0].attempt" in error for error in errors), errors)
        self.assertTrue(any("evidence.runs[0].attempt" in error for error in errors), errors)

    def test_v0_oracle_preserves_historical_nonempty_numeric_attempt_behavior(self):
        task, evidence = early_records()
        task["runs"] = [{"id": "RUN-1", "attempt": 0, "status": "PASSED"}]
        evidence["runs"] = [{"id": "RUN-1", "attempt": 0, "status": "PASSED"}]

        self.assertEqual([], validate_v0(task, evidence))

    def test_v0_python_required_fields_remain_strict_without_record_schema_enforcement(self):
        task, evidence = early_records()
        task.pop("title")

        errors = validate_v0(task, evidence)

        self.assertIn("task.title is required", errors)

    def test_v0_oracle_preserves_gate_level_blocker_and_shape_rules(self):
        task, evidence = early_records()
        self.assertEqual([], validate_v0(task, evidence, gate_ready=True))

        task, evidence = early_records()
        task["verification"]["required_levels"] = ["L9"]
        evidence["blockers"] = ["unresolved"]
        task["runs"] = "not-a-list"

        errors = validate_v0(task, evidence, gate_ready=True)

        self.assertIn("invalid required evidence level: L9", errors)
        self.assertIn("task.runs must be a list", errors)
        self.assertIn("verified evidence cannot retain blockers", errors)
        self.assertIn("gate-ready validation requires evidence.blockers to be empty", errors)

    def test_v1_oracle_retains_historical_record_schema_enforcement(self):
        task, evidence = hardened_records()
        task["type"] = "Spec"

        errors = validate_v1(task, evidence)

        self.assertTrue(any("schema enum" in error for error in errors), errors)

    def test_early_shape_passes_v0_and_fails_hardened_v1(self):
        task, evidence = early_records()

        self.assertEqual([], validate_v0(task, evidence))
        v1_errors = validate_v1(task, evidence)

        self.assertTrue(any("authority" in error for error in v1_errors), v1_errors)
        self.assertTrue(any("phase" in error for error in v1_errors), v1_errors)

    def test_hardened_shape_passes_v1(self):
        task, evidence = hardened_records()

        self.assertEqual([], validate_v1(task, evidence))

    def test_malformed_early_record_and_false_green_are_rejected(self):
        task, evidence = early_records()
        evidence["task_id"] = "TASK-WRONG"
        evidence["blockers"] = ["unresolved"]

        errors = validate_v0(task, evidence)

        self.assertTrue(any("does not match" in error for error in errors), errors)
        self.assertTrue(any("blocker" in error for error in errors), errors)

    def test_v0_gate_ready_requires_terminal_pair_passlike_levels_and_no_blockers(self):
        task, evidence = early_records(task_status="IN_PROGRESS", evidence_status="PENDING")
        evidence["levels"]["L0"]["status"] = "FAIL"
        evidence["blockers"] = ["blocked"]

        errors = validate_v0(task, evidence, gate_ready=True)

        self.assertTrue(any("task.status" in error for error in errors), errors)
        self.assertTrue(any("conclusion.status" in error for error in errors), errors)
        self.assertTrue(any("blockers" in error for error in errors), errors)
        self.assertTrue(any("L0" in error for error in errors), errors)


class FrozenContractSelectionTests(unittest.TestCase):
    def test_manifest_scope_selects_exact_v0_or_v1_before_validation(self):
        early_task, early_evidence = early_records()
        hardened_task, hardened_evidence = hardened_records()

        early = validate_compatible_records(
            early_task,
            early_evidence,
            container_scope=history_scope(0),
        )
        hardened = validate_compatible_records(
            hardened_task,
            hardened_evidence,
            container_scope=history_scope(1),
        )

        self.assertEqual(0, early.selection.version)
        self.assertEqual(1, hardened.selection.version)
        self.assertEqual((), early.errors)
        self.assertEqual((), hardened.errors)

    def test_v1_failure_never_attempts_v0(self):
        task, evidence = early_records()
        with patch(
            "sagekit.validation_contracts.v0.validate_records",
            side_effect=AssertionError("v0 fallback attempted"),
        ):
            result = validate_compatible_records(
                task,
                evidence,
                container_scope=history_scope(1),
            )

        self.assertEqual(1, result.selection.version)
        self.assertTrue(result.errors)

    def test_v0_failure_never_attempts_other_versions(self):
        task, evidence = early_records()
        evidence["task_id"] = "TASK-WRONG"
        with patch(
            "sagekit.validation_contracts.v1.validate_records",
            side_effect=AssertionError("v1 fallback attempted"),
        ), patch(
            "sagekit.validation_contracts.v2.validate_records",
            side_effect=AssertionError("v2 fallback attempted"),
        ):
            result = validate_compatible_records(
                task,
                evidence,
                container_scope=history_scope(0),
            )

        self.assertEqual(0, result.selection.version)
        self.assertTrue(result.errors)

    def test_explicit_v2_overrides_manifest_v0_and_does_not_fallback(self):
        task, evidence = hardened_records()
        from sagekit.validation_contracts.v2 import contract_metadata

        task["validation_contract"] = contract_metadata()
        evidence["validation_contract"] = contract_metadata()
        evidence["task_id"] = "TASK-WRONG"

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=history_scope(0),
        )

        self.assertEqual(2, result.selection.version)
        self.assertTrue(result.errors)

    def test_nonterminal_pair_cannot_use_manifest_v0_or_v1(self):
        for version in (0, 1):
            with self.subTest(version=version):
                task, evidence = early_records(
                    task_status="IN_PROGRESS",
                    evidence_status="PENDING",
                )
                result = validate_compatible_records(
                    task,
                    evidence,
                    container_scope=history_scope(version),
                )
                self.assertIsNone(result.selection)
                self.assertTrue(result.active_reconciliation)


class GenericContainerDiscoveryTests(unittest.TestCase):
    def test_discovers_milestone_generic_and_nested_containers(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = {
                "docs/M1",
                "docs/architecture/GATE_1",
                "docs/nested/group/container",
            }
            for index, container in enumerate(sorted(expected)):
                write_pair(root, container, f"TASK-{index}", task, evidence)

            discovery = discover_task_dispatch_records(root)

        self.assertFalse(discovery.findings, discovery.findings)
        self.assertEqual(expected, {record.container_path for record in discovery.records})

    def test_excludes_templates_profiles_and_template_directories(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_pair(root, "docs/templates/example", "TASK-1", task, evidence)
            write_pair(root, "docs/profiles/example", "TASK-2", task, evidence)
            write_pair(root, "docs/live/_TEMPLATE", "TASK-3", task, evidence)
            write_pair(root, "docs/live/container", "TASK-4", task, evidence)

            discovery = discover_task_dispatch_records(root)

        self.assertEqual(
            {"docs/live/container"},
            {record.container_path for record in discovery.records},
        )

    def test_nested_dispatch_is_a_blocking_discovery_finding(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "docs/C1/dispatch/archive/dispatch/TASK-1"
            record.mkdir(parents=True)
            write_json(record / "task.yaml", task)
            write_json(record / "evidence.yaml", evidence)

            discovery = discover_task_dispatch_records(root)

        self.assertFalse(discovery.records)
        self.assertTrue(
            any("nested dispatch" in finding.message for finding in discovery.findings),
            discovery.findings,
        )

    def test_missing_pair_is_reported_for_generic_container(self):
        task, _ = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "docs/group/C1/dispatch/TASK-1"
            record.mkdir(parents=True)
            write_json(record / "task.yaml", task)

            discovery = discover_task_dispatch_records(root)

        self.assertTrue(
            any("evidence.yaml is missing" in finding.message for finding in discovery.findings),
            discovery.findings,
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support unavailable")
    def test_target_external_symlink_is_rejected_or_safely_skipped(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "target"
            outside = workspace / "outside"
            outside_record = outside / "dispatch/TASK-1"
            outside_record.mkdir(parents=True)
            write_json(outside_record / "task.yaml", task)
            write_json(outside_record / "evidence.yaml", evidence)
            docs = root / "docs"
            docs.mkdir(parents=True)
            try:
                (docs / "linked").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            discovery = discover_task_dispatch_records(root)

        self.assertFalse(discovery.records)
        self.assertTrue(
            not discovery.findings
            or any("target root" in finding.message for finding in discovery.findings),
            discovery.findings,
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support unavailable")
    def test_cross_record_file_symlink_is_rejected(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = write_pair(root, "docs/C1", "one", task, evidence)
            second = write_pair(root, "docs/C1", "two", task, evidence)
            (first / "task.yaml").unlink()
            try:
                (first / "task.yaml").symlink_to(second / "task.yaml")
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            discovery = discover_task_dispatch_records(root)

        self.assertEqual(
            {second},
            {record.directory for record in discovery.records},
        )
        self.assertTrue(
            any("record directory" in finding.message for finding in discovery.findings),
            discovery.findings,
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support unavailable")
    def test_closeout_symlink_cannot_authorize_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            container = root / "docs/C1"
            outside = root / "outside"
            container.mkdir(parents=True)
            outside.mkdir()
            authority = outside / "MILESTONE_CLOSEOUT.md"
            authority.write_text("- Status: `ACCEPTED`\n", encoding="utf-8")
            try:
                (container / "MILESTONE_CLOSEOUT.md").symlink_to(authority)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            scope = RepositoryScopeResolver(root).resolve(container)

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("symlink", scope.detail)


class GenericContainerManifestTests(unittest.TestCase):
    def test_supersedes_may_be_omitted_when_no_closeout_is_overridden(self):
        payload = manifest_payload(legacy=(("C1", "docs/C1", 0, ()),))
        payload["accepted_legacy_containers"][0].pop("supersedes")
        with tempfile.TemporaryDirectory() as directory:
            manifest = load_validation_scope_manifest(
                write_json(Path(directory) / "scope.json", payload)
            )

        self.assertEqual((), manifest.accepted_legacy_containers[0].supersedes)

    def test_manifest_requires_contract_version_and_safe_unique_paths(self):
        invalid_payloads = [
            {
                **manifest_payload(),
                "accepted_legacy_containers": [
                    {"id": "C1", "path": "docs/C1", "supersedes": []}
                ],
            },
            manifest_payload(legacy=(("C1", "../outside", 0, ()),)),
            manifest_payload(legacy=(("C1", "C:/outside", 0, ()),)),
            manifest_payload(legacy=(("C1", "docs/*", 0, ()),)),
            manifest_payload(legacy=(("C1", "docs/M0-M99", 0, ()),)),
            manifest_payload(
                legacy=(
                    ("C1", "docs/C1", 0, ()),
                    ("C2", "docs/C1", 0, ()),
                )
            ),
            manifest_payload(
                active=(("C1", "docs/C1"),),
                legacy=(("C1", "docs/C2", 0, ()),),
            ),
            manifest_payload(legacy=(("C1", "docs/C1", 9, ()),)),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                path = write_json(Path(directory) / "scope.json", payload)
                with self.assertRaises(ValueError):
                    load_validation_scope_manifest(path)

    def test_manifest_selected_generic_history_is_excluded_from_active_reconciliation(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_pair(root, "docs/group/C1", "one", task, evidence)
            write_pair(root, "docs/group/C1", "two", task, evidence)
            manifest_path = write_json(
                root / "scope.json",
                manifest_payload(
                    legacy=(("C1", "docs/group/C1", 0, ()),)
                ),
            )
            manifest = load_validation_scope_manifest(manifest_path)

            findings = check_task_dispatch(root, scope_manifest=manifest)

        rules = {finding.rule for finding in findings}
        self.assertNotIn("task-dispatch-duplicate-id", rules)
        self.assertNotIn("task-dispatch-board", rules)

    def test_current_generic_container_remains_in_duplicate_and_lock_checks(self):
        task, evidence = early_records()
        task["resources"]["locks"] = [
            {
                "resource": "src/shared",
                "owner": "worker",
                "mode": "EXCLUSIVE",
                "status": "ACTIVE",
                "carried": False,
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_pair(root, "docs/group/C1", "one", task, evidence)
            write_pair(root, "docs/group/C1", "two", task, evidence)
            manifest = load_validation_scope_manifest(
                write_json(
                    root / "scope.json",
                    manifest_payload(active=(("C1", "docs/group/C1"),)),
                )
            )

            findings = check_task_dispatch(root, scope_manifest=manifest)

        rules = {finding.rule for finding in findings}
        self.assertIn("task-dispatch-duplicate-id", rules)
        self.assertIn("task-dispatch-lock-conflict", rules)

    def test_historical_and_current_same_id_only_reconcile_current_side(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_pair(root, "docs/group/HISTORY", "one", task, evidence)
            write_pair(root, "docs/group/CURRENT", "two", task, evidence)
            manifest = load_validation_scope_manifest(
                write_json(
                    root / "scope.json",
                    manifest_payload(
                        active=(("CURRENT", "docs/group/CURRENT"),),
                        legacy=(("HISTORY", "docs/group/HISTORY", 0, ()),),
                    ),
                )
            )

            findings = check_task_dispatch(root, scope_manifest=manifest)

        self.assertFalse(
            [
                finding
                for finding in findings
                if finding.rule == "task-dispatch-duplicate-id"
            ],
            findings,
        )
        board_failures = [
            finding
            for finding in findings
            if finding.rule == "task-dispatch-board"
            and finding.level == "FAIL"
        ]
        self.assertTrue(board_failures, findings)
        self.assertTrue(
            all("docs/group/CURRENT" in (finding.path or "") for finding in board_failures),
            board_failures,
        )

    def test_contract_finding_names_container_selected_version_and_policy_digest(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_pair(root, "docs/group/C1", "one", task, evidence)
            manifest = load_validation_scope_manifest(
                write_json(
                    root / "scope.json",
                    manifest_payload(
                        legacy=(("C1", "docs/group/C1", 0, ()),)
                    ),
                )
            )

            findings = check_task_dispatch(root, scope_manifest=manifest)

        message = next(
            finding.message
            for finding in findings
            if finding.rule == "validation-contract"
        )
        self.assertIn("selected v0", message)
        self.assertIn("docs/group/C1", message)
        self.assertIn("policy_digest=sha256:", message)

    def test_direct_mixed_case_dispatch_pair_still_receives_board_reconciliation(self):
        task, evidence = early_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dispatch = root / "docs/C1/Dispatch"
            dispatch.mkdir(parents=True)
            write_json(dispatch / "task.yaml", task)
            write_json(dispatch / "evidence.yaml", evidence)
            (dispatch / "DISPATCH_BOARD.md").write_text(
                "## Active Tasks\n\n| Task |\n|---|\n",
                encoding="utf-8",
            )
            manifest = load_validation_scope_manifest(
                write_json(
                    root / "scope.json",
                    manifest_payload(active=(("C1", "docs/C1"),)),
                )
            )

            findings = check_task_dispatch(root, scope_manifest=manifest)

        self.assertTrue(
            any(finding.rule == "task-dispatch-board" for finding in findings),
            findings,
        )


if __name__ == "__main__":
    unittest.main()
