from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sagekit.check import run_check
from sagekit.candidate import (
    CandidateFingerprint,
    assess_candidate_snapshot,
    collect_repository_snapshot,
    freeze_candidate,
)
from sagekit.packet import compile_packet
from sagekit.spec_sources import load_normalized_spec, package_identity
from tests.test_thin_execution_documents import create_project
from tests.test_validation_scope_manifest import (
    manifest_payload,
    record_pair,
    write_dispatch_pair,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def configure_active(root: Path) -> None:
    source = root / "specs/current"
    source.parent.mkdir(parents=True)
    shutil.move(str(root / "docs/M36"), source)
    identity = package_identity()
    write_json(
        root / "SAGEKIT_CONFIG.json",
        {
            "schema_version": 1,
            "project_id": "synthetic-active-project",
            "adoption_profile": "package-bound",
            "execution_scope": "active-only",
            "active_context": "handoff/ACTIVE.md",
            "package": identity,
            "sources": {"M36": {"adapter": "thin-v1", "path": "specs/current"}},
        },
    )
    context = root / "handoff/ACTIVE.md"
    context.parent.mkdir(parents=True)
    context.write_text(
        """# Active Context

Current milestone: M36
Current wave/phase: W1 / P2
Current state: active
Current authority: project config
Blockers: none
Next action: compile the active packet
Key decisions: use the package-bound runtime
Evidence/closeout pointers: docs/evidence/M36.md
""",
        encoding="utf-8",
    )


def stable_findings(findings):
    return [
        (item.level, item.rule, item.path, item.message)
        for item in findings
        if item.rule != "project-root"
    ]


class ActiveScopeTests(unittest.TestCase):
    def test_active_check_is_read_only_and_creates_no_runtime_state(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            configure_active(root)
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            findings = run_check(root)

            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

        self.assertFalse(any(item.level == "FAIL" for item in findings), findings)
        self.assertEqual(before, after)
        self.assertNotIn(".sagekit", {Path(item).parts[0] for item in after})

    def test_default_check_ignores_accepted_history_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            configure_active(root)

            before = stable_findings(run_check(root))
            history = root / "docs/accepted-history"
            history.mkdir(parents=True)
            for index in range(1000):
                (history / f"old-{index:04d}.json").write_text(
                    "{ definitely not a current schema }\n", encoding="utf-8"
                )
            after = stable_findings(run_check(root))

        self.assertEqual(before, after)
        self.assertFalse(any(item[0] == "FAIL" for item in after), after)

    def test_active_source_error_remains_strict_and_aggregated(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            configure_active(root)
            (root / "specs/current/MILESTONE_MANIFEST.json").write_text(
                "{}\n", encoding="utf-8"
            )

            findings = run_check(root)
            failures = [item for item in findings if item.level == "FAIL"]

        self.assertEqual(1, len(failures), failures)
        self.assertEqual("active-spec", failures[0].rule)

    def test_history_prose_does_not_change_current_semantic_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            configure_active(root)
            before = load_normalized_spec(root, "M36", contract_root=contracts)
            packet_before = compile_packet(root, "M36", contract_root=contracts)
            historical = root / "docs/accepted-history/decision.md"
            historical.parent.mkdir(parents=True)
            historical.write_text("old wording\n", encoding="utf-8")
            historical.write_text("new wording\n", encoding="utf-8")
            after = load_normalized_spec(root, "M36", contract_root=contracts)
            packet_after = compile_packet(root, "M36", contract_root=contracts)

        self.assertEqual(before.semantic_digest, after.semantic_digest)
        self.assertEqual(packet_before.digest, packet_after.digest)

    def test_history_audit_is_explicit_and_selects_frozen_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            configure_active(root)
            task, evidence = record_pair(explicit_version=None)
            write_dispatch_pair(root, "M1", task, evidence)
            write_json(
                root / "docs/SAGE_VALIDATION_SCOPE.json",
                manifest_payload(accepted=("M1",), contract_version=0),
            )

            current = run_check(root)
            history = run_check(root, scope="history")
            all_scope = run_check(root, scope="all")

        self.assertFalse(any(item.path and "docs/M1/" in item.path for item in current), current)
        self.assertTrue(
            any(
                item.rule == "validation-contract"
                and "selected v0" in item.message
                and "immutable legacy history" in item.message
                for item in history
            ),
            history,
        )
        self.assertTrue(
            any(item.rule == "validation-contract" and item.path and "docs/M1/" in item.path for item in all_scope),
            all_scope,
        )

    def test_historical_dispatch_records_do_not_join_current_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            configure_active(root)
            task, evidence = record_pair(explicit_version=None)
            write_dispatch_pair(root, "M1", task, evidence, name="first")
            write_dispatch_pair(root, "M1", task, evidence, name="second")

            findings = run_check(root)

        self.assertFalse(
            any(
                item.rule
                in {
                    "task-dispatch-duplicate-id",
                    "task-dispatch-lock-conflict",
                    "task-dispatch-lease-conflict",
                }
                for item in findings
            ),
            findings,
        )

    def test_active_spec_candidate_ignores_history_but_invalidates_on_spec_change(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            configure_active(root)
            for command in (
                ("git", "init"),
                ("git", "config", "user.email", "fixture@example.invalid"),
                ("git", "config", "user.name", "Fixture"),
                ("git", "add", "."),
                ("git", "commit", "-m", "fixture"),
            ):
                subprocess.run(
                    command,
                    cwd=root,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            initial = collect_repository_snapshot(
                root,
                snapshot_mode="active-spec",
                active_milestone_id="M36",
            )
            frozen = freeze_candidate(
                root,
                contract_digest="contract",
                dependency_digest=initial.active_spec_digest,
                review_closed=True,
                corrective_batch_closed=True,
                snapshot_mode="active-spec",
                active_milestone_id="M36",
            )
            self.assertTrue(frozen.ok, frozen)
            self.assertIsNotNone(frozen.candidate)
            self.assertEqual(5, frozen.candidate.fingerprint_version)
            candidate = CandidateFingerprint.from_dict(frozen.candidate.to_dict())
            history = root / "docs/accepted-history/decision.md"
            history.parent.mkdir(parents=True)
            history.write_text("updated historical wording\n", encoding="utf-8")
            after_history = collect_repository_snapshot(
                root,
                snapshot_mode="active-spec",
                active_milestone_id="M36",
            )
            history_assessment = assess_candidate_snapshot(
                after_history,
                candidate,
                contract_digest="contract",
                dependency_digest=initial.active_spec_digest,
            )
            manifest = root / "specs/current/MILESTONE_MANIFEST.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["objective"] = "A changed active objective."
            write_json(manifest, payload)
            after_active_change = collect_repository_snapshot(
                root,
                snapshot_mode="active-spec",
                active_milestone_id="M36",
            )
            active_assessment = assess_candidate_snapshot(
                after_active_change,
                candidate,
                contract_digest="contract",
                dependency_digest=initial.active_spec_digest,
            )

        self.assertTrue(history_assessment.ok, history_assessment)
        self.assertFalse(active_assessment.ok, active_assessment)
        self.assertTrue(
            any("active SPEC digest differs" in item for item in active_assessment.mismatches),
            active_assessment,
        )

    def test_ambiguous_active_authority_is_one_finding_not_a_storm(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            identity = package_identity()
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "synthetic-ambiguous-project",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "handoff/ACTIVE.md",
                    "package": identity,
                    "sources": {
                        "M10": {"adapter": "thin-v1", "path": "specs/a"},
                        "M11": {"adapter": "thin-v1", "path": "specs/b"},
                    },
                },
            )
            context = root / "handoff/ACTIVE.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Active Context\n\nCurrent state: active\n", encoding="utf-8")
            for index in range(100):
                path = root / f"docs/history-{index}/bad.json"
                path.parent.mkdir(parents=True)
                path.write_text("not json\n", encoding="utf-8")

            findings = run_check(root)
            failures = [item for item in findings if item.level == "FAIL"]

        self.assertEqual(1, len(failures), failures)
        self.assertEqual("active-authority", failures[0].rule)

    def test_empty_active_is_valid_only_with_equivalent_package_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            identity = package_identity()
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "synthetic-empty-project",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "ACTIVE.md",
                    "package": identity,
                    "sources": {},
                },
            )
            (root / "ACTIVE.md").write_text(
                "# Active Context\n\nCurrent milestone: none\nCurrent state: idle\n",
                encoding="utf-8",
            )
            valid = run_check(root)
            payload = json.loads((root / "SAGEKIT_CONFIG.json").read_text(encoding="utf-8"))
            payload["package"]["digest"] = "0" * 64
            write_json(root / "SAGEKIT_CONFIG.json", payload)
            invalid = run_check(root)

        self.assertFalse(any(item.level == "FAIL" for item in valid), valid)
        self.assertTrue(
            any(item.level == "FAIL" and item.rule == "package-authority" for item in invalid),
            invalid,
        )


if __name__ == "__main__":
    unittest.main()
