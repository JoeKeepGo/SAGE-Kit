import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sagekit.packet import PacketError, compile_packet, write_compiled_packet
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
    def test_standalone_and_compact_packets_are_stable_bound_and_pure(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            before = tree_digest(root)

            standalone = compile_packet(
                root, "M36", "P2", contract_root=contracts
            )
            repeat = compile_packet(root, "M36", "P2", contract_root=contracts)
            compact = compile_packet(
                root, "M36", "P2", compact=True, contract_root=contracts
            )
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
        ):
            self.assertRegex(standalone.payload["bindings"][key], r"^[0-9a-f]{64}$")
        rendered = json.dumps(standalone.payload, sort_keys=True)
        self.assertNotIn(str(workspace), rendered)

    def test_manifest_change_changes_packet_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            first = compile_packet(root, "M36", "P2", contract_root=contracts)
            phase_path = root / "docs/M36/phases/P2.json"
            phase = json.loads(phase_path.read_text(encoding="utf-8"))
            phase["objective"] = "Changed project-specific objective."
            phase_path.write_text(json.dumps(phase, indent=2) + "\n", encoding="utf-8")
            second = compile_packet(root, "M36", "P2", contract_root=contracts)

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
            packet = compile_packet(root, "M36", "P2", contract_root=contracts)

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
            packet = compile_packet(root, "M36", "P2", contract_root=contracts)
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
                compile_packet(root, "M36", "P2", contract_root=contracts)

            first["state"] = "complete"
            first_path.write_text(json.dumps(first, indent=2) + "\n", encoding="utf-8")
            milestone_path = root / "docs/M36/MILESTONE_MANIFEST.json"
            milestone = json.loads(milestone_path.read_text(encoding="utf-8"))
            milestone["state"] = "blocked"
            milestone_path.write_text(json.dumps(milestone, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(PacketError, "milestone state is not executable"):
                compile_packet(root, "M36", "P2", contract_root=contracts)


if __name__ == "__main__":
    unittest.main()
