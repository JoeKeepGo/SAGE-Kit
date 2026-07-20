from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sagekit.managed_execution import ManagedExecutionError
from sagekit.resource_governor import ResourceBusy
from sagekit.test_runner import build_plan, evidence_payload, execute_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -B scripts/run_tests.py")
    parser.add_argument(
        "lane",
        choices=("focused", "unit", "integration", "package", "final"),
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
        payload = {"ok": False, "state": exc.state, "message": str(exc)}
        print(json.dumps(payload, sort_keys=True))
        return 1
    except ManagedExecutionError as exc:
        print(
            json.dumps(
                {"ok": False, "state": "HANDOFF_READY", "message": str(exc)},
                sort_keys=True,
            )
        )
        return 3
    payload = {
        "ok": code == 0,
        "state": "COMPLETE" if code == 0 else "HANDOFF_READY",
        "serial": True,
        "nodes": evidence_payload(evidence),
    }
    print(json.dumps(payload, indent=2 if args.json else None, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
