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
    backlog: tuple[ReviewFinding, ...] = ()


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
    updated = ReviewState(
        initial_scopes=(*state.initial_scopes, report.scope),
        corrective_rounds=dict(state.corrective_rounds),
        backlog=state.backlog,
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
    if rounds.get(rereview.scope, 0) >= limits.corrective_re_review_rounds:
        return CorrectiveReviewDecision(
            RunState.HANDOFF_READY,
            state,
            (),
            state.backlog,
        )
    rounds[rereview.scope] = rounds.get(rereview.scope, 0) + 1

    original_ids = {item.finding_id for item in original.findings}
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

    updated = ReviewState(
        initial_scopes=state.initial_scopes,
        corrective_rounds=rounds,
        backlog=tuple(backlog),
    )
    return CorrectiveReviewDecision(
        RunState.HUMAN_DECISION_REQUIRED if blocking else RunState.CONTINUE,
        updated,
        tuple(blocking),
        tuple(backlog),
    )


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
