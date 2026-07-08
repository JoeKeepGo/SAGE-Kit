from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .check import run_check
from .doctor import run_doctor
from .findings import has_fail
from .init import run_init
from .modes import MODES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sagekit", description="SAGE-Kit local runtime prototype.")
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="Validate SAGE-Kit governance artifacts.")
    check.add_argument("--json", action="store_true", help="Print machine-readable findings.")
    check.add_argument(
        "--mode",
        choices=MODES,
        help="Apply Light, Standard, or Heavy adoption document requirements.",
    )
    check.add_argument(
        "--gate-ready",
        action="store_true",
        help="Require gate-ready Task Dispatch records when task/evidence pairs are present.",
    )

    doctor = subparsers.add_parser("doctor", help="Diagnose SAGE-Kit project and runtime state.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable findings.")

    init = subparsers.add_parser("init", help="Initialize SAGE-Kit governance documents.")
    init.add_argument("--json", action="store_true", help="Print machine-readable findings.")
    init.add_argument("--mode", choices=MODES, default="light", help="Adoption depth to initialize.")
    init.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    init.add_argument("--force", action="store_true", help="Overwrite existing SAGE-Kit documents.")
    return parser


def emit_findings(findings, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"findings": [finding.to_json() for finding in findings]}, indent=2))
        return
    for finding in findings:
        print(finding.to_text())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if int(exc.code) else 0

    try:
        if args.command == "check":
            findings = run_check(Path.cwd(), gate_ready=args.gate_ready, mode=args.mode)
        elif args.command == "doctor":
            findings = run_doctor(Path.cwd())
        elif args.command == "init":
            findings = run_init(Path.cwd(), mode=args.mode, dry_run=args.dry_run, force=args.force)
        else:
            parser.print_help(sys.stderr)
            return 2
        emit_findings(findings, args.json)
        return 1 if has_fail(findings) else 0
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "findings": [
                            {
                                "level": "FAIL",
                                "rule": "internal-error",
                                "message": str(exc),
                            }
                        ]
                    },
                    indent=2,
                )
            )
        else:
            print(f"FAIL internal-error: {exc}", file=sys.stderr)
        return 3
