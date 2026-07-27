from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from .candidate import CandidateFingerprint
from .change_control import ChangeClass
from .graph_contract import validate_graph_contract
from .pathing import paths_overlap
from .ready_resolver import (
    canonical_ready_input_digest,
    resolve_ready_nodes,
)
from .transition_resolver import canonical_node_result_digest


LINEAGE_INPUT_SCHEMA_ID = "urn:sagekit:evidence-lineage:v1:input"
LINEAGE_RESULT_SCHEMA_ID = "urn:sagekit:evidence-lineage:v1:result"
LINEAGE_ERROR_SCHEMA_ID = "urn:sagekit:evidence-lineage:v1:error"
LINEAGE_SCHEMA_VERSION = 1

NODE_INPUT_FINGERPRINT_DOMAIN = b"sagekit-evidence-lineage-node-input-v1\0"
JOIN_INTEGRATION_FINGERPRINT_DOMAIN = (
    b"sagekit-evidence-lineage-join-integration-v1\0"
)
JOIN_DEFINITION_FINGERPRINT_DOMAIN = (
    b"sagekit-evidence-lineage-join-definition-v1\0"
)
MAX_INPUT_CANONICAL_BYTES = 8 * 1024 * 1024
MAX_RESULT_CANONICAL_BYTES = 8 * 1024 * 1024
MAX_ERROR_CANONICAL_BYTES = 1024 * 1024
MAX_LINEAGE_NODES = 10000
MAX_LINEAGE_EDGES = 50000
MAX_TRANSITION_BINDINGS = 10000
MAX_JOIN_INTEGRATIONS = 10000
MAX_JOIN_CONTRIBUTORS = 10000
MAX_EXTERNAL_DECISION_REFS = 10000
MAX_ISSUES = 100

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ISSUE_LOCATION = re.compile(
    r"^\$(?:(?:\.[A-Za-z_][A-Za-z0-9_]*)|\[[0-9]{1,7}\])*$"
)
_BOUNDED_REF = re.compile(
    r"^(?![A-Za-z]:)(?![/\\])(?!(?:file|http|https|unc):)[^\r\n]{1,512}$",
    re.IGNORECASE,
)
_OWNER_KINDS = frozenset(
    {
        "GRAPH_NODE",
        "JOIN",
        "PATH",
        "CONTRACT",
        "AUTHORITY",
        "DEPENDENCY_SET",
        "TOOLCHAIN",
        "PLATFORM",
        "EVIDENCE",
        "CANDIDATE",
    }
)
_EDGE_TYPES = frozenset(
    {
        "NODE_OUTPUT",
        "JOIN_INTEGRATION",
        "PATH",
        "CONTRACT",
        "AUTHORITY",
        "DEPENDENCY_SET",
        "TOOLCHAIN",
        "PLATFORM",
        "CANDIDATE",
    }
)
_TARGETED_EDGE_TYPES = (
    "NODE_OUTPUT",
    "JOIN_INTEGRATION",
    "PATH",
    "DEPENDENCY_SET",
    "TOOLCHAIN",
    "PLATFORM",
)
_TARGETED_EDGE_SET = frozenset(_TARGETED_EDGE_TYPES)
_INVALID_EDGE_TYPES = ("CONTRACT", "AUTHORITY", "CANDIDATE")
_INVALID_EDGE_SET = frozenset(_INVALID_EDGE_TYPES)
_OWNER_EDGE_TYPE = {
    "GRAPH_NODE": "NODE_OUTPUT",
    "JOIN": "JOIN_INTEGRATION",
    "PATH": "PATH",
    "CONTRACT": "CONTRACT",
    "AUTHORITY": "AUTHORITY",
    "DEPENDENCY_SET": "DEPENDENCY_SET",
    "TOOLCHAIN": "TOOLCHAIN",
    "PLATFORM": "PLATFORM",
    "CANDIDATE": "CANDIDATE",
}
_EDGE_OWNER = {
    "NODE_OUTPUT": "GRAPH_NODE",
    "JOIN_INTEGRATION": "JOIN",
    "PATH": "PATH",
    "CONTRACT": "CONTRACT",
    "AUTHORITY": "AUTHORITY",
    "DEPENDENCY_SET": "DEPENDENCY_SET",
    "TOOLCHAIN": "TOOLCHAIN",
    "PLATFORM": "PLATFORM",
    "CANDIDATE": "CANDIDATE",
}
_INVALID_REASON = {
    "CONTRACT": "CONTRACT_CHANGED",
    "AUTHORITY": "AUTHORITY_CHANGED",
    "CANDIDATE": "CANDIDATE_CHANGED",
}
_ERROR_MESSAGES = {
    "INPUT_INVALID": "STRICT_INPUT_REQUIRED",
    "INPUT_TOO_LARGE": "INPUT_BYTE_BUDGET_EXCEEDED",
    "LINEAGE_LIMIT_EXCEEDED": "STRUCTURAL_LIMIT_EXCEEDED",
    "LINEAGE_CYCLE": "ACYCLIC_LINEAGE_REQUIRED",
    "GRAPH_BINDING_MISMATCH": "GRAPH_BINDING_REQUIRED",
    "LINEAGE_INVALID": "VALID_LINEAGE_REQUIRED",
    "RESULT_TOO_LARGE": "RESULT_BYTE_BUDGET_EXCEEDED",
}
_INPUT_FIELDS = frozenset(
    {"schema_id", "schema_version", "baseline", "candidate"}
)
_SNAPSHOT_FIELDS = frozenset(
    {
        "graph_binding",
        "stage4_bindings",
        "lineage_nodes",
        "lineage_edges",
        "join_integrations",
        "final_evidence_node_id",
    }
)
_GRAPH_BINDING_FIELDS = frozenset(
    {"graph_id", "graph_generation", "graph_digest"}
)
_STAGE4_FIELDS = frozenset({"ready_input_digest", "transition_bindings"})
_TRANSITION_FIELDS = frozenset(
    {"node_id", "transition_input_digest", "node_result_digest"}
)
_NODE_FIELDS = frozenset(
    {
        "lineage_node_id",
        "owner_kind",
        "owner_id",
        "input_fingerprint",
        "output_fingerprint",
    }
)
_EDGE_FIELDS = frozenset(
    {
        "source_node_id",
        "target_node_id",
        "edge_type",
        "source_output_fingerprint",
        "target_input_fingerprint",
    }
)
_JOIN_FIELDS = frozenset(
    {
        "join_id",
        "policy",
        "definition_fingerprint",
        "contributor_node_ids",
        "ready_input_digest",
        "external_decision_refs",
    }
)
_JOIN_POLICIES = frozenset(
    {
        "all-required",
        "required-plus-optional",
        "first-success",
        "manual-gate",
        "corrective-join",
    }
)
_EXTERNAL_JOIN_POLICIES = frozenset({"manual-gate", "corrective-join"})


@dataclass(frozen=True)
class EvidenceFingerprint:
    evidence_id: str
    kind: str
    lane: str
    base_sha: str
    head_sha: str
    covered_paths: tuple[str, ...]
    covered_contracts: tuple[str, ...]
    command: str
    dependency_fingerprint: str
    toolchain_fingerprint: str
    platform: str
    authority_version: str
    result: str
    candidate_fingerprint: str | None = None


@dataclass(frozen=True)
class ChangeEvent:
    change_class: ChangeClass
    changed_paths: tuple[str, ...] = ()
    changed_contracts: tuple[str, ...] = ()
    build_or_dependency_change: bool = False
    dependency_fingerprint: str | None = None
    toolchain_fingerprint: str | None = None
    platform: str | None = None
    authority_version: str | None = None
    current_candidate_fingerprint: str | None = None


@dataclass(frozen=True)
class EvidenceAssessment:
    evidence_id: str
    reusable: bool
    reasons: tuple[str, ...]


def assess_evidence(
    fingerprint: EvidenceFingerprint,
    event: ChangeEvent,
) -> EvidenceAssessment:
    reasons: list[str] = []
    if fingerprint.result != "PASS":
        reasons.append(f"evidence result is not reusable: {fingerprint.result}")
    platform = "windows" if fingerprint.platform.lower().startswith("win") else "posix"
    path_changed = any(
        paths_overlap(covered, changed, platform)
        for covered in fingerprint.covered_paths
        for changed in event.changed_paths
    )

    if event.change_class == ChangeClass.C0_RECORD_ONLY:
        if fingerprint.kind == "record-consistency" and path_changed:
            reasons.append("covered record changed")
    elif event.change_class == ChangeClass.C1_BOUNDED_CORRECTIVE and path_changed:
        if fingerprint.kind in {"focused", "affected-lane", "semantic", "integration"}:
            reasons.append("covered path changed")

    elif event.change_class == ChangeClass.C2_CONTRACT_AFFECTING:
        if set(fingerprint.covered_contracts).intersection(event.changed_contracts):
            reasons.append("covered contract changed")
        if path_changed and fingerprint.kind in {"semantic", "affected-lane", "integration"}:
            reasons.append("covered semantic path changed")

    if event.build_or_dependency_change and fingerprint.kind in {
        "build",
        "platform",
        "package",
        "integration",
    }:
        reasons.append("build or dependency surface changed")
    if (
        event.dependency_fingerprint is not None
        and event.dependency_fingerprint != fingerprint.dependency_fingerprint
    ):
        reasons.append("dependency fingerprint changed")
    if (
        event.toolchain_fingerprint is not None
        and event.toolchain_fingerprint != fingerprint.toolchain_fingerprint
    ):
        reasons.append("toolchain fingerprint changed")
    if event.platform is not None and event.platform != fingerprint.platform:
        reasons.append("platform changed")
    if (
        event.authority_version is not None
        and event.authority_version != fingerprint.authority_version
        and fingerprint.kind in {"record-consistency", "semantic", "affected-lane", "integration"}
    ):
        reasons.append("authority version changed")
    if (
        fingerprint.candidate_fingerprint is not None
        and event.current_candidate_fingerprint is not None
        and fingerprint.candidate_fingerprint != event.current_candidate_fingerprint
        and fingerprint.kind in {"integration", "package", "build", "platform"}
    ):
        reasons.append("candidate fingerprint changed")

    return EvidenceAssessment(fingerprint.evidence_id, not reasons, tuple(dict.fromkeys(reasons)))


@dataclass(frozen=True, order=True)
class EvidenceLineageIssue:
    """A bounded machine-readable Evidence Lineage validation issue."""

    location: str
    issue_code: str

    def as_dict(self) -> dict[str, str]:
        return {
            "issue_code": self.issue_code,
            "location": self.location,
        }


class EvidenceLineageOutcome:
    """Resolver-created immutable snapshot of one complete Result or Error."""

    __slots__ = ("_result_snapshot", "_error_snapshot")

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise ValueError("EvidenceLineageOutcome is resolver-created")

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("EvidenceLineageOutcome is immutable")

    def __delattr__(self, _name: str) -> None:
        raise AttributeError("EvidenceLineageOutcome is immutable")

    @classmethod
    def _from_result(cls, result: Mapping[str, Any]) -> EvidenceLineageOutcome:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", _freeze_json(result))
        object.__setattr__(instance, "_error_snapshot", None)
        return instance

    @classmethod
    def _from_error(cls, error: Mapping[str, Any]) -> EvidenceLineageOutcome:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", None)
        object.__setattr__(instance, "_error_snapshot", _freeze_json(error))
        return instance

    @property
    def result(self) -> dict[str, Any] | None:
        return _thaw_json(self._result_snapshot)

    @property
    def error(self) -> dict[str, Any] | None:
        return _thaw_json(self._error_snapshot)

    @property
    def succeeded(self) -> bool:
        return self._result_snapshot is not None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EvidenceLineageOutcome):
            return NotImplemented
        return (
            self._result_snapshot == other._result_snapshot
            and self._error_snapshot == other._error_snapshot
        )


class _StrictJSONError(ValueError):
    pass


class _CanonicalSizeExceeded(_StrictJSONError):
    pass


def _normalized_string(value: str) -> str:
    if not any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        return value
    output: list[str] = []
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(value):
                raise _StrictJSONError("unpaired high surrogate")
            low = ord(value[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise _StrictJSONError("unpaired high surrogate")
            output.append(
                chr(0x10000 + ((codepoint - 0xD800) << 10) + low - 0xDC00)
            )
            index += 2
            continue
        if 0xDC00 <= codepoint <= 0xDFFF:
            raise _StrictJSONError("unpaired low surrogate")
        output.append(value[index])
        index += 1
    return "".join(output)


def _normalized_json(
    value: Any,
    active: set[int] | None = None,
) -> Any:
    if active is None:
        active = set()
    if value is None or type(value) in {bool, int}:
        return value
    if type(value) is str:
        return _normalized_string(value)
    if type(value) is float:
        raise _StrictJSONError("floating-point values are not admitted")
    if type(value) is list:
        identity = id(value)
        if identity in active:
            raise _StrictJSONError("cyclic JSON value")
        active.add(identity)
        try:
            return [_normalized_json(item, active) for item in value]
        finally:
            active.remove(identity)
    if type(value) is dict:
        identity = id(value)
        if identity in active:
            raise _StrictJSONError("cyclic JSON value")
        active.add(identity)
        normalized: dict[str, Any] = {}
        try:
            for key, item in value.items():
                if type(key) is not str:
                    raise _StrictJSONError("object names must be strings")
                normalized_key = _normalized_string(key)
                if normalized_key in normalized:
                    raise _StrictJSONError("duplicate normalized object name")
                normalized[normalized_key] = _normalized_json(item, active)
        finally:
            active.remove(identity)
        return normalized
    raise _StrictJSONError("value is not strict JSON")


def _canonical_json_bytes(
    value: Any,
    *,
    limit: int | None = None,
) -> bytes:
    normalized = _normalized_json(value)
    try:
        encoded = json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError) as exc:
        raise _StrictJSONError("value cannot be canonically encoded") from exc
    if limit is not None and len(encoded) > limit:
        raise _CanonicalSizeExceeded("canonical byte limit exceeded")
    return encoded


def _freeze_json(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw_json(item) for item in value]
    return value


def _is_digest(value: Any) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _is_id(value: Any) -> bool:
    return type(value) is str and bool(value)


def _exact_object(value: Any, fields: frozenset[str]) -> bool:
    return type(value) is dict and set(value) == fields


def _issue(
    location: str,
    issue_code: str,
) -> EvidenceLineageIssue:
    if _ISSUE_LOCATION.fullmatch(location) is None:
        location = "$"
    return EvidenceLineageIssue(location, issue_code)


def _failure(
    error_code: str,
    issues: list[EvidenceLineageIssue] | tuple[EvidenceLineageIssue, ...],
) -> EvidenceLineageOutcome:
    ordered = tuple(sorted(set(issues)))[:MAX_ISSUES]
    error = {
        "schema_id": LINEAGE_ERROR_SCHEMA_ID,
        "schema_version": LINEAGE_SCHEMA_VERSION,
        "error_code": error_code,
        "message_code": _ERROR_MESSAGES[error_code],
        "issues": [item.as_dict() for item in ordered],
    }
    try:
        _canonical_json_bytes(error, limit=MAX_ERROR_CANONICAL_BYTES)
    except _StrictJSONError:
        error = {
            "schema_id": LINEAGE_ERROR_SCHEMA_ID,
            "schema_version": LINEAGE_SCHEMA_VERSION,
            "error_code": error_code,
            "message_code": _ERROR_MESSAGES[error_code],
            "issues": [],
        }
    return EvidenceLineageOutcome._from_error(error)


def canonical_node_input_fingerprint(
    graph_binding: Any,
    incoming_edges: Any,
) -> str | None:
    """Fingerprint one node's complete typed inputs without redefining owners."""

    if (
        not _exact_object(graph_binding, _GRAPH_BINDING_FIELDS)
        or not _is_id(graph_binding.get("graph_id"))
        or type(graph_binding.get("graph_generation")) is not int
        or graph_binding["graph_generation"] < 1
        or not _is_digest(graph_binding.get("graph_digest"))
        or type(incoming_edges) is not list
        or len(incoming_edges) > MAX_LINEAGE_EDGES
    ):
        return None
    normalized_edges: list[dict[str, str]] = []
    expected_fields = frozenset(
        {"edge_type", "source_node_id", "source_output_fingerprint"}
    )
    for edge in incoming_edges:
        if (
            not _exact_object(edge, expected_fields)
            or edge.get("edge_type") not in _EDGE_TYPES
            or not _is_id(edge.get("source_node_id"))
            or not _is_digest(edge.get("source_output_fingerprint"))
        ):
            return None
        normalized_edges.append(dict(edge))
    normalized_edges.sort(
        key=lambda edge: (
            edge["edge_type"],
            edge["source_node_id"],
            edge["source_output_fingerprint"],
        )
    )
    projection = {
        "graph_binding": dict(graph_binding),
        "incoming_edges": normalized_edges,
    }
    try:
        canonical = _canonical_json_bytes(
            projection,
            limit=MAX_INPUT_CANONICAL_BYTES,
        )
    except _StrictJSONError:
        return None
    return hashlib.sha256(NODE_INPUT_FINGERPRINT_DOMAIN + canonical).hexdigest()


def canonical_node_output_fingerprint(
    graph_or_candidate: Any,
    node_result: Any = None,
) -> str | None:
    """Use the owning Transition or Candidate digest without copying semantics."""

    if isinstance(graph_or_candidate, CandidateFingerprint):
        if node_result is not None:
            return None
        try:
            return graph_or_candidate.digest
        except (TypeError, ValueError, RecursionError):
            return None
    return canonical_node_result_digest(graph_or_candidate, node_result)


def _join_definition_projection(
    graph: dict[str, Any],
    join: dict[str, Any],
) -> dict[str, Any]:
    contributor_ids = set(join["requires"])
    return {
        "join_definition": {
            "id": join["id"],
            "policy": join["policy"],
            "requires": sorted(join["requires"]),
        },
        "optional_member_node_ids": sorted(
            item["id"]
            for item in graph["nodes"]
            if item["id"] in contributor_ids
            and item["classification"] == "optional"
        ),
    }


def _canonical_join_definition_fingerprint(
    graph: dict[str, Any],
    join: dict[str, Any],
) -> str | None:
    try:
        canonical = _canonical_json_bytes(
            _join_definition_projection(graph, join),
            limit=MAX_INPUT_CANONICAL_BYTES,
        )
    except (KeyError, TypeError, _StrictJSONError):
        return None
    return hashlib.sha256(
        JOIN_DEFINITION_FINGERPRINT_DOMAIN + canonical
    ).hexdigest()


def canonical_join_integration_fingerprint(
    graph: Any,
    ready_input: Any,
    join_id: Any,
) -> str | None:
    """Bind one Graph join to its owner-produced Ready decision and input digest."""

    if not _is_id(join_id):
        return None
    graph_validation = validate_graph_contract(graph)
    if not graph_validation.valid or graph_validation.semantic_digest is None:
        return None
    ready_digest = canonical_ready_input_digest(ready_input)
    if ready_digest is None:
        return None
    ready_outcome = resolve_ready_nodes(graph, ready_input)
    if ready_outcome.result is None:
        return None
    joins = [
        item
        for item in graph["joins"]
        if item["id"] == join_id
    ]
    decisions = [
        item
        for item in ready_outcome.result["join_decisions"]
        if item["join_id"] == join_id
    ]
    if len(joins) != 1 or len(decisions) != 1:
        return None
    external = [
        item
        for item in ready_input["external_join_decisions"]
        if item["join_id"] == join_id
    ]
    if len(external) > 1:
        return None
    external_refs: list[str] = []
    if external:
        authority = external[0].get("authority_ref")
        if authority is not None:
            external_refs.append(authority)
        external_refs.extend(external[0].get("evidence_refs", []))
    projection = {
        "graph_digest": graph_validation.semantic_digest,
        "join_definition": _join_definition_projection(graph, joins[0]),
        "contributor_node_ids": sorted(joins[0]["requires"]),
        "ready_input_digest": ready_digest,
        "ready_join_decision": decisions[0],
        "external_decision_refs": sorted(set(external_refs)),
    }
    try:
        canonical = _canonical_json_bytes(
            projection,
            limit=MAX_INPUT_CANONICAL_BYTES,
        )
    except _StrictJSONError:
        return None
    return hashlib.sha256(
        JOIN_INTEGRATION_FINGERPRINT_DOMAIN + canonical
    ).hexdigest()


def _shape_issue(
    issues: list[EvidenceLineageIssue],
    location: str,
) -> None:
    if len(issues) < MAX_ISSUES:
        issues.append(_issue(location, "INVALID_SHAPE"))


def _valid_string_array(
    value: Any,
    *,
    references: bool = False,
) -> bool:
    if type(value) is not list:
        return False
    for item in value:
        if not _is_id(item):
            return False
        if references and _BOUNDED_REF.fullmatch(item) is None:
            return False
    return True


def _direct_limit_exceeded(value: Any) -> bool:
    if type(value) is not dict:
        return False
    for snapshot_name in ("baseline", "candidate"):
        snapshot = value.get(snapshot_name)
        if type(snapshot) is not dict:
            continue
        stage4 = snapshot.get("stage4_bindings")
        collections = (
            (snapshot.get("lineage_nodes"), MAX_LINEAGE_NODES),
            (snapshot.get("lineage_edges"), MAX_LINEAGE_EDGES),
            (snapshot.get("join_integrations"), MAX_JOIN_INTEGRATIONS),
            (
                stage4.get("transition_bindings")
                if type(stage4) is dict
                else None,
                MAX_TRANSITION_BINDINGS,
            ),
        )
        for collection, maximum in collections:
            if type(collection) is list and len(collection) > maximum:
                return True
        joins = snapshot.get("join_integrations")
        if type(joins) is list:
            for join in joins[: MAX_JOIN_INTEGRATIONS + 1]:
                if type(join) is not dict:
                    continue
                contributors = join.get("contributor_node_ids")
                references = join.get("external_decision_refs")
                if (
                    type(contributors) is list
                    and len(contributors) > MAX_JOIN_CONTRIBUTORS
                ) or (
                    type(references) is list
                    and len(references) > MAX_EXTERNAL_DECISION_REFS
                ):
                    return True
    return False


def _validate_input_shape(value: Any) -> tuple[EvidenceLineageIssue, ...]:
    issues: list[EvidenceLineageIssue] = []
    if not _exact_object(value, _INPUT_FIELDS):
        return (_issue("$", "INVALID_SHAPE"),)
    if value.get("schema_id") != LINEAGE_INPUT_SCHEMA_ID:
        _shape_issue(issues, "$.schema_id")
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != LINEAGE_SCHEMA_VERSION
    ):
        _shape_issue(issues, "$.schema_version")
    for snapshot_name in ("baseline", "candidate"):
        location = f"$.{snapshot_name}"
        snapshot = value.get(snapshot_name)
        if not _exact_object(snapshot, _SNAPSHOT_FIELDS):
            _shape_issue(issues, location)
            continue
        binding = snapshot.get("graph_binding")
        if (
            not _exact_object(binding, _GRAPH_BINDING_FIELDS)
            or not _is_id(binding.get("graph_id"))
            or type(binding.get("graph_generation")) is not int
            or binding.get("graph_generation", 0) < 1
            or not _is_digest(binding.get("graph_digest"))
        ):
            _shape_issue(issues, f"{location}.graph_binding")
        stage4 = snapshot.get("stage4_bindings")
        if not _exact_object(stage4, _STAGE4_FIELDS):
            _shape_issue(issues, f"{location}.stage4_bindings")
        else:
            if not _is_digest(stage4.get("ready_input_digest")):
                _shape_issue(
                    issues,
                    f"{location}.stage4_bindings.ready_input_digest",
                )
            transitions = stage4.get("transition_bindings")
            if type(transitions) is not list:
                _shape_issue(
                    issues,
                    f"{location}.stage4_bindings.transition_bindings",
                )
            else:
                for index, item in enumerate(transitions):
                    if (
                        not _exact_object(item, _TRANSITION_FIELDS)
                        or not _is_id(item.get("node_id"))
                        or not _is_digest(item.get("transition_input_digest"))
                        or not _is_digest(item.get("node_result_digest"))
                    ):
                        _shape_issue(
                            issues,
                            f"{location}.stage4_bindings.transition_bindings[{index}]",
                        )
        nodes = snapshot.get("lineage_nodes")
        if type(nodes) is not list or not nodes:
            _shape_issue(issues, f"{location}.lineage_nodes")
        elif len(nodes) <= MAX_LINEAGE_NODES:
            for index, item in enumerate(nodes):
                if (
                    not _exact_object(item, _NODE_FIELDS)
                    or not _is_id(item.get("lineage_node_id"))
                    or item.get("owner_kind") not in _OWNER_KINDS
                    or not _is_id(item.get("owner_id"))
                    or not _is_digest(item.get("input_fingerprint"))
                    or not _is_digest(item.get("output_fingerprint"))
                ):
                    _shape_issue(
                        issues,
                        f"{location}.lineage_nodes[{index}]",
                    )
        edges = snapshot.get("lineage_edges")
        if type(edges) is not list or not edges:
            _shape_issue(issues, f"{location}.lineage_edges")
        elif len(edges) <= MAX_LINEAGE_EDGES:
            for index, item in enumerate(edges):
                if (
                    not _exact_object(item, _EDGE_FIELDS)
                    or not _is_id(item.get("source_node_id"))
                    or not _is_id(item.get("target_node_id"))
                    or item.get("edge_type") not in _EDGE_TYPES
                    or not _is_digest(item.get("source_output_fingerprint"))
                    or not _is_digest(item.get("target_input_fingerprint"))
                ):
                    _shape_issue(
                        issues,
                        f"{location}.lineage_edges[{index}]",
                    )
        joins = snapshot.get("join_integrations")
        if type(joins) is not list:
            _shape_issue(issues, f"{location}.join_integrations")
        elif len(joins) <= MAX_JOIN_INTEGRATIONS:
            for index, item in enumerate(joins):
                join_location = f"{location}.join_integrations[{index}]"
                valid = (
                    _exact_object(item, _JOIN_FIELDS)
                    and _is_id(item.get("join_id"))
                    and item.get("policy") in _JOIN_POLICIES
                    and _is_digest(item.get("definition_fingerprint"))
                    and _valid_string_array(item.get("contributor_node_ids"))
                    and bool(item.get("contributor_node_ids"))
                    and _is_digest(item.get("ready_input_digest"))
                    and _valid_string_array(
                        item.get("external_decision_refs"),
                        references=True,
                    )
                )
                if valid:
                    refs = item["external_decision_refs"]
                    if item["policy"] in _EXTERNAL_JOIN_POLICIES:
                        valid = bool(refs)
                    else:
                        valid = not refs
                if not valid:
                    _shape_issue(issues, join_location)
        if not _is_id(snapshot.get("final_evidence_node_id")):
            _shape_issue(issues, f"{location}.final_evidence_node_id")
    return tuple(sorted(set(issues)))


def _duplicate_identity(values: list[Any], field: str) -> bool:
    identities = [
        value.get(field)
        for value in values
        if type(value) is dict and _is_id(value.get(field))
    ]
    return len(identities) != len(set(identities))


def _snapshot_semantic_issues(
    snapshot: dict[str, Any],
    graph: dict[str, Any],
    snapshot_name: str,
    *,
    current: bool,
) -> tuple[EvidenceLineageIssue, ...]:
    issues: list[EvidenceLineageIssue] = []
    prefix = f"$.{snapshot_name}"
    nodes_list = snapshot["lineage_nodes"]
    edges = snapshot["lineage_edges"]
    joins_list = snapshot["join_integrations"]
    transitions_list = snapshot["stage4_bindings"]["transition_bindings"]

    if _duplicate_identity(nodes_list, "lineage_node_id"):
        issues.append(_issue(f"{prefix}.lineage_nodes", "DUPLICATE_IDENTITY"))
    if _duplicate_identity(transitions_list, "node_id"):
        issues.append(
            _issue(
                f"{prefix}.stage4_bindings.transition_bindings",
                "DUPLICATE_IDENTITY",
            )
        )
    if _duplicate_identity(joins_list, "join_id"):
        issues.append(
            _issue(f"{prefix}.join_integrations", "DUPLICATE_IDENTITY")
        )
    edge_identities = [
        (
            edge["source_node_id"],
            edge["target_node_id"],
            edge["edge_type"],
            edge["source_output_fingerprint"],
            edge["target_input_fingerprint"],
        )
        for edge in edges
    ]
    if len(edge_identities) != len(set(edge_identities)):
        issues.append(_issue(f"{prefix}.lineage_edges", "DUPLICATE_IDENTITY"))
    for index, join in enumerate(joins_list):
        if (
            len(join["contributor_node_ids"])
            != len(set(join["contributor_node_ids"]))
            or len(join["external_decision_refs"])
            != len(set(join["external_decision_refs"]))
        ):
            issues.append(
                _issue(
                    f"{prefix}.join_integrations[{index}]",
                    "DUPLICATE_IDENTITY",
                )
            )
    if issues:
        return tuple(sorted(set(issues)))

    nodes = {item["lineage_node_id"]: item for item in nodes_list}
    transitions = {item["node_id"]: item for item in transitions_list}
    joins = {item["join_id"]: item for item in joins_list}
    graph_nodes = {item["id"]: item for item in graph["nodes"]}
    graph_joins = {item["id"]: item for item in graph["joins"]}

    for index, edge in enumerate(edges):
        location = f"{prefix}.lineage_edges[{index}]"
        source = nodes.get(edge["source_node_id"])
        target = nodes.get(edge["target_node_id"])
        if source is None or target is None:
            issues.append(_issue(location, "REFERENCE_NOT_FOUND"))
            continue
        if source["owner_kind"] != _EDGE_OWNER[edge["edge_type"]]:
            issues.append(_issue(location, "EDGE_OWNER_MISMATCH"))
        if edge["source_output_fingerprint"] != source["output_fingerprint"]:
            issues.append(_issue(location, "SOURCE_FINGERPRINT_MISMATCH"))
        if edge["target_input_fingerprint"] != target["input_fingerprint"]:
            issues.append(_issue(location, "TARGET_FINGERPRINT_MISMATCH"))

    final_id = snapshot["final_evidence_node_id"]
    final_node = nodes.get(final_id)
    if final_node is None or final_node["owner_kind"] != "EVIDENCE":
        issues.append(
            _issue(f"{prefix}.final_evidence_node_id", "FINAL_EVIDENCE_INVALID")
        )
    candidate_edges = [
        edge for edge in edges if edge["edge_type"] == "CANDIDATE"
    ]
    if (
        len(candidate_edges) != 1
        or candidate_edges[0]["target_node_id"] != final_id
        or nodes.get(candidate_edges[0]["source_node_id"], {}).get("owner_kind")
        != "CANDIDATE"
    ):
        issues.append(
            _issue(f"{prefix}.lineage_edges", "FINAL_CANDIDATE_INVALID")
        )

    graph_lineage = [
        item for item in nodes_list if item["owner_kind"] == "GRAPH_NODE"
    ]
    join_lineage = [
        item for item in nodes_list if item["owner_kind"] == "JOIN"
    ]
    if set(transitions) != {item["owner_id"] for item in graph_lineage}:
        issues.append(
            _issue(
                f"{prefix}.stage4_bindings.transition_bindings",
                "TRANSITION_BINDING_MISMATCH",
            )
        )
    for item in graph_lineage:
        transition = transitions.get(item["owner_id"])
        if (
            transition is None
            or transition["node_result_digest"] != item["output_fingerprint"]
        ):
            issues.append(
                _issue(
                    f"{prefix}.stage4_bindings.transition_bindings",
                    "NODE_RESULT_BINDING_MISMATCH",
                )
            )
        if current and item["owner_id"] not in graph_nodes:
            issues.append(
                _issue(f"{prefix}.lineage_nodes", "GRAPH_NODE_NOT_FOUND")
            )
    if current:
        graph_node_ids = set(graph_nodes)
        graph_lineage_ids = [item["owner_id"] for item in graph_lineage]
        if (
            len(graph_lineage_ids) != len(graph_node_ids)
            or set(graph_lineage_ids) != graph_node_ids
        ):
            issues.append(
                _issue(f"{prefix}.lineage_nodes", "GRAPH_NODE_NOT_FOUND")
            )
        if (
            len(transitions_list) != len(graph_node_ids)
            or set(transitions) != graph_node_ids
        ):
            issues.append(
                _issue(
                    f"{prefix}.stage4_bindings.transition_bindings",
                    "TRANSITION_BINDING_MISMATCH",
                )
            )
        graph_join_ids = set(graph_joins)
        join_lineage_ids = [item["owner_id"] for item in join_lineage]
        if (
            len(join_lineage_ids) != len(graph_join_ids)
            or set(join_lineage_ids) != graph_join_ids
            or len(joins_list) != len(graph_join_ids)
            or set(joins) != graph_join_ids
        ):
            issues.append(
                _issue(
                    f"{prefix}.join_integrations",
                    "JOIN_DEFINITION_MISMATCH",
                )
            )

    ready_digest = snapshot["stage4_bindings"]["ready_input_digest"]
    for index, join in enumerate(joins_list):
        join_location = f"{prefix}.join_integrations[{index}]"
        if join["ready_input_digest"] != ready_digest:
            issues.append(_issue(join_location, "READY_BINDING_MISMATCH"))
        owner = nodes.get(join["join_id"])
        if (
            owner is None
            or owner["owner_kind"] != "JOIN"
            or owner["owner_id"] != join["join_id"]
        ):
            issues.append(_issue(join_location, "JOIN_OWNER_MISMATCH"))
        contributors = join["contributor_node_ids"]
        if any(
            nodes.get(node_id, {}).get("owner_kind") != "GRAPH_NODE"
            for node_id in contributors
        ):
            issues.append(_issue(join_location, "JOIN_CONTRIBUTOR_INVALID"))
        if current:
            graph_join = graph_joins.get(join["join_id"])
            if (
                graph_join is None
                or graph_join["policy"] != join["policy"]
                or sorted(graph_join["requires"]) != sorted(contributors)
                or join["definition_fingerprint"]
                != _canonical_join_definition_fingerprint(graph, graph_join)
            ):
                issues.append(_issue(join_location, "JOIN_DEFINITION_MISMATCH"))

    incoming: dict[str, list[dict[str, str]]] = {
        node_id: [] for node_id in nodes
    }
    for edge in edges:
        if edge["target_node_id"] not in incoming:
            continue
        incoming[edge["target_node_id"]].append(
            {
                "edge_type": edge["edge_type"],
                "source_node_id": edge["source_node_id"],
                "source_output_fingerprint": edge[
                    "source_output_fingerprint"
                ],
            }
        )
    for node_id, node in nodes.items():
        expected = canonical_node_input_fingerprint(
            snapshot["graph_binding"],
            incoming[node_id],
        )
        if expected != node["input_fingerprint"]:
            issues.append(
                _issue(f"{prefix}.lineage_nodes", "INPUT_FINGERPRINT_MISMATCH")
            )
            break
    return tuple(sorted(set(issues)))[:MAX_ISSUES]


def _normalized_join_record(join: dict[str, Any]) -> dict[str, Any]:
    return {
        **join,
        "contributor_node_ids": sorted(join["contributor_node_ids"]),
        "external_decision_refs": sorted(join["external_decision_refs"]),
    }


def _changed_incoming_edges(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, set[str]]:
    changed: dict[str, set[str]] = {}
    baseline_nodes = {
        item["lineage_node_id"]: item
        for item in baseline["lineage_nodes"]
    }
    candidate_nodes = {
        item["lineage_node_id"]: item
        for item in candidate["lineage_nodes"]
    }

    def keyed(
        snapshot: dict[str, Any],
    ) -> dict[tuple[str, str, str], dict[str, Any]]:
        return {
            (
                edge["source_node_id"],
                edge["target_node_id"],
                edge["edge_type"],
            ): edge
            for edge in snapshot["lineage_edges"]
        }

    old_edges = keyed(baseline)
    new_edges = keyed(candidate)
    for identity in sorted(set(old_edges) | set(new_edges)):
        old = old_edges.get(identity)
        new = new_edges.get(identity)
        if (
            old is not None
            and new is not None
            and old["source_output_fingerprint"]
            == new["source_output_fingerprint"]
        ):
            continue
        source_id, target_id, edge_type = identity
        target = target_id if target_id in candidate_nodes else None
        if target is not None:
            changed.setdefault(target, set()).add(edge_type)
        if edge_type == "PATH" and old is not None and new is not None:
            old_source = baseline_nodes.get(source_id)
            new_source = candidate_nodes.get(source_id)
            if old_source is not None and new_source is not None:
                paths_overlap(
                    old_source["owner_id"],
                    new_source["owner_id"],
                    "posix",
                )
    return changed


def _propagation_adjacency(
    graph: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    current_graph: bool,
) -> dict[str, set[str]]:
    nodes = {
        item["lineage_node_id"]: item
        for item in snapshot["lineage_nodes"]
    }
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    for edge in snapshot["lineage_edges"]:
        adjacency[edge["source_node_id"]].add(edge["target_node_id"])

    by_graph_owner = {
        item["owner_id"]: item["lineage_node_id"]
        for item in snapshot["lineage_nodes"]
        if item["owner_kind"] == "GRAPH_NODE"
    }
    join_owners = {
        item["owner_id"]: item["lineage_node_id"]
        for item in snapshot["lineage_nodes"]
        if item["owner_kind"] == "JOIN"
    }
    if current_graph:
        graph_nodes = graph["nodes"]
        joins = (
            {
                "join_id": item["id"],
                "contributor_node_ids": item["requires"],
            }
            for item in graph["joins"]
        )
    else:
        graph_nodes = ()
        joins = snapshot["join_integrations"]
    for graph_node in graph_nodes:
        target = by_graph_owner.get(graph_node["id"])
        if target is None:
            continue
        for predecessor_id in graph_node["depends_on"]:
            predecessor = by_graph_owner.get(predecessor_id)
            if predecessor is not None:
                adjacency[predecessor].add(target)
    for join in joins:
        target = join_owners.get(join["join_id"])
        if target is None:
            continue
        for contributor_id in join["contributor_node_ids"]:
            contributor = by_graph_owner.get(contributor_id)
            if contributor is not None:
                adjacency[contributor].add(target)
    return adjacency


def _topological_order(adjacency: dict[str, set[str]]) -> list[str]:
    indegree = {node_id: 0 for node_id in adjacency}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1
    ready = sorted(
        node_id for node_id, degree in indegree.items() if degree == 0
    )
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for target in sorted(adjacency[current]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    return order


def _primary_invalid_type(values: set[str]) -> str | None:
    for edge_type in _INVALID_EDGE_TYPES:
        if edge_type in values:
            return edge_type
    return None


def _ordered_targeted_types(values: set[str]) -> list[str]:
    return [
        edge_type
        for edge_type in _TARGETED_EDGE_TYPES
        if edge_type in values
    ]


def _classify(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    adjacency: dict[str, set[str]],
    order: list[str],
) -> dict[str, dict[str, Any]]:
    old_nodes = {
        item["lineage_node_id"]: item
        for item in baseline["lineage_nodes"]
    }
    new_nodes = {
        item["lineage_node_id"]: item
        for item in candidate["lineage_nodes"]
    }
    graph_identity_changed = any(
        baseline["graph_binding"][field] != candidate["graph_binding"][field]
        for field in ("graph_id", "graph_generation", "graph_digest")
    )
    if graph_identity_changed:
        return {
            node_id: {
                "disposition": "INVALIDATE",
                "input_fingerprint": new_nodes[node_id]["input_fingerprint"],
                "output_fingerprint": new_nodes[node_id]["output_fingerprint"],
                "changed_edge_types": [],
                "reason_codes": ["GRAPH_IDENTITY_CHANGED"],
            }
            for node_id in sorted(new_nodes)
        }

    direct = _changed_incoming_edges(baseline, candidate)

    for node_id, node in new_nodes.items():
        old = old_nodes.get(node_id)
        if old == node:
            continue
        owner_changed = (
            old is None
            or old["owner_kind"] != node["owner_kind"]
            or old["owner_id"] != node["owner_id"]
            or old["output_fingerprint"] != node["output_fingerprint"]
        )
        if owner_changed:
            owner_type = _OWNER_EDGE_TYPE.get(node["owner_kind"])
            if owner_type is not None:
                direct.setdefault(node_id, set()).add(owner_type)
            elif node_id == candidate["final_evidence_node_id"]:
                direct.setdefault(node_id, set()).add("CANDIDATE")
            else:
                direct.setdefault(node_id, set()).add("NODE_OUTPUT")
        elif (
            node["input_fingerprint"] != old["input_fingerprint"]
            and node_id not in direct
        ):
            direct.setdefault(node_id, set()).add("NODE_OUTPUT")

    old_transitions = {
        item["node_id"]: item
        for item in baseline["stage4_bindings"]["transition_bindings"]
    }
    new_transitions = {
        item["node_id"]: item
        for item in candidate["stage4_bindings"]["transition_bindings"]
    }
    graph_lineage = {
        item["owner_id"]: item["lineage_node_id"]
        for item in candidate["lineage_nodes"]
        if item["owner_kind"] == "GRAPH_NODE"
    }
    for owner_id in set(old_transitions) | set(new_transitions):
        if old_transitions.get(owner_id) != new_transitions.get(owner_id):
            lineage_id = graph_lineage.get(owner_id)
            if lineage_id is not None:
                direct.setdefault(lineage_id, set()).add("NODE_OUTPUT")
    ready_input_changed = (
        baseline["stage4_bindings"]["ready_input_digest"]
        != candidate["stage4_bindings"]["ready_input_digest"]
    )
    if ready_input_changed:
        for lineage_id in graph_lineage.values():
            direct.setdefault(lineage_id, set()).add("NODE_OUTPUT")

    old_joins = {
        item["join_id"]: _normalized_join_record(item)
        for item in baseline["join_integrations"]
    }
    new_joins = {
        item["join_id"]: _normalized_join_record(item)
        for item in candidate["join_integrations"]
    }
    join_lineage = {
        item["owner_id"]: item["lineage_node_id"]
        for item in candidate["lineage_nodes"]
        if item["owner_kind"] == "JOIN"
    }
    if ready_input_changed:
        for lineage_id in join_lineage.values():
            direct.setdefault(lineage_id, set()).add("JOIN_INTEGRATION")
    for join_id in set(old_joins) | set(new_joins):
        if old_joins.get(join_id) != new_joins.get(join_id):
            lineage_id = join_lineage.get(join_id)
            if lineage_id is not None:
                direct.setdefault(lineage_id, set()).add("JOIN_INTEGRATION")

    inherited_invalid: dict[str, set[str]] = {
        node_id: set() for node_id in new_nodes
    }
    inherited_targeted: dict[str, set[str]] = {
        node_id: set() for node_id in new_nodes
    }
    decisions: dict[str, dict[str, Any]] = {}

    for node_id in order:
        node = new_nodes[node_id]
        local = direct.get(node_id, set())
        invalid_types = (local & _INVALID_EDGE_SET) | inherited_invalid[node_id]
        targeted_types = (
            local & _TARGETED_EDGE_SET
        ) | inherited_targeted[node_id]
        if invalid_types:
            primary = _primary_invalid_type(invalid_types)
            assert primary is not None
            decision = {
                "disposition": "INVALIDATE",
                "input_fingerprint": node["input_fingerprint"],
                "output_fingerprint": node["output_fingerprint"],
                "changed_edge_types": [primary],
                "reason_codes": [_INVALID_REASON[primary]],
            }
            propagated_invalid = invalid_types
            propagated_targeted = set()
        elif targeted_types:
            decision = {
                "disposition": "REVERIFY_TARGETED",
                "input_fingerprint": node["input_fingerprint"],
                "output_fingerprint": node["output_fingerprint"],
                "changed_edge_types": _ordered_targeted_types(targeted_types),
                "reason_codes": [
                    "DIRECT_INPUT_CHANGED"
                    if local
                    else "TRANSITIVE_INPUT_CHANGED"
                ],
            }
            propagated_invalid = set()
            propagated_targeted = targeted_types
        else:
            decision = {
                "disposition": "REUSE",
                "input_fingerprint": node["input_fingerprint"],
                "output_fingerprint": node["output_fingerprint"],
                "changed_edge_types": [],
                "reason_codes": ["FINGERPRINTS_MATCH"],
            }
            propagated_invalid = set()
            propagated_targeted = set()
        decisions[node_id] = decision
        for target in adjacency[node_id]:
            inherited_invalid[target].update(propagated_invalid)
            inherited_targeted[target].update(propagated_targeted)
    return {node_id: decisions[node_id] for node_id in sorted(decisions)}


def resolve_evidence_lineage(
    graph: Any,
    lineage_input: Any,
) -> EvidenceLineageOutcome:
    """Classify two complete Stage 5A snapshots without side effects."""

    try:
        input_snapshot = _normalized_json(lineage_input)
        _canonical_json_bytes(
            input_snapshot,
            limit=MAX_INPUT_CANONICAL_BYTES,
        )
    except _CanonicalSizeExceeded:
        return _failure(
            "INPUT_TOO_LARGE",
            [_issue("$", "CANONICAL_SIZE_EXCEEDED")],
        )
    except (_StrictJSONError, RecursionError):
        return _failure(
            "INPUT_INVALID",
            [_issue("$", "STRICT_JSON_REQUIRED")],
        )

    if _direct_limit_exceeded(input_snapshot):
        return _failure(
            "LINEAGE_LIMIT_EXCEEDED",
            [_issue("$", "STRUCTURAL_LIMIT_EXCEEDED")],
        )
    shape_issues = _validate_input_shape(input_snapshot)
    if shape_issues:
        return _failure("INPUT_INVALID", shape_issues)

    try:
        graph_snapshot = _normalized_json(graph)
        graph_validation = validate_graph_contract(graph_snapshot)
    except (KeyError, TypeError, ValueError, RecursionError, _StrictJSONError):
        return _failure(
            "INPUT_INVALID",
            [_issue("$", "GRAPH_INVALID")],
        )
    if not graph_validation.valid or graph_validation.semantic_digest is None:
        return _failure(
            "INPUT_INVALID",
            [_issue("$", "GRAPH_INVALID")],
        )
    graph_digest = graph_validation.semantic_digest

    candidate = input_snapshot["candidate"]
    candidate_binding = candidate["graph_binding"]
    if (
        candidate_binding["graph_id"] != graph_snapshot["graph_id"]
        or candidate_binding["graph_generation"] != graph_snapshot["generation"]
        or candidate_binding["graph_digest"] != graph_digest
    ):
        return _failure(
            "GRAPH_BINDING_MISMATCH",
            [_issue("$.candidate.graph_binding", "GRAPH_BINDING_MISMATCH")],
        )

    same_graph_digest = (
        input_snapshot["baseline"]["graph_binding"]["graph_digest"]
        == candidate_binding["graph_digest"]
    )
    semantic_issues: list[EvidenceLineageIssue] = []
    for name in ("baseline", "candidate"):
        semantic_issues.extend(
            _snapshot_semantic_issues(
                input_snapshot[name],
                graph_snapshot,
                name,
                current=name == "candidate" or same_graph_digest,
            )
        )
    if semantic_issues:
        return _failure("LINEAGE_INVALID", semantic_issues)

    propagation_orders: dict[
        str,
        tuple[dict[str, set[str]], list[str]],
    ] = {}
    for name in ("baseline", "candidate"):
        adjacency = _propagation_adjacency(
            graph_snapshot,
            input_snapshot[name],
            current_graph=name == "candidate" or same_graph_digest,
        )
        order = _topological_order(adjacency)
        if len(order) != len(adjacency):
            return _failure(
                "LINEAGE_CYCLE",
                [_issue(f"$.{name}.lineage_edges", "LINEAGE_CYCLE")],
            )
        propagation_orders[name] = (adjacency, order)

    candidate_adjacency, candidate_order = propagation_orders["candidate"]
    decisions = _classify(
        input_snapshot["baseline"],
        candidate,
        candidate_adjacency,
        candidate_order,
    )
    result = {
        "schema_id": LINEAGE_RESULT_SCHEMA_ID,
        "schema_version": LINEAGE_SCHEMA_VERSION,
        "graph_id": candidate_binding["graph_id"],
        "graph_generation": candidate_binding["graph_generation"],
        "graph_digest": candidate_binding["graph_digest"],
        "decisions": decisions,
        "final_evidence_node_id": candidate["final_evidence_node_id"],
    }
    try:
        _canonical_json_bytes(result, limit=MAX_RESULT_CANONICAL_BYTES)
    except _StrictJSONError:
        return _failure(
            "RESULT_TOO_LARGE",
            [_issue("$", "RESULT_BYTE_BUDGET_EXCEEDED")],
        )
    return EvidenceLineageOutcome._from_result(result)


__all__ = [
    "ChangeEvent",
    "EvidenceAssessment",
    "EvidenceFingerprint",
    "EvidenceLineageIssue",
    "EvidenceLineageOutcome",
    "assess_evidence",
    "canonical_join_integration_fingerprint",
    "canonical_node_input_fingerprint",
    "canonical_node_output_fingerprint",
    "resolve_evidence_lineage",
]
