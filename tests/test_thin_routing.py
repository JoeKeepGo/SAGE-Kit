import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from sagekit import (
    PacketConfigurationError,
    PacketError,
    check_project,
    compile_ephemeral_packet,
    write_ephemeral_packet,
)
from sagekit.check import check_execution_documents


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_json(root: Path, relative: str, payload: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def project_lock() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sagekit_contract": "2026.7.19.3",
        "execution_document_model": "thin-v1",
        "effective_from": "M36",
        "legacy_documents": "immutable",
        "profiles": ["standard-milestone@v1", "standard-phase@v1"],
        "overrides": {},
    }


def milestone_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sagekit_contract": "2026.7.19.3",
        "document_model": "thin-v1",
        "milestone_id": "M36",
        "objective": "Ship a thin execution-document model.",
        "capability_outcome": "Compile governed packets without copied policy prose.",
        "authority_references": ["SAGE_PROJECT.json"],
        "governance_profile": "standard-milestone@v1",
        "dependency_dag": {"P01": []},
        "approval_gates": [
            {
                "id": "G-M36-WRITE",
                "applies_to": ["P01"],
                "status": "approved",
                "permission_mode": "WRITE_AUTHORIZED",
                "authority_reference": "SAGE_PROJECT.json",
            }
        ],
        "phase_ids": ["P01"],
        "acceptance_criteria": ["The thin manifest validates."],
        "invariants": ["Task Dispatch contract selection remains independent."],
        "state": "active",
        "evidence_references": [],
    }


def phase_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sagekit_contract": "2026.7.19.3",
        "document_model": "thin-v1",
        "phase_id": "P01",
        "objective": "Implement deterministic thin validation.",
        "depends_on": [],
        "execution_profile": "standard-phase@v1",
        "permission_mode": "WRITE_AUTHORIZED",
        "owner": "Root Controller",
        "writable_paths": ["sagekit/"],
        "read_only_references": ["SAGE_PROJECT.json", "docs/M36/MILESTONE_MANIFEST.json"],
        "forbidden_paths": ["secrets/"],
        "inherit_forbidden": True,
        "acceptance_criteria": ["Focused tests pass."],
        "verification_commands": ["python -B -m unittest tests.test_thin_routing"],
        "evidence_requirements": ["Record the focused test exit code."],
        "stop_conditions": ["Stop on authority conflict."],
        "handoff_target": "Final Review",
        "state": "planned",
    }


def write_thin_project(root: Path) -> None:
    write_json(root, "SAGE_PROJECT.json", project_lock())
    write_json(root, "docs/M36/MILESTONE_MANIFEST.json", milestone_manifest())
    write_json(root, "docs/M36/phases/P01.json", phase_manifest())


def write_required_docs(root: Path) -> None:
    required = {
        "docs/PROJECT_PROFILE.md": "# Project Profile\n\nSynthetic thin project.\n",
        "docs/QUALITY_GATES.md": "# Quality Gates\n\nRequire focused verification.\n",
        "docs/ACTIVE_CONTEXT.md": "# Active Context\n\nCurrent milestone: M36\n",
        "docs/DOC_ROUTING.md": "# Routing\n\nRouting policy: read the active thin manifests.\n",
    }
    for relative, content in required.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class ThinExecutionRoutingTests(unittest.TestCase):
    def test_effective_from_rejects_retroactive_thin_and_post_adoption_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)
            lock_payload = project_lock()
            lock_payload["effective_from"] = "M37"
            write_json(root, "SAGE_PROJECT.json", lock_payload)
            findings = check_execution_documents(root)
            self.assertTrue(
                any(
                    item.level == "FAIL"
                    and item.rule == "execution-document-authority"
                    and item.path == "docs/M36"
                    and "precedes" in item.message
                    for item in findings
                )
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)
            legacy = root / "docs/M37/01-late.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("# Late\n\nObjective: late legacy format\n", encoding="utf-8")
            findings = check_execution_documents(root)
            self.assertTrue(
                any(
                    item.level == "FAIL"
                    and item.rule == "execution-document-authority"
                    and item.path == "docs/M37"
                    for item in findings
                )
            )

    def test_pre_adoption_legacy_remains_legacy_with_a_valid_thin_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)
            legacy = root / "docs/M35/01-legacy.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("# Legacy\n\nObjective: pre-adoption format\n", encoding="utf-8")
            findings = check_execution_documents(root)
            self.assertTrue(any(item.rule == "phase-governance" for item in findings))
            self.assertFalse(
                any(
                    item.rule == "execution-document-authority" and item.path == "docs/M35"
                    for item in findings
                )
            )

    def test_valid_lock_without_adoption_anchor_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root, "SAGE_PROJECT.json", project_lock())

            findings = check_execution_documents(root)

            self.assertTrue(
                any(
                    item.level == "FAIL"
                    and item.rule == "execution-document-authority"
                    and item.path == "docs/M36"
                    for item in findings
                )
            )

    def test_noncanonical_reserved_names_fail_on_every_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root, "sage_project.json", project_lock())
            write_json(root, "docs/M36/milestone_manifest.json", milestone_manifest())
            write_json(root, "docs/M36/phases/p1.json", phase_manifest())
            (root / "docs/manual").mkdir(parents=True)

            findings = check_execution_documents(root)

            aliases = [item for item in findings if item.rule == "execution-document-name"]
            self.assertEqual(
                {
                    "sage_project.json",
                    "docs/M36/milestone_manifest.json",
                    "docs/M36/phases/p1.json",
                },
                {item.path for item in aliases},
            )
            self.assertTrue(all(item.level == "FAIL" for item in aliases))
            self.assertFalse(any(item.path == "docs/manual" for item in aliases))

    def test_adoption_anchor_cannot_point_at_accepted_legacy_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root, "SAGE_PROJECT.json", project_lock())
            legacy = root / "docs/M36/01-history.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("# Accepted history\n\nObjective: immutable\n", encoding="utf-8")
            (root / "docs/M36/MILESTONE_CLOSEOUT.md").write_text(
                "# Closeout\n\nStatus: ACCEPTED\n",
                encoding="utf-8",
            )
            (root / "docs/ACTIVE_CONTEXT.md").write_text(
                "# Active Context\n\n- Current milestone: `M37`\n",
                encoding="utf-8",
            )

            findings = check_execution_documents(root)

            self.assertTrue(
                any(
                    item.level == "FAIL"
                    and item.rule == "execution-document-authority"
                    and "explicit thin-v1 milestone manifest" in item.message
                    for item in findings
                )
            )
            self.assertFalse(
                any(item.rule == "phase-scope-compatibility" for item in findings)
            )
            self.assertFalse(any(item.rule == "phase-governance" for item in findings))

    def test_execution_contract_runtime_and_document_resources_are_package_owned(self):
        version = "2026.7.20.1"
        runtime = (
            REPO_ROOT
            / "sagekit/resources/execution_documents"
            / version
            / "contract.json"
        )
        documented = (
            REPO_ROOT
            / "sagekit/resources/docs/contracts/execution-documents"
            / version
            / "contract.json"
        )
        self.assertTrue(runtime.is_file(), runtime)
        self.assertTrue(documented.is_file(), documented)
        self.assertEqual(runtime.read_bytes(), documented.read_bytes())

    def test_explicit_thin_milestone_routes_to_thin_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)

            findings = check_execution_documents(root)

            failures = [item for item in findings if item.level == "FAIL"]
            self.assertEqual([], failures)
            self.assertTrue(
                any(item.rule == "execution-document-model" and "thin-v1" in item.message for item in findings)
            )

    def test_thin_artifact_without_project_lock_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root, "docs/M36/MILESTONE_MANIFEST.json", milestone_manifest())

            findings = check_execution_documents(root)

            self.assertTrue(
                any(
                    item.level == "FAIL"
                    and item.rule == "execution-document-authority"
                    and "SAGE_PROJECT.json" in item.message
                    for item in findings
                )
            )

    def test_same_active_milestone_cannot_mix_legacy_and_thin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)
            legacy = root / "docs/M36/01-legacy.md"
            legacy.write_text("# Phase\n\nObjective: conflicting format\n", encoding="utf-8")

            findings = check_execution_documents(root)

            mixed = [item for item in findings if item.rule == "execution-document-mixed-format"]
            self.assertEqual(1, len(mixed))
            self.assertEqual("FAIL", mixed[0].level)

    def test_pre_adoption_legacy_phase_uses_existing_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            phase = root / "docs/M1/01-planning.md"
            phase.parent.mkdir(parents=True)
            phase.write_text("# Planning\n\nObjective: intentionally incomplete\n", encoding="utf-8")

            findings = check_execution_documents(root)

            self.assertTrue(any(item.rule == "phase-governance" for item in findings))
            self.assertFalse(any(item.rule == "execution-document-authority" for item in findings))

    def test_duplicate_project_lock_key_is_not_downgraded_to_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / "SAGE_PROJECT.json"
            lock.write_text(
                '{"schema_version":1,"sagekit_contract":"2026.7.19.3",'
                '"execution_document_model":"thin-v1","execution_document_model":"legacy-markdown",'
                '"effective_from":"M36","legacy_documents":"immutable","profiles":[],"overrides":{}}\n',
                encoding="utf-8",
            )
            write_json(root, "docs/M36/MILESTONE_MANIFEST.json", milestone_manifest())

            findings = check_execution_documents(root)

            self.assertTrue(
                any(item.level == "FAIL" and item.rule == "project-contract" for item in findings)
            )

    def test_project_lock_unknown_override_fails_without_a_milestone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_payload = project_lock()
            lock_payload["overrides"] = {
                "standard-phase@v1": {"approval_required_for_write": False}
            }
            write_json(root, "SAGE_PROJECT.json", lock_payload)

            findings = check_execution_documents(root)

            self.assertTrue(
                any(
                    item.level == "FAIL"
                    and item.rule == "project-contract"
                    and "unknown override" in item.message
                    for item in findings
                )
            )

    def test_packet_compile_defaults_to_memory_and_does_not_write_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)
            before = tree_digest(root)

            packet = compile_ephemeral_packet(root, "M36", "P01")

            self.assertEqual(
                "sagekit-packet-compile@v3",
                packet.payload["_generated_by"],
            )
            self.assertIn('"packet_sha256"', packet.to_json())
            self.assertEqual(before, tree_digest(root))

    def test_packet_json_representation_retains_the_compiled_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)

            packet = compile_ephemeral_packet(root, "M36", "P01")

            payload = json.loads(packet.to_json())
            self.assertEqual("thin-v1", payload["document_model"])
            self.assertEqual(packet.digest, payload["packet_sha256"])

    def test_packet_output_is_project_relative_and_nested_on_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)

            packet = compile_ephemeral_packet(root, "M36", "P01")
            output = write_ephemeral_packet(
                root,
                ".sagekit/packets/P01.json",
                packet,
            )

            self.assertEqual(
                (root / ".sagekit/packets/P01.json").resolve(),
                output.resolve(),
            )
            self.assertTrue(output.is_file())

    def test_check_and_packet_harness_results_fail_closed_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)
            write_required_docs(root)
            check = check_project(root)
            packet = compile_ephemeral_packet(root, "M36", "P01")
            self.assertTrue(check.ok)
            self.assertEqual(packet.digest, packet.payload["packet_sha256"])

            lock = root / "SAGE_PROJECT.json"
            lock.write_text(
                '{"schema_version":1,"schema_version":1}\n', encoding="utf-8"
            )
            failed_check = check_project(root)
            self.assertFalse(failed_check.ok)
            self.assertTrue(
                any(
                    item.rule == "project-contract"
                    for item in failed_check.findings
                )
            )
            with self.assertRaises(PacketConfigurationError):
                compile_ephemeral_packet(root, "M36", "P01")

    def test_overwrite_is_available_only_on_the_explicit_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_thin_project(root)
            packet = compile_ephemeral_packet(root, "M36", "P01")
            output = ".sagekit/packets/P01.json"

            write_ephemeral_packet(root, output, packet)
            with self.assertRaisesRegex(PacketError, "already exists"):
                write_ephemeral_packet(root, output, packet)
            rewritten = write_ephemeral_packet(
                root,
                output,
                packet,
                overwrite_generated=True,
            )

            self.assertTrue(rewritten.is_file())


if __name__ == "__main__":
    unittest.main()
