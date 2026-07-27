from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import convergence as _convergence
from .change_control import RunState


_MAX_ITEMS = 100
_MAX_TEXT_LENGTH = 2_000
_MAX_FINDING_VALUE = 2_147_483_647
_MAX_NO_PROGRESS_ROUNDS = 2


def _bounded_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"graph evolution convergence {field} must not be empty")
    text = value.strip()
    if len(text) > _MAX_TEXT_LENGTH:
        raise ValueError(
            f"graph evolution convergence {field} exceeds "
            f"{_MAX_TEXT_LENGTH} characters"
        )
    return text


def _bounded_text_tuple(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"graph evolution convergence {field} must be a sequence")
    if len(values) > _MAX_ITEMS:
        raise ValueError(
            f"graph evolution convergence {field} exceeds {_MAX_ITEMS} items"
        )
    normalized = tuple(_bounded_text(value, field) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"graph evolution convergence {field} must be unique")
    return normalized


def _bounded_finding_value(
    value: object,
    field: str,
    *,
    optional: bool = False,
) -> int | None:
    if optional and value is None:
        return None
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > _MAX_FINDING_VALUE
    ):
        raise ValueError(
            f"graph evolution convergence {field} must be a bounded "
            "non-negative integer"
        )
    return value


class GraphEvolutionConvergenceCode(str, Enum):
    """Bounded Stage 6 outcomes; none grants mutation or authority."""

    CONTINUE = "CONTINUE"
    HANDOFF = "HANDOFF"
    BLOCKED_NO_PROGRESS = "BLOCKED_NO_PROGRESS"
    PM_DECISION_REQUIRED = "PM_DECISION_REQUIRED"
    NO_CHANGE_ACCEPTED = "NO_CHANGE_ACCEPTED"


@dataclass(frozen=True)
class GraphEvolutionConvergenceEvidence:
    """One immutable Stage 6 convergence observation."""

    execution_scope: str
    root_cause_family: str
    root_cause_id: str
    finding_count: int
    finding_severity: int | None
    evidence_refs: tuple[str, ...]
    affected_scope: tuple[str, ...]
    targeted_review_closed: bool
    next_evidence_layer_exposed: bool = False
    no_change_decision: bool = False

    def __post_init__(self) -> None:
        for field in ("execution_scope", "root_cause_family", "root_cause_id"):
            object.__setattr__(
                self,
                field,
                _bounded_text(getattr(self, field), field),
            )
        object.__setattr__(
            self,
            "finding_count",
            _bounded_finding_value(self.finding_count, "finding count"),
        )
        object.__setattr__(
            self,
            "finding_severity",
            _bounded_finding_value(
                self.finding_severity,
                "finding severity",
                optional=True,
            ),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _bounded_text_tuple(self.evidence_refs, "evidence references"),
        )
        object.__setattr__(
            self,
            "affected_scope",
            _bounded_text_tuple(self.affected_scope, "affected scope"),
        )
        for field in (
            "targeted_review_closed",
            "next_evidence_layer_exposed",
            "no_change_decision",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValueError(
                    f"graph evolution convergence {field} must be boolean"
                )


@dataclass(frozen=True)
class GraphEvolutionConvergenceState:
    """The bounded observation needed to evaluate the next round."""

    execution_scope: str
    root_cause_family: str
    root_cause_id: str
    finding_count: int
    finding_severity: int | None
    evidence_refs: tuple[str, ...]
    affected_scope: tuple[str, ...]
    targeted_review_closed: bool
    no_progress_rounds: int

    def __post_init__(self) -> None:
        for field in ("execution_scope", "root_cause_family", "root_cause_id"):
            object.__setattr__(
                self,
                field,
                _bounded_text(getattr(self, field), field),
            )
        object.__setattr__(
            self,
            "finding_count",
            _bounded_finding_value(self.finding_count, "finding count"),
        )
        object.__setattr__(
            self,
            "finding_severity",
            _bounded_finding_value(
                self.finding_severity,
                "finding severity",
                optional=True,
            ),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _bounded_text_tuple(self.evidence_refs, "evidence references"),
        )
        object.__setattr__(
            self,
            "affected_scope",
            _bounded_text_tuple(self.affected_scope, "affected scope"),
        )
        if not isinstance(self.targeted_review_closed, bool):
            raise ValueError(
                "graph evolution convergence targeted_review_closed must be boolean"
            )
        if (
            not isinstance(self.no_progress_rounds, int)
            or isinstance(self.no_progress_rounds, bool)
            or not 0
            <= self.no_progress_rounds
            <= _MAX_NO_PROGRESS_ROUNDS
        ):
            raise ValueError(
                "graph evolution convergence no-progress rounds are out of bounds"
            )


@dataclass(frozen=True)
class GraphEvolutionConvergenceDecision:
    """A pure decision bound to the exact observation that produced it."""

    code: GraphEvolutionConvergenceCode
    run_state: RunState
    trend: str
    reason: str
    evidence: GraphEvolutionConvergenceEvidence
    state: GraphEvolutionConvergenceState

    def __post_init__(self) -> None:
        if not isinstance(self.code, GraphEvolutionConvergenceCode):
            raise TypeError("graph evolution convergence decision code is invalid")
        if not isinstance(self.run_state, RunState):
            raise TypeError("graph evolution convergence run state is invalid")
        object.__setattr__(self, "trend", _bounded_text(self.trend, "trend"))
        object.__setattr__(self, "reason", _bounded_text(self.reason, "reason"))
        if not isinstance(self.evidence, GraphEvolutionConvergenceEvidence):
            raise TypeError("graph evolution convergence decision evidence is invalid")
        if not isinstance(self.state, GraphEvolutionConvergenceState):
            raise TypeError("graph evolution convergence decision state is invalid")


def _as_convergence_evidence(
    evidence: GraphEvolutionConvergenceEvidence,
) -> _convergence.ConvergenceEvidence:
    return _convergence.ConvergenceEvidence(
        execution_scope=evidence.execution_scope,
        root_cause_family=evidence.root_cause_family,
        root_cause_id=evidence.root_cause_id,
        finding_count=evidence.finding_count,
        finding_severity=evidence.finding_severity,
        semantic_change="implementation-preserving",
        targeted_review_closed=evidence.targeted_review_closed,
        next_layer_exposed=evidence.next_evidence_layer_exposed,
    )


def _evaluate(
    authority: _convergence.PreauthorizedConvergenceAuthority,
    evidence: GraphEvolutionConvergenceEvidence,
    previous: GraphEvolutionConvergenceState | None,
) -> _convergence.ConvergenceDecision:
    return _convergence.evaluate_convergence(
        authority,
        _as_convergence_evidence(evidence),
        previous_root_cause_id=(
            previous.root_cause_id if previous is not None else None
        ),
        previous_finding_count=(
            previous.finding_count if previous is not None else None
        ),
        previous_finding_severity=(
            previous.finding_severity if previous is not None else None
        ),
        previous_no_progress_rounds=(
            previous.no_progress_rounds if previous is not None else 0
        ),
    )


def _no_change_evidence_satisfied(
    evidence: GraphEvolutionConvergenceEvidence,
) -> bool:
    return (
        evidence.no_change_decision
        and evidence.finding_count == 0
        and evidence.finding_severity in (None, 0)
        and bool(evidence.evidence_refs)
        and bool(evidence.affected_scope)
        and evidence.targeted_review_closed
    )


def _force_no_progress_evaluation(
    authority: _convergence.PreauthorizedConvergenceAuthority,
    evidence: GraphEvolutionConvergenceEvidence,
    previous: GraphEvolutionConvergenceState | None,
) -> _convergence.ConvergenceDecision:
    rounds = previous.no_progress_rounds if previous is not None else 0
    return _convergence.evaluate_convergence(
        authority,
        _as_convergence_evidence(evidence),
        previous_root_cause_id=evidence.root_cause_id,
        previous_finding_count=evidence.finding_count,
        previous_finding_severity=evidence.finding_severity,
        previous_no_progress_rounds=rounds,
    )


def _decision_code(
    decision: _convergence.ConvergenceDecision,
) -> GraphEvolutionConvergenceCode:
    if decision.state is RunState.BLOCKED and decision.trend == "no-progress":
        return GraphEvolutionConvergenceCode.BLOCKED_NO_PROGRESS
    if decision.trend == "findings-increased":
        return GraphEvolutionConvergenceCode.PM_DECISION_REQUIRED
    if decision.state is RunState.HANDOFF_READY:
        if "targeted review" in decision.reason:
            return GraphEvolutionConvergenceCode.HANDOFF
        return GraphEvolutionConvergenceCode.PM_DECISION_REQUIRED
    if decision.state is RunState.BLOCKED:
        return GraphEvolutionConvergenceCode.HANDOFF
    return GraphEvolutionConvergenceCode.CONTINUE


def evaluate_graph_evolution_convergence(
    authority: _convergence.PreauthorizedConvergenceAuthority,
    evidence: GraphEvolutionConvergenceEvidence,
    *,
    previous: GraphEvolutionConvergenceState | None = None,
) -> GraphEvolutionConvergenceDecision:
    """Evaluate one Stage 6 round without changing a graph or granting authority."""

    if not isinstance(
        authority,
        _convergence.PreauthorizedConvergenceAuthority,
    ):
        raise TypeError("graph evolution convergence authority is invalid")
    if not isinstance(evidence, GraphEvolutionConvergenceEvidence):
        raise TypeError("graph evolution convergence evidence is invalid")
    if previous is not None and not isinstance(
        previous,
        GraphEvolutionConvergenceState,
    ):
        raise TypeError("graph evolution convergence previous state is invalid")

    evaluated = _evaluate(authority, evidence, previous)
    if (
        _no_change_evidence_satisfied(evidence)
        and evaluated.state is RunState.CONTINUE
    ):
        code = GraphEvolutionConvergenceCode.NO_CHANGE_ACCEPTED
        run_state = RunState.STOP
        trend = "no-change-accepted"
        reason = "bound evidence supports no graph change"
        no_progress_rounds = 0
    else:
        if (
            evidence.no_change_decision
            and evaluated.state is RunState.CONTINUE
            and evaluated.trend != "next-layer-exposed"
        ):
            evaluated = _force_no_progress_evaluation(
                authority,
                evidence,
                previous,
            )
        code = _decision_code(evaluated)
        run_state = evaluated.state
        trend = evaluated.trend
        reason = evaluated.reason
        no_progress_rounds = min(
            evaluated.no_progress_rounds,
            _MAX_NO_PROGRESS_ROUNDS,
        )

    state = GraphEvolutionConvergenceState(
        execution_scope=evidence.execution_scope,
        root_cause_family=evidence.root_cause_family,
        root_cause_id=evidence.root_cause_id,
        finding_count=evidence.finding_count,
        finding_severity=evidence.finding_severity,
        evidence_refs=evidence.evidence_refs,
        affected_scope=evidence.affected_scope,
        targeted_review_closed=evidence.targeted_review_closed,
        no_progress_rounds=no_progress_rounds,
    )
    return GraphEvolutionConvergenceDecision(
        code=code,
        run_state=run_state,
        trend=trend,
        reason=reason,
        evidence=evidence,
        state=state,
    )


__all__ = [
    "GraphEvolutionConvergenceCode",
    "GraphEvolutionConvergenceDecision",
    "GraphEvolutionConvergenceEvidence",
    "GraphEvolutionConvergenceState",
    "evaluate_graph_evolution_convergence",
]
