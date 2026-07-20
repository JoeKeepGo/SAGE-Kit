"""Child process for serial unittest lanes with current-test heartbeat state."""

from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
import uuid
from pathlib import Path


FOCUSED_TESTS = (
    "tests.test_thin_execution_documents",
    "tests.test_packet_compile",
    "tests.test_thin_routing",
    "tests.test_thin_documentation",
    "tests.unit.test_resource_governor",
    "tests.unit.test_resource_policy",
    "tests.unit.test_workspace_binding",
    "tests.unit.test_candidate_snapshot",
    "tests.unit.test_normalization",
    "tests.integration.test_process_supervisor",
    "tests.integration.test_resource_cli",
)

TEST_MODULE_LANES = {
    "test_ci_workflow": "unit",
    "test_convergence_authority": "integration",
    "test_execution_economy": "integration",
    "test_frozen_contracts_and_containers": "unit",
    "test_package_smoke": "unit",
    "test_packet_compile": "unit",
    "test_pathing": "unit",
    "test_sagekit_check": "integration",
    "test_sagekit_simulations": "integration",
    "test_task_dispatch_validator": "unit",
    "test_thin_documentation": "unit",
    "test_thin_execution_documents": "unit",
    "test_thin_routing": "integration",
    "test_validation_compatibility": "unit",
    "test_validation_scope_manifest": "integration",
    "test_verification_lifecycle": "integration",
}


class HeartbeatResult(unittest.TextTestResult):
    def startTest(self, test) -> None:
        _write_heartbeat(str(test))
        super().startTest(test)


def _write_heartbeat(current_test: str) -> None:
    raw_path = os.environ.get("SAGEKIT_TEST_HEARTBEAT_FILE")
    if not raw_path:
        return
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps({"schema_version": 1, "current_test": current_test}) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def build_suite(lane: str, repository: Path) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    if lane == "focused":
        return loader.loadTestsFromNames(FOCUSED_TESTS)
    if lane not in {"unit", "integration"}:
        raise ValueError(f"unknown unittest lane: {lane}")
    discovered = loader.discover(
        str(repository / "tests" / lane),
        pattern="test*.py",
        top_level_dir=str(repository),
    )
    names = tuple(
        f"tests.{module}"
        for module, selected_lane in TEST_MODULE_LANES.items()
        if selected_lane == lane
    )
    return unittest.TestSuite((discovered, loader.loadTestsFromNames(names)))


def validate_test_inventory(repository: Path) -> tuple[str, ...]:
    discovered = {
        path.stem for path in (repository / "tests").glob("test_*.py")
    }
    configured = set(TEST_MODULE_LANES)
    errors = [f"unclassified test module: {name}" for name in sorted(discovered - configured)]
    errors.extend(
        f"missing configured test module: {name}" for name in sorted(configured - discovered)
    )
    errors.extend(
        f"invalid test lane for {name}: {lane}"
        for name, lane in sorted(TEST_MODULE_LANES.items())
        if lane not in {"unit", "integration", "package"}
    )
    return tuple(errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sagekit.test_node")
    parser.add_argument("lane", choices=("focused", "unit", "integration"))
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    repository = args.repository.resolve(strict=True)
    suite = build_suite(args.lane, repository)
    result = unittest.TextTestRunner(
        stream=sys.stderr,
        verbosity=2,
        resultclass=HeartbeatResult,
    ).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
