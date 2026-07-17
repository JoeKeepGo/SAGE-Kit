from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .candidate import (
    CandidateFingerprint,
    assess_candidate,
    convergence_authority_mismatches,
)
from .change_control import ChangeClass
from .convergence import PreauthorizedConvergenceAuthority
from .evidence import EvidenceFingerprint
from .execution_limits import COUNTER_NAMES, ExecutionCounters
from .pathing import is_within, relative_repo_path


CHECKPOINT_SCHEMA_VERSION = 4
SUPPORTED_CHECKPOINT_SCHEMA_VERSIONS = frozenset({1, 2, 3, CHECKPOINT_SCHEMA_VERSION})
MAX_CHECKPOINT_BYTES = 32_000
REQUIRED_FIELDS = {
    "run_id",
    "goal",
    "repository_root",
    "branch",
    "base_sha",
    "head_sha",
    "authority",
    "change_class",
    "completed_work",
    "open_findings",
    "evidence_references",
    "invalidated_evidence",
    "execution_counters",
    "next_action",
    "allowed_paths",
    "stop_conditions",
}
SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "PASSWORD=",
    "TOKEN=",
    "API_KEY=",
    "BEARER ",
    "AUTHORIZATION:",
    "CLIENT_SECRET",
)


@dataclass(frozen=True)
class CheckpointResult:
    ok: bool
    rule: str
    message: str
    checkpoint: dict[str, object] | None = None
    mismatches: tuple[str, ...] = ()


def checkpoint_path(repository_root: Path) -> Path:
    return repository_root.resolve(strict=False) / ".sagekit/runtime/CURRENT_RUN.json"


def create_checkpoint(
    repository_root: Path,
    *,
    run_id: str,
    goal: str,
    authority_id: str,
    authority_version: str,
    authority_summary: str,
    change_class: ChangeClass,
    completed_work: Iterable[str],
    open_findings: Iterable[str],
    evidence_references: Iterable[object],
    invalidated_evidence: Iterable[str],
    execution_counters: ExecutionCounters,
    next_action: str,
    allowed_paths: Iterable[str],
    stop_conditions: Iterable[str],
    authority_references: Iterable[str] = (),
    base_sha: str | None = None,
    candidate: CandidateFingerprint | None = None,
    convergence_authority: PreauthorizedConvergenceAuthority | None = None,
) -> CheckpointResult:
    root = repository_root.resolve(strict=False)
    git_root, branch, head = _git_state(root)
    if git_root != root:
        raise ValueError(f"target is not the repository root: {root}")
    references = [_file_reference(root, value) for value in authority_references]
    authority_payload = {
        "id": _bounded_text(authority_id, "authority id"),
        "version": _bounded_text(authority_version, "authority version"),
        "summary": _bounded_text(authority_summary, "authority summary", 2_000),
        "references": references,
    }
    authority_payload["payload_sha256"] = _json_digest(authority_payload)
    evidence_payload = [_serialize_evidence_reference(root, value) for value in evidence_references]
    if candidate is not None:
        if candidate.convergence_authority_digest is not None and convergence_authority is None:
            raise ValueError("convergence candidate requires its authority payload")
        if convergence_authority is not None and (
            candidate.convergence_authority_digest != convergence_authority.digest
        ):
            raise ValueError("candidate convergence authority digest differs")
        if convergence_authority is not None:
            snapshot_mismatches = convergence_authority_mismatches(
                candidate,
                convergence_authority,
            )
            if snapshot_mismatches:
                raise ValueError(
                    "candidate convergence authority snapshot differs: "
                    + "; ".join(snapshot_mismatches)
                )
    now = datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "run_id": _bounded_text(run_id, "run id"),
        "goal": _bounded_text(goal, "goal", 2_000),
        "repository_root": str(root),
        "branch": branch,
        "base_sha": base_sha or _base_sha(root, head),
        "head_sha": head,
        "authority": authority_payload,
        "change_class": change_class.value,
        "completed_work": _bounded_list(completed_work, "completed work"),
        "open_findings": _bounded_list(open_findings, "open findings"),
        "evidence_references": evidence_payload,
        "invalidated_evidence": _bounded_list(invalidated_evidence, "invalidated evidence"),
        "execution_counters": execution_counters.to_dict(),
        "next_action": _bounded_text(next_action, "next action", 2_000),
        "allowed_paths": [
            relative_repo_path(root, value)
            for value in allowed_paths
        ],
        "stop_conditions": _bounded_list(stop_conditions, "stop conditions"),
        "candidate": candidate.to_dict() if candidate is not None else None,
        "convergence_authority": (
            convergence_authority.to_dict()
            if convergence_authority is not None
            else None
        ),
        "created_at": now,
        "updated_at": now,
    }
    payload["payload_sha256"] = _json_digest(payload)
    _reject_secrets(payload)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > MAX_CHECKPOINT_BYTES:
        raise ValueError(f"checkpoint exceeds {MAX_CHECKPOINT_BYTES} bytes")
    path = _safe_checkpoint_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix="CURRENT_RUN.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    temporary.replace(path)
    return CheckpointResult(True, "checkpoint-created", f"checkpoint created at {path}", payload)


def resume_checkpoint(
    repository_root: Path,
    *,
    expected_authority_id: str | None = None,
    expected_authority_version: str | None = None,
    expected_convergence_authority: PreauthorizedConvergenceAuthority | None = None,
) -> CheckpointResult:
    root = repository_root.resolve(strict=False)
    loaded = _load_checkpoint(root)
    if not loaded.ok or loaded.checkpoint is None:
        return loaded
    payload = loaded.checkpoint
    mismatches: list[str] = []
    try:
        git_root, branch, head = _git_state(root)
    except ValueError as exc:
        return CheckpointResult(False, "checkpoint-mismatch", str(exc), payload, (str(exc),))
    if str(payload.get("repository_root")) != str(git_root):
        mismatches.append(
            f"repository root differs: checkpoint={payload.get('repository_root')} current={git_root}"
        )
    if payload.get("branch") != branch:
        mismatches.append(f"branch differs: checkpoint={payload.get('branch')} current={branch}")
    if payload.get("head_sha") != head:
        mismatches.append(f"HEAD differs: checkpoint={payload.get('head_sha')} current={head}")
    recorded_payload_digest = payload.get("payload_sha256")
    digest_payload = {key: value for key, value in payload.items() if key != "payload_sha256"}
    if recorded_payload_digest != _json_digest(digest_payload):
        mismatches.append("checkpoint payload digest differs")
    authority = payload.get("authority")
    if isinstance(authority, dict):
        if expected_authority_id is not None and authority.get("id") != expected_authority_id:
            mismatches.append(
                f"authority id differs: checkpoint={authority.get('id')} "
                f"expected={expected_authority_id}"
            )
        if (
            expected_authority_version is not None
            and authority.get("version") != expected_authority_version
        ):
            mismatches.append(
                f"authority version differs: checkpoint={authority.get('version')} "
                f"expected={expected_authority_version}"
            )
        recorded_digest = authority.get("payload_sha256")
        digest_payload = {key: value for key, value in authority.items() if key != "payload_sha256"}
        if recorded_digest != _json_digest(digest_payload):
            mismatches.append("authority payload digest differs")
        mismatches.extend(_reference_mismatches(root, authority.get("references"), "authority"))
    else:
        mismatches.append("authority payload is missing or invalid")
    mismatches.extend(
        _reference_mismatches(root, payload.get("evidence_references"), "evidence")
    )
    convergence_authority: PreauthorizedConvergenceAuthority | None = None
    convergence_payload = payload.get("convergence_authority")
    if convergence_payload is not None:
        try:
            convergence_authority = PreauthorizedConvergenceAuthority.from_dict(
                convergence_payload
            )
        except ValueError as exc:
            mismatches.append(f"convergence authority is invalid: {exc}")
    if expected_convergence_authority is not None:
        if convergence_authority is None:
            mismatches.append("expected convergence authority is missing")
        elif convergence_authority.digest != expected_convergence_authority.digest:
            mismatches.append("expected convergence authority digest differs")
    candidate_payload = payload.get("candidate")
    if isinstance(candidate_payload, dict):
        try:
            candidate = CandidateFingerprint.from_dict(candidate_payload)
            candidate_assessment = assess_candidate(
                root,
                candidate,
                contract_digest=candidate.contract_digest,
                dependency_digest=candidate.dependency_digest,
            )
            mismatches.extend(
                f"candidate {item}" for item in candidate_assessment.mismatches
            )
            if candidate.convergence_authority_digest is not None:
                if convergence_authority is None:
                    mismatches.append("candidate convergence authority is missing")
                else:
                    mismatches.extend(
                        "candidate convergence authority snapshot: " + item
                        for item in convergence_authority_mismatches(
                            candidate,
                            convergence_authority,
                        )
                    )
            elif convergence_authority is not None:
                mismatches.append("legacy candidate cannot gain convergence authority")
        except ValueError as exc:
            mismatches.append(f"candidate fingerprint is invalid: {exc}")
    elif payload.get("schema_version") in {2, 3, CHECKPOINT_SCHEMA_VERSION} and candidate_payload is not None:
        mismatches.append("candidate fingerprint is invalid")
    if mismatches:
        return CheckpointResult(
            False,
            "checkpoint-mismatch",
            f"checkpoint does not match current state ({len(mismatches)} differences)",
            payload,
            tuple(mismatches),
        )
    return CheckpointResult(
        True,
        "checkpoint-resumable",
        "checkpoint matches repository, branch, HEAD, authority, and evidence",
        payload,
    )


def clear_checkpoint(repository_root: Path) -> CheckpointResult:
    root = repository_root.resolve(strict=False)
    try:
        path = _safe_checkpoint_path(root)
    except ValueError as exc:
        return CheckpointResult(False, "checkpoint-unsafe-path", str(exc))
    expected_parent = root / ".sagekit/runtime"
    if path.parent != expected_parent or not is_within(root, path):
        return CheckpointResult(False, "checkpoint-unsafe-path", f"unsafe checkpoint path: {path}")
    if not path.exists():
        return CheckpointResult(False, "checkpoint-missing", f"checkpoint not found: {path}")
    path.unlink()
    return CheckpointResult(True, "checkpoint-cleared", f"checkpoint cleared: {path}")


def _load_checkpoint(root: Path) -> CheckpointResult:
    try:
        path = _safe_checkpoint_path(root)
    except ValueError as exc:
        return CheckpointResult(False, "checkpoint-unsafe-path", str(exc))
    if not path.exists():
        return CheckpointResult(False, "checkpoint-missing", f"checkpoint not found: {path}")
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_CHECKPOINT_BYTES:
            raise ValueError(f"checkpoint exceeds {MAX_CHECKPOINT_BYTES} bytes")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("checkpoint root must be an object")
        missing = sorted(REQUIRED_FIELDS - set(payload))
        if missing:
            raise ValueError("checkpoint missing fields: " + ", ".join(missing))
        if payload.get("schema_version") not in SUPPORTED_CHECKPOINT_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported checkpoint schema: {payload.get('schema_version')}")
        if payload.get("schema_version") in {2, 3, CHECKPOINT_SCHEMA_VERSION} and "candidate" not in payload:
            raise ValueError("checkpoint missing fields: candidate")
        if payload.get("schema_version") == CHECKPOINT_SCHEMA_VERSION and "convergence_authority" not in payload:
            raise ValueError("checkpoint missing fields: convergence_authority")
        structure_errors = _checkpoint_structure_errors(root, payload)
        if structure_errors:
            raise ValueError("; ".join(structure_errors))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return CheckpointResult(False, "checkpoint-corrupt", f"checkpoint is corrupt: {exc}")
    return CheckpointResult(True, "checkpoint-loaded", "checkpoint loaded", payload)


def _git_state(root: Path) -> tuple[Path, str, str]:
    top = _run_git(root, "rev-parse", "--show-toplevel")
    branch = _run_git(root, "branch", "--show-current")
    head = _run_git(root, "rev-parse", "HEAD")
    if not branch:
        raise ValueError("checkpoint requires a named Git branch")
    return Path(top).resolve(strict=False), branch, head


def _base_sha(root: Path, head: str) -> str:
    try:
        return _run_git(root, "merge-base", "HEAD", "origin/main")
    except ValueError:
        roots = _run_git(root, "rev-list", "--max-parents=0", head).splitlines()
        return roots[-1] if roots else head


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _file_reference(root: Path, value: str | Path) -> dict[str, str]:
    relative = relative_repo_path(root, value)
    path = root / relative
    if not path.is_file():
        raise ValueError(f"reference is not a file: {relative}")
    return {"path": relative, "sha256": _file_digest(path)}


def _serialize_evidence_reference(root: Path, value: object) -> object:
    if isinstance(value, (str, Path)):
        return {"type": "file", **_file_reference(root, value)}
    if isinstance(value, EvidenceFingerprint):
        fingerprint = asdict(value)
        return {
            "type": "fingerprint",
            "fingerprint": fingerprint,
            "sha256": _json_digest(fingerprint),
        }
    if isinstance(value, Mapping):
        fingerprint = dict(value)
        allowed = set(EvidenceFingerprint.__dataclass_fields__)
        required = allowed - {"candidate_fingerprint"}
        if not required.issubset(fingerprint) or not set(fingerprint).issubset(allowed):
            raise ValueError("evidence fingerprint has missing or unknown fields")
        return {
            "type": "fingerprint",
            "fingerprint": fingerprint,
            "sha256": _json_digest(fingerprint),
        }
    raise ValueError(f"unsupported evidence reference: {type(value).__name__}")


def _reference_mismatches(root: Path, references: object, label: str) -> list[str]:
    if references is None:
        return []
    if not isinstance(references, list):
        return [f"{label} references are invalid"]
    mismatches: list[str] = []
    for reference in references:
        if not isinstance(reference, dict):
            mismatches.append(f"{label} reference is invalid")
            continue
        reference_type = "file" if label == "authority" else reference.get("type")
        if reference_type == "fingerprint":
            fingerprint = reference.get("fingerprint")
            allowed = set(EvidenceFingerprint.__dataclass_fields__)
            required = allowed - {"candidate_fingerprint"}
            if (
                not isinstance(fingerprint, dict)
                or not required.issubset(fingerprint)
                or not set(fingerprint).issubset(allowed)
            ):
                mismatches.append(f"{label} fingerprint is invalid")
            elif reference.get("sha256") != _json_digest(fingerprint):
                mismatches.append(f"{label} fingerprint digest differs")
            continue
        if reference_type != "file" or "path" not in reference or "sha256" not in reference:
            mismatches.append(f"{label} reference is invalid")
            continue
        try:
            relative = relative_repo_path(root, str(reference["path"]))
        except ValueError:
            mismatches.append(f"{label} reference escapes repository: {reference.get('path')}")
            continue
        path = root / relative
        if not path.is_file():
            mismatches.append(f"{label} reference missing: {relative}")
        elif _file_digest(path) != reference["sha256"]:
            mismatches.append(f"{label} reference digest differs: {relative}")
    return mismatches


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_text(value: str, field: str, maximum: int = 500) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} must not be empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return text


def _bounded_list(values: Iterable[str], field: str) -> list[str]:
    items = [_bounded_text(str(value), field, 2_000) for value in values]
    if len(items) > 100:
        raise ValueError(f"{field} exceeds 100 items")
    return items


def _reject_secrets(value: object) -> None:
    strings: list[str] = []

    def collect(item: object) -> None:
        if isinstance(item, str):
            strings.append(item)
        elif isinstance(item, Mapping):
            for key, child in item.items():
                collect(key)
                collect(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                collect(child)

    collect(value)
    upper = "\n".join(strings).upper()
    if any(marker in upper for marker in SECRET_MARKERS):
        raise ValueError("checkpoint text appears to contain a credential or secret")


def _safe_checkpoint_path(root: Path) -> Path:
    root = root.resolve(strict=False)
    sagekit_dir = root / ".sagekit"
    runtime_dir = sagekit_dir / "runtime"
    for directory in (sagekit_dir, runtime_dir):
        if directory.exists() or directory.is_symlink():
            if directory.is_symlink() or not is_within(root, directory):
                raise ValueError(f"checkpoint runtime path escapes repository: {directory}")
    return runtime_dir / "CURRENT_RUN.json"


def _checkpoint_structure_errors(root: Path, payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for field in (
        "run_id",
        "goal",
        "repository_root",
        "branch",
        "base_sha",
        "head_sha",
        "next_action",
        "payload_sha256",
    ):
        if not isinstance(payload.get(field), str) or not payload.get(field):
            errors.append(f"{field} must be a non-empty string")
    try:
        ChangeClass(str(payload.get("change_class")))
    except ValueError:
        errors.append("change_class is invalid")
    list_fields = (
        "completed_work",
        "open_findings",
        "evidence_references",
        "invalidated_evidence",
        "allowed_paths",
        "stop_conditions",
    )
    for field in list_fields:
        value = payload.get(field)
        if not isinstance(value, list) or len(value) > 100:
            errors.append(f"{field} must be a bounded list")
    allowed = payload.get("allowed_paths")
    if isinstance(allowed, list):
        for path in allowed:
            if not isinstance(path, str):
                errors.append("allowed_paths entries must be strings")
                continue
            try:
                relative_repo_path(root, path)
            except ValueError:
                errors.append(f"allowed path escapes repository: {path}")
    counters = payload.get("execution_counters")
    expected = set(ExecutionCounters().to_dict())
    previous_v2 = expected - {"verification_attempts"}
    legacy = {
        "implementation_workers",
        "read_only_review_agents",
        "parallel_agent_waves",
        "corrective_re_review_rounds",
        "full_suite_runs_after_baseline",
        "wheel_install_verification_runs",
        "reviewer_reports_per_scope",
        "root_cause_no_progress",
        "exception_events",
    }
    counter_fields = frozenset(counters) if isinstance(counters, dict) else frozenset()
    schema_version = payload.get("schema_version")
    allowed_counter_fields = {
        1: {frozenset(legacy)},
        2: {frozenset(previous_v2)},
        3: {frozenset(expected)},
        CHECKPOINT_SCHEMA_VERSION: {frozenset(expected)},
    }.get(schema_version, set())
    if not isinstance(counters, dict) or counter_fields not in allowed_counter_fields:
        errors.append("execution_counters fields are invalid")
    else:
        try:
            parsed = ExecutionCounters.from_dict(counters)
            numeric = [getattr(parsed, name) for name in COUNTER_NAMES]
            numeric.extend(parsed.final_full_suite_runs.values())
            numeric.extend(parsed.final_wheel_install_runs.values())
            numeric.extend(parsed.root_cause_no_progress.values())
            if any(item < 0 for item in numeric):
                errors.append("execution_counters values must be non-negative")
        except (TypeError, ValueError):
            errors.append("execution_counters values are invalid")
    if not isinstance(payload.get("authority"), dict):
        errors.append("authority must be an object")
    candidate = payload.get("candidate")
    if candidate is not None:
        if not isinstance(candidate, dict):
            errors.append("candidate must be an object or null")
        else:
            try:
                CandidateFingerprint.from_dict(candidate)
            except ValueError as exc:
                errors.append(f"candidate is invalid: {exc}")
    convergence_payload = payload.get("convergence_authority")
    schema_version = payload.get("schema_version")
    convergence_authority: PreauthorizedConvergenceAuthority | None = None
    if schema_version in {1, 2, 3} and convergence_payload is not None:
        errors.append("legacy checkpoint cannot contain convergence authority")
    elif convergence_payload is not None:
        try:
            convergence_authority = PreauthorizedConvergenceAuthority.from_dict(
                convergence_payload
            )
        except ValueError as exc:
            errors.append(f"convergence_authority is invalid: {exc}")
    return errors
