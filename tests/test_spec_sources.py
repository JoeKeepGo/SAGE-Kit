from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.check import run_check
from sagekit.packet import PacketError, _compile_packet
from sagekit.spec_sources import (
    DocumentClass,
    PUBLIC_CONTRACT_MANIFEST_VERSION,
    PUBLIC_HARNESS_API_VERSION,
    SourceConfigurationError,
    load_normalized_spec,
    package_identity,
    current_source_pointer,
    public_contract_manifest,
    resolve_active_context_path,
    resolve_doc_routing_path,
)
from tests.test_thin_execution_documents import (
    create_project,
    milestone_payload,
    phase_payload,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class SpecSourceTests(unittest.TestCase):
    def test_doc_routing_uses_configured_path_with_legacy_schema_v1_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "routing-authority-project",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "handoff/NOW.md",
                    "doc_routing": "routing/PROJECT.md",
                    "package": package_identity(),
                    "sources": {},
                },
            )
            configured = resolve_doc_routing_path(root)
            payload = json.loads((root / "SAGEKIT_CONFIG.json").read_text(encoding="utf-8"))
            del payload["doc_routing"]
            write_json(root / "SAGEKIT_CONFIG.json", payload)
            legacy = resolve_doc_routing_path(root)

        self.assertEqual(root / "routing/PROJECT.md", configured)
        self.assertEqual(root / "docs/DOC_ROUTING.md", legacy)

    def test_active_task_dispatch_requires_explicit_profile_and_records(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "profile-authority-project",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "docs/ACTIVE_CONTEXT.md",
                    "package": package_identity(),
                    "profiles": ["task-dispatch-v2"],
                    "sources": {
                        "M36": {"adapter": "thin-v1", "path": "docs/M36"}
                    },
                },
            )
            (root / "docs/ACTIVE_CONTEXT.md").write_text(
                "# Active Context\n\n- Current milestone: `M36`\n",
                encoding="utf-8",
            )
            findings = run_check(root)

        self.assertTrue(
            any(
                item.level == "FAIL" and item.rule == "active-task-dispatch"
                for item in findings
            )
        )

    def test_active_only_file_mapping_uses_normalized_container_and_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "file-mapped-profile",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "docs/ACTIVE_CONTEXT.md",
                    "package": package_identity(),
                    "profiles": ["task-dispatch-v2"],
                    "sources": {
                        "M36": {
                            "adapter": "thin-v1",
                            "path": "docs/M36/MILESTONE_MANIFEST.json",
                        }
                    },
                },
            )
            (root / "docs/ACTIVE_CONTEXT.md").write_text(
                "# Active Context\n\n- Current milestone: `M36`\n",
                encoding="utf-8",
            )

            with patch("sagekit.check.check_active_task_dispatch", return_value=[]) as dispatch:
                findings = run_check(root, gate_ready=True, mode="heavy")

        self.assertTrue(any(item.rule == "check-mode" for item in findings))
        self.assertFalse(any(item.rule == "required-docs" for item in findings))
        self.assertEqual(root / "docs/M36", dispatch.call_args.args[2])
        self.assertTrue(dispatch.call_args.kwargs["gate_ready"])

    def test_active_check_uses_explicit_manifest_for_history_source_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            history = root / "docs/history/M36"
            history.parent.mkdir(parents=True)
            shutil.move(str(root / "docs/M36"), history)
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "external-history-authority",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "docs/ACTIVE_CONTEXT.md",
                    "package": package_identity(),
                    "sources": {
                        "M36": {"adapter": "thin-v1", "path": "docs/history/M36"}
                    },
                },
            )
            (root / "docs/ACTIVE_CONTEXT.md").write_text(
                "# Active Context\n\n- Current milestone: `M36`\n",
                encoding="utf-8",
            )
            manifest = workspace / "scope.json"
            write_json(
                manifest,
                {
                    "schema_version": 1,
                    "active_containers": [],
                    "accepted_legacy_containers": [
                        {
                            "id": "M36",
                            "path": "docs/history/M36",
                            "contract_version": 1,
                            "supersedes": [],
                        }
                    ],
                    "authority": {
                        "source": "project-owner migration acceptance",
                        "approved_by": "project-owner",
                        "approved_at": "2026-01-01T00:00:00Z",
                        "baseline_head": "0" * 40,
                    },
                },
            )

            findings = run_check(root, scope_manifest_path=manifest)

        active_spec = [item for item in findings if item.rule == "active-spec"]
        self.assertEqual("FAIL", active_spec[0].level)
        self.assertIn("accepted history is non-executable", active_spec[0].message)
    def test_active_context_source_pointer_accepts_canonical_and_legacy_labels(self):
        for label in ("Current SPEC source", "Current source", "Active SPEC source"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                root = workspace / "project"
                contracts = workspace / "contracts"
                create_project(root, contracts)
                source = root / "specs/current"
                source.parent.mkdir(parents=True)
                shutil.move(str(root / "docs/M36"), source)
                write_json(
                    root / "SAGEKIT_CONFIG.json",
                    {
                        "schema_version": 1,
                        "project_id": "source-pointer-project",
                        "adoption_profile": "package-bound",
                        "execution_scope": "active-only",
                        "active_context": "docs/ACTIVE_CONTEXT.md",
                        "package": package_identity(),
                        "sources": {},
                    },
                )
                (root / "docs/ACTIVE_CONTEXT.md").write_text(
                    f"# Active Context\n\nCurrent milestone: M36\n{label}: specs/current\n",
                    encoding="utf-8",
                )

                normalized = load_normalized_spec(
                    root, "M36"
                )

            self.assertEqual("active-context", normalized.provenance.authority)
            self.assertEqual("M36", normalized.project.milestone.milestone_id)

    def test_active_context_source_pointer_ignores_examples_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "docs/ACTIVE_CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text(
                "# Active Context\n\n"
                "<!-- Current source: docs/commented -->\n"
                "```markdown\nCurrent source: docs/example\n```\n"
                "Current source: specs/current\n",
                encoding="utf-8",
            )

            self.assertEqual("specs/current", current_source_pointer(root))

            context.write_text(
                "Current source: specs/one\nCurrent source: specs/two\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SourceConfigurationError, "conflicting"):
                current_source_pointer(root)

    def test_configured_source_mapping_reconciles_active_context_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "source-reconciliation-project",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "docs/ACTIVE_CONTEXT.md",
                    "package": package_identity(),
                    "sources": {
                        "M36": {"adapter": "thin-v1", "path": "docs/M36"}
                    },
                },
            )
            context = root / "docs/ACTIVE_CONTEXT.md"
            context.write_text(
                "Current milestone: M36\nCurrent source: docs/M36\n",
                encoding="utf-8",
            )

            normalized = load_normalized_spec(root, "M36")

            self.assertEqual("project-config", normalized.provenance.authority)
            context.write_text(
                "Current milestone: M36\nCurrent source: docs/other\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SourceConfigurationError, "conflicts"):
                load_normalized_spec(root, "M36")

    def test_explicitly_classified_accepted_history_is_not_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            history = root / "docs/history/M36"
            history.parent.mkdir(parents=True)
            shutil.move(str(root / "docs/M36"), history)
            write_json(
                root / "docs/SAGE_VALIDATION_SCOPE.json",
                {
                    "schema_version": 1,
                    "active_containers": [],
                    "accepted_legacy_containers": [
                        {
                            "id": "M36",
                            "path": "docs/history/M36",
                            "contract_version": 1,
                        }
                    ],
                    "authority": {
                        "source": "accepted closeout",
                        "approved_by": "project owner",
                        "approved_at": "2026-07-21T00:00:00Z",
                        "baseline_head": "a" * 40,
                    },
                },
            )

            with self.assertRaisesRegex(
                SourceConfigurationError, "accepted history is non-executable"
            ):
                load_normalized_spec(
                    root,
                    "M36",
                    source=Path("docs/history/M36"),
                )

    def test_public_contract_binding_ignores_unrelated_files_but_tracks_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            package_root = Path(directory) / "sagekit"
            for relative in (
                "resources/contracts/v2/policy.json",
                "resources/execution_documents/v1/contract.json",
                "resources/resource_governance/conservative.json",
            ):
                path = package_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"contract": 1}\n', encoding="utf-8")

            first = package_identity(package_root)
            manifest = public_contract_manifest(package_root)
            unrelated_doc = package_root / "resources/docs/README.md"
            unrelated_doc.parent.mkdir(parents=True)
            unrelated_doc.write_text("ordinary documentation\n", encoding="utf-8")
            (package_root / "unrelated_implementation.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            after_unrelated_change = package_identity(package_root)
            contract = package_root / "resources/execution_documents/v1/contract.json"
            contract.write_text('{"contract": 2}\n', encoding="utf-8")
            after_contract_change = package_identity(package_root)

        self.assertEqual(PUBLIC_CONTRACT_MANIFEST_VERSION, first["version"])
        self.assertEqual(
            PUBLIC_HARNESS_API_VERSION, manifest["public_api_version"]
        )
        self.assertEqual(first, after_unrelated_change)
        self.assertNotEqual(first["digest"], after_contract_change["digest"])

    def test_explicit_source_and_configuration_no_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "specs/current"
            source.parent.mkdir(parents=True)
            shutil.move(str(root / "docs/M36"), source)

            packet = _compile_packet(
                root,
                "M36",
                "P2",
                source=Path("specs/current"),
            )
            normalized = load_normalized_spec(
                root,
                "M36",
                source=Path("specs/current"),
            )

            with self.assertRaises(PacketError) as caught:
                _compile_packet(
                    root,
                    "M36",
                    "P2",
                    source=Path("missing"),
                )

        self.assertFalse(normalized.provenance.legacy_fallback)
        for expected in (
            "target root:",
            "selected adapter:",
            "configured source:",
            "legacy fallback enabled: false",
        ):
            self.assertIn(expected, str(caught.exception))

    def test_arbitrary_thin_source_compiles_and_relocation_is_semantically_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            first_source = root / "product/specs/current"
            first_source.parent.mkdir(parents=True)
            shutil.move(str(root / "docs/M36"), first_source)

            first = _compile_packet(
                root,
                "M36",
                "P2",
                source=Path("product/specs/current"),
            )
            normalized_first = load_normalized_spec(
                root,
                "M36",
                source=Path("product/specs/current"),
            )
            second_source = root / "decisions/active-spec"
            second_source.parent.mkdir(parents=True)
            shutil.move(str(first_source), second_source)
            second = _compile_packet(
                root,
                "M36",
                "P2",
                source=Path("decisions/active-spec"),
            )
            normalized_second = load_normalized_spec(
                root,
                "M36",
                source=Path("decisions/active-spec"),
            )

        self.assertEqual(normalized_first.semantic_digest, normalized_second.semantic_digest)
        self.assertEqual(first.digest, second.digest)
        first_identity = dict(first.payload)
        second_identity = dict(second.payload)
        first_provenance = first_identity.pop("source_provenance")
        second_provenance = second_identity.pop("source_provenance")
        self.assertEqual(first_identity, second_identity)
        self.assertEqual(first.payload["source_authority"], second.payload["source_authority"])
        self.assertNotEqual(first_provenance, second_provenance)
        self.assertNotEqual(
            normalized_first.provenance.canonical_path,
            normalized_second.provenance.canonical_path,
        )

    def test_explicit_missing_source_never_falls_back_to_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)

            with self.assertRaises(SourceConfigurationError) as caught:
                load_normalized_spec(
                    root,
                    "M36",
                    source=Path("missing/spec"),
                )

        message = str(caught.exception)
        for expected in (
            "target root:",
            "selected adapter:",
            "configured source:",
            "resolved canonical path:",
            "missing semantic input:",
            "legacy fallback enabled: false",
        ):
            self.assertIn(expected, message)

    def test_configured_source_rejects_traversal_and_windows_alias_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            base = {
                "schema_version": 1,
                "project_id": "synthetic-source-project",
                "adoption_profile": "package-bound",
                "execution_scope": "active-only",
                "active_context": "docs/ACTIVE_CONTEXT.md",
                "package": package_identity(),
                "sources": {
                    "M36": {"adapter": "thin-v1", "path": "../outside"}
                },
            }
            write_json(root / "SAGEKIT_CONFIG.json", base)
            with self.assertRaisesRegex(SourceConfigurationError, "normalized target-relative"):
                load_normalized_spec(root, "M36")
            base["sources"]["M36"]["path"] = "C:/project/spec"
            write_json(root / "SAGEKIT_CONFIG.json", base)
            with self.assertRaisesRegex(SourceConfigurationError, "normalized target-relative"):
                load_normalized_spec(root, "M36")

    def test_legacy_docs_milestone_remains_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)

            normalized = load_normalized_spec(
                root, "M36"
            )
            packet = _compile_packet(root, "M36", "P2")

        self.assertEqual("legacy-thin-v1", normalized.provenance.adapter)
        self.assertTrue(normalized.provenance.legacy_fallback)
        self.assertEqual("M36", packet.payload["target"]["milestone_id"])

    def test_markdown_source_reads_one_explicit_normalized_spec_block(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "product/M36-spec.md"
            payload = {
                "milestone": milestone_payload(),
                "phases": {
                    "P1": {**phase_payload("P1", []), "state": "complete"},
                    "P2": phase_payload("P2", ["P1"], "WRITE_AUTHORIZED"),
                },
            }
            source.parent.mkdir(parents=True)
            source.write_text(
                "# Product milestone\n\n```sagekit-spec\n"
                + json.dumps(payload, indent=2)
                + "\n```\n",
                encoding="utf-8",
            )

            normalized = load_normalized_spec(
                root,
                "M36",
                source=Path("product/M36-spec.md"),
            )
            packet = _compile_packet(
                root,
                "M36",
                "P2",
                source=Path("product/M36-spec.md"),
            )

        self.assertEqual("markdown-v1", normalized.provenance.adapter)
        self.assertEqual("M36", packet.payload["target"]["milestone_id"])

    def test_project_mapping_and_custom_active_context_path_are_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "specs/now"
            source.parent.mkdir(parents=True)
            shutil.move(str(root / "docs/M36"), source)
            write_json(
                root / "SAGEKIT_CONFIG.json",
                {
                    "schema_version": 1,
                    "project_id": "synthetic-mapped-project",
                    "adoption_profile": "package-bound",
                    "execution_scope": "active-only",
                    "active_context": "handoff/NOW.md",
                    "package": package_identity(),
                    "sources": {
                        "M36": {"adapter": "thin-v1", "path": "specs/now"}
                    },
                },
            )
            active_context = root / "handoff/NOW.md"
            active_context.parent.mkdir(parents=True)
            active_context.write_text(
                "# Active Context\n\nCurrent milestone: M36\nCurrent source: specs/now\n",
                encoding="utf-8",
            )

            normalized = load_normalized_spec(root, "M36")
            resolved_active_context = resolve_active_context_path(root)
            before_digest = normalized.semantic_digest
            active_context.write_text(
                "# Active Context\n\n"
                "Current milestone: M36\n"
                "Current state: review\n"
                "Next action: hand off targeted evidence\n",
                encoding="utf-8",
            )
            after_status_update = load_normalized_spec(
                root, "M36"
            )
            authority = json.loads(
                (root / "SAGEKIT_CONFIG.json").read_text(encoding="utf-8")
            )
            authority["project_id"] = "renamed-synthetic-project"
            write_json(root / "SAGEKIT_CONFIG.json", authority)
            after_authority_update = load_normalized_spec(
                root, "M36"
            )

        self.assertEqual(active_context.resolve(), resolved_active_context)
        self.assertEqual("configured-thin-v1", normalized.provenance.adapter)
        self.assertFalse(normalized.provenance.legacy_fallback)
        self.assertEqual(DocumentClass.ACTIVE_SPEC, normalized.document_class)
        self.assertIsNotNone(normalized.active_context)
        self.assertEqual("M36", normalized.active_context.current_milestone)
        self.assertEqual(before_digest, after_status_update.semantic_digest)
        self.assertNotEqual(
            before_digest, after_authority_update.semantic_digest,
            "project authority is part of execution identity",
        )
        self.assertEqual("review", after_status_update.active_context.current_state)

    def test_malformed_markdown_fails_closed_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "spec.md"
            source.write_text("# Missing semantic block\n", encoding="utf-8")
            before = source.read_bytes()

            with self.assertRaisesRegex(PacketError, "sagekit-spec|semantic"):
                _compile_packet(root, "M36", source=source)

            self.assertEqual(before, source.read_bytes())
            self.assertFalse((root / ".sagekit").exists())

    def test_normalized_spec_preserves_more_than_eight_phases_and_waves(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            phase_ids = [f"P{index}" for index in range(1, 13)]
            milestone = milestone_payload()
            milestone["phase_ids"] = phase_ids
            milestone["dependency_dag"] = {phase_id: [] for phase_id in phase_ids}
            milestone["approval_gates"] = []
            phases = {
                phase_id: phase_payload(phase_id, []) for phase_id in phase_ids
            }
            waves = [
                {"id": f"W{index}", "depends_on": [], "phase_ids": [f"P{index}"]}
                for index in range(1, 13)
            ]
            source = root / "planning/deep-plan.md"
            source.parent.mkdir(parents=True)
            source.write_text(
                "# Deep plan\n\n```sagekit-spec\n"
                + json.dumps(
                    {"milestone": milestone, "phases": phases, "waves": waves},
                    indent=2,
                )
                + "\n```\n",
                encoding="utf-8",
            )

            normalized = load_normalized_spec(
                root, "M36", source=source
            )
            packet = _compile_packet(
                root, "M36", source=source
            )

        self.assertEqual(12, len(normalized.waves))
        self.assertEqual(12, len(normalized.project.phases))
        self.assertEqual(12, len(packet.payload["scope"]["waves"]))

    def test_phase_packet_reads_only_target_and_exact_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            milestone_path = root / "docs/M36/MILESTONE_MANIFEST.json"
            milestone = json.loads(milestone_path.read_text(encoding="utf-8"))
            milestone["phase_ids"].append("P9")
            milestone["dependency_dag"]["P9"] = []
            write_json(milestone_path, milestone)
            unrelated = root / "docs/M36/phases/P9.json"
            unrelated.write_text("{ invalid unrelated phase }\n", encoding="utf-8")

            packet = _compile_packet(
                root, "M36", "P2"
            )
            with self.assertRaises(PacketError):
                _compile_packet(root, "M36")

        self.assertEqual("P2", packet.payload["target"]["phase_id"])


if __name__ == "__main__":
    unittest.main()
