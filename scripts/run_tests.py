from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sagekit.managed_execution import ManagedExecutionError
from sagekit.resource_governor import ResourceBusy
from sagekit.test_runner import build_plan, evidence_payload, execute_plan


def classify_managed_execution_error(message: str) -> tuple[str, str]:
    folded = message.casefold()
    if any(
        marker in folded
        for marker in ("authority", "permission", "forbidden", "delegation", "workspace binding")
    ):
        return "AUTHORITY_REQUIRED", "authority"
    if any(
        marker in folded
        for marker in ("capability", "containment", "not supported", "unavailable")
    ):
        return "CAPABILITY_LIMITATION", "capability"
    if any(marker in folded for marker in ("resource", "lease", "occupied")):
        return "RESOURCE_WAIT", "resource"
    return "EXECUTION_FAILED", "execution"


def classify_evidence(code: int, evidence) -> tuple[str, str]:
    if code == 0:
        return "COMPLETE", "success"
    failed = [item for item in evidence if item.state == "FAIL"]
    classifications = {item.classification for item in failed}
    if "nonzero" in classifications:
        return "NEEDS_CORRECTION", "test-failure"
    if "capability" in classifications:
        return "CAPABILITY_LIMITATION", "capability"
    if "timeout" in classifications or "interrupted" in classifications:
        return "EXECUTION_FAILED", "execution"
    return "EXECUTION_FAILED", "execution"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -B scripts/run_tests.py")
    parser.add_argument(
        "lane",
        choices=("focused", "unit", "integration", "source-repo", "package", "final"),
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--waive-high-load", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    def progress(payload: dict[str, object]) -> None:
        print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)

    try:
        plan = build_plan(args.lane, waive_high_load=args.waive_high_load)
        code, evidence = execute_plan(
            args.repository,
            plan,
            progress=progress,
        )
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    except ResourceBusy as exc:
        payload = {
            "ok": False,
            "state": "RESOURCE_WAIT",
            "category": "resource",
            "resource_state": exc.state,
            "message": str(exc),
        }
        print(json.dumps(payload, sort_keys=True))
        return 1
    except ManagedExecutionError as exc:
        state, category = classify_managed_execution_error(str(exc))
        print(
            json.dumps(
                {
                    "ok": False,
                    "state": state,
                    "category": category,
                    "message": str(exc),
                },
                sort_keys=True,
            )
        )
        return 3
    state, category = classify_evidence(code, evidence)
    payload = {
        "ok": code == 0,
        "state": state,
        "category": category,
        "serial": True,
        "nodes": evidence_payload(evidence),
    }
    print(json.dumps(payload, indent=2 if args.json else None, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
