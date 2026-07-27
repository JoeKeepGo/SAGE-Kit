from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from sagekit.compatibility import ContractScope, validate_compatible_records
from sagekit.milestone_scope import MilestoneScope, MilestoneScopeKind
from sagekit.modes import required_docs_for_mode
from sagekit.spec_sources import load_source_config, package_identity
from sagekit.task_dispatch_validator import load_record
from sagekit.validation_contracts.v1 import contract_metadata as v1_metadata


STAGE7_PARENT = "b7ca521f2feb58ba7441f9c354b9ac081e594bf8"
REPO_ROOT = Path(os.environ.get("STAGE8_COMPATIBILITY_ROOT", Path(__file__).resolve().parents[1])).resolve()
TEMPLATE_ROOT = REPO_ROOT / "docs/profiles/task-dispatch/templates"
MAP_PATH = "docs/design/rebuild/STAGE_8_COMPATIBILITY_MAP.json"

STAGE8_ALLOWLIST = {
    "docs/SAGE_CORE.md",
    "docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md",
    MAP_PATH,
    "docs/profiles/control-plane-agent/BOUNDARY_TEMPLATE.md",
    "docs/profiles/task-dispatch/DISPATCH_PROFILE.md",
    "docs/profiles/task-dispatch/README.md",
    "docs/templates/ROADMAP_TEMPLATE.md",
    "sagekit/resources/docs/SAGE_CORE.md",
    "sagekit/resources/docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md",
    "sagekit/resources/docs/profiles/control-plane-agent/BOUNDARY_TEMPLATE.md",
    "sagekit/resources/docs/profiles/task-dispatch/DISPATCH_PROFILE.md",
    "sagekit/resources/docs/profiles/task-dispatch/README.md",
    "sagekit/resources/docs/templates/ROADMAP_TEMPLATE.md",
    "tests/test_stage8_compatibility.py",
}

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


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    def test_map_has_complete_stable_schema_like_entries(self) -> None:
        payload = json.loads((REPO_ROOT / MAP_PATH).read_text(encoding="utf-8"))

        self.assertEqual("spec.compatibility-map.v1", payload["schema_id"])
        self.assertEqual("stage-8a-compatibility-map", payload["map_id"])
        self.assertEqual(payload["map_id"], payload["stage_owner"])
        entries = payload["compatibility_entries"]
        self.assertEqual(STABLE_MAP_IDS, {entry["id"] for entry in entries})
        evidence_ids = {item["id"] for item in payload["evidence_catalog"]}
        self.assertEqual(len(entries), len({entry["id"] for entry in entries}))
        for entry in entries:
            self.assertTrue(
                {"id", "owner_pointer", "status", "compatibility_rule", "evidence_refs", "stage_owner"}
                <= set(entry),
                entry,
            )
            self.assertEqual(payload["stage_owner"], entry["stage_owner"])
            owner_pointer = entry["owner_pointer"]
            self.assertTrue({"owner", "pointer"} <= set(owner_pointer), entry["id"])
            self.assertTrue(owner_pointer["owner"])
            self.assertGreaterEqual(len(owner_pointer["pointer"].split(".")), 2)
            self.assertTrue(set(entry["evidence_refs"]) <= evidence_ids, entry["id"])

    def test_document_sources_and_packaged_mirrors_are_byte_identical(self) -> None:
        for source, mirror in MIRROR_PAIRS:
            with self.subTest(source=source):
                self.assertEqual(
                    (REPO_ROOT / source).read_bytes(),
                    (REPO_ROOT / mirror).read_bytes(),
                )

    def test_frozen_v0_v1_resources_match_stage7_parent_blobs(self) -> None:
        for relative in FROZEN_RESOURCES:
            with self.subTest(resource=relative):
                parent_blob = subprocess.run(
                    ["git", "show", f"{STAGE7_PARENT}:{relative}"],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                ).stdout
                current_blob = (REPO_ROOT / relative).read_bytes()
                self.assertEqual(sha256_bytes(parent_blob), sha256_bytes(current_blob))
                self.assertEqual(parent_blob, current_blob)

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
        self.assertNotIn("docs/profiles/task-dispatch/DISPATCH_PROFILE.md", required_docs_for_mode("light"))
        self.assertNotIn("docs/profiles/task-dispatch/DISPATCH_PROFILE.md", required_docs_for_mode("standard"))

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

    def test_stage8_diff_is_exactly_allowlisted_and_cannot_reintroduce_a_cli(self) -> None:
        status = (
            git("diff", "--name-status", f"{STAGE7_PARENT}..HEAD").splitlines()
            + git("diff", "--cached", "--name-status").splitlines()
        )
        changed = {line.split("\t", 1)[1] for line in status}

        self.assertEqual(STAGE8_ALLOWLIST, changed)
        self.assertFalse(any(line.startswith("D\t") for line in status), status)
        self.assertFalse(any(path.startswith("scripts/") for path in changed), changed)
        self.assertFalse(any(path.endswith((".py", ".pyw")) and not path.startswith("tests/") for path in changed), changed)


if __name__ == "__main__":
    unittest.main()
