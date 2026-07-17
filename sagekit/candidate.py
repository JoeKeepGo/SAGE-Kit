from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .change_control import RunState
from .convergence import (
    ConvergenceEvidence,
    PreauthorizedConvergenceAuthority,
    evaluate_convergence,
    evaluate_convergence_stops,
    paths_outside_authority,
)


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
    convergence_authority_digest: str | None = None
    convergence_authority_id: str | None = None
    execution_scope: str | None = None
    root_cause_family: str | None = None
    convergence_allowed_paths: tuple[str, ...] = ()
    convergence_invariant: str | None = None
    convergence_semantic_change_policy: str | None = None
    convergence_stop_conditions: tuple[str, ...] = ()
    finding_severity: int | None = None
    targeted_review_closed: bool = False
    finding_trend: str | None = None

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
        if self.fingerprint_version >= 2:
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
        if self.fingerprint_version == 3:
            payload.update(
                {
                    "convergence_authority_digest": self.convergence_authority_digest,
                    "convergence_authority_id": self.convergence_authority_id,
                    "execution_scope": self.execution_scope,
                    "root_cause_family": self.root_cause_family,
                    "convergence_allowed_paths": list(self.convergence_allowed_paths),
                    "convergence_invariant": self.convergence_invariant,
                    "convergence_semantic_change_policy": self.convergence_semantic_change_policy,
                    "convergence_stop_conditions": list(self.convergence_stop_conditions),
                    "finding_severity": self.finding_severity,
                    "targeted_review_closed": self.targeted_review_closed,
                    "finding_trend": self.finding_trend,
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
        version_2_fields = legacy_fields | {
            "fingerprint_version",
            "corrective_batch_id",
            "authority_anchor",
            "root_cause_id",
            "open_findings_count",
            "no_progress_rounds",
        }
        version_3_fields = version_2_fields | {
            "convergence_authority_digest",
            "convergence_authority_id",
            "execution_scope",
            "root_cause_family",
            "convergence_allowed_paths",
            "convergence_invariant",
            "convergence_semantic_change_policy",
            "convergence_stop_conditions",
            "finding_severity",
            "targeted_review_closed",
            "finding_trend",
        }
        fields = set(value)
        if fields not in {
            frozenset(legacy_fields),
            frozenset(version_2_fields),
            frozenset(version_3_fields),
        }:
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
        if fingerprint_version not in {1, 2, 3}:
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
        convergence_strings = (
            "convergence_authority_digest",
            "convergence_authority_id",
            "execution_scope",
            "root_cause_family",
            "convergence_invariant",
            "convergence_semantic_change_policy",
            "finding_trend",
        )
        if fingerprint_version == 3:
            for field in convergence_strings:
                if not isinstance(value.get(field), str) or not str(value[field]).strip():
                    raise ValueError(f"candidate {field.replace('_', ' ')} is invalid")
            for field in ("convergence_allowed_paths", "convergence_stop_conditions"):
                items = value.get(field)
                if (
                    not isinstance(items, list)
                    or not items
                    or not all(isinstance(item, str) and item for item in items)
                ):
                    raise ValueError(f"candidate {field.replace('_', ' ')} is invalid")
            if not isinstance(value.get("targeted_review_closed"), bool):
                raise ValueError("candidate targeted review state is invalid")
            finding_severity = value.get("finding_severity")
            if finding_severity is not None and (
                not isinstance(finding_severity, int)
                or isinstance(finding_severity, bool)
                or finding_severity < 0
            ):
                raise ValueError("candidate finding severity is invalid")
        elif any(value.get(field) is not None for field in convergence_strings):
            raise ValueError("legacy candidate cannot contain convergence authority")
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
            convergence_authority_digest=value.get("convergence_authority_digest"),
            convergence_authority_id=value.get("convergence_authority_id"),
            execution_scope=value.get("execution_scope"),
            root_cause_family=value.get("root_cause_family"),
            convergence_allowed_paths=tuple(value.get("convergence_allowed_paths", ())),
            convergence_invariant=value.get("convergence_invariant"),
            convergence_semantic_change_policy=value.get(
                "convergence_semantic_change_policy"
            ),
            convergence_stop_conditions=tuple(
                value.get("convergence_stop_conditions", ())
            ),
            finding_severity=value.get("finding_severity"),
            targeted_review_closed=value.get("targeted_review_closed", False),
            finding_trend=value.get("finding_trend"),
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
    finding_trend: str | None = None
    stop_reason: str | None = None


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
    convergence_authority: PreauthorizedConvergenceAuthority | None = None,
    convergence_evidence: ConvergenceEvidence | None = None,
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

    if (convergence_authority is None) != (convergence_evidence is None):
        reason = "convergence authority and structured evidence must be provided together"
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
        )

    generation = 1
    predecessor: str | None = None
    no_progress_rounds = 0
    finding_trend: str | None = None
    if previous is not None:
        assessment = assess_candidate(
            root,
            previous,
            contract_digest=contract_digest,
            dependency_digest=dependency_digest,
        )
        if assessment.ok:
            if previous.convergence_authority_digest is None:
                if convergence_authority is not None:
                    reason = (
                        "stable legacy candidate cannot gain convergence authority "
                        "without a successor handoff"
                    )
                    return CandidateFreezeResult(
                        False,
                        RunState.HANDOFF_READY,
                        reason,
                        stop_reason=reason,
                    )
            elif convergence_authority is not None and convergence_evidence is not None:
                stable_mismatches = list(
                    convergence_authority_mismatches(previous, convergence_authority)
                )
                stable_evidence = {
                    "execution scope": (
                        previous.execution_scope,
                        convergence_evidence.execution_scope,
                    ),
                    "root-cause family": (
                        previous.root_cause_family,
                        convergence_evidence.root_cause_family,
                    ),
                    "root-cause id": (
                        previous.root_cause_id,
                        convergence_evidence.root_cause_id,
                    ),
                    "finding count": (
                        previous.open_findings_count,
                        convergence_evidence.finding_count,
                    ),
                    "finding severity": (
                        previous.finding_severity,
                        convergence_evidence.finding_severity,
                    ),
                    "targeted review state": (
                        previous.targeted_review_closed,
                        convergence_evidence.targeted_review_closed,
                    ),
                }
                stable_mismatches.extend(
                    f"stable convergence {field} differs"
                    for field, (recorded, current) in stable_evidence.items()
                    if recorded != current
                )
                if stable_mismatches:
                    reason = "; ".join(stable_mismatches)
                    return CandidateFreezeResult(
                        False,
                        RunState.HANDOFF_READY,
                        reason,
                        mismatches=tuple(stable_mismatches),
                        stop_reason=reason,
                    )
                stopped = evaluate_convergence_stops(
                    convergence_authority,
                    convergence_evidence,
                    previous_no_progress_rounds=previous.no_progress_rounds,
                )
                if stopped is not None:
                    return CandidateFreezeResult(
                        False,
                        stopped.state,
                        stopped.reason,
                        finding_trend=stopped.trend,
                        stop_reason=stopped.reason,
                    )
            return CandidateFreezeResult(
                True,
                RunState.CONTINUE,
                "existing stable candidate still matches",
                previous,
            )
        window_active = previous.convergence_authority_digest is not None
        if window_active:
            if convergence_authority is None or convergence_evidence is None:
                reason = "active convergence window authority or evidence is missing"
                return CandidateFreezeResult(
                    False,
                    RunState.HANDOFF_READY,
                    reason,
                    mismatches=assessment.mismatches,
                    stop_reason=reason,
                )
            if not approved_corrective:
                reason = "successor is not classified as an approved corrective"
                return CandidateFreezeResult(
                    False,
                    RunState.HANDOFF_READY,
                    reason,
                    mismatches=assessment.mismatches,
                    stop_reason=reason,
                )
            authority_mismatches = convergence_authority_mismatches(
                previous,
                convergence_authority,
            )
            if authority_mismatches:
                reason = "; ".join(authority_mismatches)
                return CandidateFreezeResult(
                    False,
                    RunState.HANDOFF_READY,
                    reason,
                    mismatches=authority_mismatches,
                    stop_reason=reason,
                )
            if previous.contract_digest != contract_digest:
                reason = "contract digest changed outside convergence authority"
                return CandidateFreezeResult(
                    False,
                    RunState.HANDOFF_READY,
                    reason,
                    mismatches=assessment.mismatches,
                    stop_reason=reason,
                )
            changed_paths = _changed_paths(root, previous.head_sha)
            outside = paths_outside_authority(root, convergence_authority, changed_paths)
            if outside:
                reason = "changed paths outside convergence allowed paths: " + ", ".join(outside)
                return CandidateFreezeResult(
                    False,
                    RunState.HANDOFF_READY,
                    reason,
                    mismatches=(reason,),
                    stop_reason=reason,
                )
            convergence = evaluate_convergence(
                convergence_authority,
                convergence_evidence,
                previous_root_cause_id=previous.root_cause_id,
                previous_finding_count=previous.open_findings_count,
                previous_finding_severity=previous.finding_severity,
                previous_no_progress_rounds=previous.no_progress_rounds,
            )
            if convergence.state != RunState.CONTINUE:
                return CandidateFreezeResult(
                    False,
                    convergence.state,
                    convergence.reason,
                    mismatches=assessment.mismatches,
                    finding_trend=convergence.trend,
                    stop_reason=convergence.reason,
                )
            no_progress_rounds = convergence.no_progress_rounds
            finding_trend = convergence.trend
        elif convergence_authority is not None and not handoff_successor_approved:
            reason = "previous candidate has no convergence authority; a handoff approval is required"
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                reason,
                mismatches=assessment.mismatches,
                stop_reason=reason,
            )
        elif previous_final_verified and not handoff_successor_approved:
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
        if window_active:
            pass
        elif handoff_successor_approved:
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
    elif convergence_authority is not None and convergence_evidence is not None:
        outside = paths_outside_authority(
            root,
            convergence_authority,
            _changed_paths(root, None),
        )
        if outside:
            reason = "changed paths outside convergence allowed paths: " + ", ".join(outside)
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                reason,
                mismatches=(reason,),
                stop_reason=reason,
            )
        convergence = evaluate_convergence(
            convergence_authority,
            convergence_evidence,
            previous_root_cause_id=None,
            previous_finding_count=None,
            previous_finding_severity=None,
            previous_no_progress_rounds=0,
        )
        if convergence.state != RunState.CONTINUE:
            return CandidateFreezeResult(
                False,
                convergence.state,
                convergence.reason,
                finding_trend=convergence.trend,
                stop_reason=convergence.reason,
            )
        finding_trend = convergence.trend

    candidate = CandidateFingerprint(
        head_sha=_git_text(root, "rev-parse", "HEAD"),
        diff_hash=_diff_hash(root),
        contract_digest=_required_digest(contract_digest, "contract"),
        dependency_digest=_required_digest(dependency_digest, "dependency"),
        review_closed=True,
        corrective_batch_closed=True,
        generation=generation,
        predecessor_digest=predecessor,
        fingerprint_version=3 if convergence_authority is not None else 2,
        corrective_batch_id=(
            str(corrective_batch_id).strip() if corrective_batch_id else None
        ),
        authority_anchor=(
            convergence_authority.authority_id
            if convergence_authority is not None
            else (str(authority_anchor).strip() if authority_anchor else None)
        ),
        root_cause_id=(
            convergence_evidence.root_cause_id
            if convergence_evidence is not None
            else (str(root_cause_id).strip() if root_cause_id else None)
        ),
        open_findings_count=(
            convergence_evidence.finding_count
            if convergence_evidence is not None
            else open_findings_count
        ),
        no_progress_rounds=no_progress_rounds,
        convergence_authority_digest=(
            convergence_authority.digest if convergence_authority is not None else None
        ),
        convergence_authority_id=(
            convergence_authority.authority_id
            if convergence_authority is not None
            else None
        ),
        execution_scope=(
            convergence_authority.execution_scope
            if convergence_authority is not None
            else None
        ),
        root_cause_family=(
            convergence_authority.root_cause_family
            if convergence_authority is not None
            else None
        ),
        convergence_allowed_paths=(
            convergence_authority.allowed_paths
            if convergence_authority is not None
            else ()
        ),
        convergence_invariant=(
            convergence_authority.invariant
            if convergence_authority is not None
            else None
        ),
        convergence_semantic_change_policy=(
            convergence_authority.semantic_change_policy
            if convergence_authority is not None
            else None
        ),
        convergence_stop_conditions=(
            convergence_authority.stop_conditions
            if convergence_authority is not None
            else ()
        ),
        finding_severity=(
            convergence_evidence.finding_severity
            if convergence_evidence is not None
            else None
        ),
        targeted_review_closed=(
            convergence_evidence.targeted_review_closed
            if convergence_evidence is not None
            else False
        ),
        finding_trend=finding_trend,
    )
    return CandidateFreezeResult(
        True,
        RunState.CONTINUE,
        "stable candidate frozen",
        candidate,
        finding_trend=finding_trend,
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


def _changed_paths(root: Path, previous_head: str | None) -> tuple[str, ...]:
    if previous_head is None:
        try:
            base = _git_text(root, "merge-base", "HEAD", "origin/main")
        except ValueError:
            roots = _git_text(root, "rev-list", "--max-parents=0", "HEAD").splitlines()
            base = roots[-1]
    else:
        base = previous_head
    raw = _git_bytes(
        root,
        "diff",
        "--no-renames",
        "--name-only",
        "-z",
        f"{base}..HEAD",
    )
    return tuple(
        item.decode("utf-8", errors="strict").replace("\\", "/")
        for item in raw.split(b"\0")
        if item
    )


def convergence_authority_mismatches(
    previous: CandidateFingerprint,
    authority: PreauthorizedConvergenceAuthority,
) -> tuple[str, ...]:
    mismatches: list[str] = []
    if previous.convergence_authority_id != authority.authority_id:
        mismatches.append("convergence authority id changed")
    if previous.execution_scope != authority.execution_scope:
        mismatches.append("convergence execution scope changed")
    if previous.root_cause_family != authority.root_cause_family:
        mismatches.append("convergence root-cause family changed")
    if previous.convergence_allowed_paths != authority.allowed_paths:
        mismatches.append("convergence allowed paths changed")
    if previous.convergence_invariant != authority.invariant:
        mismatches.append("convergence invariant changed")
    if (
        previous.convergence_semantic_change_policy
        != authority.semantic_change_policy
    ):
        mismatches.append("convergence semantic change policy changed")
    if previous.convergence_stop_conditions != authority.stop_conditions:
        mismatches.append("convergence stop conditions changed")
    if previous.convergence_authority_digest != authority.digest:
        mismatches.append("convergence authority digest changed")
    return tuple(mismatches)


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
