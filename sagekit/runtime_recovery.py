"""Deterministic replay and explicit single-writer runtime recovery.

Replay and assessment are read-only.  Recovery mutation is available only
through a live :class:`RuntimeWriter` and delegates state-last persistence to
the atomic runtime store.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import runtime_store as _store
from .runtime_store import RuntimeStoreIntegrityError, RuntimeWriter


MAX_RECOVERY_ISSUES = 8


class RecoveryClassification(str, Enum):
    CONSISTENT = "CONSISTENT"
    STATE_MISSING = "STATE_MISSING"
    STATE_BEHIND_EVENTS = "STATE_BEHIND_EVENTS"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    RECOVERED = "RECOVERED"
    EVENT_LOG_TORN = "EVENT_LOG_TORN"
    EVENT_LOG_CORRUPT = "EVENT_LOG_CORRUPT"
    GRAPH_CORRUPT = "GRAPH_CORRUPT"
    STATE_AHEAD_OF_EVENTS = "STATE_AHEAD_OF_EVENTS"
    STATE_DIVERGED = "STATE_DIVERGED"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"
    LOCKED_BY_OTHER_WRITER = "LOCKED_BY_OTHER_WRITER"
    LOCK_INTEGRITY_ERROR = "LOCK_INTEGRITY_ERROR"


@dataclass(frozen=True, order=True)
class RecoveryIssue:
    code: str
    message: str


@dataclass(frozen=True)
class ReplayResult:
    classification: RecoveryClassification
    reconstructed_state: dict[str, Any] | None = None
    last_valid_sequence: int = 0
    attempt_counts: tuple[tuple[str, int], ...] = ()
    issues: tuple[RecoveryIssue, ...] = ()


@dataclass(frozen=True)
class RecoveryAssessment:
    classification: RecoveryClassification
    replay: ReplayResult | None = None
    current_state: dict[str, Any] | None = None
    issues: tuple[RecoveryIssue, ...] = ()


@dataclass(frozen=True)
class RecoveryResult:
    classification: RecoveryClassification
    recovered_state: dict[str, Any] | None = None
    appended_event_count: int = 0
    issues: tuple[RecoveryIssue, ...] = ()


@dataclass(frozen=True)
class _RecoverySnapshot:
    graph: dict[str, Any]
    state: dict[str, Any] | None
    events: tuple[dict[str, Any], ...]
    graph_bytes: bytes
    state_bytes: bytes | None
    event_bytes: bytes


def _issues(*values: RecoveryIssue) -> tuple[RecoveryIssue, ...]:
    return tuple(values[:MAX_RECOVERY_ISSUES])


def _issue_result(
    classification: RecoveryClassification,
    code: str,
    message: str,
) -> ReplayResult:
    return ReplayResult(
        classification=classification,
        issues=_issues(RecoveryIssue(code, message)),
    )


def _issue_assessment(
    classification: RecoveryClassification,
    code: str,
    message: str,
) -> RecoveryAssessment:
    return RecoveryAssessment(
        classification=classification,
        issues=_issues(RecoveryIssue(code, message)),
    )


def _binding_mismatch(
    event: Any,
    *,
    run_id: str,
    graph_digest: str,
    authority_id: str,
    controller_id: str,
) -> bool:
    return type(event) is dict and (
        event.get("run_id") != run_id
        or event.get("graph_digest") != graph_digest
        or event.get("authority_id") != authority_id
        or event.get("actor_id") != controller_id
    )


def replay_runtime_events(
    graph: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    graph_digest: str,
    authority_id: str,
    controller_id: str,
) -> ReplayResult:
    """Purely reconstruct a state from a complete ordered event sequence."""

    try:
        actual_graph_digest = _store._validate_graph(graph)
    except RuntimeStoreIntegrityError:
        return _issue_result(
            RecoveryClassification.GRAPH_CORRUPT,
            "GRAPH_INVALID",
            "graph snapshot is invalid",
        )
    if actual_graph_digest != graph_digest:
        return _issue_result(
            RecoveryClassification.AUTHORITY_MISMATCH,
            "GRAPH_BINDING_MISMATCH",
            "graph snapshot does not match the expected identity",
        )
    if type(events) not in {list, tuple}:
        return _issue_result(
            RecoveryClassification.EVENT_LOG_CORRUPT,
            "EVENT_SEQUENCE_INVALID",
            "event history must be a bounded ordered sequence",
        )
    if any(
        _binding_mismatch(
            event,
            run_id=run_id,
            graph_digest=graph_digest,
            authority_id=authority_id,
            controller_id=controller_id,
        )
        for event in events
    ):
        return _issue_result(
            RecoveryClassification.AUTHORITY_MISMATCH,
            "EVENT_BINDING_MISMATCH",
            "event history does not match the expected identity",
        )
    try:
        state, attempts, in_progress, completed = _store._replay_event_history(
            graph,
            events,
            run_id=run_id,
            graph_digest=graph_digest,
            authority_id=authority_id,
            controller_id=controller_id,
        )
    except RuntimeStoreIntegrityError as exc:
        return _issue_result(
            RecoveryClassification.EVENT_LOG_CORRUPT,
            "EVENT_HISTORY_INVALID",
            str(exc),
        )
    classification = RecoveryClassification.CONSISTENT
    if in_progress:
        classification = RecoveryClassification.RECOVERY_IN_PROGRESS
    elif completed:
        classification = RecoveryClassification.RECOVERED
    return ReplayResult(
        classification=classification,
        reconstructed_state=copy.deepcopy(state),
        last_valid_sequence=len(events),
        attempt_counts=tuple(sorted(attempts.items())),
    )


def _map_event_problem(
    problem: _store.RuntimeStoreInspection,
) -> RecoveryAssessment:
    issue = problem.issues[0]
    if problem.status is _store.RuntimeStoreStatus.AUTHORITY_MISMATCH:
        classification = RecoveryClassification.AUTHORITY_MISMATCH
    elif issue.code == "EVENT_LOG_TORN" or (
        problem.status is _store.RuntimeStoreStatus.RECOVERY_REQUIRED
        and issue.code == "EVENT_LOG_MALFORMED"
    ):
        classification = RecoveryClassification.EVENT_LOG_TORN
    else:
        classification = RecoveryClassification.EVENT_LOG_CORRUPT
    return _issue_assessment(classification, issue.code, issue.message)


def _read_snapshot(
    root: str | os.PathLike[str],
    *,
    run_id: str,
    graph_digest: str,
    authority_id: str,
    controller_id: str,
    writer_id: str | None,
) -> tuple[RecoveryAssessment | None, _RecoverySnapshot | None]:
    try:
        paths = _store._paths(root)
        if not _store._ensure_runtime_directory(paths, create=False):
            return (
                _issue_assessment(
                    RecoveryClassification.GRAPH_CORRUPT,
                    "RUNTIME_NOT_INITIALIZED",
                    "runtime graph and event history are unavailable",
                ),
                None,
            )
        graph_bytes, _ = _store._read_regular_bytes(
            paths.graph,
            maximum=_store.MAX_GRAPH_BYTES,
        )
        graph = _store._strict_json_loads(graph_bytes, "graph snapshot")
        if _store._canonical_json_bytes(graph) != graph_bytes:
            raise RuntimeStoreIntegrityError("graph snapshot is not canonical")
        actual_graph_digest = _store._validate_graph(graph)
    except (_store.RuntimeStoreError, RuntimeStoreIntegrityError):
        return (
            _issue_assessment(
                RecoveryClassification.GRAPH_CORRUPT,
                "GRAPH_INVALID",
                "graph snapshot is missing, unsafe, or invalid",
            ),
            None,
        )
    if actual_graph_digest != graph_digest:
        return (
            _issue_assessment(
                RecoveryClassification.AUTHORITY_MISMATCH,
                "GRAPH_BINDING_MISMATCH",
                "graph snapshot does not match the expected identity",
            ),
            None,
        )

    lock, lock_problem = _store._inspect_lock(paths)
    if lock_problem is not None:
        return (
            _issue_assessment(
                RecoveryClassification.LOCK_INTEGRITY_ERROR,
                "LOCK_INTEGRITY_ERROR",
                lock_problem.issues[0].message,
            ),
            None,
        )
    expected_lock = (run_id, graph_digest, authority_id, controller_id)
    if lock is not None:
        actual_lock = (
            lock["run_id"],
            lock["graph_digest"],
            lock["authority_id"],
            lock["controller_id"],
        )
        if actual_lock != expected_lock:
            return (
                _issue_assessment(
                    RecoveryClassification.AUTHORITY_MISMATCH,
                    "LOCK_BINDING_MISMATCH",
                    "writer lock does not match the expected identity",
                ),
                None,
            )
        if writer_id is not None and lock["writer_id"] != writer_id:
            return (
                _issue_assessment(
                    RecoveryClassification.LOCKED_BY_OTHER_WRITER,
                    "LOCKED_BY_OTHER_WRITER",
                    "runtime recovery is owned by another writer",
                ),
                None,
            )

    binding = {
        "run_id": run_id,
        "graph_digest": graph_digest,
        "authority_id": authority_id,
        "controller_id": controller_id,
    }
    try:
        event_bytes, _ = _store._read_regular_bytes(
            paths.events,
            maximum=_store.MAX_EVENTS_BYTES,
        )
    except RuntimeStoreIntegrityError:
        return (
            _issue_assessment(
                RecoveryClassification.EVENT_LOG_CORRUPT,
                "EVENT_LOG_UNAVAILABLE",
                "event history is missing or unsafe",
            ),
            None,
        )
    events, event_problem = _store._parse_event_log(
        event_bytes,
        graph,
        binding,
    )
    if event_problem is not None:
        return _map_event_problem(event_problem), None

    state: dict[str, Any] | None = None
    state_bytes: bytes | None = None
    if _store._entry_lstat(paths.state) is not None:
        try:
            state_bytes, _ = _store._read_regular_bytes(
                paths.state,
                maximum=_store.MAX_STATE_BYTES,
            )
            state = _store._strict_json_loads(state_bytes, "runtime state")
            if _store._canonical_json_bytes(state) != state_bytes:
                raise RuntimeStoreIntegrityError(
                    "runtime state is not canonical"
                )
            if type(state) is not dict or (
                state.get("run_id") != run_id
                or state.get("graph_digest") != graph_digest
                or state.get("authority_id") != authority_id
                or state.get("controller_id") != controller_id
            ):
                return (
                    _issue_assessment(
                        RecoveryClassification.AUTHORITY_MISMATCH,
                        "STATE_BINDING_MISMATCH",
                        "runtime state does not match the expected identity",
                    ),
                    None,
                )
            _store.validate_runtime_state(
                state,
                graph,
                run_id=run_id,
                graph_digest=graph_digest,
                authority_id=authority_id,
                controller_id=controller_id,
            )
        except RuntimeStoreIntegrityError:
            return (
                _issue_assessment(
                    RecoveryClassification.STATE_DIVERGED,
                    "STATE_INVALID",
                    "runtime state is unsafe, invalid, or semantically divergent",
                ),
                None,
            )
    return (
        None,
        _RecoverySnapshot(
            graph=graph,
            state=state,
            events=events,
            graph_bytes=graph_bytes,
            state_bytes=state_bytes,
            event_bytes=event_bytes,
        ),
    )


def _assess_with_snapshot(
    root: str | os.PathLike[str],
    *,
    run_id: str,
    graph_digest: str,
    authority_id: str,
    controller_id: str,
    writer_id: str | None,
) -> tuple[RecoveryAssessment, _RecoverySnapshot | None]:
    problem, snapshot = _read_snapshot(
        root,
        run_id=run_id,
        graph_digest=graph_digest,
        authority_id=authority_id,
        controller_id=controller_id,
        writer_id=writer_id,
    )
    if problem is not None or snapshot is None:
        return problem or _issue_assessment(
            RecoveryClassification.EVENT_LOG_CORRUPT,
            "SNAPSHOT_UNAVAILABLE",
            "runtime recovery snapshot is unavailable",
        ), None
    replay = replay_runtime_events(
        snapshot.graph,
        snapshot.events,
        run_id=run_id,
        graph_digest=graph_digest,
        authority_id=authority_id,
        controller_id=controller_id,
    )
    if replay.reconstructed_state is None:
        return (
            RecoveryAssessment(
                classification=replay.classification,
                replay=replay,
                current_state=copy.deepcopy(snapshot.state),
                issues=replay.issues,
            ),
            snapshot,
        )
    if snapshot.state is None:
        classification = (
            RecoveryClassification.RECOVERY_IN_PROGRESS
            if replay.classification
            is RecoveryClassification.RECOVERY_IN_PROGRESS
            else RecoveryClassification.STATE_MISSING
        )
        return (
            RecoveryAssessment(classification=classification, replay=replay),
            snapshot,
        )

    state_sequence = snapshot.state["last_event_sequence"]
    if state_sequence > replay.last_valid_sequence:
        return (
            RecoveryAssessment(
                classification=RecoveryClassification.STATE_AHEAD_OF_EVENTS,
                replay=replay,
                current_state=copy.deepcopy(snapshot.state),
                issues=_issues(
                    RecoveryIssue(
                        "STATE_AHEAD_OF_EVENTS",
                        "runtime state refers to unavailable events",
                    )
                ),
            ),
            snapshot,
        )
    if state_sequence < 2:
        prefix_matches = False
    else:
        prefix = replay_runtime_events(
            snapshot.graph,
            snapshot.events[:state_sequence],
            run_id=run_id,
            graph_digest=graph_digest,
            authority_id=authority_id,
            controller_id=controller_id,
        )
        prefix_matches = (
            prefix.reconstructed_state is not None
            and _store._canonical_json_bytes(prefix.reconstructed_state)
            == _store._canonical_json_bytes(snapshot.state)
        )
    if state_sequence < replay.last_valid_sequence:
        if not prefix_matches:
            classification = RecoveryClassification.STATE_DIVERGED
        elif replay.classification is RecoveryClassification.RECOVERY_IN_PROGRESS:
            classification = RecoveryClassification.RECOVERY_IN_PROGRESS
        else:
            classification = RecoveryClassification.STATE_BEHIND_EVENTS
        return (
            RecoveryAssessment(
                classification=classification,
                replay=replay,
                current_state=copy.deepcopy(snapshot.state),
            ),
            snapshot,
        )
    if (
        _store._canonical_json_bytes(replay.reconstructed_state)
        != _store._canonical_json_bytes(snapshot.state)
    ):
        classification = RecoveryClassification.STATE_DIVERGED
    else:
        classification = RecoveryClassification.CONSISTENT
    return (
        RecoveryAssessment(
            classification=classification,
            replay=replay,
            current_state=copy.deepcopy(snapshot.state),
        ),
        snapshot,
    )


def assess_runtime_recovery(
    root: str | os.PathLike[str],
    *,
    run_id: str,
    graph_digest: str,
    authority_id: str,
    controller_id: str,
    writer_id: str | None = None,
) -> RecoveryAssessment:
    """Read and classify a runtime store without creating or changing files."""

    assessment, _ = _assess_with_snapshot(
        root,
        run_id=run_id,
        graph_digest=graph_digest,
        authority_id=authority_id,
        controller_id=controller_id,
        writer_id=writer_id,
    )
    return assessment


def _recovery_event(
    writer: RuntimeWriter,
    *,
    sequence: int,
    event_type: str,
    observed_at: str,
) -> dict[str, Any]:
    return {
        "schema_id": _store.EVENT_SCHEMA_ID,
        "schema_version": 1,
        "event_id": _store.derive_event_id(writer.run_id, sequence),
        "run_id": writer.run_id,
        "sequence": sequence,
        "graph_digest": writer.graph_digest,
        "event_type": event_type,
        "authority_id": writer.authority_id,
        "actor_id": writer.controller_id,
        "observed_at": observed_at,
        "reason_code": f"RUNTIME_{event_type}",
        "evidence_refs": [],
        "artifact_refs": [],
    }


def recover_runtime_state(
    writer: RuntimeWriter,
    *,
    clock: Callable[[], Any] | None = None,
) -> RecoveryResult:
    """Explicitly recover only missing or event-lagging state for a live writer."""

    try:
        _store._verify_writer(writer)
    except RuntimeStoreIntegrityError as exc:
        return RecoveryResult(
            classification=RecoveryClassification.LOCK_INTEGRITY_ERROR,
            issues=_issues(
                RecoveryIssue("WRITER_INVALID", str(exc))
            ),
        )
    assessment, snapshot = _assess_with_snapshot(
        writer.root,
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        controller_id=writer.controller_id,
        writer_id=writer.writer_id,
    )
    if assessment.classification is RecoveryClassification.CONSISTENT:
        return RecoveryResult(
            classification=RecoveryClassification.CONSISTENT,
            recovered_state=copy.deepcopy(assessment.current_state),
        )
    recoverable = {
        RecoveryClassification.STATE_MISSING,
        RecoveryClassification.STATE_BEHIND_EVENTS,
        RecoveryClassification.RECOVERY_IN_PROGRESS,
    }
    if assessment.classification not in recoverable or snapshot is None:
        return RecoveryResult(
            classification=assessment.classification,
            recovered_state=copy.deepcopy(assessment.current_state),
            issues=assessment.issues,
        )

    next_sequence = len(snapshot.events) + 1
    recovery_events: list[dict[str, Any]] = []
    if snapshot.events[-1]["event_type"] == "RECOVERY_STARTED":
        observed_at = _store._clock_value(clock)
        recovery_events.append(
            _recovery_event(
                writer,
                sequence=next_sequence,
                event_type="RECOVERY_COMPLETED",
                observed_at=observed_at,
            )
        )
    elif not (
        len(snapshot.events) >= 2
        and snapshot.events[-2]["event_type"] == "RECOVERY_STARTED"
        and snapshot.events[-1]["event_type"] == "RECOVERY_COMPLETED"
    ):
        observed_at = _store._clock_value(clock)
        recovery_events.extend(
            (
                _recovery_event(
                    writer,
                    sequence=next_sequence,
                    event_type="RECOVERY_STARTED",
                    observed_at=observed_at,
                ),
                _recovery_event(
                    writer,
                    sequence=next_sequence + 1,
                    event_type="RECOVERY_COMPLETED",
                    observed_at=observed_at,
                ),
            )
        )

    combined = snapshot.events + tuple(recovery_events)
    replay = replay_runtime_events(
        snapshot.graph,
        combined,
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        controller_id=writer.controller_id,
    )
    if replay.reconstructed_state is None:
        return RecoveryResult(
            classification=replay.classification,
            issues=replay.issues,
        )
    _store._commit_runtime_recovery(
        writer,
        expected_graph_bytes=snapshot.graph_bytes,
        expected_state_bytes=snapshot.state_bytes,
        expected_event_bytes=snapshot.event_bytes,
        recovery_events=recovery_events,
        recovered_state=replay.reconstructed_state,
    )
    final = assess_runtime_recovery(
        writer.root,
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        controller_id=writer.controller_id,
        writer_id=writer.writer_id,
    )
    if final.classification is not RecoveryClassification.CONSISTENT:
        return RecoveryResult(
            classification=final.classification,
            recovered_state=copy.deepcopy(final.current_state),
            appended_event_count=len(recovery_events),
            issues=final.issues,
        )
    return RecoveryResult(
        classification=RecoveryClassification.RECOVERED,
        recovered_state=copy.deepcopy(final.current_state),
        appended_event_count=len(recovery_events),
    )


__all__ = [
    "MAX_RECOVERY_ISSUES",
    "RecoveryAssessment",
    "RecoveryClassification",
    "RecoveryIssue",
    "RecoveryResult",
    "ReplayResult",
    "assess_runtime_recovery",
    "recover_runtime_state",
    "replay_runtime_events",
]
