from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from .change_control import RunState


COUNTER_NAMES = (
    "implementation_workers",
    "read_only_review_agents",
    "parallel_agent_waves",
    "corrective_re_review_rounds",
    "full_suite_runs_after_baseline",
    "wheel_install_verification_runs",
    "reviewer_reports_per_scope",
)


@dataclass(frozen=True)
class ExecutionLimits:
    implementation_workers: int = 1
    read_only_review_agents: int = 2
    parallel_agent_waves: int = 1
    corrective_re_review_rounds: int = 1
    full_suite_runs_after_baseline: int = 1
    wheel_install_verification_runs: int = 1
    reviewer_reports_per_scope: int = 1
    repeated_root_cause_without_progress: int = 2


@dataclass(frozen=True)
class ExecutionCounters:
    implementation_workers: int = 0
    read_only_review_agents: int = 0
    parallel_agent_waves: int = 0
    corrective_re_review_rounds: int = 0
    full_suite_runs_after_baseline: int = 0
    wheel_install_verification_runs: int = 0
    reviewer_reports_per_scope: int = 0
    root_cause_no_progress: dict[str, int] = field(default_factory=dict)
    exception_events: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in COUNTER_NAMES
        } | {
            "root_cause_no_progress": dict(sorted(self.root_cause_no_progress.items())),
            "exception_events": list(self.exception_events),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "ExecutionCounters":
        kwargs = {name: int(value.get(name, 0)) for name in COUNTER_NAMES}
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


def consume_event(
    counters: ExecutionCounters,
    limits: ExecutionLimits,
    event: str,
    *,
    invalidation_reason: str | None = None,
) -> LimitDecision:
    if event not in COUNTER_NAMES:
        raise ValueError(f"unknown execution event: {event}")
    current = getattr(counters, event)
    limit = getattr(limits, event)
    if current >= limit:
        if event == "full_suite_runs_after_baseline" and invalidation_reason:
            updated = replace(
                counters,
                **{
                    event: current + 1,
                    "exception_events": (
                        *counters.exception_events,
                        f"{event}: {invalidation_reason}",
                    ),
                },
            )
            return LimitDecision(RunState.CONTINUE, updated, "invalidated evidence required rerun")
        return LimitDecision(
            RunState.HANDOFF_READY,
            counters,
            f"{event} limit reached ({limit})",
        )
    return LimitDecision(
        RunState.CONTINUE,
        replace(counters, **{event: current + 1}),
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
