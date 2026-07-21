from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .change_control import RunState
from .execution_limits import ExecutionLimits


BLOCKING_P2_CATEGORIES = {
    "authority",
    "false-green",
    "approval-gate",
    "security",
    "safety",
    "source-authority",
    "evidence-integrity",
    "validator",
}


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ReviewTopology(str, Enum):
    LIGHT = "LIGHT"
    STANDARD = "STANDARD"
    HEAVY = "HEAVY"


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    priority: Priority
    category: str
    root_cause: str
    direct_regression: bool = False


@dataclass(frozen=True)
class ReviewReport:
    scope: str
    findings: tuple[ReviewFinding, ...]


@dataclass(frozen=True)
class ReviewState:
    initial_scopes: tuple[str, ...] = ()
    corrective_rounds: dict[str, int] = field(default_factory=dict)
    root_cause_no_progress: dict[str, int] = field(default_factory=dict)
    root_cause_status: dict[str, tuple[int, int]] = field(default_factory=dict)
    backlog: tuple[ReviewFinding, ...] = ()
    root_cause_no_progress_by_scope: dict[str, dict[str, int]] = field(
        default_factory=dict
    )
    root_cause_status_by_scope: dict[str, dict[str, tuple[int, int]]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class InitialReviewDecision:
    outcome: RunState
    state: ReviewState
    blocking_findings: tuple[ReviewFinding, ...]


@dataclass(frozen=True)
class CorrectiveReviewDecision:
    outcome: RunState
    state: ReviewState
    blocking_findings: tuple[ReviewFinding, ...]
    backlog: tuple[ReviewFinding, ...]


def is_blocking(finding: ReviewFinding) -> bool:
    if finding.priority in {Priority.P0, Priority.P1}:
        return True
    return finding.priority == Priority.P2 and finding.category in BLOCKING_P2_CATEGORIES


def accept_initial_report(
    state: ReviewState,
    report: ReviewReport,
    limits: ExecutionLimits,
) -> InitialReviewDecision:
    if report.scope in state.initial_scopes:
        return InitialReviewDecision(
            RunState.HANDOFF_READY,
            state,
            tuple(item for item in report.findings if is_blocking(item)),
        )
    no_progress_by_scope, status_by_scope = _scoped_root_cause_state(state)
    no_progress_by_scope.setdefault(report.scope, {})
    status = _root_cause_status(report.findings)
    status_by_scope[report.scope] = status
    updated = ReviewState(
        initial_scopes=(*state.initial_scopes, report.scope),
        corrective_rounds=dict(state.corrective_rounds),
        root_cause_no_progress=dict(no_progress_by_scope[report.scope]),
        root_cause_status=dict(status),
        backlog=state.backlog,
        root_cause_no_progress_by_scope=no_progress_by_scope,
        root_cause_status_by_scope=status_by_scope,
    )
    blocking = tuple(item for item in report.findings if is_blocking(item))
    return InitialReviewDecision(
        RunState.HUMAN_DECISION_REQUIRED if blocking else RunState.CONTINUE,
        updated,
        blocking,
    )


def evaluate_corrective_rereview(
    state: ReviewState,
    original: ReviewReport,
    rereview: ReviewReport,
    limits: ExecutionLimits,
) -> CorrectiveReviewDecision:
    if rereview.scope != original.scope:
        return CorrectiveReviewDecision(
            RunState.HANDOFF_READY,
            state,
            (),
            state.backlog,
        )
    rounds = dict(state.corrective_rounds)
    rounds[rereview.scope] = rounds.get(rereview.scope, 0) + 1

    original_by_id = {item.finding_id: item for item in original.findings}
    original_ids = set(original_by_id)
    blocking: list[ReviewFinding] = []
    backlog: list[ReviewFinding] = list(state.backlog)
    for finding in rereview.findings:
        if finding.finding_id in original_ids or finding.direct_regression or is_blocking(finding):
            if is_blocking(finding):
                blocking.append(finding)
            elif finding.priority in {Priority.P2, Priority.P3}:
                backlog.append(finding)
            continue
        if finding.priority in {Priority.P2, Priority.P3}:
            backlog.append(finding)

    no_progress_by_scope, status_by_scope = _scoped_root_cause_state(state)
    previous_progress = no_progress_by_scope.get(rereview.scope, {})
    previous_status = status_by_scope.get(rereview.scope, {})
    progress, status = _updated_root_cause_progress(
        previous_progress,
        previous_status,
        tuple(blocking),
    )
    no_progress_by_scope[rereview.scope] = progress
    status_by_scope[rereview.scope] = status
    updated = ReviewState(
        initial_scopes=state.initial_scopes,
        corrective_rounds=rounds,
        root_cause_no_progress=progress,
        root_cause_status=status,
        backlog=tuple(backlog),
        root_cause_no_progress_by_scope=no_progress_by_scope,
        root_cause_status_by_scope=status_by_scope,
    )
    new_blocking = any(
        item.finding_id not in original_ids
        or item.direct_regression
        or not is_blocking(original_by_id[item.finding_id])
        for item in blocking
    )
    regressed = any(
        root in previous_status
        and (
            observed[0] > previous_status[root][0]
            or observed[1] > previous_status[root][1]
        )
        for root, observed in status.items()
    )
    stalled = tuple(
        root
        for root in sorted({item.root_cause for item in blocking})
        if progress.get(root, 0)
        >= limits.repeated_root_cause_without_progress
    )
    if new_blocking or regressed:
        outcome = RunState.HUMAN_DECISION_REQUIRED
    elif stalled:
        outcome = RunState.BLOCKED
    else:
        outcome = RunState.CONTINUE
    return CorrectiveReviewDecision(
        outcome,
        updated,
        tuple(blocking),
        tuple(backlog),
    )


def _updated_root_cause_progress(
    previous: dict[str, int],
    previous_status: dict[str, tuple[int, int]],
    blocking: tuple[ReviewFinding, ...],
) -> tuple[dict[str, int], dict[str, tuple[int, int]]]:
    updated = dict(previous)
    current_by_root = _blocking_by_root(blocking)
    current_status = _root_cause_status(blocking)
    for root in set(updated) | set(previous_status):
        if root not in current_by_root:
            updated[root] = 0
    for root in current_by_root:
        baseline = previous_status.get(root)
        observed = current_status[root]
        progressed = baseline is not None and (
            observed[0] < baseline[0] or observed[1] < baseline[1]
        )
        updated[root] = 0 if progressed else updated.get(root, 0) + 1
    return updated, current_status


def _scoped_root_cause_state(
    state: ReviewState,
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, tuple[int, int]]]]:
    no_progress_by_scope = {
        scope: dict(progress)
        for scope, progress in state.root_cause_no_progress_by_scope.items()
    }
    status_by_scope = {
        scope: dict(status)
        for scope, status in state.root_cause_status_by_scope.items()
    }
    if not status_by_scope and len(state.initial_scopes) == 1:
        scope = state.initial_scopes[0]
        no_progress_by_scope[scope] = dict(state.root_cause_no_progress)
        status_by_scope[scope] = dict(state.root_cause_status)
    return no_progress_by_scope, status_by_scope


def _blocking_by_root(
    findings: tuple[ReviewFinding, ...],
) -> dict[str, tuple[ReviewFinding, ...]]:
    grouped: dict[str, list[ReviewFinding]] = {}
    for finding in findings:
        if is_blocking(finding):
            grouped.setdefault(finding.root_cause, []).append(finding)
    return {root: tuple(items) for root, items in grouped.items()}


def _root_cause_status(
    findings: tuple[ReviewFinding, ...],
) -> dict[str, tuple[int, int]]:
    grouped = _blocking_by_root(findings)
    return {
        root: (len(items), max(_priority_score(item.priority) for item in items))
        for root, items in grouped.items()
    }


def _priority_score(priority: Priority) -> int:
    return {
        Priority.P0: 4,
        Priority.P1: 3,
        Priority.P2: 2,
        Priority.P3: 1,
    }[priority]


def shared_file_density(write_sets: tuple[tuple[str, ...], ...]) -> bool:
    seen: set[str] = set()
    for write_set in write_sets:
        current = set(write_set)
        if seen.intersection(current):
            return True
        seen.update(current)
    return False


def select_topology(risk_flags: tuple[str, ...]) -> ReviewTopology:
    risks = {item.casefold() for item in risk_flags}
    if risks.intersection({"p0", "p1", "security", "authority", "cross-contract", "destructive"}):
        return ReviewTopology.HEAVY
    if risks:
        return ReviewTopology.STANDARD
    return ReviewTopology.LIGHT
