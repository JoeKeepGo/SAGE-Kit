from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable

from .candidate import CandidateAssessment, CandidateFingerprint
from .change_control import RunState


LIMIT_COUNTER_NAMES = (
    "implementation_workers",
    "read_only_review_agents",
    "parallel_agent_waves",
    "corrective_re_review_rounds",
    "reviewer_reports_per_scope",
)
COUNTER_NAMES = (
    *LIMIT_COUNTER_NAMES,
    "preliminary_full_suite_runs",
    "preliminary_wheel_install_runs",
)


@dataclass(frozen=True)
class ExecutionLimits:
    implementation_workers: int = 1
    read_only_review_agents: int = 2
    parallel_agent_waves: int = 1
    corrective_re_review_rounds: int = 1
    reviewer_reports_per_scope: int = 1
    repeated_root_cause_without_progress: int = 2
    max_full_suite_runs_per_candidate: int = 1
    max_wheel_install_runs_per_candidate: int = 1


@dataclass(frozen=True)
class ExecutionCounters:
    implementation_workers: int = 0
    read_only_review_agents: int = 0
    parallel_agent_waves: int = 0
    corrective_re_review_rounds: int = 0
    reviewer_reports_per_scope: int = 0
    preliminary_full_suite_runs: int = 0
    preliminary_wheel_install_runs: int = 0
    final_full_suite_runs: dict[str, int] = field(default_factory=dict)
    final_wheel_install_runs: dict[str, int] = field(default_factory=dict)
    root_cause_no_progress: dict[str, int] = field(default_factory=dict)
    exception_events: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in COUNTER_NAMES
        } | {
            "final_full_suite_runs": dict(sorted(self.final_full_suite_runs.items())),
            "final_wheel_install_runs": dict(sorted(self.final_wheel_install_runs.items())),
            "root_cause_no_progress": dict(sorted(self.root_cause_no_progress.items())),
            "exception_events": list(self.exception_events),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "ExecutionCounters":
        kwargs = {name: int(value.get(name, 0)) for name in COUNTER_NAMES}
        if "preliminary_full_suite_runs" not in value:
            kwargs["preliminary_full_suite_runs"] = int(
                value.get("full_suite_runs_after_baseline", 0)
            )
        if "preliminary_wheel_install_runs" not in value:
            kwargs["preliminary_wheel_install_runs"] = int(
                value.get("wheel_install_verification_runs", 0)
            )
        for field_name in ("final_full_suite_runs", "final_wheel_install_runs"):
            raw = value.get(field_name, {})
            kwargs[field_name] = (
                {str(key): int(count) for key, count in raw.items()}
                if isinstance(raw, dict)
                else {}
            )
        roots = value.get("root_cause_no_progress", {})
        kwargs["root_cause_no_progress"] = (
            {str(key): int(count) for key, count in roots.items()}
            if isinstance(roots, dict)
            else {}
        )
        events = value.get("exception_events", [])
        kwargs["exception_events"] = tuple(str(item) for item in events) if isinstance(events, list) else ()
        return cls(**kwargs)


@dataclass(frozen=True)
class LimitDecision:
    state: RunState
    counters: ExecutionCounters
    reason: str | None = None


CheckpointWriter = Callable[[ExecutionCounters, str], bool]


class VerificationKind(str, Enum):
    FULL_SUITE = "full-suite"
    WHEEL_INSTALL = "wheel-install"


class VerificationStage(str, Enum):
    PRELIMINARY = "preliminary"
    FINAL_CANDIDATE = "final-candidate"


@dataclass(frozen=True)
class VerificationRunDecision:
    state: RunState
    stage: VerificationStage
    counters: ExecutionCounters
    allowed_to_run: bool
    consumes_final_candidate_budget: bool
    merge_gate_eligible: bool
    reason: str


def consume_event(
    counters: ExecutionCounters,
    limits: ExecutionLimits,
    event: str,
    *,
    invalidation_reason: str | None = None,
) -> LimitDecision:
    if event not in LIMIT_COUNTER_NAMES:
        raise ValueError(f"unknown execution event: {event}")
    current = getattr(counters, event)
    limit = getattr(limits, event)
    if current >= limit:
        return LimitDecision(
            RunState.HANDOFF_READY,
            counters,
            f"{event} limit reached ({limit})",
        )
    return LimitDecision(
        RunState.CONTINUE,
        replace(counters, **{event: current + 1}),
    )


def consume_verification_run(
    counters: ExecutionCounters,
    limits: ExecutionLimits,
    kind: VerificationKind,
    *,
    candidate: CandidateFingerprint | None,
    assessment: CandidateAssessment | None,
) -> VerificationRunDecision:
    if candidate is None or not (
        candidate.review_closed and candidate.corrective_batch_closed
    ):
        field_name = (
            "preliminary_full_suite_runs"
            if kind == VerificationKind.FULL_SUITE
            else "preliminary_wheel_install_runs"
        )
        updated = replace(counters, **{field_name: getattr(counters, field_name) + 1})
        return VerificationRunDecision(
            RunState.CONTINUE,
            VerificationStage.PRELIMINARY,
            updated,
            True,
            False,
            False,
            "review or corrective closure is incomplete; run is preliminary only",
        )
    if assessment is None or not assessment.ok:
        reason = (
            assessment.message
            if assessment is not None
            else "candidate assessment is required for final verification"
        )
        return VerificationRunDecision(
            RunState.HANDOFF_READY,
            VerificationStage.FINAL_CANDIDATE,
            counters,
            False,
            False,
            False,
            reason,
        )

    if kind == VerificationKind.FULL_SUITE:
        field_name = "final_full_suite_runs"
        limit = limits.max_full_suite_runs_per_candidate
    else:
        field_name = "final_wheel_install_runs"
        limit = limits.max_wheel_install_runs_per_candidate
    runs = dict(getattr(counters, field_name))
    current = runs.get(candidate.digest, 0)
    if current >= limit:
        return VerificationRunDecision(
            RunState.HANDOFF_READY,
            VerificationStage.FINAL_CANDIDATE,
            counters,
            False,
            True,
            False,
            f"{kind.value} final run limit reached for candidate {candidate.digest}",
        )
    runs[candidate.digest] = current + 1
    updated = replace(counters, **{field_name: runs})
    return VerificationRunDecision(
        RunState.CONTINUE,
        VerificationStage.FINAL_CANDIDATE,
        updated,
        True,
        True,
        True,
        f"{kind.value} authorized for stable candidate {candidate.digest}",
    )


def consume_event_with_checkpoint(
    counters: ExecutionCounters,
    limits: ExecutionLimits,
    event: str,
    checkpoint_writer: CheckpointWriter,
    *,
    invalidation_reason: str | None = None,
) -> LimitDecision:
    """Persist resumable state before exposing a limit-driven handoff."""
    decision = consume_event(
        counters,
        limits,
        event,
        invalidation_reason=invalidation_reason,
    )
    if decision.state != RunState.HANDOFF_READY:
        return decision
    reason = decision.reason or f"{event} limit reached"
    if checkpoint_writer(decision.counters, reason):
        return decision
    return LimitDecision(
        RunState.BLOCKED,
        decision.counters,
        f"checkpoint persistence failed before handoff: {reason}",
    )


def record_root_cause_progress(
    counters: ExecutionCounters,
    limits: ExecutionLimits,
    root_cause: str,
    progressed: bool,
) -> LimitDecision:
    roots = dict(counters.root_cause_no_progress)
    roots[root_cause] = 0 if progressed else roots.get(root_cause, 0) + 1
    updated = replace(counters, root_cause_no_progress=roots)
    if roots[root_cause] >= limits.repeated_root_cause_without_progress:
        return LimitDecision(
            RunState.BLOCKED,
            updated,
            f"root cause made no progress for {roots[root_cause]} consecutive rounds: {root_cause}",
        )
    return LimitDecision(RunState.CONTINUE, updated)
