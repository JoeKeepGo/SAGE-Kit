from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .change_control import RunState
from .managed_execution import ManagedExecutionError, run_managed_git
from .normalization import NormalizationFinding, NormalizationReport, whitespace_preflight
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
    snapshot_mode: str = "clean-head"
    working_tree_digest: str | None = None
    snapshot_paths: tuple[str, ...] = ()
    snapshot_authority: str | None = None
    active_milestone_id: str | None = None
    active_spec_digest: str | None = None

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
        if self.fingerprint_version >= 3:
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
        if self.fingerprint_version >= 4:
            payload.update(
                {
                    "snapshot_mode": self.snapshot_mode,
                    "working_tree_digest": self.working_tree_digest,
                    "snapshot_paths": list(self.snapshot_paths),
                    "snapshot_authority": self.snapshot_authority,
                }
            )
        if self.fingerprint_version >= 5:
            payload.update(
                {
                    "active_milestone_id": self.active_milestone_id,
                    "active_spec_digest": self.active_spec_digest,
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
        version_4_fields = version_3_fields | {
            "snapshot_mode",
            "working_tree_digest",
            "snapshot_paths",
            "snapshot_authority",
        }
        version_5_fields = version_4_fields | {
            "active_milestone_id",
            "active_spec_digest",
        }
        fields = set(value)
        fingerprint_version = value.get("fingerprint_version", 1)
        if (
            not isinstance(fingerprint_version, int)
            or isinstance(fingerprint_version, bool)
            or fingerprint_version not in {1, 2, 3, 4, 5}
        ):
            raise ValueError("candidate fingerprint version is invalid")
        expected_fields = {
            1: legacy_fields,
            2: version_2_fields,
            3: version_3_fields,
            4: version_4_fields,
            5: version_5_fields,
        }[fingerprint_version]
        if fields != expected_fields:
            raise ValueError(
                f"candidate fingerprint fields do not match version {fingerprint_version}"
            )
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
        has_convergence = value.get("convergence_authority_digest") is not None
        if fingerprint_version >= 3 and has_convergence:
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
        elif fingerprint_version == 3:
            raise ValueError("version 3 candidate requires convergence authority")
        elif any(value.get(field) is not None for field in convergence_strings):
            raise ValueError("candidate cannot contain partial convergence authority")
        elif fingerprint_version >= 4 and (
            value.get("convergence_allowed_paths")
            or value.get("convergence_stop_conditions")
            or value.get("finding_severity") is not None
            or value.get("targeted_review_closed") is not False
        ):
            raise ValueError("candidate cannot contain partial convergence evidence")
        if fingerprint_version == 4:
            if value.get("snapshot_mode") != "working-tree":
                raise ValueError("version 4 candidate snapshot mode is invalid")
            if not isinstance(value.get("working_tree_digest"), str) or not value[
                "working_tree_digest"
            ]:
                raise ValueError("working-tree candidate digest is invalid")
            snapshot_paths = value.get("snapshot_paths")
            if not isinstance(snapshot_paths, list) or not all(
                isinstance(item, str) and item for item in snapshot_paths
            ):
                raise ValueError("working-tree candidate paths are invalid")
            if snapshot_paths != sorted(set(snapshot_paths)) or any(
                Path(item).is_absolute()
                or item.replace("\\", "/") != item
                or ".." in Path(item).parts
                for item in snapshot_paths
            ):
                raise ValueError("working-tree candidate paths are not canonical")
            _required_snapshot_authority(value.get("snapshot_authority"))
        elif fingerprint_version == 5:
            if value.get("snapshot_mode") != "active-spec":
                raise ValueError("version 5 candidate snapshot mode is invalid")
            milestone_id = value.get("active_milestone_id")
            spec_digest = value.get("active_spec_digest")
            if not isinstance(milestone_id, str) or not milestone_id.strip():
                raise ValueError("active-spec candidate milestone is invalid")
            if not isinstance(spec_digest, str) or not spec_digest.strip():
                raise ValueError("active-spec candidate digest is invalid")
            if (
                value.get("working_tree_digest") is not None
                or value.get("snapshot_paths") != []
                or value.get("snapshot_authority") is not None
            ):
                raise ValueError("active-spec candidate cannot contain working-tree state")
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
            snapshot_mode=value.get("snapshot_mode", "clean-head"),
            working_tree_digest=value.get("working_tree_digest"),
            snapshot_paths=tuple(value.get("snapshot_paths", ())),
            snapshot_authority=value.get("snapshot_authority"),
            active_milestone_id=value.get("active_milestone_id"),
            active_spec_digest=value.get("active_spec_digest"),
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
    normalization_findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkingTreeSnapshot:
    digest: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class RepositorySnapshot:
    repository_root: str
    head_sha: str
    diff_hash: str
    snapshot_mode: str
    worktree_changes: tuple[str, ...]
    working_tree: WorkingTreeSnapshot | None
    collection_errors: tuple[str, ...] = ()
    normalization_findings: tuple[NormalizationFinding, ...] = ()
    active_milestone_id: str | None = None
    active_spec_digest: str | None = None


def collect_repository_snapshot(
    repository_root: Path,
    *,
    snapshot_mode: str = "clean-head",
    active_milestone_id: str | None = None,
) -> RepositorySnapshot:
    """Collect candidate Git state once; comparison is handled by pure functions."""
    root = _repository_root(repository_root)
    return _collect_repository_snapshot(
        root,
        snapshot_mode=_normalize_snapshot_mode(snapshot_mode),
        active_milestone_id=active_milestone_id,
    )


def _collect_repository_snapshot(
    root: Path,
    *,
    snapshot_mode: str,
    active_milestone_id: str | None = None,
) -> RepositorySnapshot:
    active_spec_digest: str | None = None
    if snapshot_mode == "active-spec":
        normalization = NormalizationReport(())
        normalization_error = None
        if not isinstance(active_milestone_id, str) or not active_milestone_id.strip():
            active_error = "active-spec snapshot requires one milestone ID"
        else:
            try:
                from .spec_sources import load_normalized_spec

                active_spec_digest = load_normalized_spec(
                    root, active_milestone_id.strip()
                ).semantic_digest
            except (ValueError, OSError) as exc:
                active_error = f"active-spec snapshot unavailable: {exc}"
            else:
                active_error = None
        head_sha = active_spec_digest or "active-spec-unavailable"
        diff_hash = active_spec_digest or "active-spec-unavailable"
    else:
        active_error = None
        try:
            normalization = whitespace_preflight(root)
        except ValueError as exc:
            normalization = NormalizationReport(())
            normalization_error = f"diff whitespace preflight unavailable: {exc}"
        else:
            normalization_error = None
        head_sha = _git_text(root, "rev-parse", "HEAD")
        diff_hash = _diff_hash(root)
    changes: tuple[str, ...] = ()
    working_tree: WorkingTreeSnapshot | None = None
    errors: tuple[str, ...] = (
        (normalization_error,) if normalization_error is not None else ()
    )
    if active_error is not None:
        errors += (active_error,)
    if snapshot_mode == "working-tree":
        try:
            working_tree = _working_tree_snapshot(root)
        except ValueError as exc:
            errors = errors + (f"working-tree snapshot unavailable: {exc}",)
    else:
        changes = _worktree_changes(root)
    return RepositorySnapshot(
        repository_root=str(root),
        head_sha=head_sha,
        diff_hash=diff_hash,
        snapshot_mode=snapshot_mode,
        worktree_changes=changes,
        working_tree=working_tree,
        collection_errors=errors,
        normalization_findings=normalization.findings,
        active_milestone_id=(
            active_milestone_id.strip()
            if isinstance(active_milestone_id, str) and active_milestone_id.strip()
            else None
        ),
        active_spec_digest=active_spec_digest,
    )


def candidate_fingerprint_from_snapshot(
    snapshot: RepositorySnapshot,
    *,
    contract_digest: str,
    dependency_digest: str,
    review_closed: bool,
    corrective_batch_closed: bool,
    generation: int = 1,
    predecessor_digest: str | None = None,
    fingerprint_version: int = 1,
    corrective_batch_id: str | None = None,
    authority_anchor: str | None = None,
    root_cause_id: str | None = None,
    open_findings_count: int | None = None,
    no_progress_rounds: int = 0,
    convergence_authority_digest: str | None = None,
    convergence_authority_id: str | None = None,
    execution_scope: str | None = None,
    root_cause_family: str | None = None,
    convergence_allowed_paths: tuple[str, ...] = (),
    convergence_invariant: str | None = None,
    convergence_semantic_change_policy: str | None = None,
    convergence_stop_conditions: tuple[str, ...] = (),
    finding_severity: int | None = None,
    targeted_review_closed: bool = False,
    finding_trend: str | None = None,
    snapshot_authority: str | None = None,
) -> CandidateFingerprint:
    """Create the versioned fingerprint from an immutable repository snapshot."""
    if snapshot.collection_errors:
        raise ValueError("; ".join(snapshot.collection_errors))
    working_tree = snapshot.working_tree
    if snapshot.snapshot_mode == "working-tree" and working_tree is None:
        raise ValueError("working-tree snapshot data is missing")
    if snapshot.snapshot_mode == "clean-head" and working_tree is not None:
        raise ValueError("clean-head snapshot contains working-tree snapshot data")
    if snapshot.snapshot_mode == "active-spec" and (
        snapshot.active_milestone_id is None or snapshot.active_spec_digest is None
    ):
        raise ValueError("active-spec snapshot data is missing")
    if snapshot.snapshot_mode == "active-spec" and fingerprint_version != 5:
        raise ValueError("active-spec snapshot requires candidate fingerprint version 5")
    return CandidateFingerprint(
        head_sha=snapshot.head_sha,
        diff_hash=snapshot.diff_hash,
        contract_digest=_required_digest(contract_digest, "contract"),
        dependency_digest=_required_digest(dependency_digest, "dependency"),
        review_closed=review_closed,
        corrective_batch_closed=corrective_batch_closed,
        generation=generation,
        predecessor_digest=predecessor_digest,
        fingerprint_version=fingerprint_version,
        corrective_batch_id=corrective_batch_id,
        authority_anchor=authority_anchor,
        root_cause_id=root_cause_id,
        open_findings_count=open_findings_count,
        no_progress_rounds=no_progress_rounds,
        convergence_authority_digest=convergence_authority_digest,
        convergence_authority_id=convergence_authority_id,
        execution_scope=execution_scope,
        root_cause_family=root_cause_family,
        convergence_allowed_paths=convergence_allowed_paths,
        convergence_invariant=convergence_invariant,
        convergence_semantic_change_policy=convergence_semantic_change_policy,
        convergence_stop_conditions=convergence_stop_conditions,
        finding_severity=finding_severity,
        targeted_review_closed=targeted_review_closed,
        finding_trend=finding_trend,
        snapshot_mode=snapshot.snapshot_mode,
        working_tree_digest=(working_tree.digest if working_tree is not None else None),
        snapshot_paths=(working_tree.paths if working_tree is not None else ()),
        snapshot_authority=snapshot_authority,
        active_milestone_id=snapshot.active_milestone_id,
        active_spec_digest=snapshot.active_spec_digest,
    )


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
    snapshot_mode: str = "clean-head",
    snapshot_authority: str | None = None,
    active_milestone_id: str | None = None,
) -> CandidateFreezeResult:
    root = _repository_root(repository_root)
    try:
        normalized_snapshot_mode = _normalize_snapshot_mode(snapshot_mode)
    except ValueError as exc:
        reason = str(exc)
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
        )
    try:
        normalized_snapshot_authority = (
            _required_snapshot_authority(snapshot_authority)
            if normalized_snapshot_mode == "working-tree"
            else None
        )
    except ValueError as exc:
        reason = str(exc)
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
        )
    if normalized_snapshot_mode != "working-tree" and snapshot_authority is not None:
        reason = "snapshot authority is valid only for working-tree mode"
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
        )
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
    initial_snapshot = _collect_repository_snapshot(
        root,
        snapshot_mode=normalized_snapshot_mode,
        active_milestone_id=active_milestone_id,
    )
    if initial_snapshot.collection_errors:
        reason = initial_snapshot.collection_errors[0]
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
        )
    normalization = NormalizationReport(initial_snapshot.normalization_findings)
    finding_labels = tuple(
        f"{item.kind.value}:{item.path}:{item.reason}"
        for item in normalization.findings
    )
    if normalization.handoff_findings:
        reason = (
            "mechanical whitespace finding touches protected or byte-bound content; "
            "HANDOFF/PM review is required without modifying the file"
        )
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=finding_labels,
            stop_reason=reason,
            normalization_findings=finding_labels,
        )
    if normalization.auto_findings:
        return CandidateFreezeResult(
            False,
            RunState.AUTO_CORRECT,
            "AUTO_NORMALIZATION_CORRECTIVE",
            mismatches=finding_labels,
            normalization_findings=finding_labels,
        )
    working_snapshot = initial_snapshot.working_tree
    if normalized_snapshot_mode == "clean-head":
        if initial_snapshot.worktree_changes:
            mismatch = "unexpected worktree changes: " + ", ".join(
                initial_snapshot.worktree_changes
            )
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                mismatch,
                mismatches=(mismatch,),
            )

    snapshot_mode_changed = (
        previous is not None
        and previous.snapshot_mode != normalized_snapshot_mode
    )
    if snapshot_mode_changed and not handoff_successor_approved:
        reason = (
            "snapshot mode differs from previous candidate: "
            f"candidate={previous.snapshot_mode} requested={normalized_snapshot_mode}"
            "; explicit handoff successor approval is required"
        )
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
        )
    if (
        previous is not None
        and not snapshot_mode_changed
        and previous.snapshot_mode == "working-tree"
        and previous.snapshot_authority != normalized_snapshot_authority
    ):
        reason = "snapshot authority differs from previous candidate"
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
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
        assessment = assess_candidate_snapshot(
            initial_snapshot,
            previous,
            contract_digest=contract_digest,
            dependency_digest=dependency_digest,
        )
        if assessment.ok and snapshot_mode_changed:
            mode_mismatch = (
                "snapshot mode differs from previous candidate: "
                f"candidate={previous.snapshot_mode} "
                f"requested={normalized_snapshot_mode}"
            )
            assessment = CandidateAssessment(
                False,
                RunState.HANDOFF_READY,
                mode_mismatch,
                (mode_mismatch,),
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
            try:
                changed_paths = _changed_paths(
                    root,
                    previous.head_sha,
                    working_tree_paths=(
                        working_snapshot.paths if working_snapshot is not None else ()
                    ),
                )
            except ValueError as exc:
                reason = f"changed path discovery failed closed: {exc}"
                return CandidateFreezeResult(
                    False,
                    RunState.HANDOFF_READY,
                    reason,
                    mismatches=(reason,),
                    stop_reason=reason,
                )
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
        try:
            changed_paths = _changed_paths(
                root,
                None,
                working_tree_paths=(
                    working_snapshot.paths if working_snapshot is not None else ()
                ),
            )
        except ValueError as exc:
            reason = f"changed path discovery failed closed: {exc}"
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                reason,
                mismatches=(reason,),
                stop_reason=reason,
            )
        outside = paths_outside_authority(
            root,
            convergence_authority,
            changed_paths,
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

    final_snapshot = _collect_repository_snapshot(
        root,
        snapshot_mode=normalized_snapshot_mode,
        active_milestone_id=active_milestone_id,
    )
    if final_snapshot.collection_errors:
        reason = "final " + final_snapshot.collection_errors[0]
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=(reason,),
            stop_reason=reason,
        )
    if working_snapshot is not None:
        final_working_snapshot = final_snapshot.working_tree
        if final_working_snapshot != working_snapshot:
            reason = "working-tree snapshot changed after authority processing"
            return CandidateFreezeResult(
                False,
                RunState.HANDOFF_READY,
                reason,
                mismatches=(reason,),
                stop_reason=reason,
            )
        working_snapshot = final_working_snapshot

    candidate = candidate_fingerprint_from_snapshot(
        final_snapshot,
        contract_digest=contract_digest,
        dependency_digest=dependency_digest,
        review_closed=True,
        corrective_batch_closed=True,
        generation=generation,
        predecessor_digest=predecessor,
        fingerprint_version=(
            5
            if normalized_snapshot_mode == "active-spec"
            else 4
            if normalized_snapshot_mode == "working-tree"
            else (3 if convergence_authority is not None else 2)
        ),
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
        snapshot_authority=normalized_snapshot_authority,
    )
    final_assessment = assess_candidate_snapshot(
        final_snapshot,
        candidate,
        contract_digest=_required_digest(contract_digest, "contract"),
        dependency_digest=_required_digest(dependency_digest, "dependency"),
    )
    if not final_assessment.ok:
        reason = "candidate changed during final consistency assessment"
        return CandidateFreezeResult(
            False,
            RunState.HANDOFF_READY,
            reason,
            mismatches=final_assessment.mismatches,
            stop_reason=reason,
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
    snapshot = _collect_repository_snapshot(
        root,
        snapshot_mode=candidate.snapshot_mode,
        active_milestone_id=candidate.active_milestone_id,
    )
    return assess_candidate_snapshot(
        snapshot,
        candidate,
        contract_digest=contract_digest,
        dependency_digest=dependency_digest,
    )


def assess_candidate_snapshot(
    snapshot: RepositorySnapshot,
    candidate: CandidateFingerprint | None,
    *,
    contract_digest: str,
    dependency_digest: str,
) -> CandidateAssessment:
    """Compare a candidate to already-collected repository state without I/O."""
    if candidate is None:
        return CandidateAssessment(
            False,
            RunState.HANDOFF_READY,
            "candidate fingerprint is missing",
            ("candidate fingerprint is missing",),
        )
    mismatches: list[str] = []
    current_head = snapshot.head_sha
    current_diff = snapshot.diff_hash
    if candidate.snapshot_mode == "active-spec":
        if candidate.active_milestone_id != snapshot.active_milestone_id:
            mismatches.append("active milestone differs")
        if candidate.active_spec_digest != snapshot.active_spec_digest:
            mismatches.append(
                "active SPEC digest differs: "
                f"candidate={candidate.active_spec_digest} "
                f"current={snapshot.active_spec_digest}"
            )
    else:
        if candidate.head_sha != current_head:
            mismatches.append(
                f"HEAD differs: candidate={candidate.head_sha} current={current_head}"
            )
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
    mismatches.extend(snapshot.collection_errors)
    if candidate.snapshot_mode == "working-tree":
        current_snapshot = snapshot.working_tree
        if current_snapshot is not None:
            if candidate.working_tree_digest != current_snapshot.digest:
                mismatches.append(
                    "working-tree snapshot differs: "
                    f"candidate={candidate.working_tree_digest} "
                    f"current={current_snapshot.digest}"
                )
            if candidate.snapshot_paths != current_snapshot.paths:
                mismatches.append("working-tree snapshot paths differ")
    elif candidate.snapshot_mode == "clean-head":
        changes = snapshot.worktree_changes
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
        "candidate fingerprint matches current scope",
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


def _normalize_snapshot_mode(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in {"clean-head", "working-tree", "active-spec"}:
        raise ValueError(
            "snapshot mode must be clean-head, working-tree, or active-spec; no fallback is allowed"
        )
    return normalized


def _required_snapshot_authority(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("working-tree snapshot authority is required")
    if value != value.strip() or not value:
        raise ValueError("working-tree snapshot authority must be a non-empty trimmed string")
    if len(value) > 256 or any(ord(character) < 32 for character in value):
        raise ValueError("working-tree snapshot authority is malformed")
    return value


def _working_tree_snapshot(root: Path) -> WorkingTreeSnapshot:
    status = _snapshot_status(root)
    _reject_unsupported_worktree_states(status)
    index_state = _git_bytes(root, "ls-files", "--stage", "-z")
    staged_diff = _git_bytes(
        root,
        "diff",
        "--cached",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
    )
    unstaged_diff = _git_bytes(
        root,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
    )
    untracked_raw = _git_bytes(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    untracked_paths = tuple(
        _decode_repository_path(item)
        for item in untracked_raw.split(b"\0")
        if item
    )
    untracked_entries = tuple(
        _snapshot_untracked_entry(root, relative) for relative in untracked_paths
    )
    staged_paths = _git_name_only(root, "diff", "--cached")
    unstaged_paths = _git_name_only(root, "diff")

    final_status = _snapshot_status(root)
    final_index_state = _git_bytes(root, "ls-files", "--stage", "-z")
    final_staged_diff = _git_bytes(
        root,
        "diff",
        "--cached",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
    )
    final_unstaged_diff = _git_bytes(
        root,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
    )
    final_untracked_raw = _git_bytes(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    final_untracked_paths = tuple(
        _decode_repository_path(item)
        for item in final_untracked_raw.split(b"\0")
        if item
    )
    final_untracked_entries = tuple(
        _snapshot_untracked_entry(root, relative)
        for relative in final_untracked_paths
    )
    final_staged_paths = _git_name_only(root, "diff", "--cached")
    final_unstaged_paths = _git_name_only(root, "diff")
    if (
        status != final_status
        or index_state != final_index_state
        or staged_diff != final_staged_diff
        or unstaged_diff != final_unstaged_diff
        or untracked_paths != final_untracked_paths
        or untracked_entries != final_untracked_entries
        or staged_paths != final_staged_paths
        or unstaged_paths != final_unstaged_paths
    ):
        raise ValueError(
            "Git status, index, diff, or untracked content changed while snapshotting"
        )

    paths = tuple(sorted(set(staged_paths) | set(unstaged_paths) | set(untracked_paths)))
    payload = {
        "snapshot_format": 1,
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "index_sha256": hashlib.sha256(index_state).hexdigest(),
        "staged_diff_sha256": hashlib.sha256(staged_diff).hexdigest(),
        "unstaged_diff_sha256": hashlib.sha256(unstaged_diff).hexdigest(),
        "untracked": list(untracked_entries),
        "paths": list(paths),
    }
    return WorkingTreeSnapshot(_json_digest(payload), paths)


def _snapshot_status(root: Path) -> bytes:
    return _git_bytes(
        root,
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )


def _reject_unsupported_worktree_states(status_output: bytes) -> None:
    records = [record for record in status_output.split(b"\0") if record]
    for record in records:
        if record.startswith(b"u "):
            raise ValueError("unmerged index state cannot be deterministically bound")
        if not (record.startswith(b"1 ") or record.startswith(b"2 ")):
            continue
        fields = record.split(b" ", 3)
        if len(fields) < 3:
            raise ValueError("Git returned malformed worktree status")
        submodule_state = fields[2]
        if submodule_state.startswith(b"S") and submodule_state != b"S...":
            raise ValueError(
                "dirty submodule state cannot be deterministically bound: "
                + submodule_state.decode("ascii", errors="replace")
            )


def _git_name_only(root: Path, *prefix: str) -> tuple[str, ...]:
    raw = _git_bytes(
        root,
        *prefix,
        "--name-only",
        "-z",
        "--no-renames",
    )
    return tuple(
        _decode_repository_path(item) for item in raw.split(b"\0") if item
    )


def _decode_repository_path(value: bytes) -> str:
    path = value.decode("utf-8", errors="strict")
    if "\\" in path:
        raise ValueError(
            f"repository path contains an unsupported backslash: {path!r}"
        )
    parts = Path(path).parts
    if not path or Path(path).is_absolute() or ".." in parts:
        raise ValueError(f"Git returned unsafe repository path: {path!r}")
    return path


def _snapshot_untracked_entry(root: Path, relative: str) -> dict[str, object]:
    path = root.joinpath(*relative.split("/"))
    before = path.lstat()
    mode = before.st_mode
    if stat.S_ISLNK(mode):
        target = os.readlink(path)
        entry: dict[str, object] = {
            "path": relative,
            "kind": "symlink",
            "mode": stat.S_IMODE(mode),
            "target": target,
        }
    elif stat.S_ISREG(mode):
        content = path.read_bytes()
        entry = {
            "path": relative,
            "kind": "file",
            "mode": stat.S_IMODE(mode),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    else:
        raise ValueError(
            f"unsupported untracked entry type cannot be bound: {relative}"
        )
    after = path.lstat()
    if (
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError(f"untracked entry changed while snapshotting: {relative}")
    return entry


def _changed_paths(
    root: Path,
    previous_head: str | None,
    *,
    working_tree_paths: tuple[str, ...] = (),
) -> tuple[str, ...]:
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
    committed = tuple(
        _decode_repository_path(item) for item in raw.split(b"\0") if item
    )
    return tuple(sorted(set(committed) | set(working_tree_paths)))


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
    try:
        result = run_managed_git(
            root,
            args,
            stage=f"candidate-git-{'-'.join(args[:2]) or 'command'}",
            timeout=30.0,
        )
    except ManagedExecutionError as exc:
        raise ValueError(str(exc)) from exc
    return result.stdout


def _json_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
