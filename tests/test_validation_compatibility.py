import json
import hashlib
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.check import (
    SOURCE_REQUIRED_FILES,
    check_task_dispatch,
    validate_task_dispatch_pair,
)
from sagekit.compatibility import (
    ContractScope,
    select_validation_contract,
    validate_compatible_records,
)
from sagekit.findings import Finding
from sagekit.milestone_scope import (
    MilestoneScope,
    MilestoneScopeKind,
    RepositoryScopeResolver,
)
from sagekit.reporting import build_finding_report, finding_report_payload
from sagekit.task_dispatch_validator import load_record
from sagekit.validation_contracts import contract_resource
from sagekit.validation_contracts.v1 import contract_metadata as v1_metadata
from sagekit.validation_contracts.v2 import contract_metadata as v2_metadata
from sagekit.validation_scope_manifest import load_validation_scope_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "docs/profiles/task-dispatch/templates"
FROZEN_V1_BASE_SHA = "626706a5c4a9bc4cce9ce7dc69effb6eaf960141"
FROZEN_V1_PATHS = {
    "task.schema.json": "docs/profiles/task-dispatch/schemas/task.schema.json",
    "evidence.schema.json": "docs/profiles/task-dispatch/schemas/evidence.schema.json",
}
FROZEN_V1_SCHEMA_SHA256 = {
    "task.schema.json": "d8fbfd72bfae672e740fa3aa0537e19639ff53c0165142e7a596a332e23494a3",
    "evidence.schema.json": "59ba187deaa95cb1b95d9dccd4f135fb2f473d02af20af8469da5261645509b7",
}
FROZEN_V1_POLICY_SHA256 = (
    "2f1796fa24262200dea64e74b969ad86cb33b1781dd4754b35bd7328c7cc20a2"
)


def canonical_digest(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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


def write_scope_authority(
    root,
    *,
    active_milestones=(),
    closeouts=None,
):
    active_value = ", ".join(active_milestones) if active_milestones else "none"
    active_context = root / "docs/ACTIVE_CONTEXT.md"
    active_context.parent.mkdir(parents=True, exist_ok=True)
    active_context.write_text(
        f"# Active Context\n\n- Current milestone: `{active_value}`\n",
        encoding="utf-8",
    )
    for milestone, closeout_text in (closeouts or {}).items():
        milestone_dir = root / "docs" / milestone
        milestone_dir.mkdir(parents=True, exist_ok=True)
        (milestone_dir / "MILESTONE_CLOSEOUT.md").write_text(
            closeout_text,
            encoding="utf-8",
        )


def write_dispatch_records(root, milestone, directory, task, evidence):
    pair = root / "docs" / milestone / "dispatch" / directory
    pair.mkdir(parents=True, exist_ok=True)
    (pair / "task.yaml").write_text(json.dumps(task), encoding="utf-8")
    (pair / "evidence.yaml").write_text(json.dumps(evidence), encoding="utf-8")
    return pair


def write_validation_scope_manifest(root, *, active=(), accepted=("M1",)):
    for item in (*active, *accepted):
        (root / f"docs/{item}").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "active_containers": [
            {"id": item, "path": f"docs/{item}"} for item in active
        ],
        "accepted_legacy_containers": [
            {
                "id": item,
                "path": f"docs/{item}",
                "contract_version": 1,
                "supersedes": [],
            }
            for item in accepted
        ],
        "authority": {
            "source": "project-owner compatibility authority",
            "approved_by": "project-owner",
            "approved_at": "2026-01-01T00:00:00Z",
            "baseline_head": "0123456789abcdef0123456789abcdef01234567",
        },
    }
    path = root / "docs/SAGE_VALIDATION_SCOPE.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


ACCEPTED_CLOSEOUT = """\
# Milestone Closeout

## Outcome

- Status: `ACCEPTED`
"""


def accepted_history_scope():
    return MilestoneScope(
        "M1",
        MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
        ("docs/M1/MILESTONE_CLOSEOUT.md accepted outcome: ACCEPTED",),
        "trusted accepted closeout authority and no active milestone authority",
        contract_version=1,
    )


def active_scope():
    return MilestoneScope(
        "M1",
        MilestoneScopeKind.CURRENT,
        ("docs/ACTIVE_CONTEXT.md active milestone field: M1",),
        "explicit active milestone authority requires the current contract",
    )


class ContractSelectionTests(unittest.TestCase):
    def test_closed_unversioned_history_uses_frozen_v1(self):
        task, evidence = closed_legacy_records()

        selection = select_validation_contract(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

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

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=active_scope(),
        )

        self.assertIsNone(result.selection)
        self.assertTrue(any("active milestone" in error for error in result.errors))

    def test_mixed_metadata_fails_closed(self):
        task, evidence = active_records()
        evidence.pop("validation_contract")

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

        self.assertIsNone(result.selection)
        self.assertTrue(any("mixed" in error for error in result.errors))

    def test_non_scalar_contract_version_fails_closed(self):
        task, evidence = active_records()
        task["validation_contract"]["version"] = []
        evidence["validation_contract"]["version"] = []

        result = validate_compatible_records(task, evidence)

        self.assertIsNone(result.selection)
        self.assertTrue(any("unsupported" in error for error in result.errors))

    def test_v2_failure_never_falls_back_to_v1(self):
        task, evidence = active_records()
        evidence["task_id"] = "TASK-WRONG"

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

        self.assertEqual(2, result.selection.version)
        self.assertTrue(any("does not match evidence.task_id" in error for error in result.errors))
        self.assertNotEqual(v1_metadata()["policy_id"], result.selection.policy_id)

    def test_v2_policy_snapshot_tamper_fails(self):
        task, evidence = active_records()
        evidence["validation_contract"]["policy_sha256"] = "0" * 64

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

        self.assertEqual(2, result.selection.version)
        self.assertTrue(any("policy snapshot" in error for error in result.errors))

    def test_explicit_v1_cannot_be_used_for_active_work(self):
        task, evidence = active_records()
        legacy = v1_metadata()
        legacy["scope"] = "active"
        task["validation_contract"] = dict(legacy)
        evidence["validation_contract"] = dict(legacy)

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

        self.assertIsNone(result.selection)
        self.assertTrue(any("v1" in error and "active" in error for error in result.errors))

    def test_explicit_closed_scope_v1_still_rejects_nonterminal_records(self):
        task, evidence = active_records()
        task["validation_contract"] = v1_metadata()
        evidence["validation_contract"] = v1_metadata()

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

        self.assertIsNone(result.selection)
        self.assertTrue(any("v1" in error and "terminal" in error for error in result.errors))

    def test_explicit_v1_snapshot_tamper_fails(self):
        task, evidence = closed_legacy_records()
        task["validation_contract"] = v1_metadata()
        evidence["validation_contract"] = v1_metadata()
        evidence["validation_contract"]["policy_sha256"] = "f" * 64

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

        self.assertEqual(1, result.selection.version)
        self.assertTrue(any("policy snapshot" in error for error in result.errors))

    def test_explicit_frozen_metadata_must_match_manifest_pinned_version(self):
        task, evidence = closed_legacy_records()
        task["validation_contract"] = v1_metadata()
        evidence["validation_contract"] = v1_metadata()
        scope = MilestoneScope(
            "M1",
            MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
            ("scope manifest",),
            "manifest-selected history",
            contract_version=0,
        )

        result = validate_compatible_records(task, evidence, container_scope=scope)

        self.assertIsNone(result.selection)
        self.assertTrue(any("manifest-pinned" in error for error in result.errors))

    def test_closed_history_is_not_returned_for_active_reconciliation(self):
        task, evidence = closed_legacy_records()

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )

        self.assertFalse(result.active_reconciliation)

    def test_terminal_v2_in_accepted_history_remains_in_active_reconciliation(self):
        task, evidence = closed_legacy_records()
        task["validation_contract"] = v2_metadata()
        evidence["validation_contract"] = v2_metadata()

        result = validate_compatible_records(
            task,
            evidence,
            container_scope=accepted_history_scope(),
        )
        self.assertEqual(2, result.selection.version)
        self.assertTrue(result.active_reconciliation)

    def test_explicit_v2_in_ambiguous_scope_remains_v2_and_blocks_authority(self):
        task, evidence = active_records()
        scope = MilestoneScope(
            "M1",
            MilestoneScopeKind.AMBIGUOUS,
            (),
            "active and accepted authority conflict",
        )

        result = validate_compatible_records(task, evidence, container_scope=scope)

        self.assertEqual(2, result.selection.version)
        self.assertIn("active and accepted authority conflict", result.errors)
        self.assertTrue(result.active_reconciliation)


class MilestoneScopeResolverTests(unittest.TestCase):
    def test_supported_structured_accepted_outcomes_require_manifest_authority(self):
        statuses = (
            "ACCEPTED",
            "ACCEPTED_WITH_CONCERNS",
            "DONE",
            "DONE_WITH_CONCERNS",
            "PM_ACCEPTED / ACCEPTED / CLOSED",
        )
        for status in statuses:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_scope_authority(
                    root,
                    closeouts={
                        "M1": (
                            "# Milestone Closeout\n\n"
                            "## Outcome\n\n"
                            f"- Status: `{status}`\n"
                        )
                    },
                )

                scope = RepositoryScopeResolver(root).resolve(root / "docs/M1")

                self.assertEqual(MilestoneScopeKind.CURRENT, scope.kind)
                self.assertIn("Validation Scope Manifest", scope.detail)

    def test_table_status_is_structured_closeout_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                closeouts={
                    "M1": (
                        "# Milestone Closeout\n\n"
                        "| Field | Value |\n"
                        "|---|---|\n"
                        "| Status | DONE |\n"
                    )
                },
            )

            scope = RepositoryScopeResolver(root).resolve(root / "docs/M1")

        self.assertEqual(MilestoneScopeKind.CURRENT, scope.kind)
        self.assertIn("Validation Scope Manifest", scope.detail)

    def test_configured_active_context_drives_scope_authority_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(root, active_milestones=("M1",))
            write_validation_scope_manifest(root, active=("M2",))
            (root / "SAGEKIT_CONFIG.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "project_id": "configured-context",
                        "adoption_profile": "package-bound",
                        "execution_scope": "active-only",
                        "active_context": "handoff/NOW.md",
                        "package": {
                            "name": "sagekit",
                            "version": "public-contract-v1",
                            "digest": "0" * 64,
                        },
                        "sources": {},
                    }
                ),
                encoding="utf-8",
            )
            configured = root / "handoff/NOW.md"
            configured.parent.mkdir(parents=True)
            configured.write_text(
                "# Active Context\n\n- Current milestone: `M2`\n",
                encoding="utf-8",
            )
            manifest = load_validation_scope_manifest(
                root / "docs/SAGE_VALIDATION_SCOPE.json"
            )

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )

        self.assertEqual(MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY, scope.kind)
        self.assertTrue(
            any("handoff/NOW.md" in authority for authority in scope.authorities),
            scope,
        )

    def test_unknown_or_conflicting_structured_outcomes_are_ambiguous(self):
        closeouts = (
            "# Milestone Closeout\n\n- Status: `READY_FOR_REVIEW`\n",
            (
                "# Milestone Closeout\n\n"
                "- Status: `ACCEPTED`\n"
                "- Outcome: `BLOCKED`\n"
            ),
        )
        for closeout in closeouts:
            with self.subTest(closeout=closeout), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_scope_authority(root, closeouts={"M1": closeout})

                scope = RepositoryScopeResolver(root).resolve(root / "docs/M1")

                self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)

    def test_fenced_examples_do_not_create_closeout_or_active_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_context = root / "docs/ACTIVE_CONTEXT.md"
            active_context.parent.mkdir(parents=True, exist_ok=True)
            active_context.write_text(
                "# Active Context\n\n"
                "```markdown\n"
                "- Current milestone: `M1`\n"
                "```\n",
                encoding="utf-8",
            )
            milestone = root / "docs/M1"
            milestone.mkdir(parents=True)
            (milestone / "MILESTONE_CLOSEOUT.md").write_text(
                "# Milestone Closeout\n\n"
                "```markdown\n"
                "- Status: `ACCEPTED`\n"
                "```\n",
                encoding="utf-8",
            )

            scope = RepositoryScopeResolver(root).resolve(milestone)

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("no structured", scope.detail)

    def test_accepted_closeout_requires_explicit_active_set_authority(self):
        active_contexts = {
            "missing": None,
            "missing-field": "# Active Context\n\n- Current focus: implementation\n",
            "placeholder": (
                "# Active Context\n\n"
                "- Current milestone: `<milestone ID or none>`\n"
            ),
        }
        for label, active_text in active_contexts.items():
            with self.subTest(authority=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                milestone = root / "docs/M1"
                milestone.mkdir(parents=True)
                (milestone / "MILESTONE_CLOSEOUT.md").write_text(
                    ACCEPTED_CLOSEOUT,
                    encoding="utf-8",
                )
                if active_text is not None:
                    (root / "docs/ACTIVE_CONTEXT.md").write_text(
                        active_text,
                        encoding="utf-8",
                    )

                scope = RepositoryScopeResolver(root).resolve(milestone)

                self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
                self.assertIn("active milestone authority", scope.detail)

    def test_unresolved_active_placeholder_keeps_nonhistorical_scope_strict_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_context = root / "docs/ACTIVE_CONTEXT.md"
            active_context.parent.mkdir(parents=True, exist_ok=True)
            active_context.write_text(
                "# Active Context\n\n"
                "- Current milestone: `<milestone ID or none>`\n",
                encoding="utf-8",
            )
            milestone = root / "docs/M1"
            milestone.mkdir(parents=True)

            scope = RepositoryScopeResolver(root).resolve(milestone)

        self.assertEqual(MilestoneScopeKind.CURRENT, scope.kind)
        self.assertIn("current checks remain required", scope.detail)

    def test_explicit_inactive_set_is_in_historical_authority_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                active_milestones=("M2",),
                closeouts={"M1": ACCEPTED_CLOSEOUT},
            )

            scope = RepositoryScopeResolver(root).resolve(root / "docs/M1")

        self.assertEqual(MilestoneScopeKind.CURRENT, scope.kind)
        self.assertTrue(
            any("ACTIVE_CONTEXT.md" in authority for authority in scope.authorities),
            scope,
        )

    def test_html_comments_do_not_create_closeout_or_active_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                closeouts={
                    "M1": (
                        "# Milestone Closeout\n\n"
                        "<!--\n"
                        "- Status: `DONE`\n"
                        "-->\n"
                    )
                },
            )

            closeout_scope = RepositoryScopeResolver(root).resolve(root / "docs/M1")

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, closeout_scope.kind)
        self.assertIn("no structured", closeout_scope.detail)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                closeouts={"M1": ACCEPTED_CLOSEOUT},
            )
            with (root / "docs/ACTIVE_CONTEXT.md").open(
                "a",
                encoding="utf-8",
            ) as active_context:
                active_context.write(
                    "<!--\n"
                    "- Current milestone: `M1`\n"
                    "-->\n"
                )

            active_scope = RepositoryScopeResolver(root).resolve(root / "docs/M1")

        self.assertEqual(
            MilestoneScopeKind.CURRENT,
            active_scope.kind,
        )
        self.assertIn("Validation Scope Manifest", active_scope.detail)

    def test_active_milestone_separator_alias_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                active_milestones=("M1.1",),
                closeouts={"M1_1": ACCEPTED_CLOSEOUT},
            )

            scope = RepositoryScopeResolver(root).resolve(root / "docs/M1_1")

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("identifier", scope.detail)


class ContractResourceTests(unittest.TestCase):
    def test_packaged_policy_and_schemas_are_discoverable_for_all_versions(self):
        for version in (0, 1, 2):
            for name in ("policy.json", "task.schema.json", "evidence.schema.json"):
                resource = contract_resource(version, name)
                self.assertTrue(resource.is_file(), f"v{version}/{name}")
                self.assertGreater(len(resource.read_bytes()), 20)
            if version in {0, 1}:
                self.assertTrue(contract_resource(version, "rules.json").is_file())
                self.assertTrue(contract_resource(version, "validator.json").is_file())

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
                self.assertEqual(canonical_digest(packaged), policy["schema_sha256"][name])
                if version == 2:
                    current = json.loads((source_root / name).read_text(encoding="utf-8"))
                    self.assertEqual(current, packaged)
                else:
                    self.assertEqual(FROZEN_V1_SCHEMA_SHA256[name], canonical_digest(packaged))

    def test_frozen_v1_policy_has_fixed_digest_and_true_provenance(self):
        policy = json.loads(contract_resource(1, "policy.json").read_text(encoding="utf-8"))

        self.assertEqual(FROZEN_V1_POLICY_SHA256, canonical_digest(policy))
        self.assertEqual(FROZEN_V1_BASE_SHA, policy["frozen_from_base_sha"])
        self.assertEqual(FROZEN_V1_PATHS, policy["frozen_from_paths"])
        self.assertEqual(FROZEN_V1_SCHEMA_SHA256, policy["schema_sha256"])

    def test_frozen_v1_constants_detect_snapshot_or_policy_tamper(self):
        policy = json.loads(contract_resource(1, "policy.json").read_text(encoding="utf-8"))
        schema = json.loads(
            contract_resource(1, "task.schema.json").read_text(encoding="utf-8")
        )
        tampered_policy = dict(policy)
        tampered_policy["scope"] = "active"
        tampered_schema = dict(schema)
        tampered_schema["title"] = "tampered"

        self.assertNotEqual(FROZEN_V1_POLICY_SHA256, canonical_digest(tampered_policy))
        self.assertNotEqual(
            FROZEN_V1_SCHEMA_SHA256["task.schema.json"],
            canonical_digest(tampered_schema),
        )

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
            "sagekit/milestone_scope.py",
            "sagekit/candidate.py",
            "sagekit/reporting.py",
            "sagekit/validation_contracts/__init__.py",
            "sagekit/validation_contracts/frozen_validator.py",
            "sagekit/validation_contracts/v0.py",
            "sagekit/validation_contracts/v1.py",
            "sagekit/validation_contracts/v2.py",
            "sagekit/resources/contracts/v0/policy.json",
            "sagekit/resources/contracts/v0/rules.json",
            "sagekit/resources/contracts/v0/validator.json",
            "sagekit/resources/contracts/v0/task.schema.json",
            "sagekit/resources/contracts/v0/evidence.schema.json",
            "sagekit/resources/contracts/v1/policy.json",
            "sagekit/resources/contracts/v1/rules.json",
            "sagekit/resources/contracts/v1/validator.json",
            "sagekit/resources/contracts/v1/task.schema.json",
            "sagekit/resources/contracts/v1/evidence.schema.json",
            "sagekit/resources/contracts/v2/policy.json",
            "sagekit/resources/contracts/v2/task.schema.json",
            "sagekit/resources/contracts/v2/evidence.schema.json",
            "tests/test_validation_compatibility.py",
        ):
            self.assertIn(relative, SOURCE_REQUIRED_FILES)


class ProjectCheckCompatibilityTests(unittest.TestCase):
    def test_ambiguous_scope_is_reported_once_but_all_pairs_are_reconciled(self):
        lock = {
            "resource": "src/shared",
            "owner": "worker",
            "mode": "EXCLUSIVE",
            "status": "ACTIVE",
            "carried": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_context = root / "docs/ACTIVE_CONTEXT.md"
            active_context.parent.mkdir(parents=True, exist_ok=True)
            active_context.write_text(
                "# Active Context\n\n- Current focus: implementation\n",
                encoding="utf-8",
            )
            milestone = root / "docs/M1"
            milestone.mkdir(parents=True)
            (milestone / "MILESTONE_CLOSEOUT.md").write_text(
                ACCEPTED_CLOSEOUT,
                encoding="utf-8",
            )
            for directory_id in ("record-a", "record-b"):
                task, evidence = closed_legacy_records()
                task["id"] = "TASK-SHARED"
                evidence["task_id"] = task["id"]
                task["resources"]["locks"] = [dict(lock)]
                write_dispatch_records(root, "M1", directory_id, task, evidence)
            (root / "docs/M1/dispatch/DISPATCH_BOARD.md").write_text(
                "## Active Tasks\n\n| Task |\n|---|\n",
                encoding="utf-8",
            )

            findings = check_task_dispatch(root)

        self.assertEqual(
            1,
            len(
                [
                    item
                    for item in findings
                    if item.rule == "milestone-scope" and item.level == "FAIL"
                ]
            ),
            findings,
        )
        self.assertFalse(
            [
                item
                for item in findings
                if item.rule == "task-dispatch"
                and "active milestone authority" in item.message
            ],
            findings,
        )
        rules = {item.rule for item in findings}
        self.assertIn("task-dispatch-duplicate-id", rules)
        self.assertIn("task-dispatch-lock-conflict", rules)

    def test_explicit_v2_remains_selected_under_blocking_ambiguous_scope(self):
        task, evidence = active_records()
        evidence["task_id"] = "TASK-WRONG"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_context = root / "docs/ACTIVE_CONTEXT.md"
            active_context.parent.mkdir(parents=True, exist_ok=True)
            active_context.write_text(
                "# Active Context\n\n- Current focus: implementation\n",
                encoding="utf-8",
            )
            milestone = root / "docs/M1"
            milestone.mkdir(parents=True)
            (milestone / "MILESTONE_CLOSEOUT.md").write_text(
                ACCEPTED_CLOSEOUT,
                encoding="utf-8",
            )
            write_dispatch_records(root, "M1", "TASK-ACTIVE", task, evidence)

            findings = check_task_dispatch(root)

        self.assertTrue(
            any(
                item.rule == "validation-contract"
                and "selected v2" in item.message
                for item in findings
            ),
            findings,
        )
        self.assertTrue(
            any(
                item.rule == "task-dispatch"
                and "does not match evidence.task_id" in item.message
                for item in findings
            ),
            findings,
        )
        self.assertTrue(
            any(item.rule == "milestone-scope" and item.level == "FAIL" for item in findings),
            findings,
        )

    def test_single_pair_validator_resolves_repository_scope(self):
        task, evidence = closed_legacy_records()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                active_milestones=("M2",),
                closeouts={"M1": ACCEPTED_CLOSEOUT},
            )
            write_validation_scope_manifest(root, active=("M2",))
            pair = write_dispatch_records(root, "M1", "TASK-LEGACY", task, evidence)

            findings = validate_task_dispatch_pair(
                root,
                pair / "task.yaml",
                pair / "evidence.yaml",
                False,
            )

        self.assertTrue(
            any(
                item.rule == "validation-contract"
                and "v1" in item.message
                and "MILESTONE_CLOSEOUT.md" in item.message
                for item in findings
            ),
            findings,
        )

    def test_dispatch_resolves_each_milestone_scope_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(root, active_milestones=("M1",))
            board_ids = []
            for index in (1, 2):
                task, evidence = active_records()
                task["id"] = f"TASK-{index}"
                evidence["task_id"] = task["id"]
                board_ids.append(task["id"])
                write_dispatch_records(root, "M1", task["id"], task, evidence)
            (root / "docs/M1/dispatch/DISPATCH_BOARD.md").write_text(
                "## Active Tasks\n\n| Task |\n|---|\n"
                + "".join(f"| {task_id} |\n" for task_id in board_ids),
                encoding="utf-8",
            )
            original = RepositoryScopeResolver.resolve
            calls = []

            def tracked_resolve(resolver, milestone_dir):
                calls.append(milestone_dir.name)
                return original(resolver, milestone_dir)

            with patch.object(RepositoryScopeResolver, "resolve", tracked_resolve):
                check_task_dispatch(root)

        self.assertEqual(["M1"], calls)

    def test_verified_history_uses_v1_only_with_accepted_inactive_scope(self):
        task, evidence = closed_legacy_records()
        task["status"] = "VERIFIED"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                active_milestones=("M2",),
                closeouts={"M1": ACCEPTED_CLOSEOUT},
            )
            write_validation_scope_manifest(root, active=("M2",))
            write_dispatch_records(root, "M1", "TASK-LEGACY", task, evidence)
            (root / "docs/M1/dispatch/DISPATCH_BOARD.md").write_text(
                "## Active Tasks\n\n| Task |\n|---|\n",
                encoding="utf-8",
            )

            findings = check_task_dispatch(root)

        contract_messages = [
            item.message for item in findings if item.rule == "validation-contract"
        ]
        self.assertTrue(any("v1" in message for message in contract_messages), findings)
        self.assertTrue(
            any("MILESTONE_CLOSEOUT.md" in message for message in contract_messages),
            contract_messages,
        )
        self.assertFalse(
            any(item.level == "FAIL" and item.rule == "task-dispatch" for item in findings),
            findings,
        )

    def test_verified_history_without_accepted_closeout_fails_closed(self):
        task, evidence = closed_legacy_records()
        task["status"] = "VERIFIED"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(root, active_milestones=("M2",))
            write_dispatch_records(root, "M1", "TASK-LEGACY", task, evidence)

            findings = check_task_dispatch(root)

        self.assertTrue(
            any(
                item.level == "FAIL"
                and item.rule == "task-dispatch"
                and "accepted" in item.message.lower()
                for item in findings
            ),
            findings,
        )

    def test_verified_record_in_active_milestone_cannot_use_v1(self):
        task, evidence = closed_legacy_records()
        task["status"] = "VERIFIED"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(root, active_milestones=("M1",))
            write_dispatch_records(root, "M1", "TASK-LEGACY", task, evidence)

            findings = check_task_dispatch(root)

        self.assertFalse(
            any(item.rule == "validation-contract" and "v1" in item.message for item in findings),
            findings,
        )
        self.assertTrue(
            any(
                item.level == "FAIL"
                and item.rule == "task-dispatch"
                and "active milestone" in item.message.lower()
                for item in findings
            ),
            findings,
        )

    def test_active_and_accepted_authority_conflict_fails_closed(self):
        task, evidence = closed_legacy_records()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(
                root,
                active_milestones=("M1",),
                closeouts={"M1": ACCEPTED_CLOSEOUT},
            )
            write_dispatch_records(root, "M1", "TASK-LEGACY", task, evidence)

            findings = check_task_dispatch(root)

        self.assertTrue(
            any(
                item.level == "FAIL"
                and "authority conflict" in item.message.lower()
                for item in findings
            ),
            findings,
        )
        self.assertFalse(
            any(item.rule == "validation-contract" and "v1" in item.message for item in findings),
            findings,
        )

    def test_prose_accepted_or_nonaccepted_closeout_cannot_authorize_v1(self):
        closeouts = {
            "prose": (
                "# Milestone Closeout\n\n"
                "The word accepted appears in background prose only.\n"
            ),
            "pending": "# Milestone Closeout\n\n- Status: `PENDING`\n",
            "draft": "# Milestone Closeout\n\n- Status: `DRAFT`\n",
            "blocked": "# Milestone Closeout\n\n- Status: `BLOCKED`\n",
            "handoff": "# Milestone Closeout\n\n- Status: `HANDOFF`\n",
            "needs-correction": (
                "# Milestone Closeout\n\n- Status: `NEEDS_CORRECTION`\n"
            ),
        }
        for label, closeout in closeouts.items():
            with self.subTest(closeout=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                task, evidence = closed_legacy_records()
                write_scope_authority(root, closeouts={"M1": closeout})
                write_dispatch_records(root, "M1", "TASK-LEGACY", task, evidence)

                findings = check_task_dispatch(root)

                self.assertFalse(
                    any(
                        item.rule == "validation-contract" and "v1" in item.message
                        for item in findings
                    ),
                    findings,
                )
                self.assertTrue(
                    any(item.level == "FAIL" for item in findings),
                    findings,
                )

    def test_explicit_v1_requires_immutable_accepted_scope(self):
        task, evidence = closed_legacy_records()
        task["validation_contract"] = v1_metadata()
        evidence["validation_contract"] = v1_metadata()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(root, active_milestones=("M2",))
            write_dispatch_records(root, "M1", "TASK-LEGACY", task, evidence)

            findings = check_task_dispatch(root)

        self.assertFalse(
            any(item.rule == "validation-contract" and "v1" in item.message for item in findings),
            findings,
        )
        self.assertTrue(
            any(
                item.level == "FAIL"
                and "immutable" in item.message.lower()
                for item in findings
            ),
            findings,
        )

    def test_ambiguous_terminal_history_stays_in_active_reconciliation(self):
        current_task, current_evidence = active_records()
        ambiguous_task, ambiguous_evidence = closed_legacy_records()
        ambiguous_task["id"] = current_task["id"]
        ambiguous_evidence["task_id"] = current_task["id"]
        lock = {
            "resource": "src/shared",
            "owner": "worker",
            "mode": "EXCLUSIVE",
            "status": "ACTIVE",
            "carried": False,
        }
        current_task["resources"]["locks"] = [dict(lock)]
        ambiguous_task["resources"]["locks"] = [dict(lock)]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scope_authority(root, active_milestones=("M2",))
            write_dispatch_records(root, "M2", "TASK-CURRENT", current_task, current_evidence)
            write_dispatch_records(
                root,
                "M1",
                "TASK-AMBIGUOUS",
                ambiguous_task,
                ambiguous_evidence,
            )
            for milestone in ("M1", "M2"):
                (root / f"docs/{milestone}/dispatch/DISPATCH_BOARD.md").write_text(
                    "## Active Tasks\n\n| Task |\n|---|\n",
                    encoding="utf-8",
                )

            findings = check_task_dispatch(root)

        rules = {item.rule for item in findings}
        self.assertIn("task-dispatch-duplicate-id", rules)
        self.assertIn("task-dispatch-lock-conflict", rules)

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
            write_scope_authority(
                root,
                active_milestones=("M2",),
                closeouts={"M1": ACCEPTED_CLOSEOUT},
            )
            write_validation_scope_manifest(root, active=("M2",))
            active_dir = root / "docs/M2/dispatch/TASK-ACTIVE"
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
            (root / "docs/M2/dispatch/DISPATCH_BOARD.md").write_text(
                "## Active Tasks\n\n| Task |\n| --- |\n| TASK-ACTIVE |\n",
                encoding="utf-8",
            )
            (root / "docs/M1/dispatch/DISPATCH_BOARD.md").write_text(
                "## Active Tasks\n\n| Task |\n| --- |\n",
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

    def test_bounded_finding_report_observes_max_findings_limit(self):
        findings = [
            Finding("WARN", f"rule-{index}", f"{index}.md", None, f"message {index}")
            for index in range(4)
        ]
        payload = finding_report_payload(build_finding_report(findings, max_findings=2))
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
        lower = text.lower()
        normalized = " ".join(text.split()).lower()
        self.assertIn("closed legacy history", lower)
        self.assertIn("active/new work", lower)
        self.assertIn("ambiguous or mixed", lower)
        self.assertIn("must not fall back", lower)
        self.assertIn("terminal task/evidence", text)
        self.assertIn("`VERIFIED` alone", text)
        self.assertIn("trusted accepted closeout", text)
        self.assertIn("immutable accepted historical phases", normalized)
        self.assertIn("harness validator", lower)
        self.assertIn("must not rewrite", normalized)
        self.assertNotIn("specific external project", text.lower())

    def test_skill_defers_scope_selection_to_runtime_and_protects_history(self):
        text = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Runtime validator owns contract and milestone scope selection", text)
        self.assertIn("Do not rewrite accepted historical documents", text)

    def test_task_dispatch_summaries_name_container_scope_requirement(self):
        for relative in (
            "docs/profiles/task-dispatch/README.md",
            "docs/profiles/task-dispatch/DISPATCH_PROFILE.md",
        ):
            source = REPO_ROOT / relative
            packaged = REPO_ROOT / "sagekit/resources" / relative
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                packaged.read_text(encoding="utf-8"),
            )
            normalized = " ".join(source.read_text(encoding="utf-8").split()).lower()
            self.assertIn("trusted accepted", normalized)
            self.assertIn("container", normalized)

    def test_runtime_python_uses_python_310_compatible_syntax(self):
        for path in sorted((REPO_ROOT / "sagekit").rglob("*.py")):
            source = path.read_text(encoding="utf-8-sig")
            try:
                ast.parse(source, filename=str(path), feature_version=(3, 10))
            except SyntaxError as exc:
                self.fail(f"{path.relative_to(REPO_ROOT)} is not Python 3.10-compatible: {exc}")


if __name__ == "__main__":
    unittest.main()
