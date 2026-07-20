from __future__ import annotations

import io
import json
import multiprocessing
import os
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sagekit.cli import main
from sagekit.packet import compile_packet
from sagekit.resource_governor import (
    ResourceBusy,
    ResourceClass,
    ResourceManager,
    ResourceRequest,
    current_process_identity,
)
from sagekit.resource_cli import (
    ResourceOperationalError,
    _request,
    live_authority,
    manager_for_target,
    resource_run_payload,
)
from tests.test_thin_execution_documents import create_project


def _lease_holder(
    host: str,
    project: str,
    ready,
    release,
) -> None:
    manager = ResourceManager(
        host_runtime=Path(host),
        project_runtime=Path(project),
    )
    lease = manager.acquire(
        ResourceRequest(
            resource_class=ResourceClass.CPU_HEAVY,
            run_id="holder",
            controller="holder-controller",
            stage="hold",
            authority_digest="a" * 64,
            host_identity="host-A",
            project_identity="project-A",
            worktree_identity="worktree-A",
            permission_mode="ENVIRONMENT_WRITE_AUTHORIZED",
        )
    )
    ready.set()
    release.wait(20)
    manager.release(lease)


class ResourceCliIntegrationTests(unittest.TestCase):
    def test_nested_run_without_root_delegation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            controller = "root-controller"
            permission = "WRITE_AUTHORIZED"
            authority = live_authority(
                root,
                permission_mode=permission,
                controller=controller,
            )
            manager, identity = manager_for_target(root)
            parent = manager.acquire(
                _request(
                    authority,
                    identity,
                    resource_class=ResourceClass.REPO_READ,
                    run_id="parent",
                    stage="parent",
                    exclusive=(),
                )
            )
            inherited_environment = {
                "SAGEKIT_LEASE_ID": parent.lease_id,
                "SAGEKIT_AUTHORITY_DIGEST": authority.digest,
                "SAGEKIT_PERMISSION_MODE": permission,
                "SAGEKIT_ALLOWED_CLASSES": ",".join(parent.record.allowed_classes),
                "SAGEKIT_CONTROLLER": controller,
                "SAGEKIT_DESCENDANT": "1",
            }
            try:
                with (
                    patch.dict(os.environ, inherited_environment, clear=False),
                    patch("sagekit.resource_cli.run_process") as launch,
                ):
                    with self.assertRaisesRegex(ResourceOperationalError, "delegation"):
                        resource_run_payload(
                            root,
                            resource_class=ResourceClass.REPO_READ,
                            run_id="nested",
                            stage="nested",
                            packet_path=None,
                            permission_mode=permission,
                            controller=controller,
                            wait_timeout=0,
                            timeout=1,
                            exclusive=(),
                            command=(os.sys.executable, "-B", "-c", "pass"),
                        )
                launch.assert_not_called()
                self.assertEqual(1, len(manager.status()))
            finally:
                manager.release(parent)

    def test_acquire_heartbeat_release_cli_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root, packet = self.make_packet(workspace)
            code, output, error = self.invoke(
                [
                    "resource",
                    "acquire",
                    "--target",
                    str(root),
                    "--packet",
                    str(packet),
                    "--class",
                    "repo-read",
                    "--run-id",
                    "manual-lifecycle",
                    "--json",
                ]
            )
            self.assertEqual(0, code, output + error)
            lease_id = json.loads(output)["lease"]["lease_id"]
            code, output, error = self.invoke(
                [
                    "resource",
                    "heartbeat",
                    "--target",
                    str(root),
                    "--lease",
                    lease_id,
                    "--stage",
                    "manual-heartbeat",
                    "--json",
                ]
            )
            self.assertEqual(0, code, output + error)
            self.assertEqual(
                "manual-heartbeat", json.loads(output)["lease"]["command_stage"]
            )
            code, output, error = self.invoke(
                [
                    "resource",
                    "release",
                    "--target",
                    str(root),
                    "--lease",
                    lease_id,
                    "--json",
                ]
            )
            self.assertEqual(0, code, output + error)
            self.assertEqual("RELEASED", json.loads(output)["state"])

    def make_packet(self, workspace: Path, *, phase: str | None = "P2") -> tuple[Path, Path]:
        root = workspace / "project"
        contracts = workspace / "contracts"
        create_project(root, contracts)
        packet = compile_packet(root, "M36", phase, contract_root=contracts)
        path = workspace / "packet.json"
        path.write_text(packet.to_json(), encoding="utf-8")
        return root, path

    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_workspace_verify_accepts_exact_packet_and_rejects_wrong_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root, packet = self.make_packet(workspace)
            code, output, _ = self.invoke(
                ["workspace", "verify", "--target", str(root), "--packet", str(packet), "--json"]
            )
            self.assertEqual(0, code, output)
            self.assertTrue(json.loads(output)["ok"])

            wrong = workspace / "wrong-project"
            wrong.mkdir()
            code, output, _ = self.invoke(
                ["workspace", "verify", "--target", str(wrong), "--packet", str(packet), "--json"]
            )
            self.assertEqual(1, code)
            self.assertFalse(json.loads(output)["ok"])
            self.assertIn("project_root differs", output)

    def test_resource_run_uses_packet_lease_supervisor_and_finally_releases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root, packet = self.make_packet(workspace)
            code, output, error = self.invoke(
                [
                    "resource",
                    "run",
                    "--target",
                    str(root),
                    "--packet",
                    str(packet),
                    "--class",
                    "repo-read",
                    "--run-id",
                    "integration-resource-run",
                    "--timeout",
                    "10",
                    "--json",
                    "--",
                    os.sys.executable,
                    "-B",
                    "-c",
                    "print('managed-ok')",
                ]
            )
            self.assertEqual(0, code, output + error)
            payload = json.loads(output)
            self.assertEqual("success", payload["process"]["classification"])
            self.assertEqual(0, payload["process"]["orphan_count"])
            self.assertEqual(
                "HARD" if os.name == "nt" else "MANAGED",
                payload["process"]["containment_level"],
            )
            self.assertEqual(
                os.name == "nt", payload["process"]["containment_complete"]
            )
            self.assertTrue(payload["process"]["platform_adapter"])
            self.assertIsInstance(payload["process"]["limitations"], list)
            self.assertIn("managed-ok", payload["process"]["stdout_tail"])

            code, status, _ = self.invoke(
                ["resource", "status", "--target", str(root), "--json"]
            )
            self.assertEqual(0, code)
            self.assertEqual([], json.loads(status)["leases"])

    def test_resource_run_reverifies_binding_after_lease_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root, packet = self.make_packet(workspace)
            verified = SimpleNamespace(ok=True, errors=())
            drifted = SimpleNamespace(ok=False, errors=("branch differs", "HEAD differs"))
            with (
                patch(
                    "sagekit.resource_cli.verify_workspace",
                    side_effect=(verified, drifted),
                ),
                patch("sagekit.resource_cli.run_process") as launch,
            ):
                with self.assertRaisesRegex(
                    ResourceOperationalError, "changed before launch"
                ):
                    resource_run_payload(
                        root,
                        resource_class=ResourceClass.REPO_READ,
                        run_id="binding-drift",
                        stage="binding-drift",
                        packet_path=packet,
                        permission_mode="READ_ONLY_REVIEW",
                        controller="root",
                        wait_timeout=0,
                        timeout=1,
                        exclusive=(),
                        command=(os.sys.executable, "-B", "-c", "print('no')"),
                    )
            launch.assert_not_called()
            manager, _ = manager_for_target(root)
            self.assertEqual((), manager.status())

    def test_reasoning_only_milestone_packet_cannot_start_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root, packet = self.make_packet(workspace, phase=None)
            code, output, _ = self.invoke(
                [
                    "resource",
                    "run",
                    "--target",
                    str(root),
                    "--packet",
                    str(packet),
                    "--class",
                    "reasoning-only",
                    "--run-id",
                    "forbidden-command",
                    "--timeout",
                    "10",
                    "--json",
                    "--",
                    os.sys.executable,
                    "-B",
                    "-c",
                    "print('must-not-run')",
                ]
            )
            self.assertEqual(1, code)
            self.assertIn("reasoning-only", output)
            self.assertNotIn("must-not-run", output)

    def test_timeout_returns_operational_failure_and_releases_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root, packet = self.make_packet(workspace)
            code, output, _ = self.invoke(
                [
                    "resource",
                    "run",
                    "--target",
                    str(root),
                    "--packet",
                    str(packet),
                    "--class",
                    "repo-read",
                    "--run-id",
                    "timeout-release",
                    "--timeout",
                    "0.25",
                    "--json",
                    "--",
                    os.sys.executable,
                    "-B",
                    "-c",
                    "import time; time.sleep(60)",
                ]
            )
            self.assertEqual(1, code)
            payload = json.loads(output)
            self.assertEqual("timeout", payload["process"]["classification"])
            self.assertTrue(payload["process"]["cleanup_complete"])
            self.assertEqual(0, payload["process"]["orphan_count"])
            self.assertEqual(
                "HARD" if os.name == "nt" else "MANAGED",
                payload["process"]["containment_level"],
            )
            self.assertEqual(
                os.name == "nt", payload["process"]["containment_complete"]
            )
            code, status, _ = self.invoke(
                ["resource", "status", "--target", str(root), "--json"]
            )
            self.assertEqual([], json.loads(status)["leases"])

    def test_independent_processes_compete_for_same_host_cpu_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = multiprocessing.get_context("spawn")
            ready = context.Event()
            release = context.Event()
            process = context.Process(
                target=_lease_holder,
                args=(str(root / "host"), str(root / "project"), ready, release),
            )
            process.start()
            try:
                self.assertTrue(ready.wait(10), "lease holder did not become ready")
                manager = ResourceManager(
                    host_runtime=root / "host",
                    project_runtime=root / "project",
                    process_identity=current_process_identity(),
                )
                with self.assertRaises(ResourceBusy):
                    manager.acquire(
                        ResourceRequest(
                            resource_class=ResourceClass.CPU_HEAVY,
                            run_id="competitor",
                            controller="root-controller",
                            stage="compete",
                            authority_digest="b" * 64,
                            host_identity="host-A",
                            project_identity="project-A",
                            worktree_identity="worktree-B",
                            permission_mode="ENVIRONMENT_WRITE_AUTHORIZED",
                        ),
                        wait_timeout=0,
                    )
            finally:
                release.set()
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            self.assertEqual(0, process.exitcode)


if __name__ == "__main__":
    unittest.main()
