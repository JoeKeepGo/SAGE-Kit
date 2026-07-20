from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.managed_execution import _inherited_lease
from sagekit.resource_governor import (
    ProcessIdentity,
    ResourceClass,
    ResourceManager,
    ResourceRequest,
)


class ManagedExecutionInheritanceTests(unittest.TestCase):
    def test_parent_lease_is_reused_only_when_claims_cover_child_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(101, "root-process"),
                process_probe=lambda pid: "root-process" if pid == 101 else None,
            )
            parent = parent_manager.acquire(
                ResourceRequest(
                    resource_class=ResourceClass.CPU_HEAVY,
                    run_id="parent",
                    controller="root-controller",
                    stage="parent-stage",
                    authority_digest="a" * 64,
                    host_identity="host-A",
                    project_identity="project-A",
                    worktree_identity="worktree-A",
                    permission_mode="WRITE_AUTHORIZED",
                    allowed_classes=(ResourceClass.CPU_HEAVY, ResourceClass.REPO_READ),
                )
            )
            environment = {
                "SAGEKIT_LEASE_ID": parent.lease_id,
                "SAGEKIT_DELEGATION_SECRET": parent.delegation_secret,
                "SAGEKIT_AUTHORITY_DIGEST": "a" * 64,
                "SAGEKIT_ALLOWED_CLASSES": "cpu-heavy,repo-read",
            }
            child_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(202, "child-process"),
                process_probe=lambda pid: (
                    "root-process" if pid == 101 else "child-process"
                ),
                parent_pid_provider=lambda: 101,
            )
            try:
                with patch.dict("os.environ", environment, clear=False):
                    inherited = _inherited_lease(
                        child_manager,
                        resource_class=ResourceClass.REPO_READ,
                        authority_digest="a" * 64,
                        project_identity="project-A",
                        worktree_identity="worktree-A",
                    )
                self.assertIsNone(inherited)
            finally:
                parent_manager.release(parent)


if __name__ == "__main__":
    unittest.main()
