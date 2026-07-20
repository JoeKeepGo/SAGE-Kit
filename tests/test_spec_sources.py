from __future__ import annotations

import json
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout

from sagekit.cli import main
from sagekit.packet import PacketError, compile_packet
from sagekit.spec_sources import (
    DocumentClass,
    SourceConfigurationError,
    load_normalized_spec,
    package_identity,
    resolve_active_context_path,
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
    def test_cli_explicit_source_and_configuration_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "specs/current"
            source.parent.mkdir(parents=True)
            shutil.move(str(root / "docs/M36"), source)
            output = io.StringIO()
            with redirect_stdout(output):
                success = main(
                    [
                        "packet",
                        "compile",
                        "--target",
                        str(root),
                        "--milestone",
                        "M36",
                        "--phase",
                        "P2",
                        "--source",
                        "specs/current",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            error = io.StringIO()
            with redirect_stderr(error):
                missing = main(
                    [
                        "packet",
                        "compile",
                        "--target",
                        str(root),
                        "--milestone",
                        "M36",
                        "--source",
                        "missing",
                    ]
                )

        self.assertEqual(0, success)
        self.assertTrue(payload["ok"])
        self.assertEqual("explicit-source", payload["source_provenance"]["authority"])
        self.assertEqual(2, missing)
        self.assertIn("legacy fallback enabled: false", error.getvalue())

    def test_arbitrary_thin_source_compiles_and_relocation_is_semantically_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            first_source = root / "product/specs/current"
            first_source.parent.mkdir(parents=True)
            shutil.move(str(root / "docs/M36"), first_source)

            first = compile_packet(
                root,
                "M36",
                "P2",
                source=Path("product/specs/current"),
                contract_root=contracts,
            )
            normalized_first = load_normalized_spec(
                root,
                "M36",
                source=Path("product/specs/current"),
                contract_root=contracts,
            )
            second_source = root / "decisions/active-spec"
            second_source.parent.mkdir(parents=True)
            shutil.move(str(first_source), second_source)
            second = compile_packet(
                root,
                "M36",
                "P2",
                source=Path("decisions/active-spec"),
                contract_root=contracts,
            )
            normalized_second = load_normalized_spec(
                root,
                "M36",
                source=Path("decisions/active-spec"),
                contract_root=contracts,
            )

        self.assertEqual(normalized_first.semantic_digest, normalized_second.semantic_digest)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.payload, second.payload)
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
                    contract_root=contracts,
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
                load_normalized_spec(root, "M36", contract_root=contracts)
            base["sources"]["M36"]["path"] = "C:/project/spec"
            write_json(root / "SAGEKIT_CONFIG.json", base)
            with self.assertRaisesRegex(SourceConfigurationError, "normalized target-relative"):
                load_normalized_spec(root, "M36", contract_root=contracts)

    def test_legacy_docs_milestone_remains_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)

            normalized = load_normalized_spec(
                root, "M36", contract_root=contracts
            )
            packet = compile_packet(root, "M36", "P2", contract_root=contracts)

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
                contract_root=contracts,
            )
            packet = compile_packet(
                root,
                "M36",
                "P2",
                source=Path("product/M36-spec.md"),
                contract_root=contracts,
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

            normalized = load_normalized_spec(root, "M36", contract_root=contracts)
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
                root, "M36", contract_root=contracts
            )
            authority = json.loads(
                (root / "SAGEKIT_CONFIG.json").read_text(encoding="utf-8")
            )
            authority["project_id"] = "renamed-synthetic-project"
            write_json(root / "SAGEKIT_CONFIG.json", authority)
            after_authority_update = load_normalized_spec(
                root, "M36", contract_root=contracts
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
                compile_packet(root, "M36", source=source, contract_root=contracts)

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
                root, "M36", source=source, contract_root=contracts
            )
            packet = compile_packet(
                root, "M36", source=source, contract_root=contracts
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

            packet = compile_packet(
                root, "M36", "P2", contract_root=contracts
            )
            with self.assertRaises(PacketError):
                compile_packet(root, "M36", contract_root=contracts)

        self.assertEqual("P2", packet.payload["target"]["phase_id"])


if __name__ == "__main__":
    unittest.main()
