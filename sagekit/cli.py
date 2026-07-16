from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .change_control import ChangeClass
from .check import run_check, run_source_repo_check
from .continuity import CheckpointResult, clear_checkpoint, create_checkpoint, resume_checkpoint
from .doctor import run_doctor
from .execution_limits import ExecutionCounters
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

    checkpoint = subparsers.add_parser("checkpoint", help="Manage local resumable run state.")
    checkpoint_commands = checkpoint.add_subparsers(dest="checkpoint_command", required=True)

    checkpoint_create = checkpoint_commands.add_parser("create", help="Create or replace CURRENT_RUN.json.")
    add_target_argument(checkpoint_create)
    checkpoint_create.add_argument("--json", action="store_true", help="Print machine-readable output.")
    checkpoint_create.add_argument("--run-id", required=True)
    checkpoint_create.add_argument("--goal", required=True)
    checkpoint_create.add_argument("--authority-id", required=True)
    checkpoint_create.add_argument("--authority-version", required=True)
    checkpoint_create.add_argument("--authority-summary", required=True)
    checkpoint_create.add_argument(
        "--authority-ref",
        action="append",
        default=[],
        help="Repository-relative authority file to fingerprint; repeat as needed.",
    )
    checkpoint_create.add_argument(
        "--change-class",
        required=True,
        choices=[item.value for item in ChangeClass],
    )
    checkpoint_create.add_argument("--completed-work", action="append", default=[])
    checkpoint_create.add_argument("--open-finding", action="append", default=[])
    checkpoint_create.add_argument("--evidence-ref", action="append", default=[])
    checkpoint_create.add_argument("--invalidated-evidence", action="append", default=[])
    checkpoint_create.add_argument("--next-action", required=True)
    checkpoint_create.add_argument("--allowed-path", action="append", default=[])
    checkpoint_create.add_argument("--stop-condition", action="append", default=[])
    checkpoint_create.add_argument("--base-sha")

    checkpoint_status = checkpoint_commands.add_parser("status", help="Validate the current checkpoint.")
    add_target_argument(checkpoint_status)
    checkpoint_status.add_argument("--json", action="store_true", help="Print machine-readable output.")

    checkpoint_clear = checkpoint_commands.add_parser("clear", help="Remove only CURRENT_RUN.json.")
    add_target_argument(checkpoint_clear)
    checkpoint_clear.add_argument("--json", action="store_true", help="Print machine-readable output.")

    resume = subparsers.add_parser("resume", help="Validate and emit the current run's next action.")
    add_target_argument(resume)
    resume.add_argument("--json", action="store_true", help="Print machine-readable output.")
    return parser


def emit_findings(findings, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"findings": [finding.to_json() for finding in findings]}, indent=2))
        return
    for finding in findings:
        print(finding.to_text())


def checkpoint_finding(result: CheckpointResult) -> Finding:
    details = result.message
    if result.mismatches:
        details += ": " + "; ".join(result.mismatches)
    return Finding(
        "PASS" if result.ok else "FAIL",
        result.rule,
        ".sagekit/runtime/CURRENT_RUN.json",
        None,
        details,
    )


def safe_resume_payload(result: CheckpointResult) -> dict[str, object] | None:
    if not result.ok or result.checkpoint is None:
        return None
    checkpoint = result.checkpoint
    return {
        "run_id": checkpoint.get("run_id"),
        "goal": checkpoint.get("goal"),
        "change_class": checkpoint.get("change_class"),
        "completed_work": checkpoint.get("completed_work", []),
        "open_findings": checkpoint.get("open_findings", []),
        "evidence_references": checkpoint.get("evidence_references", []),
        "invalidated_evidence": checkpoint.get("invalidated_evidence", []),
        "execution_counters": checkpoint.get("execution_counters", {}),
        "next_action": checkpoint.get("next_action"),
        "allowed_paths": checkpoint.get("allowed_paths", []),
        "stop_conditions": checkpoint.get("stop_conditions", []),
    }


def emit_checkpoint_result(
    result: CheckpointResult,
    *,
    as_json: bool,
    include_resume: bool = False,
) -> None:
    finding = checkpoint_finding(result)
    if as_json:
        payload: dict[str, object] = {"findings": [finding.to_json()]}
        if include_resume:
            resume_payload = safe_resume_payload(result)
            if resume_payload is not None:
                payload["resume"] = resume_payload
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(finding.to_text())
    if include_resume:
        resume_payload = safe_resume_payload(result)
        if resume_payload is not None:
            print(f"NEXT_ACTION: {resume_payload['next_action']}")


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
        elif args.command == "checkpoint":
            if args.checkpoint_command == "create":
                result = create_checkpoint(
                    target,
                    run_id=args.run_id,
                    goal=args.goal,
                    authority_id=args.authority_id,
                    authority_version=args.authority_version,
                    authority_summary=args.authority_summary,
                    authority_references=args.authority_ref,
                    change_class=ChangeClass(args.change_class),
                    completed_work=args.completed_work,
                    open_findings=args.open_finding,
                    evidence_references=args.evidence_ref,
                    invalidated_evidence=args.invalidated_evidence,
                    execution_counters=ExecutionCounters(),
                    next_action=args.next_action,
                    allowed_paths=args.allowed_path,
                    stop_conditions=args.stop_condition,
                    base_sha=args.base_sha,
                )
            elif args.checkpoint_command == "status":
                result = resume_checkpoint(target)
            else:
                result = clear_checkpoint(target)
            emit_checkpoint_result(result, as_json=args.json)
            return 0 if result.ok else 1
        elif args.command == "resume":
            result = resume_checkpoint(target)
            emit_checkpoint_result(result, as_json=args.json, include_resume=True)
            return 0 if result.ok else 1
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
