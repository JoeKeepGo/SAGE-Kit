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
MAX_EVALUATOR_RISKS = 16
MAX_EVALUATOR_FINDINGS = 100
MAX_EVALUATOR_IDENTITY = 256
MAX_ORACLE_REF = 512


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ReviewTopology(str, Enum):
    LIGHT = "LIGHT"
    STANDARD = "STANDARD"
    HEAVY = "HEAVY"


class EvaluatorKind(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    FRESH_CONTEXT = "FRESH_CONTEXT"


class EvaluatorRisk(str, Enum):
    MECHANICAL = "mechanical"
    P0 = "p0"
    P1 = "p1"
    SECURITY = "security"
    AUTHORITY = "authority"
    SAFETY = "safety"
    CROSS_CONTRACT = "cross-contract"
    DESTRUCTIVE = "destructive"
    HARNESS = "harness"
    SEMANTIC = "semantic"


class EvaluatorVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class ReceiptStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDEPENDENT_EVALUATOR_REQUIRED = "INDEPENDENT_EVALUATOR_REQUIRED"
    INVALID_RECEIPT = "INVALID_RECEIPT"


FRESH_CONTEXT_RISKS = frozenset(
    {
        EvaluatorRisk.AUTHORITY,
        EvaluatorRisk.SAFETY,
        EvaluatorRisk.CROSS_CONTRACT,
        EvaluatorRisk.DESTRUCTIVE,
        EvaluatorRisk.HARNESS,
        EvaluatorRisk.SEMANTIC,
    }
)


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


@dataclass(frozen=True)
class EvaluatorSelection:
    evaluator: EvaluatorKind
    topology: ReviewTopology
    oracle_ref: str | None

    def __post_init__(self) -> None:
        if type(self.evaluator) is not EvaluatorKind:
            raise ValueError("evaluator selection kind is invalid")
        if type(self.topology) is not ReviewTopology:
            raise ValueError("evaluator selection topology is invalid")
        if self.evaluator is EvaluatorKind.DETERMINISTIC:
            _bounded_text(self.oracle_ref, "oracle ref", MAX_ORACLE_REF)
        elif self.oracle_ref is not None:
            raise ValueError("fresh-context selection cannot carry an oracle ref")


@dataclass(frozen=True)
class DeterministicReceipt:
    oracle_ref: str
    input_fingerprint: str
    result_fingerprint: str

    def __post_init__(self) -> None:
        _bounded_text(self.oracle_ref, "oracle ref", MAX_ORACLE_REF)
        _validate_fingerprint(self.input_fingerprint, "input fingerprint")
        _validate_fingerprint(self.result_fingerprint, "result fingerprint")


@dataclass(frozen=True)
class FreshContextReceipt:
    author_identity: str
    evaluator_identity: str
    verdict: EvaluatorVerdict

    def __post_init__(self) -> None:
        _bounded_text(
            self.author_identity,
            "author identity",
            MAX_EVALUATOR_IDENTITY,
        )
        _bounded_text(
            self.evaluator_identity,
            "evaluator identity",
            MAX_EVALUATOR_IDENTITY,
        )
        if type(self.verdict) is not EvaluatorVerdict:
            raise ValueError("fresh-context evaluator verdict is invalid")


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


def select_evaluator(
    risk_flags: tuple[EvaluatorRisk, ...],
    *,
    machine_oracle_ref: str | None = None,
    semantic_judgment_required: bool = False,
    findings: tuple[ReviewFinding, ...] = (),
) -> EvaluatorSelection:
    if type(risk_flags) is not tuple:
        raise TypeError("evaluator risk flags must be a tuple")
    if len(risk_flags) > MAX_EVALUATOR_RISKS:
        raise ValueError(
            f"evaluator risk flags exceed {MAX_EVALUATOR_RISKS} items"
        )
    if any(type(risk) is not EvaluatorRisk for risk in risk_flags):
        raise ValueError("evaluator risk flags contain an unknown value")
    if len(risk_flags) != len(set(risk_flags)):
        raise ValueError("evaluator risk flags must be unique")
    if type(semantic_judgment_required) is not bool:
        raise TypeError("semantic judgment requirement must be boolean")
    if type(findings) is not tuple:
        raise TypeError("evaluator findings must be a tuple")
    if len(findings) > MAX_EVALUATOR_FINDINGS:
        raise ValueError(
            f"evaluator findings exceed {MAX_EVALUATOR_FINDINGS} items"
        )
    if any(type(finding) is not ReviewFinding for finding in findings):
        raise ValueError("evaluator findings contain an unknown value")

    oracle_ref = (
        None
        if machine_oracle_ref is None
        else _bounded_text(machine_oracle_ref, "oracle ref", MAX_ORACLE_REF)
    )
    topology_flags = tuple(risk.value for risk in risk_flags)
    topology = select_topology(topology_flags)
    blocking_finding = any(is_blocking(finding) for finding in findings)
    fresh_context_required = (
        semantic_judgment_required
        or blocking_finding
        or topology is ReviewTopology.HEAVY
        or bool(FRESH_CONTEXT_RISKS.intersection(risk_flags))
    )
    if oracle_ref is not None and not fresh_context_required:
        return EvaluatorSelection(
            EvaluatorKind.DETERMINISTIC,
            topology,
            oracle_ref,
        )
    return EvaluatorSelection(EvaluatorKind.FRESH_CONTEXT, topology, None)


def validate_evaluator_receipt(
    selection: EvaluatorSelection,
    receipt: DeterministicReceipt | FreshContextReceipt | object,
) -> ReceiptStatus:
    if type(selection) is not EvaluatorSelection:
        return ReceiptStatus.INVALID_RECEIPT
    if selection.evaluator is EvaluatorKind.DETERMINISTIC:
        if type(receipt) is not DeterministicReceipt:
            return ReceiptStatus.INVALID_RECEIPT
        if receipt.oracle_ref != selection.oracle_ref:
            return ReceiptStatus.INVALID_RECEIPT
        return ReceiptStatus.PASS
    if type(receipt) is not FreshContextReceipt:
        return ReceiptStatus.INVALID_RECEIPT
    if receipt.evaluator_identity == receipt.author_identity:
        return ReceiptStatus.INDEPENDENT_EVALUATOR_REQUIRED
    if receipt.verdict is EvaluatorVerdict.PASS:
        return ReceiptStatus.PASS
    return ReceiptStatus.FAIL


def _bounded_text(value: object, field: str, maximum: int) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"evaluator {field} must not be empty")
    if value != value.strip():
        raise ValueError(f"evaluator {field} must not contain outer whitespace")
    if len(value) > maximum:
        raise ValueError(f"evaluator {field} exceeds {maximum} characters")
    return value


def _validate_fingerprint(value: object, field: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"evaluator {field} must be lowercase sha256")
