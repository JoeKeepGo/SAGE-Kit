from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class ProcessBoundaryTests(unittest.TestCase):
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
