from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .check import run_check, run_source_repo_check
from .doctor import run_doctor
from .findings import Finding, has_fail
from .init import run_init
from .modes import MODES


class TargetError(ValueError):
    pass


def resolve_target(target: Path | None) -> Path:
    if target is None:
        return Path.cwd()
    expanded = target.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    if expanded.exists() and not expanded.is_dir():
        raise TargetError(f"--target must be a directory or a path that can become a directory: {expanded}")
    return expanded.resolve(strict=False)


def add_target_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target",
        type=Path,
        help="Run against this project path instead of the current working directory.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sagekit", description="SAGE-Kit local runtime prototype.")
    parser.add_argument("--version", action="version", version=f"sagekit {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="Validate SAGE-Kit governance artifacts.")
    add_target_argument(check)
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
    check.add_argument(
        "--source-repo",
        action="store_true",
        help="Check the SAGE-Kit source repository instead of an adopted project.",
    )

    doctor = subparsers.add_parser("doctor", help="Diagnose SAGE-Kit project and runtime state.")
    add_target_argument(doctor)
    doctor.add_argument("--json", action="store_true", help="Print machine-readable findings.")

    init = subparsers.add_parser("init", help="Initialize SAGE-Kit governance documents.")
    add_target_argument(init)
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
        target_argument = getattr(args, "target", None)
        try:
            target = resolve_target(target_argument)
        except TargetError as exc:
            findings = [Finding("FAIL", "target", None, None, str(exc))]
            emit_findings(findings, getattr(args, "json", False))
            return 1
        if args.command == "check":
            if args.source_repo:
                findings = run_source_repo_check(target)
            else:
                findings = run_check(target, gate_ready=args.gate_ready, mode=args.mode)
        elif args.command == "doctor":
            findings = run_doctor(target)
        elif args.command == "init":
            findings = run_init(
                target,
                mode=args.mode,
                dry_run=args.dry_run,
                force=args.force,
                exact_root=target_argument is not None,
            )
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
