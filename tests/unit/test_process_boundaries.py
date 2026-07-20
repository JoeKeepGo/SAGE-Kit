from __future__ import annotations

import ast
import base64
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sagekit.process_supervisor import _windows_gated_bootstrap


REPO_ROOT = Path(__file__).resolve().parents[2]


class ProcessBoundaryTests(unittest.TestCase):
    def test_windows_bootstrap_prebinds_delegated_target_and_scrubs_runtime_paths(self) -> None:
        command = [sys.executable, "-c", "print('target')"]
        payload = base64.urlsafe_b64encode(json.dumps(command).encode("utf-8")).decode(
            "ascii"
        )
        environment = {
            "SAGEKIT_LEASE_ID": "lease-1",
            "SAGEKIT_DELEGATION_SECRET": "secret-1",
            "SAGEKIT_DELEGATION_HOST_RUNTIME": str(REPO_ROOT / ".host-runtime"),
            "SAGEKIT_DELEGATION_PROJECT_RUNTIME": str(REPO_ROOT / ".project-runtime"),
        }
        child = SimpleNamespace(pid=303, wait=lambda: 0, terminate=lambda: None)

        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"GO\n"))),
            patch(
                "sagekit.process_supervisor.subprocess.Popen", return_value=child
            ) as popen,
            patch("sagekit.resource_governor.ResourceManager") as manager,
        ):
            self.assertEqual(0, _windows_gated_bootstrap(payload))

        manager.return_value.bind_windows_gated_delegate.assert_called_once_with(
            "lease-1", delegation_secret="secret-1", delegate_pid=303
        )
        launched_environment = popen.call_args.kwargs["env"]
        self.assertEqual("secret-1", launched_environment["SAGEKIT_DELEGATION_SECRET"])
        self.assertNotIn("SAGEKIT_DELEGATION_HOST_RUNTIME", launched_environment)
        self.assertNotIn("SAGEKIT_DELEGATION_PROJECT_RUNTIME", launched_environment)

    def test_product_external_processes_route_only_through_supervisor(self) -> None:
        candidates = sorted((REPO_ROOT / "sagekit").glob("*.py")) + [
            REPO_ROOT / "scripts/wheel_smoke.py"
        ]
        violations: list[str] = []
        for path in candidates:
            if path.name == "process_supervisor.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                if (
                    isinstance(owner, ast.Name)
                    and owner.id == "subprocess"
                    and node.func.attr in {"run", "Popen", "call", "check_call", "check_output"}
                ):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}:{node.func.attr}"
                    )
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
