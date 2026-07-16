from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .change_control import RunState


@dataclass(frozen=True)
class CandidateFingerprint:
    head_sha: str
    diff_hash: str
    contract_digest: str
    dependency_digest: str
    review_closed: bool
    corrective_batch_closed: bool
    generation: int = 1
    predecessor_digest: str | None = None
    fingerprint_version: int = 1
    corrective_batch_id: str | None = None
    authority_anchor: str | None = None
    root_cause_id: str | None = None
    open_findings_count: int | None = None
    no_progress_rounds: int = 0

    @property
    def digest(self) -> str:
        return _json_digest(self._digest_payload())

    def _digest_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "head_sha": self.head_sha,
            "diff_hash": self.diff_hash,
            "contract_digest": self.contract_digest,
            "dependency_digest": self.dependency_digest,
            "review_closed": self.review_closed,
            "corrective_batch_closed": self.corrective_batch_closed,
            "generation": self.generation,
            "predecessor_digest": self.predecessor_digest,
        }
        if self.fingerprint_version == 2:
            payload.update(
                {
                    "fingerprint_version": self.fingerprint_version,
                    "corrective_batch_id": self.corrective_batch_id,
                    "authority_anchor": self.authority_anchor,
                    "root_cause_id": self.root_cause_id,
                    "open_findings_count": self.open_findings_count,
                    "no_progress_rounds": self.no_progress_rounds,
                }
            )
        return payload

    def to_dict(self) -> dict[str, object]:
        return {**self._digest_payload(), "fingerprint": self.digest}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CandidateFingerprint":
        legacy_fields = {
            "head_sha",
            "diff_hash",
            "contract_digest",
            "dependency_digest",
            "review_closed",
            "corrective_batch_closed",
            "generation",
            "predecessor_digest",
            "fingerprint",
        }
        current_fields = legacy_fields | {
            "fingerprint_version",
            "corrective_batch_id",
            "authority_anchor",
            "root_cause_id",
            "open_findings_count",
            "no_progress_rounds",
        }
        fields = set(value)
        if fields not in {frozenset(legacy_fields), frozenset(current_fields)}:
            raise ValueError("candidate fingerprint fields are invalid")
        if not all(
            isinstance(value[field], str) and value[field]
            for field in ("head_sha", "diff_hash", "contract_digest", "dependency_digest")
        ):
            raise ValueError("candidate fingerprint digests must be non-empty strings")
        if not isinstance(value["review_closed"], bool) or not isinstance(
            value["corrective_batch_closed"], bool
        ):
            raise ValueError("candidate closure fields must be booleans")
        generation = value["generation"]
        if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
            raise ValueError("candidate generation must be a positive integer")
        predecessor = value["predecessor_digest"]
        if predecessor is not None and (not isinstance(predecessor, str) or not predecessor):
            raise ValueError("candidate predecessor digest is invalid")
        fingerprint_version = value.get("fingerprint_version", 1)
        if fingerprint_version not in {1, 2}:
            raise ValueError("candidate fingerprint version is invalid")
        optional_strings = (
            "corrective_batch_id",
            "authority_anchor",
            "root_cause_id",
        )
        for field in optional_strings:
            item = value.get(field)
            if item is not None and (not isinstance(item, str) or not item.strip()):
                raise ValueError(f"candidate {field.replace('_', ' ')} is invalid")
        open_findings_count = value.get("open_findings_count")
        if open_findings_count is not None and (
            not isinstance(open_findings_count, int)
            or isinstance(open_findings_count, bool)
            or open_findings_count < 0
        ):
            raise ValueError("candidate open findings count is invalid")
        no_progress_rounds = value.get("no_progress_rounds", 0)
        if (
            not isinstance(no_progress_rounds, int)
            or isinstance(no_progress_rounds, bool)
            or no_progress_rounds < 0
        ):
            raise ValueError("candidate no-progress rounds are invalid")
        candidate = cls(
            head_sha=value["head_sha"],
            diff_hash=value["diff_hash"],
            contract_digest=value["contract_digest"],
            dependency_digest=value["dependency_digest"],
            review_closed=value["review_closed"],
            corrective_batch_closed=value["corrective_batch_closed"],
            generation=generation,
            predecessor_digest=predecessor,
            fingerprint_version=fingerprint_version,
            corrective_batch_id=value.get("corrective_batch_id"),
            authority_anchor=value.get("authority_anchor"),
            root_cause_id=value.get("root_cause_id"),
            open_findings_count=open_findings_count,
            no_progress_rounds=no_progress_rounds,
        )
        if value["fingerprint"] != candidate.digest:
            raise ValueError("candidate fingerprint digest differs")
        return candidate


@dataclass(frozen=True)
class CandidateAssessment:
    ok: bool
    state: RunState
    message: str
    mismatches: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateFreezeResult:
    ok: bool
    state: RunState
    message: str
    candidate: CandidateFingerprint | None = None
    mismatches: tuple[str, ...] = ()
    manual_budget_relaxation_required: bool = False


def freeze_candidate(
    repository_root: Path,
    *,
    contract_digest: str,
    dependency_digest: str,
    review_closed: bool,
    corrective_batch_closed: bool,
    previous: CandidateFingerprint | None = None,
    approved_corrective: bool = False,
    corrective_batch_id: str | None = None,
    previous_final_verified: bool = False,
    handoff_successor_approved: bool = False,
    authority_anchor: str | None = None,
    root_cause_id: str | None = None,
    open_findings_count: int | None = None,
) -> CandidateFreezeResult:
    root = _repository_root(repository_root)
    if not review_closed or not corrective_batch_closed:
        missing = []
        if not review_closed:
            missing.append("review is not closed")
        if not corrective_batch_closed:
            missing.append("corrective batch is not closed")
        return CandidateFreezeResult(
            False,
            RunState.HUMAN_DECISION_REQUIRED,
            "; ".join(missing),
            mismatches=tuple(missing),
        )
    changes = _worktree_changes(root)
    if changes:
        mismatch = "unexpected worktree changes: " + ", ".join(changes)
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            mismatch,
            mismatches=(mismatch,),
        )

    generation = 1
    predecessor: str | None = None
    no_progress_rounds = 0
    if previous is not None:
        assessment = assess_candidate(
            root,
            previous,
            contract_digest=contract_digest,
            dependency_digest=dependency_digest,
        )
        if assessment.ok:
            return CandidateFreezeResult(
                True,
                RunState.CONTINUE,
                "existing stable candidate still matches",
                previous,
            )
        if previous_final_verified and not handoff_successor_approved:
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                "final candidate changed after final verification",
                mismatches=assessment.mismatches,
            )
        if not approved_corrective:
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                "candidate changed outside an approved corrective batch",
                mismatches=assessment.mismatches,
            )
        if handoff_successor_approved:
            missing_authority: list[str] = []
            if not str(authority_anchor or "").strip():
                missing_authority.append("authority anchor is required")
            if not str(root_cause_id or "").strip():
                missing_authority.append("root cause id is required")
            if (
                not isinstance(open_findings_count, int)
                or isinstance(open_findings_count, bool)
                or open_findings_count < 0
            ):
                missing_authority.append("open findings count is required")
            if missing_authority:
                return CandidateFreezeResult(
                    False,
                    RunState.HUMAN_DECISION_REQUIRED,
                    "; ".join(missing_authority),
                    mismatches=tuple(missing_authority),
                )
            if (
                previous.root_cause_id == root_cause_id
                and previous.open_findings_count is not None
            ):
                no_progress_rounds = (
                    previous.no_progress_rounds + 1
                    if open_findings_count >= previous.open_findings_count
                    else 0
                )
            if no_progress_rounds >= 2:
                return CandidateFreezeResult(
                    False,
                    RunState.BLOCKED,
                    "same root cause made no progress for two approved rounds",
                    mismatches=assessment.mismatches,
                )
        else:
            normalized_batch_id = str(corrective_batch_id or "").strip()
            if not normalized_batch_id:
                return CandidateFreezeResult(
                    False,
                    RunState.HUMAN_DECISION_REQUIRED,
                    "corrective batch id is required for an automatic successor",
                    mismatches=assessment.mismatches,
                )
            if previous.corrective_batch_id == normalized_batch_id:
                return CandidateFreezeResult(
                    False,
                    RunState.HANDOFF_READY,
                    "corrective batch already created its automatic successor",
                    mismatches=assessment.mismatches,
                )
        generation = previous.generation + 1
        predecessor = previous.digest

    candidate = CandidateFingerprint(
        head_sha=_git_text(root, "rev-parse", "HEAD"),
        diff_hash=_diff_hash(root),
        contract_digest=_required_digest(contract_digest, "contract"),
        dependency_digest=_required_digest(dependency_digest, "dependency"),
        review_closed=True,
        corrective_batch_closed=True,
        generation=generation,
        predecessor_digest=predecessor,
        fingerprint_version=2,
        corrective_batch_id=(
            str(corrective_batch_id).strip() if corrective_batch_id else None
        ),
        authority_anchor=(
            str(authority_anchor).strip() if authority_anchor else None
        ),
        root_cause_id=str(root_cause_id).strip() if root_cause_id else None,
        open_findings_count=open_findings_count,
        no_progress_rounds=no_progress_rounds,
    )
    return CandidateFreezeResult(
        True,
        RunState.CONTINUE,
        "stable candidate frozen",
        candidate,
    )


def assess_candidate(
    repository_root: Path,
    candidate: CandidateFingerprint | None,
    *,
    contract_digest: str,
    dependency_digest: str,
) -> CandidateAssessment:
    if candidate is None:
        return CandidateAssessment(
            False,
            RunState.HANDOFF_READY,
            "candidate fingerprint is missing",
            ("candidate fingerprint is missing",),
        )
    root = _repository_root(repository_root)
    mismatches: list[str] = []
    current_head = _git_text(root, "rev-parse", "HEAD")
    if candidate.head_sha != current_head:
        mismatches.append(
            f"HEAD differs: candidate={candidate.head_sha} current={current_head}"
        )
    current_diff = _diff_hash(root)
    if candidate.diff_hash != current_diff:
        mismatches.append(
            f"diff hash differs: candidate={candidate.diff_hash} current={current_diff}"
        )
    if candidate.contract_digest != contract_digest:
        mismatches.append(
            "contract digest differs: "
            f"candidate={candidate.contract_digest} current={contract_digest}"
        )
    if candidate.dependency_digest != dependency_digest:
        mismatches.append(
            "dependency digest differs: "
            f"candidate={candidate.dependency_digest} current={dependency_digest}"
        )
    if not candidate.review_closed:
        mismatches.append("candidate review is not closed")
    if not candidate.corrective_batch_closed:
        mismatches.append("candidate corrective batch is not closed")
    changes = _worktree_changes(root)
    if changes:
        mismatches.append("unexpected worktree changes: " + ", ".join(changes))
    if mismatches:
        return CandidateAssessment(
            False,
            RunState.HANDOFF_READY,
            f"candidate fingerprint mismatch ({len(mismatches)} differences)",
            tuple(mismatches),
        )
    return CandidateAssessment(
        True,
        RunState.CONTINUE,
        "candidate fingerprint matches current worktree",
    )


def _repository_root(repository_root: Path) -> Path:
    root = repository_root.resolve(strict=False)
    actual = Path(_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=False)
    if actual != root:
        raise ValueError(f"target is not the repository root: {root}")
    return root


def _diff_hash(root: Path) -> str:
    try:
        base = _git_text(root, "merge-base", "HEAD", "origin/main")
    except ValueError:
        roots = _git_text(root, "rev-list", "--max-parents=0", "HEAD").splitlines()
        base = roots[-1]
    payload = _git_bytes(root, "diff", "--binary", "--no-ext-diff", f"{base}...HEAD")
    return hashlib.sha256(payload).hexdigest()


def _worktree_changes(root: Path) -> tuple[str, ...]:
    output = _git_text(root, "status", "--porcelain=v1", "--untracked-files=all")
    return tuple(
        line
        for line in output.splitlines()
        if line and not line[3:].replace("\\", "/").startswith(".sagekit/runtime/")
    )


def _required_digest(value: str, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} digest must not be empty")
    return text


def _git_text(root: Path, *args: str) -> str:
    return _git_bytes(root, *args).decode("utf-8", errors="strict").strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            result.stderr.decode("utf-8", errors="replace").strip()
            or f"git {' '.join(args)} failed"
        )
    return result.stdout


def _json_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
