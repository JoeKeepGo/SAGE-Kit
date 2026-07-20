"""Fixed-order, resource-governed local verification runner."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from .managed_execution import ManagedExecutionError, run_managed_command
from .resource_governor import ResourceBusy, ResourceClass


FINAL_ORDER = ("focused", "unit", "integration", "source-repo", "package")
HIGH_LOAD_NODES = frozenset({"source-repo", "package"})
HIGH_LOAD_WAIVER = "waived by the user for a limited development host"


@dataclass(frozen=True)
class TestNode:
    name: str
    resource_class: ResourceClass
    timeout: float
    waived: bool = False
    waiver_reason: str | None = None


@dataclass(frozen=True)
class NodeEvidence:
    name: str
    state: str
    command: tuple[str, ...]
    duration_seconds: float
    resource_wait_seconds: float = 0.0
    waiver_reason: str | None = None
    classification: str | None = None
    peak_owned_processes: int | None = None
    child_cpu_seconds: float | None = None
    peak_rss_bytes: int | None = None
    output_bytes: int | None = None
    heartbeat_count: int | None = None
    current_test: str | None = None
    cleanup_complete: bool | None = None
    containment_complete: bool | None = None
    sampling_degraded: bool | None = None
    orphan_count: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


def build_plan(lane: str, *, waive_high_load: bool) -> tuple[TestNode, ...]:
    if lane == "final":
        names = FINAL_ORDER
    elif lane in FINAL_ORDER:
        names = (lane,)
    else:
        raise ValueError(f"unknown test lane: {lane}")
    classes = {
        "focused": ResourceClass.CPU_HEAVY,
        "unit": ResourceClass.CPU_HEAVY,
        "integration": ResourceClass.CPU_HEAVY,
        "source-repo": ResourceClass.REPO_READ,
        "package": ResourceClass.PACKAGE_BUILD,
    }
    timeouts = {
        "focused": 600.0,
        "unit": 600.0,
        # The serial Windows integration lane is consistently slower than the
        # unit lane and has crossed the old ten-minute process deadline while
        # continuing to emit healthy heartbeats. Keep the node bounded, but
        # leave enough margin below the CI job's twenty-minute ceiling.
        "integration": 900.0,
        "source-repo": 300.0,
        "package": 900.0,
    }
    return tuple(
        TestNode(
            name,
            classes[name],
            timeouts[name],
            waived=waive_high_load and name in HIGH_LOAD_NODES,
            waiver_reason=(
                HIGH_LOAD_WAIVER
                if waive_high_load and name in HIGH_LOAD_NODES
                else None
            ),
        )
        for name in names
    )


def command_for(node: TestNode, repository: Path) -> tuple[str, ...]:
    python = sys.executable
    if node.name in {"focused", "unit", "integration"}:
        return (
            python,
            "-B",
            "-m",
            "sagekit.test_node",
            node.name,
            "--repository",
            str(repository),
        )
    if node.name == "source-repo":
        return (python, "-B", "-m", "sagekit", "check", "--source-repo", "--json")
    if node.name == "package":
        return (python, "-B", "-m", "scripts.wheel_smoke")
    raise ValueError(f"unknown test node: {node.name}")


def execute_plan(
    repository: Path,
    plan: Sequence[TestNode],
    *,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> tuple[int, tuple[NodeEvidence, ...]]:
    repository = repository.resolve(strict=True)
    evidence: list[NodeEvidence] = []
    for node in plan:
        command = command_for(node, repository)
        if node.waived:
            item = NodeEvidence(
                node.name,
                "WAIVED",
                command,
                0.0,
                waiver_reason=node.waiver_reason,
            )
            evidence.append(item)
            if progress is not None:
                progress({"stage": node.name, "state": "WAIVED"})
            continue
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix=f"sagekit-{node.name}-") as temp_name:
            temp_root = Path(temp_name)
            heartbeat_file = temp_root / "current-test.json"
            environment = {
                "SAGEKIT_REPOSITORY_ROOT": str(repository),
                "SAGEKIT_TEST_HEARTBEAT_FILE": str(heartbeat_file),
                "TMP": str(temp_root),
                "TEMP": str(temp_root),
                "TMPDIR": str(temp_root),
            }
            delegates_managed_children = node.resource_class is ResourceClass.PACKAGE_BUILD
            if not delegates_managed_children:
                environment.update(
                    {
                        "LOCALAPPDATA": str(temp_root / "localappdata"),
                        "XDG_RUNTIME_DIR": str(temp_root / "xdg-runtime"),
                        "XDG_CACHE_HOME": str(temp_root / "xdg-cache"),
                    }
                )
            last_test: str | None = None

            def heartbeat(event: object) -> None:
                nonlocal last_test
                try:
                    payload = json.loads(heartbeat_file.read_text(encoding="utf-8"))
                    current = payload.get("current_test")
                    if isinstance(current, str) and current:
                        last_test = current
                except (OSError, json.JSONDecodeError):
                    pass
                if progress is not None:
                    progress(
                        {
                            "stage": node.name,
                            "state": "RUNNING",
                            "current_test": last_test,
                            "elapsed_seconds": getattr(event, "elapsed", None),
                        }
                    )

            result = run_managed_command(
                repository,
                command,
                resource_class=node.resource_class,
                permission_mode=(
                    "ENVIRONMENT_WRITE_AUTHORIZED"
                    if node.resource_class is ResourceClass.PACKAGE_BUILD
                    else "READ_ONLY_REVIEW"
                ),
                controller="sagekit-root-verification-controller",
                stage=node.name,
                run_id=f"test-{node.name}-{os.getpid()}",
                timeout=node.timeout,
                max_output_bytes=262_144,
                environment=environment,
                temp_root=temp_root,
                wait_timeout=120.0,
                check=False,
                on_heartbeat=heartbeat,
                on_wait=(
                    (lambda state: progress({"stage": node.name, "state": state}))
                    if progress is not None
                    else None
                ),
                delegated_classes=(
                    (node.resource_class,) if delegates_managed_children else ()
                ),
                isolated_test_harness=not delegates_managed_children,
            )
            state = "PASS" if result.ok else "FAIL"
            wall_elapsed = time.monotonic() - started
            item = NodeEvidence(
                name=node.name,
                state=state,
                command=command,
                duration_seconds=result.elapsed,
                resource_wait_seconds=max(0.0, wall_elapsed - result.elapsed),
                classification=result.classification.value,
                peak_owned_processes=result.peak_owned_processes,
                child_cpu_seconds=result.child_cpu_seconds,
                peak_rss_bytes=result.peak_rss_bytes,
                output_bytes=result.stdout_bytes + result.stderr_bytes,
                heartbeat_count=result.heartbeat_count,
                current_test=last_test,
                cleanup_complete=result.cleanup_complete,
                containment_complete=result.containment_complete,
                sampling_degraded=result.sampling_degraded,
                orphan_count=result.orphan_count,
                stdout_tail=result.stdout_tail,
                stderr_tail=result.stderr_tail,
            )
            evidence.append(item)
            if progress is not None:
                progress({"stage": node.name, "state": state})
            if not result.ok:
                return 1, tuple(evidence)
    return 0, tuple(evidence)


def evidence_payload(items: Sequence[NodeEvidence]) -> list[dict[str, object]]:
    return [asdict(item) for item in items]


__all__ = [
    "FINAL_ORDER",
    "HIGH_LOAD_NODES",
    "NodeEvidence",
    "TestNode",
    "build_plan",
    "command_for",
    "evidence_payload",
    "execute_plan",
]
