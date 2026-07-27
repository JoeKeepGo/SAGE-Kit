from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from sagekit.compatibility import ContractScope, validate_compatible_records
from sagekit.harness import check_project
from sagekit.milestone_scope import MilestoneScope, MilestoneScopeKind
from sagekit.spec_sources import load_source_config, package_identity
from sagekit.task_dispatch_validator import load_record
from sagekit.validation_contracts.v1 import contract_metadata as v1_metadata


REPO_ROOT = Path(os.environ.get("STAGE8_COMPATIBILITY_ROOT", Path(__file__).resolve().parents[1])).resolve()
TEMPLATE_ROOT = REPO_ROOT / "docs/profiles/task-dispatch/templates"
MAP_PATH = "docs/design/rebuild/STAGE_8_COMPATIBILITY_MAP.json"

MIRROR_PAIRS = (
    ("docs/SAGE_CORE.md", "sagekit/resources/docs/SAGE_CORE.md"),
    (
        "docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md",
        "sagekit/resources/docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md",
    ),
    (
        "docs/profiles/control-plane-agent/BOUNDARY_TEMPLATE.md",
        "sagekit/resources/docs/profiles/control-plane-agent/BOUNDARY_TEMPLATE.md",
    ),
    (
        "docs/profiles/task-dispatch/DISPATCH_PROFILE.md",
        "sagekit/resources/docs/profiles/task-dispatch/DISPATCH_PROFILE.md",
    ),
    (
        "docs/profiles/task-dispatch/README.md",
        "sagekit/resources/docs/profiles/task-dispatch/README.md",
    ),
    (
        "docs/templates/ROADMAP_TEMPLATE.md",
        "sagekit/resources/docs/templates/ROADMAP_TEMPLATE.md",
    ),
)

FROZEN_RESOURCES = tuple(
    f"sagekit/resources/contracts/v{version}/{name}"
    for version in (0, 1)
    for name in (
        "evidence.schema.json",
        "policy.json",
        "rules.json",
        "task.schema.json",
        "validator.json",
    )
)

# Fixed release fixtures make this oracle independent of Git history and the
# current checkout. Frozen sidecars and policies then bind their JSON artifacts.
FROZEN_RESOURCE_RAW_SHA256 = {
    "sagekit/resources/contracts/v0/evidence.schema.json": "1c788b96fecaa56c9bf7de526bb2ac3bfe79e2d926b5e7cd313a07d6924c5f87",
    "sagekit/resources/contracts/v0/policy.json": "9aeea9bdda5aa6f2ff7c5562f08c49e41f62f6e46cc578f9410293e2cde3e3e1",
    "sagekit/resources/contracts/v0/rules.json": "73672a9dbe994c9c4b2f0a7b0679cd201bccdc9bc98b6e5ec54a3a9e65b5632c",
    "sagekit/resources/contracts/v0/task.schema.json": "459d31b0b93d465757202c93094be49b416be85f186ebfad6c469b1d452ba60c",
    "sagekit/resources/contracts/v0/validator.json": "be340863381493ae35e0ad27d3d34aa943940948704a1acc08389bfec7c90a58",
    "sagekit/resources/contracts/v1/evidence.schema.json": "f6c2f6e12be0066b4e82cc4c7e52433cf41dc1b806d8486681aa3e39046902e6",
    "sagekit/resources/contracts/v1/policy.json": "a6c8eae5fce2ae67a35382ec6b28e8c60ffde2407234bcc7027798d5fce746be",
    "sagekit/resources/contracts/v1/rules.json": "4ae8d23e11e6627fda3672c9fe51ec9b63de582056b4906ab0307612f4db905f",
    "sagekit/resources/contracts/v1/task.schema.json": "82502099f5b754e4257e95c21189b8ee438f3088f0cefa7b8b60a514d440c6a6",
    "sagekit/resources/contracts/v1/validator.json": "493668554b9cb7016d3f6985703a8166267256ab9f1ab32b3512f66f1832b16c",
}

STABLE_MAP_IDS = {
    "COMPAT-CONTRACT-V0",
    "COMPAT-CONTRACT-V1",
    "COMPAT-CONTRACT-V2",
    "COMPAT-CONTRACT-V2-PLUS",
    "COMPAT-SCOPE-CLASSIFICATION",
    "COMPAT-AUTHORITY-PRECEDENCE",
    "COMPAT-HOST-UPPER-BOUND",
    "COMPAT-EXPLICIT-FAILURE-NO-FALLBACK",
    "COMPAT-MIXED-AMBIGUOUS-FAIL-CLOSED",
    "COMPAT-TASK-DISPATCH-OPTIONAL",
    "COMPAT-LEGACY-ALIASES",
    "COMPAT-PLANNING-GRANULARITY",
    "COMPAT-STAGE2-TO-STAGE7-OPTIONAL",
    "COMPAT-REMOVED-DEPRECATED-SURFACES",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_digest(payload: object) -> str:
    return sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def active_pair() -> tuple[dict, dict]:
    task = load_record(TEMPLATE_ROOT / "TASK_RECORD_TEMPLATE.yaml")
    evidence = load_record(TEMPLATE_ROOT / "EVIDENCE_RECORD_TEMPLATE.yaml")
    task["id"] = "TASK-STAGE8-ACTIVE"
    evidence["task_id"] = task["id"]
    return task, evidence


def accepted_history_pair() -> tuple[dict, dict]:
    task, evidence = active_pair()
    task["id"] = "TASK-STAGE8-HISTORY"
    evidence["task_id"] = task["id"]
    task["status"] = "CLOSED"
    task["lifecycle"].update(
        {
            "phase": "closed",
            "review_result": "ACCEPTABLE",
            "next_action": "history remains immutable",
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
        {"status": "PASS", "evidence": ["accepted evidence"], "reason": None}
    )
    evidence["conclusion"].update(
        {
            "status": "VERIFIED",
            "highest_level": "L0",
            "review_result": "ACCEPTABLE",
            "next_action": "history remains immutable",
        }
    )
    task["validation_contract"] = v1_metadata()
    evidence["validation_contract"] = v1_metadata()
    return task, evidence


def immutable_history_scope() -> MilestoneScope:
    return MilestoneScope(
        "M8-HISTORY",
        MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
        ("test manifest accepted immutable container",),
        "test accepted immutable history scope",
        contract_version=1,
        container_path="docs/M8-HISTORY",
    )


class Stage8CompatibilityTests(unittest.TestCase):
    def assert_auditable_location(self, reference: dict, *, label: str) -> None:
        path = reference.get("path")
        self.assertIsInstance(path, str, label)
        self.assertFalse(Path(path).is_absolute(), label)
        location = REPO_ROOT / path
        self.assertTrue(location.is_file(), label)

        identifier = reference.get("identifier")
        self.assertIsInstance(identifier, dict, label)
        kind = identifier.get("kind")
        value = identifier.get("value")
        self.assertIsInstance(value, str, label)
        self.assertTrue(value, label)
        if kind == "markdown-heading":
            self.assertRegex(
                location.read_text(encoding="utf-8"),
                rf"(?m)^#+ {re.escape(value)}\s*$",
                label,
            )
        elif kind == "text":
            self.assertIn(value, location.read_text(encoding="utf-8"), label)
        elif kind == "json-field":
            field = identifier.get("field")
            self.assertIsInstance(field, str, label)
            self.assertEqual(value, json.loads(location.read_text(encoding="utf-8"))[field], label)
        else:
            self.fail(f"{label}: unsupported identifier kind {kind!r}")

        digest = reference.get("digest")
        if digest is not None:
            self.assertEqual({"algorithm", "canonical_json", "value"}, set(digest), label)
            self.assertEqual("sha256", digest["algorithm"], label)
            self.assertTrue(digest["canonical_json"], label)
            self.assertEqual(
                digest["value"],
                canonical_json_digest(json.loads(location.read_text(encoding="utf-8"))),
                label,
            )

    def test_map_has_complete_stable_auditable_entries(self) -> None:
        payload = json.loads((REPO_ROOT / MAP_PATH).read_text(encoding="utf-8"))

        self.assertEqual("spec.compatibility-map.v1", payload["schema_id"])
        self.assertEqual("stage-8a-compatibility-map", payload["map_id"])
        self.assertEqual(payload["map_id"], payload["stage_owner"])
        entries = payload["compatibility_entries"]
        self.assertEqual(STABLE_MAP_IDS, {entry["id"] for entry in entries})
        evidence_catalog = {item["id"]: item for item in payload["evidence_catalog"]}
        self.assertEqual(len(entries), len({entry["id"] for entry in entries}))
        for entry in entries:
            self.assertTrue(
                {"id", "owner", "status", "compatibility_rule", "evidence_refs", "stage_owner"}
                <= set(entry),
                entry,
            )
            self.assertEqual(payload["stage_owner"], entry["stage_owner"])
            self.assert_auditable_location(entry["owner"], label=entry["id"])
            self.assertTrue(set(entry["evidence_refs"]) <= set(evidence_catalog), entry["id"])
        for evidence_id, evidence in evidence_catalog.items():
            self.assert_auditable_location(evidence, label=evidence_id)

    def test_document_sources_and_packaged_mirrors_are_byte_identical(self) -> None:
        for source, mirror in MIRROR_PAIRS:
            with self.subTest(source=source):
                self.assertEqual(
                    (REPO_ROOT / source).read_bytes(),
                    (REPO_ROOT / mirror).read_bytes(),
                )

    def test_frozen_v0_v1_resources_match_hermetic_release_oracle(self) -> None:
        self.assertEqual(set(FROZEN_RESOURCES), set(FROZEN_RESOURCE_RAW_SHA256))
        for relative, expected_digest in FROZEN_RESOURCE_RAW_SHA256.items():
            with self.subTest(resource=relative):
                current_blob = (REPO_ROOT / relative).read_bytes()
                self.assertEqual(expected_digest, sha256_bytes(current_blob))

        for version in (0, 1):
            root = REPO_ROOT / f"sagekit/resources/contracts/v{version}"
            policy = json.loads((root / "policy.json").read_text(encoding="utf-8"))
            rules = json.loads((root / "rules.json").read_text(encoding="utf-8"))
            sidecar = json.loads((root / "validator.json").read_text(encoding="utf-8"))
            self.assertEqual(canonical_json_digest(policy), sidecar["policy_sha256"])
            self.assertEqual(canonical_json_digest(rules), sidecar["validator_rules_sha256"])
            for name, digest in policy["schema_sha256"].items():
                schema = json.loads((root / name).read_text(encoding="utf-8"))
                self.assertEqual(digest, canonical_json_digest(schema))

    def test_current_v2_invalid_and_ambiguous_records_fail_closed(self) -> None:
        task, evidence = active_pair()
        evidence["task_id"] = "TASK-OTHER"
        selected_v2 = validate_compatible_records(
            task, evidence, container_scope=immutable_history_scope()
        )
        self.assertEqual(2, selected_v2.selection.version)
        self.assertEqual(ContractScope.ACTIVE, selected_v2.selection.scope)
        self.assertTrue(selected_v2.errors)

        task, evidence = active_pair()
        evidence.pop("validation_contract")
        mixed = validate_compatible_records(task, evidence)
        self.assertIsNone(mixed.selection)
        self.assertTrue(mixed.errors)
        self.assertTrue(mixed.active_reconciliation)

        task, evidence = active_pair()
        ambiguous = MilestoneScope(
            "M8", MilestoneScopeKind.AMBIGUOUS, (), "ambiguous test container"
        )
        result = validate_compatible_records(task, evidence, container_scope=ambiguous)
        self.assertEqual(2, result.selection.version)
        self.assertIn("ambiguous test container", result.errors)
        self.assertTrue(result.active_reconciliation)

    def test_accepted_immutable_history_stays_out_of_active_reconciliation(self) -> None:
        task, evidence = accepted_history_pair()
        result = validate_compatible_records(
            task, evidence, container_scope=immutable_history_scope()
        )

        self.assertEqual(1, result.selection.version)
        self.assertEqual(ContractScope.CLOSED_LEGACY, result.selection.scope)
        self.assertFalse(result.active_reconciliation)
        self.assertFalse(result.errors, result.errors)

    def test_presence_does_not_activate_task_dispatch_or_stage2_to_7_surfaces(self) -> None:
        stage_resources = (
            "sagekit/resources/contracts/graph/v1/contract.json",
            "sagekit/resources/contracts/runtime-state/v1/contract.json",
            "sagekit/resources/contracts/ready-resolution/v1/contract.json",
            "sagekit/resources/contracts/evidence-lineage/v1/contract.json",
            "sagekit/resources/contracts/graph-evolution/v1/contract.json",
            "sagekit/resources/contracts/transition-resolution/v1/contract.json",
        )
        for relative in stage_resources:
            self.assertTrue((REPO_ROOT / relative).is_file(), relative)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/profiles/task-dispatch").mkdir(parents=True)
            (root / "docs/profiles/task-dispatch/task.yaml").write_text("{}\n", encoding="utf-8")
            (root / "docs/history/M8/dispatch").mkdir(parents=True)
            (root / "docs/history/M8/dispatch/task.yaml").write_text("id: HISTORY-ONLY\n", encoding="utf-8")
            (root / "docs/history/M8/dispatch/evidence.yaml").write_text("task_id: HISTORY-ONLY\n", encoding="utf-8")
            (root / "sagekit/resources/contracts/v2").mkdir(parents=True)
            (root / "sagekit/resources/contracts/v2/policy.json").write_text("{}\n", encoding="utf-8")
            (root / "docs/ACTIVE_CONTEXT.md").write_text(
                "# Active Context\n\n- Current milestones: none\n",
                encoding="utf-8",
            )
            (root / "docs/DOC_ROUTING.md").write_text(
                "# Routing Policy\n\nRead the Task Dispatch profile only when project authority adopts it.\n",
                encoding="utf-8",
            )
            for relative in (
                "docs/PROJECT_PROFILE.md",
                "docs/QUALITY_GATES.md",
                "docs/TECHNICAL_DESIGN.md",
                "docs/ENGINEERING_SYSTEM.md",
                "docs/APPROVAL_GATES.md",
                "docs/MILESTONE_ROADMAP.md",
                "docs/SAGE_CORE.md",
                "docs/agent/GOVERNANCE_LEVELS.md",
                "docs/agent/SESSION_ORCHESTRATION.md",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture authority boundary\n", encoding="utf-8")
            (root / "SAGEKIT_CONFIG.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "project_id": "presence-is-not-activation",
                        "adoption_profile": "package-bound",
                        "execution_scope": "active-only",
                        "active_context": "docs/ACTIVE_CONTEXT.md",
                        "package": package_identity(),
                        "sources": {},
                    }
                ),
                encoding="utf-8",
            )
            config = load_source_config(root, required=True)
            self.assertEqual((), config.profiles)
            for mode in ("light", "standard", "heavy"):
                with self.subTest(mode=mode):
                    result = check_project(root, mode=mode, scope="active")
                    self.assertTrue(result.ok, tuple(item.to_text() for item in result.findings))
                    self.assertFalse(
                        any("task-dispatch" in item.rule for item in result.findings),
                        tuple(item.to_text() for item in result.findings),
                    )

    def test_roadmap_boundary_depth_and_aliases_remain_pointer_only(self) -> None:
        roadmap = (REPO_ROOT / "docs/templates/MILESTONE_ROADMAP_TEMPLATE.md").read_text(encoding="utf-8")
        roadmap_alias = (REPO_ROOT / "docs/templates/ROADMAP_TEMPLATE.md").read_text(encoding="utf-8")
        boundary = (REPO_ROOT / "docs/profiles/control-plane-agent/CONTROL_BOUNDARY_TEMPLATE.md").read_text(encoding="utf-8")
        boundary_alias = (REPO_ROOT / "docs/profiles/control-plane-agent/BOUNDARY_TEMPLATE.md").read_text(encoding="utf-8")

        for field in ("## Capability Map Link", "## Overview", "## Milestones", "Required phase decomposition"):
            self.assertIn(field, roadmap)
            self.assertNotIn(field, roadmap_alias)
        self.assertIn("Milestone, Wave, Phase, and Lane", " ".join(roadmap_alias.split()))
        self.assertIn("zero-to-product", roadmap_alias)
        self.assertIn("docs/templates/MILESTONE_ROADMAP_TEMPLATE.md", roadmap_alias)
        self.assertIn("no second roadmap authority", " ".join(roadmap_alias.split()))

        for field in ("## Components", "## Trust Boundary", "## Forbidden Paths", "## Contract Owner"):
            self.assertIn(field, boundary)
            self.assertNotIn(field, boundary_alias)
        self.assertIn("docs/profiles/control-plane-agent/CONTROL_BOUNDARY_TEMPLATE.md", boundary_alias)
        self.assertIn("no second boundary authority", boundary_alias)

if __name__ == "__main__":
    unittest.main()
