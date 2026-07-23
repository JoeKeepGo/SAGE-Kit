"""Pure, bounded, reference-only views over validated runtime state.

The views in this module are derived observations.  They are not Graph,
runtime-state, recovery, acceptance, scheduling, or execution authority.  The
module performs no store discovery, recovery, locking, filesystem access, or
mutation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import ntpath
import posixpath
import re
from typing import Any, Mapping

from . import runtime_store as _store
from .runtime_recovery import (
    RecoveryAssessment,
    RecoveryClassification,
    RecoveryResult,
    ReplayResult,
)


_VIEW_SCHEMA = "sagekit.runtime-handoff-view"
_VIEW_VERSION = 1
_AUTHORITY_CLASS = "REFERENCE_ONLY"
_SOURCE_STATE_DIGEST_DOMAIN = b"sagekit:runtime-source-state-view:v1\0"

_DEFAULT_NODE_LIMIT = 32
_DEFAULT_EVIDENCE_LIMIT = 64
_MAX_NODE_LIMIT = 256
_MAX_EVIDENCE_LIMIT = 1024
_MAX_DIAGNOSTIC_CODES = 8

_DIAGNOSTIC_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?:^|[/?:;&#\s])"
    r"(?:sagekit_delegation_secret|secret|password|passwd|credential|"
    r"api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"private[_-]?key)\s*[:=]",
    re.IGNORECASE,
)
_BEARER_CREDENTIAL_RE = re.compile(
    r"(?:^|[/?:;&#\s])authorization\s*:\s*bearer\s+\S+",
    re.IGNORECASE,
)

_ACTIVE_STATUSES = frozenset({"READY", "RUNNING"})
_WAITING_STATUSES = frozenset({"PENDING", "WAITING_RESOURCE"})
_BLOCKED_STATUSES = frozenset(
    {"FAILED", "NEEDS_CORRECTION", "HANDOFF", "BLOCKED"}
)
_TERMINAL_STATUSES = frozenset(
    {
        "SUCCEEDED",
        "NO_ACTION_REQUIRED",
        "DONE_WITH_CONCERNS",
        "CANCELLED",
    }
)
_RECOVERY_REQUIRED_CLASSIFICATIONS = frozenset(
    {
        RecoveryClassification.STATE_MISSING,
        RecoveryClassification.STATE_BEHIND_EVENTS,
        RecoveryClassification.RECOVERY_IN_PROGRESS,
    }
)

_CSV_FIELDS = (
    "authority_class",
    "view_schema",
    "view_version",
    "recovery_classification",
    "valid_for_execution",
    "required_action",
    "source_state_canonical_digest",
    "run_id",
    "graph_digest",
    "graph_generation",
    "authority_id",
    "controller_id",
    "run_status",
    "revision",
    "last_event_sequence",
    "node_total",
    "nodes_truncated",
    "record_type",
    "node_id",
    "node_status",
    "node_last_event_sequence",
    "evidence_reference_count",
    "evidence_references_json",
    "evidence_truncated",
)


class _FrozenDict(dict):
    """A JSON-serializable dictionary that cannot be changed after creation."""

    @staticmethod
    def _immutable(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("runtime views are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return _FrozenDict({key: _freeze(item) for key, item in value.items()})
    if type(value) in {list, tuple}:
        return tuple(_freeze(item) for item in value)
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reference_is_export_safe(value: str) -> bool:
    return not (
        posixpath.isabs(value)
        or ntpath.isabs(value)
        or value.startswith("\\")
        or value.casefold().startswith("file:")
        or _SECRET_ASSIGNMENT_RE.search(value) is not None
        or _BEARER_CREDENTIAL_RE.search(value) is not None
    )


def _bounded_limit(value: int, *, label: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{label} must be an integer from 1 through {maximum}")
    return value


def _classification_value(source: object) -> RecoveryClassification | None:
    value = getattr(source, "classification", None)
    return value if isinstance(value, RecoveryClassification) else None


def _source_issues(source: object) -> tuple[Any, ...]:
    issues = getattr(source, "issues", ())
    return issues if type(issues) is tuple else ()


def _diagnostic_codes(
    source: object,
    *,
    additional: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], bool]:
    candidates = list(additional)
    for issue in _source_issues(source):
        code = getattr(issue, "code", None)
        if type(code) is str and _DIAGNOSTIC_CODE_RE.fullmatch(code):
            candidates.append(code)
        else:
            candidates.append("UNSAFE_DIAGNOSTIC")
    ordered = sorted(set(candidates))
    return tuple(ordered[:_MAX_DIAGNOSTIC_CODES]), len(ordered) > _MAX_DIAGNOSTIC_CODES


def _state_from_source(source: object) -> tuple[RecoveryClassification | None, Any]:
    classification = _classification_value(source)
    if isinstance(source, RecoveryAssessment):
        if classification is RecoveryClassification.CONSISTENT:
            return classification, source.current_state
        return classification, None
    if isinstance(source, ReplayResult):
        if classification in {
            RecoveryClassification.CONSISTENT,
            RecoveryClassification.RECOVERED,
        }:
            return classification, source.reconstructed_state
        return classification, None
    if isinstance(source, RecoveryResult):
        if classification in {
            RecoveryClassification.CONSISTENT,
            RecoveryClassification.RECOVERED,
        }:
            return classification, source.recovered_state
        return classification, None
    return classification, None


def _validate_and_normalize_state(value: Any) -> dict[str, Any]:
    state = _store._require_exact_mapping(
        value,
        required=_store._STATE_REQUIRED_FIELDS,
        allowed=_store._STATE_FIELDS,
        label="runtime view source state",
    )
    if state["schema_id"] != _store.STATE_SCHEMA_ID:
        raise _store.RuntimeStoreIntegrityError("source state schema is invalid")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise _store.RuntimeStoreIntegrityError(
            "source state schema version is invalid"
        )

    _store._require_identity(state["run_id"], "source state run_id")
    _store._require_sha256(state["graph_digest"], "source state graph_digest")
    _store._require_integer(
        state["graph_generation"],
        "source state graph_generation",
        minimum=1,
        maximum=_store.MAX_GRAPH_GENERATION,
    )
    _store._require_integer(
        state["revision"],
        "source state revision",
        minimum=0,
        maximum=_store.MAX_SAFE_INTEGER,
    )
    last_event_sequence = _store._require_integer(
        state["last_event_sequence"],
        "source state last_event_sequence",
        minimum=0,
        maximum=_store.MAX_SAFE_INTEGER,
    )
    _store._require_enum(
        state["run_status"],
        _store.RUN_STATUSES,
        "source state run_status",
    )
    _store._require_identity(state["authority_id"], "source state authority_id")
    _store._require_identity(
        state["controller_id"],
        "source state controller_id",
    )
    if "handoff_ref" in state:
        handoff_ref = _store._require_reference(
            state["handoff_ref"],
            "source state handoff_ref",
        )
        if not _reference_is_export_safe(handoff_ref):
            raise _store.RuntimeStoreIntegrityError(
                "source state handoff_ref is unsafe for export"
            )
    if "recovery_status" in state:
        _store._require_string(
            state["recovery_status"],
            "source state recovery_status",
            maximum=64,
            pattern=_store._LABEL_RE,
        )

    node_values = state["node_states"]
    if type(node_values) is not list or not 1 <= len(node_values) <= 10000:
        raise _store.RuntimeStoreIntegrityError(
            "source state node_states is outside its item bound"
        )

    normalized_nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for index, value_node in enumerate(node_values):
        label = f"source state node_states[{index}]"
        node_state = _store._require_exact_mapping(
            value_node,
            required=_store._NODE_STATE_REQUIRED_FIELDS,
            allowed=_store._NODE_STATE_FIELDS,
            label=label,
        )
        node_id = _store._require_node_id(node_state["node_id"], f"{label}.node_id")
        if node_id in node_ids:
            raise _store.RuntimeStoreIntegrityError(
                "source state node identities must be unique"
            )
        node_ids.add(node_id)
        status = _store._require_enum(
            node_state["status"],
            _store.NODE_STATUSES,
            f"{label}.status",
        )
        attempt_id = node_state["attempt_id"]
        if attempt_id is not None:
            _store._require_string(
                attempt_id,
                f"{label}.attempt_id",
                maximum=256,
                pattern=_store._DERIVED_ATTEMPT_RE,
            )
        if status in _store._ATTEMPT_REQUIRED_STATUSES and attempt_id is None:
            raise _store.RuntimeStoreIntegrityError(
                f"{label}.attempt_id is required for {status}"
            )
        node_sequence = _store._require_integer(
            node_state["last_event_sequence"],
            f"{label}.last_event_sequence",
            minimum=0,
            maximum=_store.MAX_SAFE_INTEGER,
        )
        if node_sequence > last_event_sequence:
            raise _store.RuntimeStoreIntegrityError(
                f"{label}.last_event_sequence exceeds the state sequence"
            )
        evidence_refs = _store._require_reference_array(
            node_state["evidence_refs"],
            f"{label}.evidence_refs",
        )
        if any(
            not _reference_is_export_safe(reference)
            for reference in evidence_refs
        ):
            raise _store.RuntimeStoreIntegrityError(
                f"{label}.evidence_refs contains unsafe export material"
            )
        if "result_digest" in node_state:
            _store._require_identity(
                node_state["result_digest"],
                f"{label}.result_digest",
            )
        if "blocker_reason" in node_state:
            blocker_reason = _store._require_string(
                node_state["blocker_reason"],
                f"{label}.blocker_reason",
                maximum=4096,
            )
            if (
                "\r" in blocker_reason
                or "\n" in blocker_reason
                or not blocker_reason.strip()
            ):
                raise _store.RuntimeStoreIntegrityError(
                    f"{label}.blocker_reason is invalid"
                )

        normalized_node = dict(node_state)
        normalized_node["evidence_refs"] = sorted(evidence_refs)
        normalized_nodes.append(normalized_node)

    normalized = dict(state)
    normalized["node_states"] = sorted(
        normalized_nodes,
        key=lambda item: item["node_id"],
    )
    if len(_store._canonical_json_bytes(normalized)) > _store.MAX_STATE_BYTES:
        raise _store.RuntimeStoreIntegrityError(
            "source state exceeds its size bound"
        )
    return normalized


def _source_is_internally_consistent(
    source: object,
    normalized_state: Mapping[str, Any],
) -> bool:
    if _source_issues(source):
        return False
    if isinstance(source, ReplayResult):
        return (
            type(source.last_valid_sequence) is int
            and source.last_valid_sequence
            == normalized_state["last_event_sequence"]
        )
    if isinstance(source, RecoveryResult):
        return (
            type(source.appended_event_count) is int
            and source.appended_event_count >= 0
        )
    if isinstance(source, RecoveryAssessment):
        if source.replay is None:
            return False
        replay = source.replay
        if (
            replay.reconstructed_state is None
            or replay.classification
            not in {
                RecoveryClassification.CONSISTENT,
                RecoveryClassification.RECOVERED,
            }
        ):
            return False
        try:
            replay_state = _validate_and_normalize_state(replay.reconstructed_state)
        except (TypeError, ValueError, _store.RuntimeStoreIntegrityError):
            return False
        return _canonical_json_bytes(replay_state) == _canonical_json_bytes(
            normalized_state
        )
    return True


def _source_state_digest(normalized_state: Mapping[str, Any]) -> str:
    material = _SOURCE_STATE_DIGEST_DOMAIN + _canonical_json_bytes(normalized_state)
    return hashlib.sha256(material).hexdigest()


def _bounded_node_group(
    nodes: list[Mapping[str, Any]],
    statuses: frozenset[str],
    limit: int,
) -> dict[str, Any]:
    identifiers = [
        node["node_id"] for node in nodes if node["status"] in statuses
    ]
    return {
        "ids": identifiers[:limit],
        "total": len(identifiers),
        "truncated": len(identifiers) > limit,
    }


def _detail_required_action(
    state: Mapping[str, Any],
) -> str:
    run_status = state["run_status"]
    node_statuses = {node["status"] for node in state["node_states"]}
    if run_status == "RECOVERING":
        return "recovery_required"
    if (
        run_status in {"HANDOFF", "BLOCKED", "NEEDS_CORRECTION"}
        or node_statuses & _BLOCKED_STATUSES
    ):
        return "handoff_required"
    return "consult_runtime_authority"


def _base_view(
    classification: RecoveryClassification | None,
    *,
    node_limit: int,
    evidence_limit: int,
) -> dict[str, Any]:
    return {
        "view_schema": _VIEW_SCHEMA,
        "view_version": _VIEW_VERSION,
        "authority_class": _AUTHORITY_CLASS,
        "run_id": None,
        "graph_digest": None,
        "graph_generation": None,
        "authority_id": None,
        "controller_id": None,
        "run_status": None,
        "revision": None,
        "last_event_sequence": None,
        "recovery_classification": (
            classification.value if classification is not None else "UNRECOGNIZED"
        ),
        "node_status_counts": {
            status: 0 for status in sorted(_store.NODE_STATUSES)
        },
        "node_total": 0,
        "nodes": {
            group: {"ids": [], "total": 0, "truncated": False}
            for group in ("active", "waiting", "blocked", "terminal")
        },
        "reference_counts": {
            "evidence_references": 0,
            "unique_evidence_references": 0,
            "handoff_references": 0,
        },
        "evidence_references": {
            "values": [],
            "total": 0,
            "truncated": False,
        },
        "source_state_canonical_digest": None,
        "limits": {
            "node_ids_per_group": node_limit,
            "evidence_references": evidence_limit,
        },
        "truncated": False,
        "valid_for_execution": False,
        "required_action": (
            "recovery_required"
            if classification in _RECOVERY_REQUIRED_CLASSIFICATIONS
            else "handoff_required"
        ),
        "diagnostic_codes": [],
    }


def _build_view_and_state(
    source: RecoveryAssessment | ReplayResult | RecoveryResult,
    *,
    node_limit: int,
    evidence_limit: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    node_limit = _bounded_limit(
        node_limit,
        label="node_limit",
        maximum=_MAX_NODE_LIMIT,
    )
    evidence_limit = _bounded_limit(
        evidence_limit,
        label="evidence_limit",
        maximum=_MAX_EVIDENCE_LIMIT,
    )
    classification, source_state = _state_from_source(source)
    view = _base_view(
        classification,
        node_limit=node_limit,
        evidence_limit=evidence_limit,
    )
    if source_state is None:
        codes, codes_truncated = _diagnostic_codes(
            source,
            additional=(
                ("SOURCE_STATE_UNAVAILABLE",)
                if classification
                in {
                    RecoveryClassification.CONSISTENT,
                    RecoveryClassification.RECOVERED,
                }
                else ()
            ),
        )
        view["diagnostic_codes"] = list(codes)
        view["truncated"] = codes_truncated
        return view, None

    try:
        normalized_state = _validate_and_normalize_state(source_state)
    except (TypeError, ValueError, _store.RuntimeStoreIntegrityError):
        codes, codes_truncated = _diagnostic_codes(
            source,
            additional=("SOURCE_STATE_INVALID",),
        )
        view["diagnostic_codes"] = list(codes)
        view["truncated"] = codes_truncated
        view["required_action"] = "handoff_required"
        return view, None

    if not _source_is_internally_consistent(source, normalized_state):
        codes, codes_truncated = _diagnostic_codes(
            source,
            additional=("SOURCE_RESULT_INCONSISTENT",),
        )
        view["diagnostic_codes"] = list(codes)
        view["truncated"] = codes_truncated
        view["required_action"] = "handoff_required"
        return view, None

    nodes = normalized_state["node_states"]
    counts = {
        status: sum(node["status"] == status for node in nodes)
        for status in sorted(_store.NODE_STATUSES)
    }
    groups = {
        "active": _bounded_node_group(nodes, _ACTIVE_STATUSES, node_limit),
        "waiting": _bounded_node_group(nodes, _WAITING_STATUSES, node_limit),
        "blocked": _bounded_node_group(nodes, _BLOCKED_STATUSES, node_limit),
        "terminal": _bounded_node_group(nodes, _TERMINAL_STATUSES, node_limit),
    }
    all_evidence = [
        reference
        for node in nodes
        for reference in node["evidence_refs"]
    ]
    unique_evidence = sorted(set(all_evidence))
    evidence_truncated = len(unique_evidence) > evidence_limit
    nodes_truncated = any(group["truncated"] for group in groups.values())
    required_action = _detail_required_action(normalized_state)

    view.update(
        {
            "run_id": normalized_state["run_id"],
            "graph_digest": normalized_state["graph_digest"],
            "graph_generation": normalized_state["graph_generation"],
            "authority_id": normalized_state["authority_id"],
            "controller_id": normalized_state["controller_id"],
            "run_status": normalized_state["run_status"],
            "revision": normalized_state["revision"],
            "last_event_sequence": normalized_state["last_event_sequence"],
            "node_status_counts": counts,
            "node_total": len(nodes),
            "nodes": groups,
            "reference_counts": {
                "evidence_references": len(all_evidence),
                "unique_evidence_references": len(unique_evidence),
                "handoff_references": int("handoff_ref" in normalized_state),
            },
            "evidence_references": {
                "values": unique_evidence[:evidence_limit],
                "total": len(unique_evidence),
                "truncated": evidence_truncated,
            },
            "source_state_canonical_digest": _source_state_digest(
                normalized_state
            ),
            "truncated": nodes_truncated or evidence_truncated,
            "valid_for_execution": False,
            "required_action": required_action,
            "diagnostic_codes": [],
        }
    )
    return view, normalized_state


def build_runtime_handoff_view(
    source: RecoveryAssessment | ReplayResult | RecoveryResult,
    *,
    node_limit: int = _DEFAULT_NODE_LIMIT,
    evidence_limit: int = _DEFAULT_EVIDENCE_LIMIT,
) -> Mapping[str, Any]:
    """Return an immutable compact view over an explicitly supplied result.

    A detailed view is emitted only for a structurally safe ``CONSISTENT``
    assessment/replay or an explicit ``RECOVERED`` replay/recovery result.
    Other inputs produce a bounded diagnostic with no runtime detail and with
    ``valid_for_execution`` set to false.
    """

    view, _ = _build_view_and_state(
        source,
        node_limit=node_limit,
        evidence_limit=evidence_limit,
    )
    return _freeze(view)


def _csv_value(value: Any) -> str:
    if value is None:
        text = ""
    elif value is True:
        text = "true"
    elif value is False:
        text = "false"
    else:
        text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _csv_common(view: Mapping[str, Any]) -> dict[str, str]:
    return {
        "authority_class": _csv_value(view["authority_class"]),
        "view_schema": _csv_value(view["view_schema"]),
        "view_version": _csv_value(view["view_version"]),
        "recovery_classification": _csv_value(
            view["recovery_classification"]
        ),
        "valid_for_execution": _csv_value(view["valid_for_execution"]),
        "required_action": _csv_value(view["required_action"]),
        "source_state_canonical_digest": _csv_value(
            view["source_state_canonical_digest"]
        ),
        "run_id": _csv_value(view["run_id"]),
        "graph_digest": _csv_value(view["graph_digest"]),
        "graph_generation": _csv_value(view["graph_generation"]),
        "authority_id": _csv_value(view["authority_id"]),
        "controller_id": _csv_value(view["controller_id"]),
        "run_status": _csv_value(view["run_status"]),
        "revision": _csv_value(view["revision"]),
        "last_event_sequence": _csv_value(view["last_event_sequence"]),
        "node_total": _csv_value(view["node_total"]),
    }


def render_runtime_csv(
    source: RecoveryAssessment | ReplayResult | RecoveryResult,
    *,
    node_limit: int = _DEFAULT_NODE_LIMIT,
    evidence_limit: int = _DEFAULT_EVIDENCE_LIMIT,
) -> str:
    """Render a deterministic, bounded, export-only CSV reference view."""

    mutable_view, normalized_state = _build_view_and_state(
        source,
        node_limit=node_limit,
        evidence_limit=evidence_limit,
    )
    view = _freeze(mutable_view)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=_CSV_FIELDS,
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    common = _csv_common(view)

    if normalized_state is None:
        writer.writerow(
            {
                **common,
                "nodes_truncated": "false",
                "record_type": "diagnostic",
                "node_id": "",
                "node_status": "",
                "node_last_event_sequence": "",
                "evidence_reference_count": "0",
                "evidence_references_json": "[]",
                "evidence_truncated": "false",
            }
        )
        return output.getvalue()

    nodes = normalized_state["node_states"]
    selected_nodes = nodes[:node_limit]
    nodes_truncated = len(nodes) > node_limit
    remaining_evidence = evidence_limit
    for node_state in selected_nodes:
        references = node_state["evidence_refs"]
        included = references[:remaining_evidence]
        remaining_evidence -= len(included)
        evidence_truncated = len(included) < len(references)
        writer.writerow(
            {
                **common,
                "nodes_truncated": _csv_value(nodes_truncated),
                "record_type": "node",
                "node_id": _csv_value(node_state["node_id"]),
                "node_status": _csv_value(node_state["status"]),
                "node_last_event_sequence": _csv_value(
                    node_state["last_event_sequence"]
                ),
                "evidence_reference_count": _csv_value(len(references)),
                "evidence_references_json": _csv_value(
                    json.dumps(
                        included,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                ),
                "evidence_truncated": _csv_value(evidence_truncated),
            }
        )
    return output.getvalue()


__all__ = [
    "build_runtime_handoff_view",
    "render_runtime_csv",
]
