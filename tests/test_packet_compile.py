import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.packet import (
    CompiledPacket,
    PacketError,
    compile_packet,
    write_compiled_packet,
)
from sagekit.resource_governor import ResourceBusy
from sagekit.harness import discover_project_workspace, verify_project_workspace
from sagekit.workspace_binding import WorkspaceBinding
from tests.test_thin_execution_documents import create_project


def tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class PacketCompileTests(unittest.TestCase):
    def test_public_compiler_rejects_contract_root_authority_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)

            with self.assertRaises(TypeError):
                compile_packet(  # type: ignore[call-arg]
                    root, "M36", "P2", contract_root=contracts
                )

    def test_compiled_v3_packet_is_strict_resource_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36", "P2")
            output = write_compiled_packet(root, ".sagekit/packets/P2.json", packet)

            authority = json.loads(output.read_text(encoding="utf-8"))
            current = discover_project_workspace(root)
            verified = verify_project_workspace(
                WorkspaceBinding.from_dict(authority["workspace_binding"]),
                current=current,
            )
            tampered = json.loads(output.read_text(encoding="utf-8"))
            tampered["source_contract"]["semantic_sha256"] = "0" * 64
            unsigned = dict(tampered)
            unsigned.pop("packet_sha256")
            tampered["packet_sha256"] = hashlib.sha256(
                json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            output.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(PacketError, "not a recognized generated packet"):
                write_compiled_packet(
                    root,
                    ".sagekit/packets/P2.json",
                    packet,
                    overwrite_generated=True,
                )

        self.assertTrue(verified.ok, verified.errors)
        self.assertEqual(packet.digest, authority["packet_sha256"])
        self.assertEqual(
            packet.payload["resolved_policy"]["values"]["permission_mode"],
            authority["resolved_policy"]["values"]["permission_mode"],
        )

    def test_milestone_packet_can_write_compiler_owned_runtime_output(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36")

            output = write_compiled_packet(
                root, ".sagekit/packets/M36.json", packet
            )

        self.assertEqual("M36.json", output.name)

    def test_public_writer_revalidates_explicit_source_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "docs/M36"
            packet = compile_packet(root, "M36", "P2", source=source)

            output = write_compiled_packet(
                root, ".sagekit/packets/explicit.json", packet
            )
            self.assertTrue(output.is_file())
            phase_path = source / "phases/P2.json"
            phase = json.loads(phase_path.read_text(encoding="utf-8"))
            phase["objective"] = "Explicit source changed after packet compilation."
            phase_path.write_text(json.dumps(phase, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                PacketError, "current project-owned SPEC authority"
            ):
                write_compiled_packet(root, ".sagekit/packets/stale.json", packet)

    def test_json_roundtrip_retains_explicit_source_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "docs/embedded-M36"
            shutil.copytree(root / "docs/M36", source)
            packet = compile_packet(root, "M36", "P2", source=source)
            serialized = json.loads(packet.to_json())
            relocated = root / "decisions/relocated-M36"
            relocated.parent.mkdir(parents=True)
            shutil.move(source, relocated)
            serialized["source_provenance"]["configured_source"] = str(relocated)
            serialized["source_provenance"]["resolved_canonical_path"] = str(
                relocated.resolve()
            )
            reloaded = CompiledPacket(
                serialized["mode"], serialized, serialized["packet_sha256"]
            )

            configured_phase = root / "docs/M36/phases/P2.json"
            configured = json.loads(configured_phase.read_text(encoding="utf-8"))
            configured["objective"] = "Configured source must not be selected."
            configured_phase.write_text(
                json.dumps(configured, indent=2) + "\n", encoding="utf-8"
            )

            output = write_compiled_packet(
                root, ".sagekit/packets/roundtrip.json", reloaded
            )
            self.assertTrue(output.is_file())
            self.assertEqual("explicit-source", serialized["source_provenance"]["authority"])
            self.assertEqual(
                {
                    "model": "normalized-source-authority-v1",
                    "semantic_sha256": serialized["source_contract"]["semantic_sha256"],
                    "adapter": "thin-v1",
                    "document_class": "ACTIVE_SPEC",
                },
                serialized["source_authority"],
            )

    def test_malformed_serialized_source_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36", "P2", source=root / "docs/M36")
            payload = json.loads(packet.to_json())
            payload["source_provenance"] = {"authority": "explicit-source"}
            malformed = CompiledPacket(
                payload["mode"], payload, payload["packet_sha256"]
            )

            with self.assertRaisesRegex(PacketError, "digest or generated structure"):
                write_compiled_packet(root, ".sagekit/packets/malformed.json", malformed)

    def test_signed_source_authority_rejects_provenance_adapter_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36", "P2", source=root / "docs/M36")
            payload = json.loads(packet.to_json())
            payload["source_provenance"]["selected_adapter"] = "markdown-v1"
            tampered = CompiledPacket(
                payload["mode"], payload, payload["packet_sha256"]
            )

            with self.assertRaisesRegex(PacketError, "signed source authority"):
                write_compiled_packet(root, ".sagekit/packets/mismatch.json", tampered)

    def test_tampered_compiled_packet_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36", "P2")
            packet.payload["resolved_resource_policy"][
                "allowed_resource_classes"
            ].append("submit-exclusive")

            with self.assertRaisesRegex(PacketError, "digest|recognized"):
                write_compiled_packet(
                    root, ".sagekit/packets/tampered.json", packet
                )

            self.assertFalse((root / ".sagekit/packets/tampered.json").exists())

    def test_busy_output_lease_is_an_operational_packet_error(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36", "P2")

            with patch(
                "sagekit.packet.ResourceManager.acquire",
                side_effect=ResourceBusy("repo writer occupied", state="HANDOFF_READY"),
            ), self.assertRaisesRegex(PacketError, "HANDOFF_READY"):
                write_compiled_packet(root, ".sagekit/packets/P2.json", packet)

    def test_standalone_and_compact_packets_are_stable_bound_and_pure(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            before = tree_digest(root)

            standalone = compile_packet(root, "M36", "P2")
            repeat = compile_packet(root, "M36", "P2")
            compact = compile_packet(root, "M36", "P2", compact=True)
            after = tree_digest(root)
            unsigned = dict(standalone.payload)
            unsigned.pop("packet_sha256")
            expected_packet_digest = hashlib.sha256(
                json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

        self.assertEqual(before, after)
        self.assertEqual(standalone.digest, repeat.digest)
        self.assertEqual(standalone.payload, repeat.payload)
        self.assertEqual(expected_packet_digest, standalone.digest)
        self.assertEqual(expected_packet_digest, standalone.payload["packet_sha256"])
        self.assertIn("generic_rules", standalone.payload)
        self.assertNotIn("generic_rules", compact.payload)
        self.assertIn("profile_references", compact.payload)
        self.assertIn("runtime_stop_handshake", compact.payload)
        self.assertEqual(
            "WRITE_AUTHORIZED", standalone.payload["resolved_policy"]["values"]["permission_mode"]
        )
        for key in (
            "project_lock_sha256",
            "milestone_manifest_sha256",
            "phase_manifest_sha256",
            "contract_sha256",
            "resolved_policy_sha256",
            "resource_contract_sha256",
            "resolved_resource_policy_sha256",
            "workspace_binding_sha256",
        ):
            self.assertRegex(standalone.payload["bindings"][key], r"^[0-9a-f]{64}$")
        self.assertEqual(
            "conservative-host-v1",
            standalone.payload["resolved_resource_policy"]["profile_id"],
        )
        self.assertEqual(
            "root-only",
            standalone.payload["resolved_resource_policy"]["verification_controller"],
        )
        self.assertEqual(
            str(root.resolve()),
            standalone.payload["workspace_binding"]["project_root"],
        )
        self.assertEqual(
            standalone.payload["bindings"]["workspace_binding_sha256"],
            standalone.payload["workspace_binding"]["binding_sha256"],
        )

    def test_manifest_change_changes_packet_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            first = compile_packet(root, "M36", "P2")
            phase_path = root / "docs/M36/phases/P2.json"
            phase = json.loads(phase_path.read_text(encoding="utf-8"))
            phase["objective"] = "Changed project-specific objective."
            phase_path.write_text(json.dumps(phase, indent=2) + "\n", encoding="utf-8")
            second = compile_packet(root, "M36", "P2")

        self.assertNotEqual(first.digest, second.digest)
        self.assertNotEqual(
            first.payload["bindings"]["phase_manifest_sha256"],
            second.payload["bindings"]["phase_manifest_sha256"],
        )

    def test_safe_output_is_exclusive_and_protects_authority_files(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36", "P2")

            output = write_compiled_packet(root, ".sagekit/packets/P2.json", packet)
            self.assertTrue(output.is_file())
            with self.assertRaisesRegex(PacketError, "already exists"):
                write_compiled_packet(root, ".sagekit/packets/P2.json", packet)
            write_compiled_packet(
                root,
                ".sagekit/packets/P2.json",
                packet,
                overwrite_generated=True,
            )
            for protected in (
                "SAGE_PROJECT.json",
                "docs/ACTIVE_CONTEXT.md",
                "docs/DOC_ROUTING.md",
                "docs/M36/MILESTONE_MANIFEST.json",
                "docs/M36/phases/P2.json",
            ):
                with self.subTest(protected=protected), self.assertRaisesRegex(
                    PacketError, "protected authority"
                ):
                    write_compiled_packet(root, protected, packet, overwrite_generated=True)

            marker_only = root / ".sagekit/packets/marker-only.json"
            marker_only.write_text(
                json.dumps({"_generated_by": "sagekit-packet-compile@v1"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PacketError, "not a recognized generated packet"):
                write_compiled_packet(
                    root,
                    ".sagekit/packets/marker-only.json",
                    packet,
                    overwrite_generated=True,
                )

    def test_output_parent_traversal_and_symlink_escape_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            packet = compile_packet(root, "M36", "P2")
            with self.assertRaisesRegex(PacketError, "project-relative"):
                write_compiled_packet(root, "../packet.json", packet)

            outside = workspace / "outside"
            outside.mkdir()
            try:
                (root / "linked").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable on this platform")
            with self.assertRaisesRegex(PacketError, "symlink or reparse"):
                write_compiled_packet(root, "linked/packet.json", packet)

    def test_output_hardlink_alias_of_explicit_source_is_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "docs/M36/MILESTONE_MANIFEST.json"
            packet = compile_packet(
                root,
                "M36",
                "P2",
                source=source,
            )
            alias = root / "manifest-alias.json"
            try:
                os.link(source, alias)
            except OSError:
                self.skipTest("hardlink creation is unavailable on this platform")

            with self.assertRaisesRegex(PacketError, "protected authority"):
                write_compiled_packet(
                    root, "manifest-alias.json", packet, overwrite_generated=True
                )

    def test_output_hardlink_alias_of_file_inside_source_directory_is_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            source = root / "docs/M36"
            packet = compile_packet(
                root,
                "M36",
                "P2",
                source=source,
            )
            manifest = source / "MILESTONE_MANIFEST.json"
            alias = root / "manifest-from-directory-alias.json"
            try:
                os.link(manifest, alias)
            except OSError:
                self.skipTest("hardlink creation is unavailable on this platform")

            with self.assertRaisesRegex(PacketError, "protected authority"):
                write_compiled_packet(
                    root,
                    "manifest-from-directory-alias.json",
                    packet,
                    overwrite_generated=True,
                )

    def test_blocked_targets_and_incomplete_dependencies_do_not_compile(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            first_path = root / "docs/M36/phases/P1.json"
            first = json.loads(first_path.read_text(encoding="utf-8"))
            first["state"] = "ready"
            first_path.write_text(json.dumps(first, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(PacketError, "dependencies are not complete"):
                compile_packet(root, "M36", "P2")

            first["state"] = "complete"
            first_path.write_text(json.dumps(first, indent=2) + "\n", encoding="utf-8")
            milestone_path = root / "docs/M36/MILESTONE_MANIFEST.json"
            milestone = json.loads(milestone_path.read_text(encoding="utf-8"))
            milestone["state"] = "blocked"
            milestone_path.write_text(json.dumps(milestone, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(PacketError, "milestone state is not executable"):
                compile_packet(root, "M36", "P2")


if __name__ == "__main__":
    unittest.main()
