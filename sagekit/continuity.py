from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .change_control import ChangeClass
from .execution_limits import ExecutionCounters
from .pathing import is_within, relative_repo_path


CHECKPOINT_SCHEMA_VERSION = 1
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
SECRET_MARKERS = ("BEGIN PRIVATE KEY", "PASSWORD=", "TOKEN=", "API_KEY=")


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
) -> CheckpointResult:
    root = repository_root.resolve(strict=False)
    _reject_secret_text(run_id, goal, authority_summary, next_action)
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
        "created_at": now,
        "updated_at": now,
    }
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > MAX_CHECKPOINT_BYTES:
        raise ValueError(f"checkpoint exceeds {MAX_CHECKPOINT_BYTES} bytes")
    path = checkpoint_path(root)
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


def resume_checkpoint(repository_root: Path) -> CheckpointResult:
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
    authority = payload.get("authority")
    if isinstance(authority, dict):
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
    path = checkpoint_path(root)
    expected_parent = root / ".sagekit/runtime"
    if path.parent != expected_parent or not is_within(root, path):
        return CheckpointResult(False, "checkpoint-unsafe-path", f"unsafe checkpoint path: {path}")
    if not path.exists():
        return CheckpointResult(False, "checkpoint-missing", f"checkpoint not found: {path}")
    path.unlink()
    return CheckpointResult(True, "checkpoint-cleared", f"checkpoint cleared: {path}")


def _load_checkpoint(root: Path) -> CheckpointResult:
    path = checkpoint_path(root)
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
        if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError(f"unsupported checkpoint schema: {payload.get('schema_version')}")
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
        return _file_reference(root, value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError(f"unsupported evidence reference: {type(value).__name__}")


def _reference_mismatches(root: Path, references: object, label: str) -> list[str]:
    if references is None:
        return []
    if not isinstance(references, list):
        return [f"{label} references are invalid"]
    mismatches: list[str] = []
    for reference in references:
        if not isinstance(reference, dict) or "path" not in reference or "sha256" not in reference:
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


def _reject_secret_text(*values: str) -> None:
    upper = "\n".join(str(value) for value in values).upper()
    if any(marker in upper for marker in SECRET_MARKERS):
        raise ValueError("checkpoint text appears to contain a credential or secret")
