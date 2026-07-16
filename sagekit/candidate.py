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

    @property
    def digest(self) -> str:
        return _json_digest(self._digest_payload())

    def _digest_payload(self) -> dict[str, object]:
        return {
            "head_sha": self.head_sha,
            "diff_hash": self.diff_hash,
            "contract_digest": self.contract_digest,
            "dependency_digest": self.dependency_digest,
            "review_closed": self.review_closed,
            "corrective_batch_closed": self.corrective_batch_closed,
            "generation": self.generation,
            "predecessor_digest": self.predecessor_digest,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._digest_payload(), "fingerprint": self.digest}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CandidateFingerprint":
        required = {
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
        if set(value) != required:
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
        candidate = cls(
            head_sha=value["head_sha"],
            diff_hash=value["diff_hash"],
            contract_digest=value["contract_digest"],
            dependency_digest=value["dependency_digest"],
            review_closed=value["review_closed"],
            corrective_batch_closed=value["corrective_batch_closed"],
            generation=generation,
            predecessor_digest=predecessor,
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
    previous_final_verified: bool = False,
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
        if previous_final_verified:
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
        if previous.generation >= 2:
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                "candidate regeneration limit reached",
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
