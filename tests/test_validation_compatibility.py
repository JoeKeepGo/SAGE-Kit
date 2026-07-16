import json
import hashlib
import ast
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from sagekit.check import SOURCE_REQUIRED_FILES, check_task_dispatch
from sagekit.cli import build_parser, emit_findings
from sagekit.compatibility import (
    ContractScope,
    select_validation_contract,
    validate_compatible_records,
)
from sagekit.findings import Finding
from sagekit.reporting import build_finding_report, finding_report_payload
from sagekit.task_dispatch_validator import load_record
from sagekit.validation_contracts import contract_resource
from sagekit.validation_contracts.v1 import contract_metadata as v1_metadata
from sagekit.validation_contracts.v2 import contract_metadata as v2_metadata


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "docs/profiles/task-dispatch/templates"


def active_records():
    task = load_record(TEMPLATE_ROOT / "TASK_RECORD_TEMPLATE.yaml")
    evidence = load_record(TEMPLATE_ROOT / "EVIDENCE_RECORD_TEMPLATE.yaml")
    task["id"] = "TASK-ACTIVE"
    evidence["task_id"] = "TASK-ACTIVE"
    return task, evidence


def closed_legacy_records():
    task, evidence = active_records()
    task.pop("validation_contract")
    evidence.pop("validation_contract")
    task["id"] = "TASK-LEGACY"
    evidence["task_id"] = "TASK-LEGACY"
    task["status"] = "CLOSED"
    task["lifecycle"].update(
        {
            "phase": "closed",
            "review_result": "ACCEPTABLE",
            "next_action": "none; history is closed",
        }
    )
    task["closure"].update(
        {
            "accepted_by": "historical-reviewer",
            "accepted_at": "2025-01-01T00:00:00Z",
            "closed_at": "2025-01-01T00:00:00Z",
            "review_result": "ACCEPTABLE",
            "evidence_ref": "evidence.yaml",
        }
    )
    evidence["phase"] = "closed"
    evidence["levels"]["L0"].update(
        {
            "status": "PASS",
            "evidence": ["historical acceptance"],
            "reason": None,
        }
    )
    evidence["conclusion"].update(
        {
            "status": "VERIFIED",
            "highest_level": "L0",
            "review_result": "ACCEPTABLE",
            "next_action": "none; history is closed",
        }
    )
    return task, evidence


class ContractSelectionTests(unittest.TestCase):
    def test_closed_unversioned_history_uses_frozen_v1(self):
        task, evidence = closed_legacy_records()

        selection = select_validation_contract(task, evidence)

        self.assertEqual(1, selection.version)
        self.assertEqual(ContractScope.CLOSED_LEGACY, selection.scope)
        self.assertTrue(selection.implicit_legacy)

    def test_active_records_use_current_v2(self):
        task, evidence = active_records()

        selection = select_validation_contract(task, evidence)

        self.assertEqual(2, selection.version)
        self.assertEqual(ContractScope.ACTIVE, selection.scope)
        self.assertFalse(selection.implicit_legacy)

    def test_active_unversioned_records_fail_closed(self):
        task, evidence = active_records()
        task.pop("validation_contract")
        evidence.pop("validation_contract")

        result = validate_compatible_records(task, evidence)

        self.assertIsNone(result.selection)
        self.assertTrue(any("unversioned active" in error for error in result.errors))

    def test_mixed_metadata_fails_closed(self):
        task, evidence = active_records()
        evidence.pop("validation_contract")

        result = validate_compatible_records(task, evidence)

        self.assertIsNone(result.selection)
        self.assertTrue(any("mixed" in error for error in result.errors))

    def test_v2_failure_never_falls_back_to_v1(self):
        task, evidence = active_records()
        evidence["task_id"] = "TASK-WRONG"

        result = validate_compatible_records(task, evidence)

        self.assertEqual(2, result.selection.version)
        self.assertTrue(any("does not match evidence.task_id" in error for error in result.errors))
        self.assertNotEqual(v1_metadata()["policy_id"], result.selection.policy_id)

    def test_v2_policy_snapshot_tamper_fails(self):
        task, evidence = active_records()
        evidence["validation_contract"]["policy_sha256"] = "0" * 64

        result = validate_compatible_records(task, evidence)

        self.assertEqual(2, result.selection.version)
        self.assertTrue(any("policy snapshot" in error for error in result.errors))

    def test_explicit_v1_cannot_be_used_for_active_work(self):
        task, evidence = active_records()
        legacy = v1_metadata()
        legacy["scope"] = "active"
        task["validation_contract"] = dict(legacy)
        evidence["validation_contract"] = dict(legacy)

        result = validate_compatible_records(task, evidence)

        self.assertIsNone(result.selection)
        self.assertTrue(any("v1" in error and "active" in error for error in result.errors))

    def test_explicit_closed_scope_v1_still_rejects_nonterminal_records(self):
        task, evidence = active_records()
        task["validation_contract"] = v1_metadata()
        evidence["validation_contract"] = v1_metadata()

        result = validate_compatible_records(task, evidence)

        self.assertIsNone(result.selection)
        self.assertTrue(any("v1" in error and "terminal" in error for error in result.errors))

    def test_explicit_v1_snapshot_tamper_fails(self):
        task, evidence = closed_legacy_records()
        task["validation_contract"] = v1_metadata()
        evidence["validation_contract"] = v1_metadata()
        evidence["validation_contract"]["policy_sha256"] = "f" * 64

        result = validate_compatible_records(task, evidence)

        self.assertEqual(1, result.selection.version)
        self.assertTrue(any("policy snapshot" in error for error in result.errors))

    def test_closed_history_is_not_returned_for_active_reconciliation(self):
        task, evidence = closed_legacy_records()

        result = validate_compatible_records(task, evidence)

        self.assertFalse(result.active_reconciliation)


class ContractResourceTests(unittest.TestCase):
    def test_packaged_policy_and_schemas_are_discoverable_for_both_versions(self):
        for version in (1, 2):
            for name in ("policy.json", "task.schema.json", "evidence.schema.json"):
                resource = contract_resource(version, name)
                self.assertTrue(resource.is_file(), f"v{version}/{name}")
                self.assertGreater(len(resource.read_bytes()), 20)

    def test_policy_snapshot_uses_canonical_json_not_checkout_line_endings(self):
        resource = contract_resource(2, "policy.json")
        payload = json.loads(resource.read_text(encoding="utf-8"))
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = hashlib.sha256(canonical).hexdigest()
        self.assertEqual(expected, v2_metadata()["policy_sha256"])

    def test_current_templates_embed_exact_packaged_policy_snapshot(self):
        task = load_record(TEMPLATE_ROOT / "TASK_RECORD_TEMPLATE.yaml")
        evidence = load_record(TEMPLATE_ROOT / "EVIDENCE_RECORD_TEMPLATE.yaml")
        expected = v2_metadata()
        self.assertEqual(expected, task["validation_contract"])
        self.assertEqual(expected, evidence["validation_contract"])
        self.assertRegex(expected["policy_sha256"], r"^[0-9a-f]{64}$")

    def test_current_source_schemas_require_contract_metadata(self):
        schema_root = REPO_ROOT / "docs/profiles/task-dispatch/schemas"
        for name in ("task.schema.json", "evidence.schema.json"):
            payload = json.loads((schema_root / name).read_text(encoding="utf-8"))
            self.assertIn("validation_contract", payload["required"])
            self.assertIn("validation_contract", payload["properties"])

    def test_packaged_schemas_are_exact_snapshots_with_bound_digests(self):
        source_root = REPO_ROOT / "docs/profiles/task-dispatch/schemas"
        for version in (1, 2):
            policy = json.loads(contract_resource(version, "policy.json").read_text(encoding="utf-8"))
            for name in ("task.schema.json", "evidence.schema.json"):
                packaged = json.loads(contract_resource(version, name).read_text(encoding="utf-8"))
                canonical = json.dumps(
                    packaged,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.assertEqual(hashlib.sha256(canonical).hexdigest(), policy["schema_sha256"][name])
                if version == 2:
                    current = json.loads((source_root / name).read_text(encoding="utf-8"))
                    self.assertEqual(current, packaged)
                else:
                    frozen = subprocess.run(
                        [
                            "git",
                            "show",
                            "626706a5c4a9bc4cce9ce7dc69effb6eaf960141:"
                            f"docs/profiles/task-dispatch/schemas/{name}",
                        ],
                        cwd=REPO_ROOT,
                        text=True,
                        stdout=subprocess.PIPE,
                        check=True,
                    )
                    self.assertEqual(json.loads(frozen.stdout), packaged)

    def test_packaged_contracts_reject_records_missing_core_fields(self):
        from sagekit.validation_contracts.v1 import validate_records as validate_v1
        from sagekit.validation_contracts.v2 import validate_records as validate_v2

        for validate in (validate_v1, validate_v2):
            task, evidence = active_records()
            if validate is validate_v1:
                task, evidence = closed_legacy_records()
            task.pop("authority", None)
            evidence.pop("runtime_shape", None)
            errors = validate(task, evidence)
            self.assertTrue(any("authority" in error for error in errors))
            self.assertTrue(any("runtime_shape" in error for error in errors))

    def test_source_manifest_includes_compatibility_runtime_and_policy(self):
        for relative in (
            "docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md",
            "sagekit/compatibility.py",
            "sagekit/candidate.py",
            "sagekit/reporting.py",
            "sagekit/validation_contracts/__init__.py",
            "sagekit/validation_contracts/v1.py",
            "sagekit/validation_contracts/v2.py",
            "sagekit/resources/contracts/v1/policy.json",
            "sagekit/resources/contracts/v1/task.schema.json",
            "sagekit/resources/contracts/v1/evidence.schema.json",
            "sagekit/resources/contracts/v2/policy.json",
            "sagekit/resources/contracts/v2/task.schema.json",
            "sagekit/resources/contracts/v2/evidence.schema.json",
            "tests/test_validation_compatibility.py",
        ):
            self.assertIn(relative, SOURCE_REQUIRED_FILES)


class ProjectCheckCompatibilityTests(unittest.TestCase):
    def test_closed_history_does_not_pollute_active_duplicate_lock_or_board_checks(self):
        active_task, active_evidence = active_records()
        legacy_task, legacy_evidence = closed_legacy_records()
        legacy_task["id"] = active_task["id"]
        legacy_evidence["task_id"] = active_task["id"]
        lock = {
            "resource": "src/shared",
            "owner": "worker",
            "mode": "EXCLUSIVE",
            "status": "ACTIVE",
            "carried": False,
        }
        active_task["resources"]["locks"] = [dict(lock)]
        legacy_task["resources"]["locks"] = [dict(lock)]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_dir = root / "docs/M1/dispatch/TASK-ACTIVE"
            legacy_dir = root / "docs/M1/dispatch/TASK-LEGACY-HISTORY"
            active_dir.mkdir(parents=True)
            legacy_dir.mkdir(parents=True)
            (active_dir / "task.yaml").write_text(json.dumps(active_task), encoding="utf-8")
            (active_dir / "evidence.yaml").write_text(
                json.dumps(active_evidence),
                encoding="utf-8",
            )
            (legacy_dir / "task.yaml").write_text(json.dumps(legacy_task), encoding="utf-8")
            (legacy_dir / "evidence.yaml").write_text(
                json.dumps(legacy_evidence),
                encoding="utf-8",
            )
            (root / "docs/M1/dispatch/DISPATCH_BOARD.md").write_text(
                "## Active Tasks\n\n| Task |\n| --- |\n| TASK-ACTIVE |\n",
                encoding="utf-8",
            )

            findings = check_task_dispatch(root)

        contract_messages = [
            finding.message
            for finding in findings
            if finding.rule == "validation-contract"
        ]
        rules = {finding.rule for finding in findings}
        self.assertTrue(any("v1" in message for message in contract_messages))
        self.assertTrue(any("v2" in message for message in contract_messages))
        self.assertNotIn("task-dispatch-duplicate-id", rules)
        self.assertNotIn("task-dispatch-lock-conflict", rules)
        self.assertFalse(
            any(
                finding.rule == "task-dispatch-board"
                and "LEGACY" in finding.message
                for finding in findings
            )
        )

    def test_active_exclusive_run_leases_conflict_across_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in (1, 2):
                task, evidence = active_records()
                task["id"] = f"TASK-{index}"
                evidence["task_id"] = task["id"]
                run = {
                    "id": f"run-{index}",
                    "attempt": 1,
                    "status": "RUNNING",
                    "owner": f"worker-{index}",
                    "authority_ref": "approved task authority",
                    "phase": "implementation",
                    "next_action": "finish",
                    "uses_shared_resource": True,
                    "lease": {
                        "resource": "src/shared",
                        "owner": f"worker-{index}",
                        "mode": "exclusive",
                        "status": "ACTIVE",
                        "release_rule": "after completion",
                    },
                }
                task["runs"] = [run]
                evidence["runs"] = [run]
                pair = root / f"docs/M1/dispatch/TASK-{index}"
                pair.mkdir(parents=True)
                (pair / "task.yaml").write_text(json.dumps(task), encoding="utf-8")
                (pair / "evidence.yaml").write_text(json.dumps(evidence), encoding="utf-8")

            findings = check_task_dispatch(root)

        self.assertIn("task-dispatch-lease-conflict", {item.rule for item in findings})


class BoundedReportingTests(unittest.TestCase):
    def test_bounded_report_keeps_exact_totals_and_sample_fields(self):
        findings = [
            Finding(
                "FAIL" if index % 4 == 0 else "WARN",
                f"rule-{index}",
                f"docs/{index}.md",
                None,
                f"message {index}",
            )
            for index in range(25)
        ]

        report = build_finding_report(findings, max_findings=5)
        payload = finding_report_payload(report)

        self.assertEqual(25, payload["summary"]["total"])
        self.assertEqual(5, payload["summary"]["displayed"])
        self.assertEqual(20, payload["summary"]["truncated"])
        self.assertEqual({"FAIL": 7, "PASS": 0, "WARN": 18}, payload["summary"]["by_level"])
        self.assertEqual(5, len(payload["findings"]))
        for finding in payload["findings"]:
            self.assertIn("path", finding)
            self.assertIn("rule", finding)
            self.assertIn("message", finding)

    def test_json_payload_is_stable(self):
        findings = [
            Finding("WARN", "b", "b.md", None, "second"),
            Finding("FAIL", "a", "a.md", None, "first"),
        ]
        first = finding_report_payload(build_finding_report(findings, max_findings=2))
        second = finding_report_payload(build_finding_report(findings, max_findings=2))
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_invalid_report_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 500"):
            build_finding_report([], max_findings=0)

    def test_cli_parser_and_emitter_expose_bounded_summary(self):
        args = build_parser().parse_args(["check", "--max-findings", "2", "--json"])
        findings = [
            Finding("WARN", f"rule-{index}", f"{index}.md", None, f"message {index}")
            for index in range(4)
        ]
        output = StringIO()

        with redirect_stdout(output):
            emit_findings(findings, True, max_findings=args.max_findings)

        payload = json.loads(output.getvalue())
        self.assertEqual(2, payload["summary"]["displayed"])
        self.assertEqual(4, payload["summary"]["total"])


class CompatibilityDocumentationTests(unittest.TestCase):
    def test_compatibility_doc_is_packaged_and_project_neutral(self):
        source = REPO_ROOT / "docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md"
        packaged = (
            REPO_ROOT
            / "sagekit/resources/docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md"
        )

        self.assertTrue(source.is_file())
        self.assertEqual(
            source.read_text(encoding="utf-8"),
            packaged.read_text(encoding="utf-8"),
        )
        text = source.read_text(encoding="utf-8")
        self.assertIn("closed legacy history", text)
        self.assertIn("active/new work", text)
        self.assertIn("ambiguous or mixed", text)
        self.assertIn("must not fall back", text)
        self.assertNotIn("specific external project", text.lower())

    def test_runtime_python_uses_python_310_compatible_syntax(self):
        for path in sorted((REPO_ROOT / "sagekit").rglob("*.py")):
            source = path.read_text(encoding="utf-8-sig")
            try:
                ast.parse(source, filename=str(path), feature_version=(3, 10))
            except SyntaxError as exc:
                self.fail(f"{path.relative_to(REPO_ROOT)} is not Python 3.10-compatible: {exc}")


if __name__ == "__main__":
    unittest.main()
