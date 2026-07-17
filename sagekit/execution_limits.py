from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable, Mapping

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
    verification_attempts: dict[str, VerificationAttempt] = field(default_factory=dict)
    root_cause_no_progress: dict[str, int] = field(default_factory=dict)
    exception_events: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in COUNTER_NAMES
        } | {
            "final_full_suite_runs": dict(sorted(self.final_full_suite_runs.items())),
            "final_wheel_install_runs": dict(sorted(self.final_wheel_install_runs.items())),
            "verification_attempts": {
                attempt_id: attempt.to_dict()
                for attempt_id, attempt in sorted(self.verification_attempts.items())
            },
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
        attempts = value.get("verification_attempts", {})
        if not isinstance(attempts, dict):
            raise ValueError("verification attempts must be a mapping")
        kwargs["verification_attempts"] = {
            str(attempt_id): VerificationAttempt.from_dict(attempt)
            for attempt_id, attempt in attempts.items()
        }
        if any(
            attempt_id != attempt.attempt_id
            for attempt_id, attempt in kwargs["verification_attempts"].items()
        ):
            raise ValueError("verification attempt key differs from attempt id")
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


class VerificationAttemptState(str, Enum):
    PREFLIGHT = "PREFLIGHT"
    READY = "READY"
    STARTED = "STARTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


TERMINAL_ATTEMPT_STATES = frozenset(
    {
        VerificationAttemptState.PASSED,
        VerificationAttemptState.FAILED,
        VerificationAttemptState.ABORTED,
    }
)

FINAL_VERIFICATION_INELIGIBLE_REASON = (
    "final verification is not eligible before candidate freeze; "
    "use focused or affected-lane verification"
)


@dataclass(frozen=True)
class VerificationPreflightCheck:
    name: str
    passed: bool
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("preflight check name must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, value: object) -> "VerificationPreflightCheck":
        if not isinstance(value, dict) or set(value) != {"name", "passed", "detail"}:
            raise ValueError("verification preflight check fields are invalid")
        if not isinstance(value["name"], str) or not isinstance(value["passed"], bool):
            raise ValueError("verification preflight check values are invalid")
        if not isinstance(value["detail"], str):
            raise ValueError("verification preflight detail is invalid")
        return cls(value["name"], value["passed"], value["detail"])


@dataclass(frozen=True)
class VerificationPreflight:
    attempt_id: str
    candidate_fingerprint: str | None
    checks: tuple[VerificationPreflightCheck, ...]

    def __post_init__(self) -> None:
        if not self.attempt_id.strip():
            raise ValueError("verification attempt id must not be empty")
        if self.candidate_fingerprint is not None and not self.candidate_fingerprint.strip():
            raise ValueError("candidate fingerprint must not be empty")
        if not isinstance(self.checks, tuple):
            raise ValueError("verification preflight checks must be a tuple")

    @property
    def ready(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)


@dataclass(frozen=True)
class VerificationAttempt:
    attempt_id: str
    kind: VerificationKind
    stage: VerificationStage
    candidate_fingerprint: str | None
    state: VerificationAttemptState
    preflight_checks: tuple[VerificationPreflightCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "kind": self.kind.value,
            "stage": self.stage.value,
            "candidate_fingerprint": self.candidate_fingerprint,
            "state": self.state.value,
            "preflight_checks": [check.to_dict() for check in self.preflight_checks],
        }

    @classmethod
    def from_dict(cls, value: object) -> "VerificationAttempt":
        required = {
            "attempt_id",
            "kind",
            "stage",
            "candidate_fingerprint",
            "state",
            "preflight_checks",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError("verification attempt fields are invalid")
        attempt_id = value["attempt_id"]
        fingerprint = value["candidate_fingerprint"]
        checks = value["preflight_checks"]
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ValueError("verification attempt id is invalid")
        if fingerprint is not None and (not isinstance(fingerprint, str) or not fingerprint):
            raise ValueError("verification attempt candidate fingerprint is invalid")
        if not isinstance(checks, list):
            raise ValueError("verification attempt preflight checks are invalid")
        return cls(
            attempt_id=attempt_id,
            kind=VerificationKind(str(value["kind"])),
            stage=VerificationStage(str(value["stage"])),
            candidate_fingerprint=fingerprint,
            state=VerificationAttemptState(str(value["state"])),
            preflight_checks=tuple(
                VerificationPreflightCheck.from_dict(check) for check in checks
            ),
        )


@dataclass(frozen=True)
class VerificationRunDecision:
    state: RunState
    stage: VerificationStage
    attempt_id: str
    attempt_state: VerificationAttemptState
    counters: ExecutionCounters
    allowed_to_run: bool
    counted_now: bool
    consumes_final_candidate_budget: bool
    merge_gate_eligible: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "stage": self.stage.value,
            "attempt_id": self.attempt_id,
            "attempt_state": self.attempt_state.value,
            "allowed_to_run": self.allowed_to_run,
            "counted_now": self.counted_now,
            "consumes_final_candidate_budget": self.consumes_final_candidate_budget,
            "merge_gate_eligible": self.merge_gate_eligible,
            "reason": self.reason,
            "counters": self.counters.to_dict(),
        }

    def to_text(self) -> str:
        payload = self.to_dict()
        return "\n".join(
            (
                f"STATE {payload['state']}",
                f"STAGE {payload['stage']}",
                f"ATTEMPT {payload['attempt_id']}",
                f"ATTEMPT_STATE {payload['attempt_state']}",
                f"ALLOWED_TO_RUN {str(payload['allowed_to_run']).lower()}",
                f"COUNTED_NOW {str(payload['counted_now']).lower()}",
                "COUNTERS "
                + json.dumps(payload["counters"], sort_keys=True, separators=(",", ":")),
            )
        )


class VerificationNodeDisposition(str, Enum):
    EXECUTED = "executed"
    SKIPPED_DUE_TO_DEPENDENCY = "skipped_due_to_dependency"


@dataclass(frozen=True)
class VerificationNode:
    node_id: str
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("verification node id must not be empty")
        if self.node_id in self.depends_on:
            raise ValueError("verification node cannot depend on itself")


@dataclass(frozen=True)
class VerificationNodeResult:
    node_id: str
    state: VerificationAttemptState


@dataclass(frozen=True)
class VerificationNodeDecision:
    disposition: VerificationNodeDisposition
    independent: bool
    blocked_by: tuple[str, ...] = ()


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


def prepare_verification_run(
    counters: ExecutionCounters,
    kind: VerificationKind,
    preflight: VerificationPreflight,
    *,
    candidate: CandidateFingerprint | None,
    assessment: CandidateAssessment | None,
) -> VerificationRunDecision:
    stage = _verification_stage(candidate)
    candidate_fingerprint = candidate.digest if candidate is not None else None
    identity = VerificationAttempt(
        attempt_id=preflight.attempt_id,
        kind=kind,
        stage=stage,
        candidate_fingerprint=candidate_fingerprint,
        state=VerificationAttemptState.READY,
        preflight_checks=preflight.checks,
    )
    existing = counters.verification_attempts.get(preflight.attempt_id)
    if existing is not None:
        if replace(existing, state=VerificationAttemptState.READY) != identity:
            raise ValueError(
                f"verification attempt id already exists with different identity: "
                f"{preflight.attempt_id}"
            )
    if stage == VerificationStage.PRELIMINARY:
        return _attempt_decision(
            counters,
            existing or replace(identity, state=VerificationAttemptState.PREFLIGHT),
            allowed_to_run=False,
            counted_now=False,
            reason=FINAL_VERIFICATION_INELIGIBLE_REASON,
        )
    if existing is not None:
        return _attempt_decision(
            counters,
            existing,
            allowed_to_run=existing.state == VerificationAttemptState.READY,
            counted_now=False,
            reason=f"verification attempt {preflight.attempt_id} already exists",
        )

    failures = [
        check.name
        for check in preflight.checks
        if not check.passed
    ]
    if not preflight.checks:
        failures.append("structured preflight checks are missing")
    if preflight.candidate_fingerprint != candidate_fingerprint:
        failures.append(
            "candidate fingerprint differs between preflight and current verification"
        )
    if stage == VerificationStage.FINAL_CANDIDATE and (
        assessment is None or not assessment.ok
    ):
        failures.append(
            assessment.message
            if assessment is not None
            else "candidate assessment is required for final verification"
        )

    attempt = replace(
        identity,
        state=(
            VerificationAttemptState.PREFLIGHT
            if failures
            else VerificationAttemptState.READY
        ),
    )
    updated = _replace_attempt(counters, attempt)
    return _attempt_decision(
        updated,
        attempt,
        allowed_to_run=not failures,
        counted_now=False,
        reason=(
            "preflight ready; candidate execution has not started"
            if not failures
            else "preflight failed without consuming a verification run: "
            + "; ".join(failures)
        )
    )


def begin_verification_run(
    counters: ExecutionCounters,
    limits: ExecutionLimits,
    attempt_id: str,
    *,
    candidate: CandidateFingerprint | None,
    assessment: CandidateAssessment | None,
) -> VerificationRunDecision:
    attempt = counters.verification_attempts.get(attempt_id)
    if attempt is None:
        raise ValueError(f"verification attempt is not prepared: {attempt_id}")
    if attempt.stage == VerificationStage.PRELIMINARY:
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            reason=FINAL_VERIFICATION_INELIGIBLE_REASON,
        )
    if attempt.state == VerificationAttemptState.PREFLIGHT:
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            reason="verification preflight is not ready",
        )
    if attempt.state == VerificationAttemptState.STARTED:
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            reason="verification attempt already started; counter was not consumed again",
        )
    if attempt.state in TERMINAL_ATTEMPT_STATES:
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            reason=f"verification attempt already completed as {attempt.state.value}",
        )

    candidate_fingerprint = candidate.digest if candidate is not None else None
    if candidate_fingerprint != attempt.candidate_fingerprint:
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            state=RunState.HANDOFF_READY,
            reason=(
                "candidate fingerprint mismatch before execution start: "
                f"prepared={attempt.candidate_fingerprint} current={candidate_fingerprint}"
            ),
        )
    if attempt.stage == VerificationStage.FINAL_CANDIDATE and (
        assessment is None or not assessment.ok
    ):
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            state=RunState.HANDOFF_READY,
            reason=(
                assessment.message
                if assessment is not None
                else "candidate assessment is required before execution start"
            ),
        )

    if candidate is None:
        raise ValueError("final verification attempt is missing its candidate")
    if attempt.kind == VerificationKind.FULL_SUITE:
        field_name = "final_full_suite_runs"
        limit = limits.max_full_suite_runs_per_candidate
    else:
        field_name = "final_wheel_install_runs"
        limit = limits.max_wheel_install_runs_per_candidate
    runs = dict(getattr(counters, field_name))
    current = runs.get(candidate.digest, 0)
    if current >= limit:
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            state=RunState.HANDOFF_READY,
            reason=(
                f"{attempt.kind.value} final run limit reached for candidate "
                f"{candidate.digest}"
            ),
        )
    runs[candidate.digest] = current + 1
    updated = replace(counters, **{field_name: runs})

    started = replace(attempt, state=VerificationAttemptState.STARTED)
    updated = _replace_attempt(updated, started)
    return _attempt_decision(
        updated,
        started,
        allowed_to_run=True,
        counted_now=True,
        reason="verification run consumed atomically as candidate execution starts",
    )


def complete_verification_run(
    counters: ExecutionCounters,
    attempt_id: str,
    outcome: VerificationAttemptState,
) -> VerificationRunDecision:
    if outcome not in TERMINAL_ATTEMPT_STATES:
        raise ValueError("verification outcome must be PASSED, FAILED, or ABORTED")
    attempt = counters.verification_attempts.get(attempt_id)
    if attempt is None:
        raise ValueError(f"verification attempt is not prepared: {attempt_id}")
    if attempt.state in TERMINAL_ATTEMPT_STATES:
        if attempt.state != outcome:
            raise ValueError(
                f"verification attempt already completed as {attempt.state.value}"
            )
        return _attempt_decision(
            counters,
            attempt,
            allowed_to_run=False,
            counted_now=False,
            reason=f"verification attempt already completed as {outcome.value}",
        )
    if attempt.state != VerificationAttemptState.STARTED:
        raise ValueError(
            f"verification attempt must be STARTED before completion: {attempt_id}"
        )
    completed = replace(attempt, state=outcome)
    updated = _replace_attempt(counters, completed)
    return _attempt_decision(
        updated,
        completed,
        allowed_to_run=False,
        counted_now=False,
        reason=f"verification attempt completed as {outcome.value}",
    )


def decide_verification_node(
    node: VerificationNode,
    results: Mapping[str, VerificationNodeResult],
) -> VerificationNodeDecision:
    blocked_by = tuple(
        dependency
        for dependency in node.depends_on
        if dependency not in results
        or results[dependency].state != VerificationAttemptState.PASSED
    )
    if blocked_by:
        return VerificationNodeDecision(
            VerificationNodeDisposition.SKIPPED_DUE_TO_DEPENDENCY,
            independent=False,
            blocked_by=blocked_by,
        )
    return VerificationNodeDecision(
        VerificationNodeDisposition.EXECUTED,
        independent=not node.depends_on,
    )


def _verification_stage(
    candidate: CandidateFingerprint | None,
) -> VerificationStage:
    if candidate is not None and (
        candidate.review_closed and candidate.corrective_batch_closed
    ):
        return VerificationStage.FINAL_CANDIDATE
    return VerificationStage.PRELIMINARY


def _replace_attempt(
    counters: ExecutionCounters,
    attempt: VerificationAttempt,
) -> ExecutionCounters:
    attempts = dict(counters.verification_attempts)
    attempts[attempt.attempt_id] = attempt
    return replace(counters, verification_attempts=attempts)


def _attempt_decision(
    counters: ExecutionCounters,
    attempt: VerificationAttempt,
    *,
    allowed_to_run: bool,
    counted_now: bool,
    reason: str,
    state: RunState = RunState.CONTINUE,
) -> VerificationRunDecision:
    consumed = (
        attempt.stage == VerificationStage.FINAL_CANDIDATE
        and attempt.state
        in {
            VerificationAttemptState.STARTED,
            *TERMINAL_ATTEMPT_STATES,
        }
    )
    return VerificationRunDecision(
        state=state,
        stage=attempt.stage,
        attempt_id=attempt.attempt_id,
        attempt_state=attempt.state,
        counters=counters,
        allowed_to_run=allowed_to_run,
        counted_now=counted_now,
        consumes_final_candidate_budget=consumed,
        merge_gate_eligible=(
            attempt.stage == VerificationStage.FINAL_CANDIDATE
            and attempt.state == VerificationAttemptState.PASSED
        ),
        reason=reason,
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
