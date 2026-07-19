from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .candidate import CandidateFingerprint, CandidateFreezeResult, freeze_candidate
from .change_control import ChangeClass
from .check import run_check, run_source_repo_check
from .continuity import CheckpointResult, clear_checkpoint, create_checkpoint, resume_checkpoint
from .convergence import (
    ConvergenceEvidence,
    PreauthorizedConvergenceAuthority,
    load_convergence_authority,
)
from .doctor import run_doctor
from .execution_limits import COUNTER_NAMES, ExecutionCounters
from .findings import Finding, has_fail
from .init import run_init
from .modes import MODES
from .reporting import DEFAULT_MAX_FINDINGS, build_finding_report, finding_report_payload


class TargetError(ValueError):
    pass


class ConfigurationError(ValueError):
    pass


def max_findings_value(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max findings must be an integer") from exc
    if not 1 <= parsed <= 500:
        raise argparse.ArgumentTypeError("max findings must be between 1 and 500")
    return parsed


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
        "--max-findings",
        type=max_findings_value,
        default=DEFAULT_MAX_FINDINGS,
        help=f"Display at most this many findings (default: {DEFAULT_MAX_FINDINGS}).",
    )
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
    check.add_argument(
        "--scope-manifest",
        type=Path,
        help=(
            "Use an explicit Validation Scope Manifest for an adopted-project "
            "check; relative paths resolve from the invocation directory."
        ),
    )

    doctor = subparsers.add_parser("doctor", help="Diagnose SAGE-Kit project and runtime state.")
    add_target_argument(doctor)
    doctor.add_argument("--json", action="store_true", help="Print machine-readable findings.")
    doctor.add_argument(
        "--max-findings",
        type=max_findings_value,
        default=DEFAULT_MAX_FINDINGS,
        help=f"Display at most this many findings (default: {DEFAULT_MAX_FINDINGS}).",
    )

    init = subparsers.add_parser("init", help="Initialize SAGE-Kit governance documents.")
    add_target_argument(init)
    init.add_argument("--json", action="store_true", help="Print machine-readable findings.")
    init.add_argument("--mode", choices=MODES, default="light", help="Adoption depth to initialize.")
    init.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    init.add_argument("--force", action="store_true", help="Overwrite existing SAGE-Kit documents.")

    packet = subparsers.add_parser(
        "packet",
        help="Compile ephemeral execution packets from pinned thin documents.",
    )
    packet_commands = packet.add_subparsers(dest="packet_command", required=True)
    packet_compile = packet_commands.add_parser(
        "compile",
        help="Compile a standalone packet by default, or an explicit compact packet.",
    )
    add_target_argument(packet_compile)
    packet_compile.add_argument("--milestone", required=True, help="Exact milestone ID, such as M36.")
    packet_compile.add_argument("--phase", help="Exact phase ID; omit for a milestone packet.")
    packet_compile.add_argument(
        "--compact",
        action="store_true",
        help="Emit a compact packet bound to exact contract/profile digests.",
    )
    packet_compile.add_argument("--json", action="store_true", help="Print structured packet output.")
    packet_compile.add_argument(
        "--output",
        help="Explicit project-relative output file; omitted output is stdout-only.",
    )
    packet_compile.add_argument(
        "--overwrite-generated",
        action="store_true",
        help="Replace only a recognized previously generated packet.",
    )

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
    checkpoint_create.add_argument(
        "--counter",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Persist an execution counter; repeat as needed.",
    )
    checkpoint_create.add_argument("--base-sha")
    checkpoint_create.add_argument(
        "--convergence-authority",
        type=Path,
        help="Explicit preauthorized convergence authority JSON file.",
    )

    checkpoint_status = checkpoint_commands.add_parser("status", help="Validate the current checkpoint.")
    add_target_argument(checkpoint_status)
    checkpoint_status.add_argument("--json", action="store_true", help="Print machine-readable output.")
    checkpoint_status.add_argument("--expect-authority-id")
    checkpoint_status.add_argument("--expect-authority-version")
    checkpoint_status.add_argument("--convergence-authority", type=Path)

    checkpoint_clear = checkpoint_commands.add_parser("clear", help="Remove only CURRENT_RUN.json.")
    add_target_argument(checkpoint_clear)
    checkpoint_clear.add_argument("--json", action="store_true", help="Print machine-readable output.")

    candidate = subparsers.add_parser(
        "candidate",
        help="Freeze and inspect stable verification candidates.",
    )
    candidate_commands = candidate.add_subparsers(dest="candidate_command", required=True)
    candidate_freeze = candidate_commands.add_parser(
        "freeze",
        help="Validate closure and emit a stable candidate fingerprint.",
    )
    add_target_argument(candidate_freeze)
    candidate_freeze.add_argument("--json", action="store_true")
    candidate_freeze.add_argument("--contract-digest", required=True)
    candidate_freeze.add_argument("--dependency-digest", required=True)
    candidate_freeze.add_argument(
        "--snapshot-mode",
        choices=("clean-head", "working-tree"),
        default="clean-head",
        help=(
            "Freeze a clean HEAD by default, or explicitly bind staged, "
            "unstaged, and untracked Git state."
        ),
    )
    candidate_freeze.add_argument(
        "--snapshot-authority",
        help=(
            "Required ID or digest authorizing working-tree snapshot mode; "
            "invalid for clean-head."
        ),
    )
    candidate_freeze.add_argument("--review-closed", action="store_true")
    candidate_freeze.add_argument("--corrective-batch-closed", action="store_true")
    candidate_freeze.add_argument("--previous-candidate", type=Path)
    candidate_freeze.add_argument("--approved-corrective", action="store_true")
    candidate_freeze.add_argument("--corrective-batch-id")
    candidate_freeze.add_argument("--previous-final-verified", action="store_true")
    candidate_freeze.add_argument("--handoff-successor-approved", action="store_true")
    candidate_freeze.add_argument("--authority-anchor")
    candidate_freeze.add_argument("--convergence-authority", type=Path)
    candidate_freeze.add_argument("--execution-scope")
    candidate_freeze.add_argument("--root-cause-family")
    candidate_freeze.add_argument("--root-cause-id")
    candidate_freeze.add_argument("--finding-count", type=int)
    candidate_freeze.add_argument("--finding-severity", type=int)
    candidate_freeze.add_argument(
        "--semantic-change",
        choices=("implementation-preserving", "policy-changing"),
    )
    candidate_freeze.add_argument("--targeted-review-closed", action="store_true")
    candidate_freeze.add_argument("--next-layer-exposed", action="store_true")
    candidate_freeze.add_argument("--product-scope-expanded", action="store_true")
    candidate_freeze.add_argument("--approval-gate-opened", action="store_true")
    candidate_freeze.add_argument("--permissions-increased", action="store_true")
    candidate_freeze.add_argument("--test-or-gate-weakened", action="store_true")
    candidate_freeze.add_argument("--security-or-evidence-weakened", action="store_true")
    candidate_freeze.add_argument(
        "--contract-or-public-behavior-changed", action="store_true"
    )
    candidate_freeze.add_argument("--consumer-mutation", action="store_true")
    candidate_freeze.add_argument("--authority-precedence-changed", action="store_true")
    candidate_freeze.add_argument("--required-evidence-unavailable", action="store_true")

    resume = subparsers.add_parser("resume", help="Validate and emit the current run's next action.")
    add_target_argument(resume)
    resume.add_argument("--json", action="store_true", help="Print machine-readable output.")
    resume.add_argument("--expect-authority-id")
    resume.add_argument("--expect-authority-version")
    resume.add_argument("--convergence-authority", type=Path)
    return parser


def emit_findings(
    findings,
    as_json: bool,
    *,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> None:
    report = build_finding_report(findings, max_findings=max_findings)
    if as_json:
        print(json.dumps(finding_report_payload(report), indent=2, sort_keys=True))
        return
    for finding in report.findings:
        print(finding.to_text())
    print(
        f"SUMMARY findings: displayed={report.displayed} total={report.total} "
        f"truncated={report.truncated} FAIL={report.by_level['FAIL']} "
        f"WARN={report.by_level['WARN']} PASS={report.by_level['PASS']}"
    )


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
        "candidate": checkpoint.get("candidate"),
        "convergence_authority": checkpoint.get("convergence_authority"),
        "next_action": checkpoint.get("next_action"),
        "allowed_paths": checkpoint.get("allowed_paths", []),
        "stop_conditions": checkpoint.get("stop_conditions", []),
    }


def _load_authority_argument(
    path: Path | None,
) -> PreauthorizedConvergenceAuthority | None:
    if path is None:
        return None
    try:
        return load_convergence_authority(path.expanduser().resolve(strict=False))
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(str(exc)) from exc


def _load_candidate_argument(path: Path | None) -> CandidateFingerprint | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.expanduser().resolve(strict=False).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "candidate" in payload:
            payload = payload["candidate"]
        return CandidateFingerprint.from_dict(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ConfigurationError(f"could not load previous candidate: {exc}") from exc


def _convergence_evidence_argument(
    args,
    authority: PreauthorizedConvergenceAuthority | None,
) -> ConvergenceEvidence | None:
    if authority is None:
        convergence_values = (
            args.execution_scope,
            args.root_cause_family,
            args.root_cause_id,
            args.finding_count,
            args.finding_severity,
            args.semantic_change,
            args.targeted_review_closed,
            args.next_layer_exposed,
            args.product_scope_expanded,
            args.approval_gate_opened,
            args.permissions_increased,
            args.test_or_gate_weakened,
            args.security_or_evidence_weakened,
            args.contract_or_public_behavior_changed,
            args.consumer_mutation,
            args.authority_precedence_changed,
            args.required_evidence_unavailable,
        )
        if any(value not in {None, False} for value in convergence_values):
            raise ConfigurationError(
                "convergence evidence requires --convergence-authority"
            )
        return None
    missing = []
    if not args.root_cause_id:
        missing.append("--root-cause-id")
    if args.finding_count is None:
        missing.append("--finding-count")
    if not args.semantic_change:
        missing.append("--semantic-change")
    if missing:
        raise ConfigurationError(
            "convergence authority requires " + ", ".join(missing)
        )
    try:
        return ConvergenceEvidence(
            execution_scope=args.execution_scope or authority.execution_scope,
            root_cause_family=args.root_cause_family or authority.root_cause_family,
            root_cause_id=args.root_cause_id,
            finding_count=args.finding_count,
            finding_severity=args.finding_severity,
            semantic_change=args.semantic_change,
            targeted_review_closed=args.targeted_review_closed,
            next_layer_exposed=args.next_layer_exposed,
            product_scope_expanded=args.product_scope_expanded,
            approval_gate_opened=args.approval_gate_opened,
            permissions_increased=args.permissions_increased,
            test_or_gate_weakened=args.test_or_gate_weakened,
            security_or_evidence_weakened=args.security_or_evidence_weakened,
            contract_or_public_behavior_changed=args.contract_or_public_behavior_changed,
            consumer_mutation=args.consumer_mutation,
            authority_precedence_changed=args.authority_precedence_changed,
            required_evidence_unavailable=args.required_evidence_unavailable,
        )
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc


def convergence_status_payload(
    checkpoint: dict[str, object] | None = None,
    *,
    candidate: CandidateFingerprint | None = None,
    authority: PreauthorizedConvergenceAuthority | None = None,
    trend: str | None = None,
    stop_reason: str | None = None,
) -> dict[str, object]:
    if checkpoint is not None:
        authority_payload = checkpoint.get("convergence_authority")
        candidate_payload = checkpoint.get("candidate")
        if authority_payload is not None:
            try:
                authority = PreauthorizedConvergenceAuthority.from_dict(authority_payload)
            except ValueError:
                authority = None
        if isinstance(candidate_payload, dict):
            try:
                candidate = CandidateFingerprint.from_dict(candidate_payload)
            except ValueError:
                candidate = None
    return {
        "active": authority is not None or (
            candidate is not None and candidate.convergence_authority_digest is not None
        ),
        "authority_id": (
            authority.authority_id
            if authority is not None
            else (candidate.convergence_authority_id if candidate is not None else None)
        ),
        "root_cause_family": (
            authority.root_cause_family
            if authority is not None
            else (candidate.root_cause_family if candidate is not None else None)
        ),
        "root_cause_id": candidate.root_cause_id if candidate is not None else None,
        "finding_count": candidate.open_findings_count if candidate is not None else None,
        "finding_trend": trend or (candidate.finding_trend if candidate is not None else None),
        "no_progress_rounds": candidate.no_progress_rounds if candidate is not None else 0,
        "targeted_review_closed": (
            candidate.targeted_review_closed if candidate is not None else False
        ),
        "stop_reason": stop_reason,
    }


def _emit_convergence_text(payload: dict[str, object]) -> None:
    print(f"CONVERGENCE_WINDOW {'active' if payload['active'] else 'inactive'}")
    for label, field in (
        ("AUTHORITY_ID", "authority_id"),
        ("ROOT_CAUSE_FAMILY", "root_cause_family"),
        ("ROOT_CAUSE_ID", "root_cause_id"),
        ("FINDING_COUNT", "finding_count"),
        ("FINDING_TREND", "finding_trend"),
        ("NO_PROGRESS_ROUNDS", "no_progress_rounds"),
        ("STOP_REASON", "stop_reason"),
    ):
        if payload[field] is not None:
            print(f"{label} {payload[field]}")


def parse_execution_counters(values: list[str]) -> ExecutionCounters:
    payload: dict[str, object] = {}
    for value in values:
        name, separator, raw_count = value.partition("=")
        if not separator or name not in COUNTER_NAMES:
            raise ValueError(f"invalid execution counter: {value}")
        try:
            count = int(raw_count)
        except ValueError as exc:
            raise ValueError(f"invalid execution counter: {value}") from exc
        if count < 0:
            raise ValueError(f"execution counter must be non-negative: {value}")
        payload[name] = count
    return ExecutionCounters.from_dict(payload)


def emit_checkpoint_result(
    result: CheckpointResult,
    *,
    as_json: bool,
    include_resume: bool = False,
) -> None:
    finding = checkpoint_finding(result)
    report = build_finding_report([finding])
    convergence = convergence_status_payload(result.checkpoint)
    if as_json:
        payload = finding_report_payload(report)
        payload["convergence"] = convergence
        if include_resume:
            resume_payload = safe_resume_payload(result)
            if resume_payload is not None:
                payload["resume"] = resume_payload
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(finding.to_text())
    print(
        f"SUMMARY findings: displayed=1 total=1 truncated=0 "
        f"FAIL={report.by_level['FAIL']} WARN={report.by_level['WARN']} "
        f"PASS={report.by_level['PASS']}"
    )
    _emit_convergence_text(convergence)
    if include_resume:
        resume_payload = safe_resume_payload(result)
        if resume_payload is not None:
            print(f"NEXT_ACTION: {resume_payload['next_action']}")


def emit_candidate_result(
    result: CandidateFreezeResult,
    *,
    as_json: bool,
    authority: PreauthorizedConvergenceAuthority | None = None,
) -> None:
    convergence = convergence_status_payload(
        candidate=result.candidate,
        authority=authority,
        trend=result.finding_trend,
        stop_reason=result.stop_reason,
    )
    payload = {
        "ok": result.ok,
        "state": result.state.value,
        "message": result.message,
        "manual_budget_relaxation_required": result.manual_budget_relaxation_required,
        "mismatches": list(result.mismatches),
        "candidate": result.candidate.to_dict() if result.candidate is not None else None,
        "convergence": convergence,
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"STATE {payload['state']}")
    print(f"MESSAGE {payload['message']}")
    print(
        "MANUAL_BUDGET_RELAXATION_REQUIRED "
        f"{str(payload['manual_budget_relaxation_required']).lower()}"
    )
    if result.candidate is not None:
        print(f"CANDIDATE {result.candidate.digest}")
    _emit_convergence_text(convergence)
    for mismatch in result.mismatches:
        print(f"MISMATCH {mismatch}")


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
            return 2
        if args.command == "check":
            if args.source_repo and args.scope_manifest is not None:
                findings = [
                    Finding(
                        "FAIL",
                        "scope-manifest-usage",
                        None,
                        None,
                        "--scope-manifest cannot be combined with --source-repo",
                    )
                ]
                emit_findings(findings, args.json, max_findings=args.max_findings)
                return 2
            if args.source_repo:
                findings = run_source_repo_check(target)
            else:
                scope_manifest_path = None
                if args.scope_manifest is not None:
                    scope_manifest_path = args.scope_manifest.expanduser()
                    if not scope_manifest_path.is_absolute():
                        scope_manifest_path = Path.cwd() / scope_manifest_path
                    scope_manifest_path = scope_manifest_path.resolve(strict=False)
                    if not scope_manifest_path.exists():
                        findings = [
                            Finding(
                                "FAIL",
                                "scope-manifest-usage",
                                scope_manifest_path.as_posix(),
                                None,
                                f"scope manifest does not exist: {scope_manifest_path}",
                            )
                        ]
                        emit_findings(
                            findings,
                            args.json,
                            max_findings=args.max_findings,
                        )
                        return 2
                    if not scope_manifest_path.is_file():
                        findings = [
                            Finding(
                                "FAIL",
                                "scope-manifest-usage",
                                scope_manifest_path.as_posix(),
                                None,
                                f"scope manifest must be a file: {scope_manifest_path}",
                            )
                        ]
                        emit_findings(
                            findings,
                            args.json,
                            max_findings=args.max_findings,
                        )
                        return 2
                findings = run_check(
                    target,
                    gate_ready=args.gate_ready,
                    mode=args.mode,
                    scope_manifest_path=scope_manifest_path,
                )
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
        elif args.command == "packet":
            from .packet import PacketError, compile_packet, write_compiled_packet

            if not target.exists() or not target.is_dir():
                findings = [
                    Finding(
                        "FAIL",
                        "packet-target",
                        str(target),
                        None,
                        "packet compilation requires an existing project directory",
                    )
                ]
                emit_findings(findings, args.json)
                return 2
            if args.overwrite_generated and args.output is None:
                findings = [
                    Finding(
                        "FAIL",
                        "packet-output-usage",
                        None,
                        None,
                        "--overwrite-generated requires --output",
                    )
                ]
                emit_findings(findings, args.json)
                return 2
            try:
                compiled = compile_packet(
                    target,
                    args.milestone,
                    args.phase,
                    compact=args.compact,
                )
                output_path = None
                if args.output is not None:
                    output_path = write_compiled_packet(
                        target,
                        args.output,
                        compiled,
                        overwrite_generated=args.overwrite_generated,
                    )
            except PacketError as exc:
                finding = Finding("FAIL", "packet-compile", None, None, str(exc))
                emit_findings([finding], args.json)
                return 1

            packet_payload = compiled.payload
            output_display = (
                output_path.relative_to(target).as_posix()
                if output_path is not None
                else None
            )
            if args.json:
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "packet_sha256": compiled.digest,
                            "packet": packet_payload,
                            "output": output_display,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print("SAGEKIT_GENERATED_PACKET_V1")
                print(json.dumps(packet_payload, indent=2, sort_keys=True))
            return 0
        elif args.command == "candidate":
            convergence_authority = _load_authority_argument(
                args.convergence_authority
            )
            previous_candidate = _load_candidate_argument(args.previous_candidate)
            convergence_evidence = _convergence_evidence_argument(
                args,
                convergence_authority,
            )
            result = freeze_candidate(
                target,
                contract_digest=args.contract_digest,
                dependency_digest=args.dependency_digest,
                review_closed=args.review_closed,
                corrective_batch_closed=args.corrective_batch_closed,
                previous=previous_candidate,
                approved_corrective=args.approved_corrective,
                corrective_batch_id=args.corrective_batch_id,
                previous_final_verified=args.previous_final_verified,
                handoff_successor_approved=args.handoff_successor_approved,
                authority_anchor=args.authority_anchor,
                root_cause_id=args.root_cause_id,
                open_findings_count=args.finding_count,
                convergence_authority=convergence_authority,
                convergence_evidence=convergence_evidence,
                snapshot_mode=args.snapshot_mode,
                snapshot_authority=args.snapshot_authority,
            )
            emit_candidate_result(
                result,
                as_json=args.json,
            )
            return 0 if result.ok else 1
        elif args.command == "checkpoint":
            if args.checkpoint_command == "create":
                convergence_authority = _load_authority_argument(
                    args.convergence_authority
                )
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
                    execution_counters=parse_execution_counters(args.counter),
                    next_action=args.next_action,
                    allowed_paths=args.allowed_path,
                    stop_conditions=args.stop_condition,
                    base_sha=args.base_sha,
                    convergence_authority=convergence_authority,
                )
            elif args.checkpoint_command == "status":
                result = resume_checkpoint(
                    target,
                    expected_authority_id=args.expect_authority_id,
                    expected_authority_version=args.expect_authority_version,
                    expected_convergence_authority=_load_authority_argument(
                        args.convergence_authority
                    ),
                )
            else:
                result = clear_checkpoint(target)
            emit_checkpoint_result(result, as_json=args.json)
            return 0 if result.ok else 1
        elif args.command == "resume":
            result = resume_checkpoint(
                target,
                expected_authority_id=args.expect_authority_id,
                expected_authority_version=args.expect_authority_version,
                expected_convergence_authority=_load_authority_argument(
                    args.convergence_authority
                ),
            )
            emit_checkpoint_result(result, as_json=args.json, include_resume=True)
            return 0 if result.ok else 1
        else:
            parser.print_help(sys.stderr)
            return 2
        emit_findings(
            findings,
            args.json,
            max_findings=getattr(args, "max_findings", DEFAULT_MAX_FINDINGS),
        )
        return 1 if has_fail(findings) else 0
    except KeyboardInterrupt:
        raise
    except ConfigurationError as exc:
        finding = Finding("FAIL", "configuration-error", None, None, str(exc))
        emit_findings([finding], getattr(args, "json", False))
        return 2
    except Exception as exc:
        finding = Finding("FAIL", "internal-error", None, None, str(exc))
        if getattr(args, "json", False):
            print(json.dumps(finding_report_payload(build_finding_report([finding])), indent=2))
        else:
            print(f"FAIL internal-error: {exc}", file=sys.stderr)
            print(
                "SUMMARY findings: displayed=1 total=1 truncated=0 "
                "FAIL=1 WARN=0 PASS=0",
                file=sys.stderr,
            )
        return 3
