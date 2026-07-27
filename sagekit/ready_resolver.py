"""Pure, bounded Ready Resolution Contract v1 resolver.

The resolver consumes an already supplied Graph and observation input.  It does
not read or write runtime state, acquire resources, execute nodes, or mutate
either argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from .graph_contract import validate_graph_contract


INPUT_SCHEMA_ID = "urn:sagekit:ready-resolution:v1:input"
RESULT_SCHEMA_ID = "urn:sagekit:ready-resolution:v1:result"
ERROR_SCHEMA_ID = "urn:sagekit:ready-resolution:v1:error"
SCHEMA_VERSION = 1
INPUT_DIGEST_DOMAIN = b"sagekit-ready-resolution-input-v1\0"

MAX_INPUT_CANONICAL_BYTES = 16 * 1024 * 1024
MAX_GRAPH_CANONICAL_BYTES = 8 * 1024 * 1024
MAX_RESULT_CANONICAL_BYTES = 16 * 1024 * 1024
MAX_ERROR_CANONICAL_BYTES = 1024 * 1024
MAX_ISSUES = 100
MAX_GRAPH_NODES = 10000
MAX_GRAPH_JOINS = 10000
MAX_NODE_DEPENDENCIES = 10000
MAX_NODE_RESOURCES = 10000
MAX_JOIN_REQUIRES = 10000
MAX_BLOCKING_NODE_IDS = 10000
MAX_BLOCKING_RESOURCE_IDS = 10000
MAX_BLOCKING_REFS = 101

_INPUT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "graph_digest",
        "graph_generation",
        "node_states",
        "resource_availability",
        "external_join_decisions",
    }
)
_NODE_STATE_FIELDS = frozenset(
    {"node_id", "status", "result_digest", "evidence_refs"}
)
_RESOURCE_FIELDS = frozenset(
    {"resource_id", "availability", "reason_code", "evidence_refs"}
)
_EXTERNAL_FIELDS = frozenset(
    {"join_id", "decision", "authority_ref", "evidence_refs"}
)
_NODE_STATUSES = frozenset(
    {
        "PENDING",
        "READY",
        "RUNNING",
        "WAITING_RESOURCE",
        "SUCCEEDED",
        "NO_ACTION_REQUIRED",
        "FAILED",
        "NEEDS_CORRECTION",
        "HANDOFF",
        "BLOCKED",
        "CANCELLED",
        "DONE_WITH_CONCERNS",
    }
)
_RESULT_REQUIRED_STATUSES = frozenset(
    {
        "SUCCEEDED",
        "NO_ACTION_REQUIRED",
        "FAILED",
        "NEEDS_CORRECTION",
        "DONE_WITH_CONCERNS",
    }
)
_SUCCESS_STATUSES = frozenset({"SUCCEEDED", "NO_ACTION_REQUIRED"})
_JOIN_FAILURE_STATUSES = frozenset(
    {
        "FAILED",
        "NEEDS_CORRECTION",
        "DONE_WITH_CONCERNS",
        "BLOCKED",
        "CANCELLED",
    }
)
_RESOURCE_REASON = {
    "AVAILABLE": "RESOURCE_AVAILABLE",
    "BUSY": "RESOURCE_BUSY",
    "UNAVAILABLE": "RESOURCE_UNAVAILABLE",
    "UNKNOWN": "RESOURCE_UNKNOWN",
}
_EXTERNAL_DECISIONS = frozenset({"PENDING", "SATISFIED", "REJECTED"})
_EXTERNAL_JOIN_POLICIES = frozenset({"manual-gate", "corrective-join"})
_AUTOMATIC_JOIN_POLICIES = frozenset(
    {"all-required", "required-plus-optional", "first-success"}
)
_ERROR_CODES = frozenset(
    {
        "REQUIRED_INPUT_INVALID",
        "GRAPH_INVALID",
        "GRAPH_BINDING_MISMATCH",
        "INPUT_TOO_LARGE",
        "GRAPH_TOO_LARGE",
        "RESOLUTION_LIMIT_EXCEEDED",
        "RESULT_TOO_LARGE",
    }
)
_NODE_DISPOSITIONS = frozenset(
    {
        "READY",
        "WAITING_DEPENDENCY",
        "WAITING_RESOURCE",
        "IN_PROGRESS",
        "NEEDS_CORRECTION",
        "HANDOFF_REQUIRED",
        "BLOCKED",
        "COMPLETED",
        "CANCELLED",
    }
)
_JOIN_DISPOSITIONS = frozenset(
    {
        "SATISFIED",
        "WAITING_NODE",
        "REQUIRES_EXTERNAL_DECISION",
        "REJECTED",
        "BLOCKED",
    }
)
_GRAPH_DISPOSITIONS = frozenset(
    {
        "READY",
        "IN_PROGRESS",
        "WAITING",
        "NEEDS_CORRECTION",
        "HANDOFF_REQUIRED",
        "BLOCKED",
        "COMPLETED",
    }
)
_REASON_ORDER = (
    "DEPENDENCIES_SATISFIED",
    "DEPENDENCY_PENDING",
    "DEPENDENCY_FAILED",
    "RESOURCE_AVAILABLE",
    "RESOURCE_BUSY",
    "RESOURCE_UNAVAILABLE",
    "RESOURCE_UNKNOWN",
    "NODE_RUNNING",
    "NODE_SUCCEEDED",
    "NODE_NO_ACTION_REQUIRED",
    "NODE_FAILED",
    "NODE_NEEDS_CORRECTION",
    "NODE_HANDOFF",
    "NODE_BLOCKED",
    "NODE_CANCELLED",
    "NODE_DONE_WITH_CONCERNS",
    "JOIN_SATISFIED",
    "JOIN_NODE_PENDING",
    "JOIN_NODE_FAILED",
    "EXTERNAL_DECISION_MISSING",
    "EXTERNAL_DECISION_REJECTED",
)
_REASON_RANK = {value: index for index, value in enumerate(_REASON_ORDER)}
_REASON_CODES = frozenset(_REASON_ORDER)
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,255}$")


@dataclass(frozen=True, order=True)
class ReadyResolutionIssue:
    """Bounded machine-readable validation issue."""

    path: str
    code: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code}


class ReadyResolutionOutcome:
    """Resolver-created immutable snapshot of one complete Result or Error."""

    __slots__ = ("_result_snapshot", "_error_snapshot")

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise ValueError("ReadyResolutionOutcome is resolver-created")

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("ReadyResolutionOutcome is immutable")

    def __delattr__(self, _name: str) -> None:
        raise AttributeError("ReadyResolutionOutcome is immutable")

    @classmethod
    def _from_result(
        cls,
        graph: Any,
        resolution_input: Any = None,
        result: Any = None,
    ) -> ReadyResolutionOutcome:
        if (
            type(graph) is not dict
            or type(resolution_input) is not dict
            or type(result) is not dict
        ):
            raise ValueError("successful outcome requires Graph, Input, and Result")
        try:
            graph_snapshot = _normalized_json_value(graph)
            input_snapshot = _normalized_json_value(resolution_input)
            result_snapshot = _normalized_json_value(result)
        except (_CanonicalJSONError, RecursionError) as exc:
            raise ValueError("successful outcome source is not strict JSON") from exc

        expected = _resolve_ready_payload(graph_snapshot, input_snapshot)
        if isinstance(expected, ReadyResolutionOutcome):
            raise ValueError("successful outcome source does not resolve")

        graph_validation = validate_graph_contract(graph_snapshot)
        input_digest = canonical_ready_input_digest(input_snapshot)
        if (
            not graph_validation.valid
            or graph_validation.semantic_digest is None
            or input_digest is None
            or result_snapshot.get("graph_digest")
            != graph_validation.semantic_digest
            or result_snapshot.get("input_digest") != input_digest
            or not _result_is_structurally_valid(result_snapshot)
            or result_snapshot != expected
        ):
            raise ValueError("result does not match its validated source")

        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", _freeze_json(result_snapshot))
        object.__setattr__(instance, "_error_snapshot", None)
        return instance

    @classmethod
    def _from_error(cls, error: Mapping[str, Any]) -> ReadyResolutionOutcome:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", None)
        object.__setattr__(instance, "_error_snapshot", _freeze_json(error))
        return instance

    @classmethod
    def _from_validated_source(
        cls,
        graph: Any,
        resolution_input: Any,
        result: Mapping[str, Any],
    ) -> ReadyResolutionOutcome:
        return cls._from_result(graph, resolution_input, result)

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
        if not isinstance(other, ReadyResolutionOutcome):
            return NotImplemented
        return (
            self._result_snapshot == other._result_snapshot
            and self._error_snapshot == other._error_snapshot
        )


def _freeze_json(value: Any) -> Any:
    if value is None:
        return None
    if type(value) is dict:
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw_json(item) for item in value]
    return value


class _CanonicalJSONError(ValueError):
    pass


class _InvalidUnicodeScalar(_CanonicalJSONError):
    pass


class _CanonicalSizeExceeded(_CanonicalJSONError):
    pass


class _IssueCollector:
    __slots__ = ("_issues",)

    def __init__(self) -> None:
        self._issues: set[ReadyResolutionIssue] = set()

    def add(self, path: str, code: str) -> None:
        if len(self._issues) < MAX_ISSUES:
            self._issues.add(ReadyResolutionIssue(path, code))

    def result(self) -> tuple[ReadyResolutionIssue, ...]:
        return tuple(sorted(self._issues))[:MAX_ISSUES]


def _canonical_json_bytes(value: Any, *, limit: int | None = None) -> bytes:
    output = bytearray()
    active: set[int] = set()

    def emit(data: bytes) -> None:
        if limit is not None and len(data) > limit - len(output):
            raise _CanonicalSizeExceeded
        output.extend(data)

    def emit_string(value: str) -> None:
        value = _normalized_string(value)
        emit(b'"')
        index = 0
        while index < len(value):
            codepoint = ord(value[index])
            if value[index] == '"':
                emit(b'\\"')
            elif value[index] == "\\":
                emit(b"\\\\")
            elif codepoint == 0x08:
                emit(b"\\b")
            elif codepoint == 0x09:
                emit(b"\\t")
            elif codepoint == 0x0A:
                emit(b"\\n")
            elif codepoint == 0x0C:
                emit(b"\\f")
            elif codepoint == 0x0D:
                emit(b"\\r")
            elif codepoint <= 0x1F:
                emit(f"\\u{codepoint:04x}".encode("ascii"))
            else:
                emit(value[index].encode("utf-8"))
            index += 1
        emit(b'"')

    def encode(item: Any) -> None:
        if item is None:
            emit(b"null")
        elif item is True:
            emit(b"true")
        elif item is False:
            emit(b"false")
        elif (integer := _mathematical_integer(item)) is not None:
            if limit is not None:
                decimal_capacity = limit - len(output) - int(integer < 0)
                bit_length = integer.bit_length()
                # 2**10 > 10**3, so this rejects only values guaranteed not to fit.
                if decimal_capacity <= 0 or (
                    bit_length
                    and 3 * (bit_length - 1) >= 10 * decimal_capacity
                ):
                    raise _CanonicalSizeExceeded
            emit(_integer_text(integer).encode("ascii"))
        elif type(item) is float:
            raise _CanonicalJSONError("only finite mathematical integers are admitted")
        elif type(item) is str:
            emit_string(item)
        elif type(item) is list:
            identity = id(item)
            if identity in active:
                raise _CanonicalJSONError("cyclic array")
            active.add(identity)
            try:
                emit(b"[")
                for index, child in enumerate(item):
                    if index:
                        emit(b",")
                    encode(child)
                emit(b"]")
            finally:
                active.remove(identity)
        elif type(item) is dict:
            if any(type(key) is not str for key in item):
                raise _CanonicalJSONError("object keys must be strings")
            identity = id(item)
            if identity in active:
                raise _CanonicalJSONError("cyclic object")
            active.add(identity)
            try:
                emit(b"{")
                normalized_items: dict[str, Any] = {}
                for key, child in item.items():
                    normalized_key = _normalized_string(key)
                    if normalized_key in normalized_items:
                        raise _CanonicalJSONError(
                            "duplicate object key after Unicode scalar normalization"
                        )
                    normalized_items[normalized_key] = child
                for index, key in enumerate(sorted(normalized_items)):
                    if index:
                        emit(b",")
                    emit_string(key)
                    emit(b":")
                    encode(normalized_items[key])
                emit(b"}")
            finally:
                active.remove(identity)
        else:
            raise _CanonicalJSONError("value is not strict JSON")

    try:
        encode(value)
    except RecursionError as exc:
        raise _CanonicalJSONError("value nesting is too deep") from exc
    return bytes(output)


def _normalized_string(value: str) -> str:
    if not any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        return value
    output: list[str] = []
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(value):
                raise _InvalidUnicodeScalar("unpaired high surrogate")
            low = ord(value[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise _InvalidUnicodeScalar("unpaired high surrogate")
            output.append(
                chr(0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00))
            )
            index += 2
            continue
        if 0xDC00 <= codepoint <= 0xDFFF:
            raise _InvalidUnicodeScalar("unpaired low surrogate")
        output.append(value[index])
        index += 1
    return "".join(output)


def _normalized_json_value(value: Any, active: set[int] | None = None) -> Any:
    if active is None:
        active = set()
    if value is None or type(value) in {bool, int, float}:
        return value
    if type(value) is str:
        return _normalized_string(value)
    if type(value) is list:
        identity = id(value)
        if identity in active:
            raise _CanonicalJSONError("cyclic array")
        active.add(identity)
        try:
            return [_normalized_json_value(item, active) for item in value]
        finally:
            active.remove(identity)
    if type(value) is dict:
        identity = id(value)
        if identity in active:
            raise _CanonicalJSONError("cyclic object")
        active.add(identity)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise _CanonicalJSONError("object keys must be strings")
                normalized_key = _normalized_string(key)
                if normalized_key in normalized:
                    raise _CanonicalJSONError(
                        "duplicate object key after Unicode scalar normalization"
                    )
                normalized[normalized_key] = _normalized_json_value(item, active)
            return normalized
        finally:
            active.remove(identity)
    raise _CanonicalJSONError("value is not strict JSON")


def _mathematical_integer(value: Any) -> int | None:
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def _integer_text(value: int | None) -> str:
    if value is None:
        raise _CanonicalJSONError("integer value is unavailable")
    return format(Decimal(value), "f")


def _validate_exact_object(
    value: Any,
    path: str,
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    issues: _IssueCollector,
) -> dict[str, Any] | None:
    if type(value) is not dict:
        issues.add(path, "INVALID_TYPE")
        return None
    if any(type(key) is not str for key in value):
        issues.add(path, "INVALID_FIELD_NAME")
    present = {key for key in value if type(key) is str}
    if not required.issubset(present):
        issues.add(path, "REQUIRED_FIELD_MISSING")
    if not present.issubset(allowed):
        issues.add(path, "UNKNOWN_FIELD")
    return value


def _validate_unicode_scalars(
    value: Any,
    path: str,
    issues: _IssueCollector,
    active: set[int] | None = None,
) -> None:
    if active is None:
        active = set()
    if type(value) is str:
        try:
            _normalized_string(value)
        except _InvalidUnicodeScalar:
            issues.add(path, "INVALID_UNICODE_SCALAR")
        return
    if type(value) is list:
        identity = id(value)
        if identity in active:
            return
        active.add(identity)
        try:
            for index, item in enumerate(value[: MAX_GRAPH_NODES + 1]):
                _validate_unicode_scalars(item, f"{path}[{index}]", issues, active)
        finally:
            active.remove(identity)
        return
    if type(value) is dict:
        identity = id(value)
        if identity in active:
            return
        active.add(identity)
        try:
            for key, item in value.items():
                if type(key) is not str:
                    continue
                child_path = (
                    f"{path}.{key}"
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                    else path
                )
                try:
                    _normalized_string(key)
                except _InvalidUnicodeScalar:
                    issues.add(path, "INVALID_UNICODE_SCALAR")
                _validate_unicode_scalars(item, child_path, issues, active)
        finally:
            active.remove(identity)


def _validate_string(
    value: Any,
    path: str,
    issues: _IssueCollector,
    *,
    nonempty: bool = True,
) -> bool:
    if type(value) is not str:
        issues.add(path, "INVALID_TYPE")
        return False
    try:
        normalized = _normalized_string(value)
    except _CanonicalJSONError:
        issues.add(path, "INVALID_UNICODE_SCALAR")
        return False
    if nonempty and not normalized:
        issues.add(path, "VALUE_TOO_SHORT")
        return False
    return True


def _validate_reference(value: Any, path: str, issues: _IssueCollector) -> bool:
    if not _validate_string(value, path, issues):
        return False
    assert isinstance(value, str)
    invalid = (
        len(value) > 1024
        or "\r" in value
        or "\n" in value
        or value.startswith(("/", "\\"))
        or (
            len(value) >= 3
            and value[0].isascii()
            and value[0].isalpha()
            and value[1] == ":"
            and value[2] in ("/", "\\")
        )
        or value.lower().startswith(("http:", "https:", "file:"))
    )
    if invalid:
        issues.add(path, "REFERENCE_NOT_ALLOWED")
        return False
    return True


def _validate_reference_array(
    value: Any,
    path: str,
    issues: _IssueCollector,
    *,
    minimum: int = 0,
) -> bool:
    if type(value) is not list:
        issues.add(path, "INVALID_TYPE")
        return False
    valid = True
    if len(value) < minimum:
        issues.add(path, "VALUE_TOO_SHORT")
        valid = False
    if len(value) > 100:
        issues.add(path, "VALUE_TOO_LONG")
        valid = False
    seen: set[str] = set()
    for index, reference in enumerate(value[:101]):
        if not _validate_reference(reference, f"{path}[{index}]", issues):
            valid = False
        else:
            normalized = _normalized_string(reference)
            if normalized in seen:
                issues.add(path, "DUPLICATE_VALUE")
                valid = False
            else:
                seen.add(normalized)
    return valid


def _validate_node_state(
    value: Any,
    path: str,
    issues: _IssueCollector,
) -> str | None:
    item = _validate_exact_object(
        value,
        path,
        required=frozenset({"node_id", "status", "evidence_refs"}),
        allowed=_NODE_STATE_FIELDS,
        issues=issues,
    )
    if item is None:
        return None
    node_id = item.get("node_id")
    identity = (
        _normalized_string(node_id)
        if _validate_string(node_id, f"{path}.node_id", issues)
        else None
    )
    status = item.get("status")
    status_valid = type(status) is str and status in _NODE_STATUSES
    if not status_valid:
        issues.add(f"{path}.status", "VALUE_NOT_ALLOWED")
    _validate_reference_array(item.get("evidence_refs"), f"{path}.evidence_refs", issues)
    if "result_digest" in item:
        result_digest = item["result_digest"]
        if (
            type(result_digest) is not str
            or _DIGEST_REFERENCE_PATTERN.fullmatch(result_digest) is None
        ):
            issues.add(f"{path}.result_digest", "VALUE_NOT_ALLOWED")
    if status_valid and status in _RESULT_REQUIRED_STATUSES and "result_digest" not in item:
        issues.add(path, "RESULT_DIGEST_REQUIRED")
    if status == "NO_ACTION_REQUIRED":
        evidence = item.get("evidence_refs")
        if type(evidence) is list and not evidence:
            issues.add(f"{path}.evidence_refs", "EVIDENCE_REQUIRED")
    return identity


def _validate_resource_snapshot(
    value: Any,
    path: str,
    issues: _IssueCollector,
) -> str | None:
    item = _validate_exact_object(
        value,
        path,
        required=_RESOURCE_FIELDS,
        allowed=_RESOURCE_FIELDS,
        issues=issues,
    )
    if item is None:
        return None
    resource_id = item.get("resource_id")
    identity = (
        _normalized_string(resource_id)
        if _validate_string(resource_id, f"{path}.resource_id", issues)
        else None
    )
    availability = item.get("availability")
    if type(availability) is not str or availability not in _RESOURCE_REASON:
        issues.add(f"{path}.availability", "VALUE_NOT_ALLOWED")
    expected_reason = _RESOURCE_REASON.get(availability)
    if item.get("reason_code") != expected_reason:
        issues.add(f"{path}.reason_code", "VALUE_NOT_ALLOWED")
    _validate_reference_array(item.get("evidence_refs"), f"{path}.evidence_refs", issues)
    return identity


def _validate_external_decision(
    value: Any,
    path: str,
    issues: _IssueCollector,
) -> str | None:
    item = _validate_exact_object(
        value,
        path,
        required=frozenset({"join_id", "decision"}),
        allowed=_EXTERNAL_FIELDS,
        issues=issues,
    )
    if item is None:
        return None
    join_id = item.get("join_id")
    identity = (
        _normalized_string(join_id)
        if _validate_string(join_id, f"{path}.join_id", issues)
        else None
    )
    decision = item.get("decision")
    if type(decision) is not str or decision not in _EXTERNAL_DECISIONS:
        issues.add(f"{path}.decision", "VALUE_NOT_ALLOWED")
        return identity
    if decision == "PENDING":
        if "authority_ref" in item or "evidence_refs" in item:
            issues.add(path, "PENDING_DECISION_HAS_EVIDENCE")
    else:
        if "authority_ref" not in item:
            issues.add(path, "AUTHORITY_REQUIRED")
        else:
            _validate_reference(item["authority_ref"], f"{path}.authority_ref", issues)
        if "evidence_refs" not in item:
            issues.add(path, "EVIDENCE_REQUIRED")
        else:
            _validate_reference_array(
                item["evidence_refs"],
                f"{path}.evidence_refs",
                issues,
                minimum=1,
            )
    return identity


def _validate_identity_array(
    value: Any,
    path: str,
    issues: _IssueCollector,
    *,
    minimum: int,
    maximum: int,
    item_validator: Any,
) -> None:
    if type(value) is not list:
        issues.add(path, "INVALID_TYPE")
        return
    if len(value) < minimum:
        issues.add(path, "VALUE_TOO_SHORT")
    if len(value) > maximum:
        issues.add(path, "VALUE_TOO_LONG")
    identities: set[str] = set()
    for index, item in enumerate(value[: maximum + 1]):
        identity = item_validator(item, f"{path}[{index}]", issues)
        if identity is None:
            continue
        if identity in identities:
            issues.add(path, "DUPLICATE_IDENTITY")
        else:
            identities.add(identity)


def validate_ready_resolution_input(
    resolution_input: Any,
) -> tuple[ReadyResolutionIssue, ...]:
    """Strictly validate Input v1 and identity uniqueness without mutation."""

    issues = _IssueCollector()
    try:
        _validate_unicode_scalars(resolution_input, "$", issues)
    except RecursionError:
        issues.add("$", "VALUE_NESTING_TOO_DEEP")
    value = _validate_exact_object(
        resolution_input,
        "$",
        required=_INPUT_FIELDS,
        allowed=_INPUT_FIELDS,
        issues=issues,
    )
    if value is None:
        return issues.result()

    if value.get("schema_id") != INPUT_SCHEMA_ID:
        issues.add("$.schema_id", "VALUE_NOT_ALLOWED")
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        issues.add("$.schema_version", "VALUE_NOT_ALLOWED")
    graph_digest = value.get("graph_digest")
    if type(graph_digest) is not str or _DIGEST_PATTERN.fullmatch(graph_digest) is None:
        issues.add("$.graph_digest", "VALUE_NOT_ALLOWED")
    generation = value.get("graph_generation")
    generation = _mathematical_integer(generation)
    if generation is None or generation < 1:
        issues.add("$.graph_generation", "VALUE_NOT_ALLOWED")

    _validate_identity_array(
        value.get("node_states"),
        "$.node_states",
        issues,
        minimum=1,
        maximum=MAX_GRAPH_NODES,
        item_validator=_validate_node_state,
    )
    _validate_identity_array(
        value.get("resource_availability"),
        "$.resource_availability",
        issues,
        minimum=0,
        maximum=MAX_NODE_RESOURCES,
        item_validator=_validate_resource_snapshot,
    )
    _validate_identity_array(
        value.get("external_join_decisions"),
        "$.external_join_decisions",
        issues,
        minimum=0,
        maximum=MAX_GRAPH_JOINS,
        item_validator=_validate_external_decision,
    )
    return issues.result()


def _normalized_ready_input(resolution_input: Mapping[str, Any]) -> dict[str, Any]:
    resolution_input = _normalized_json_value(resolution_input)
    normalized: dict[str, Any] = {
        "schema_id": resolution_input["schema_id"],
        "schema_version": resolution_input["schema_version"],
        "graph_digest": resolution_input["graph_digest"],
        "graph_generation": _mathematical_integer(
            resolution_input["graph_generation"]
        ),
    }
    for array_name, identity_name in (
        ("node_states", "node_id"),
        ("resource_availability", "resource_id"),
        ("external_join_decisions", "join_id"),
    ):
        records: list[dict[str, Any]] = []
        for original in resolution_input[array_name]:
            copied = dict(original)
            if "evidence_refs" in copied:
                copied["evidence_refs"] = sorted(copied["evidence_refs"])
            records.append(copied)
        normalized[array_name] = sorted(records, key=lambda item: item[identity_name])
    return normalized


def canonical_ready_input_digest(resolution_input: Any) -> str | None:
    """Return the v1 semantic digest, or ``None`` when strict validation fails."""

    if validate_ready_resolution_input(resolution_input):
        return None
    try:
        normalized = _normalized_ready_input(resolution_input)
        canonical = _canonical_json_bytes(normalized)
    except (_CanonicalJSONError, KeyError, TypeError):
        return None
    return hashlib.sha256(INPUT_DIGEST_DOMAIN + canonical).hexdigest()


def _safe_graph_metadata(
    graph: Any,
) -> tuple[str | None, int | None]:
    if type(graph) is not dict:
        return None, None
    digest = None
    generation = graph.get("generation")
    generation = _mathematical_integer(generation)
    if generation is None or generation < 1:
        generation = None
    return digest, generation


def _failure(
    error_code: str,
    issues: tuple[ReadyResolutionIssue, ...] | list[ReadyResolutionIssue],
    *,
    graph_digest: str | None = None,
    graph_generation: int | None = None,
    input_digest: str | None = None,
) -> ReadyResolutionOutcome:
    if error_code not in _ERROR_CODES:
        raise ValueError("unsupported Ready Resolution error code")
    ordered = tuple(sorted(set(issues)))[:MAX_ISSUES]
    if not ordered:
        ordered = (ReadyResolutionIssue("$", "RESOLUTION_FAILED"),)
    error: dict[str, Any] = {
        "schema_id": ERROR_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "error_code": error_code,
        "issues": [issue.as_dict() for issue in ordered],
    }
    if graph_digest is not None and _DIGEST_PATTERN.fullmatch(graph_digest):
        error["graph_digest"] = graph_digest
    if (
        graph_generation is not None
        and type(graph_generation) is int
        and graph_generation >= 1
    ):
        error["graph_generation"] = graph_generation
    if (
        input_digest is not None
        and error_code != "REQUIRED_INPUT_INVALID"
        and _DIGEST_PATTERN.fullmatch(input_digest)
    ):
        error["input_digest"] = input_digest
    try:
        encoded = _canonical_json_bytes(error, limit=MAX_ERROR_CANONICAL_BYTES)
    except _CanonicalJSONError:
        encoded = b""
    if not encoded:
        error = {
            "schema_id": ERROR_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "error_code": error_code,
            "issues": [{"path": "$", "code": "ERROR_SIZE_LIMIT"}],
        }
    return ReadyResolutionOutcome._from_error(error)


def _graph_admission_issues(graph: Any) -> tuple[ReadyResolutionIssue, ...]:
    issues = _IssueCollector()
    if type(graph) is not dict:
        return ()
    nodes = graph.get("nodes")
    joins = graph.get("joins")
    if type(nodes) is list:
        if len(nodes) > MAX_GRAPH_NODES:
            issues.add("$.nodes", "RESOLUTION_LIMIT_EXCEEDED")
        for index, item in enumerate(nodes[:MAX_GRAPH_NODES]):
            if type(item) is not dict:
                continue
            dependencies = item.get("depends_on")
            resources = item.get("resources")
            if type(dependencies) is list and len(dependencies) > MAX_NODE_DEPENDENCIES:
                issues.add(
                    f"$.nodes[{index}].depends_on",
                    "RESOLUTION_LIMIT_EXCEEDED",
                )
            if type(resources) is list and len(resources) > MAX_NODE_RESOURCES:
                issues.add(
                    f"$.nodes[{index}].resources",
                    "RESOLUTION_LIMIT_EXCEEDED",
                )
    if type(joins) is list:
        if len(joins) > MAX_GRAPH_JOINS:
            issues.add("$.joins", "RESOLUTION_LIMIT_EXCEEDED")
        for index, item in enumerate(joins[:MAX_GRAPH_JOINS]):
            if type(item) is not dict:
                continue
            requires = item.get("requires")
            if type(requires) is list and len(requires) > MAX_JOIN_REQUIRES:
                issues.add(
                    f"$.joins[{index}].requires",
                    "RESOLUTION_LIMIT_EXCEEDED",
                )
    return issues.result()


def _graph_validation_issues(validation: Any) -> tuple[ReadyResolutionIssue, ...]:
    mapped: set[ReadyResolutionIssue] = set()
    for issue in validation.issues:
        code = re.sub(r"[^A-Z0-9_]", "_", issue.code.upper())
        if not code or not code[0].isalpha():
            code = "GRAPH_INVALID"
        mapped.add(ReadyResolutionIssue(issue.path, code[:64]))
    return tuple(sorted(mapped))[:MAX_ISSUES]


def _ordered_reasons(*reasons: str) -> list[str]:
    return sorted(set(reasons), key=lambda value: _REASON_RANK[value])


def _node_decision_record(
    node_id: str,
    disposition: str,
    reasons: list[str],
    *,
    blocking_nodes: list[str] | None = None,
    blocking_resources: list[str] | None = None,
    blocking_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "disposition": disposition,
        "reason_codes": reasons,
        "blocking_node_ids": [] if blocking_nodes is None else sorted(set(blocking_nodes)),
        "blocking_resource_ids": (
            [] if blocking_resources is None else sorted(set(blocking_resources))
        ),
        "blocking_refs": [] if blocking_refs is None else blocking_refs,
    }


def _resolve_node(
    node: Mapping[str, Any],
    states: Mapping[str, Mapping[str, Any]],
    resources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    node_id = node["id"]
    current = states[node_id]
    status = current["status"]
    fixed = {
        "RUNNING": ("IN_PROGRESS", "NODE_RUNNING"),
        "SUCCEEDED": ("COMPLETED", "NODE_SUCCEEDED"),
        "NO_ACTION_REQUIRED": ("COMPLETED", "NODE_NO_ACTION_REQUIRED"),
        "FAILED": ("NEEDS_CORRECTION", "NODE_FAILED"),
        "NEEDS_CORRECTION": ("NEEDS_CORRECTION", "NODE_NEEDS_CORRECTION"),
        "DONE_WITH_CONCERNS": ("NEEDS_CORRECTION", "NODE_DONE_WITH_CONCERNS"),
        "HANDOFF": ("HANDOFF_REQUIRED", "NODE_HANDOFF"),
        "BLOCKED": ("BLOCKED", "NODE_BLOCKED"),
        "CANCELLED": ("CANCELLED", "NODE_CANCELLED"),
    }
    if status in fixed:
        disposition, reason = fixed[status]
        return _node_decision_record(node_id, disposition, [reason])

    dependency_states = [
        (dependency, states[dependency]["status"])
        for dependency in node["depends_on"]
    ]
    unsatisfied = [
        dependency
        for dependency, dependency_status in dependency_states
        if dependency_status not in _SUCCESS_STATUSES
    ]
    fatal = [
        dependency
        for dependency, dependency_status in dependency_states
        if dependency_status in {"BLOCKED", "CANCELLED"}
    ]
    if fatal:
        specific = []
        if any(status == "BLOCKED" for _, status in dependency_states):
            specific.append("NODE_BLOCKED")
        if any(status == "CANCELLED" for _, status in dependency_states):
            specific.append("NODE_CANCELLED")
        return _node_decision_record(
            node_id,
            "BLOCKED",
            _ordered_reasons("DEPENDENCY_FAILED", *specific),
            blocking_nodes=unsatisfied,
        )

    failed = [
        dependency
        for dependency, dependency_status in dependency_states
        if dependency_status
        in {"FAILED", "NEEDS_CORRECTION", "DONE_WITH_CONCERNS"}
    ]
    pending = [
        dependency
        for dependency, dependency_status in dependency_states
        if dependency_status not in _SUCCESS_STATUSES
        and dependency_status
        not in {"FAILED", "NEEDS_CORRECTION", "DONE_WITH_CONCERNS"}
    ]
    if failed or pending:
        reasons = []
        if failed:
            reasons.append("DEPENDENCY_FAILED")
        if pending:
            reasons.append("DEPENDENCY_PENDING")
        return _node_decision_record(
            node_id,
            "WAITING_DEPENDENCY",
            _ordered_reasons(*reasons),
            blocking_nodes=[*failed, *pending],
        )

    unavailable: list[str] = []
    non_available: list[str] = []
    waiting_reasons: list[str] = []
    for resource_id in node["resources"]:
        snapshot = resources.get(resource_id)
        availability = "UNKNOWN" if snapshot is None else snapshot["availability"]
        if availability == "UNAVAILABLE":
            unavailable.append(resource_id)
            non_available.append(resource_id)
        elif availability in {"BUSY", "UNKNOWN"}:
            non_available.append(resource_id)
            waiting_reasons.append(_RESOURCE_REASON[availability])
    if unavailable:
        return _node_decision_record(
            node_id,
            "BLOCKED",
            ["RESOURCE_UNAVAILABLE"],
            blocking_resources=non_available,
        )
    if non_available:
        return _node_decision_record(
            node_id,
            "WAITING_RESOURCE",
            _ordered_reasons(*waiting_reasons),
            blocking_resources=non_available,
        )
    ready_reasons = ["DEPENDENCIES_SATISFIED"]
    if node["resources"]:
        ready_reasons.append("RESOURCE_AVAILABLE")
    return _node_decision_record(node_id, "READY", ready_reasons)


def _join_failure_reasons(
    node_ids: list[str],
    states: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    reasons = ["JOIN_NODE_FAILED"]
    for node_id in node_ids:
        status = states[node_id]["status"]
        if status in {"FAILED", "NEEDS_CORRECTION"}:
            reasons.append("NODE_FAILED")
        elif status == "DONE_WITH_CONCERNS":
            reasons.append("NODE_DONE_WITH_CONCERNS")
        elif status == "BLOCKED":
            reasons.append("NODE_BLOCKED")
        elif status == "CANCELLED":
            reasons.append("NODE_CANCELLED")
    return _ordered_reasons(*reasons)


def _join_decision_record(
    join_id: str,
    disposition: str,
    reasons: list[str],
    *,
    blocking_nodes: list[str] | None = None,
    blocking_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "join_id": join_id,
        "disposition": disposition,
        "reason_codes": reasons,
        "blocking_node_ids": [] if blocking_nodes is None else sorted(set(blocking_nodes)),
        "blocking_refs": [] if blocking_refs is None else blocking_refs,
    }


def _automatic_join_prerequisites(
    join: Mapping[str, Any],
    graph_nodes: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    if join["policy"] != "required-plus-optional":
        return list(join["requires"])
    return [
        node_id
        for node_id in join["requires"]
        if graph_nodes[node_id]["classification"] == "required"
    ]


def _resolve_join(
    join: Mapping[str, Any],
    graph_nodes: Mapping[str, Mapping[str, Any]],
    states: Mapping[str, Mapping[str, Any]],
    external_decisions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    join_id = join["id"]
    policy = join["policy"]
    required = _automatic_join_prerequisites(join, graph_nodes)

    if policy == "first-success":
        succeeded = [
            node_id for node_id in required if states[node_id]["status"] in _SUCCESS_STATUSES
        ]
        if succeeded:
            return _join_decision_record(join_id, "SATISFIED", ["JOIN_SATISFIED"])
        possible = [
            node_id
            for node_id in required
            if states[node_id]["status"] not in _JOIN_FAILURE_STATUSES
        ]
        if possible:
            return _join_decision_record(
                join_id,
                "WAITING_NODE",
                ["JOIN_NODE_PENDING"],
                blocking_nodes=possible,
            )
        return _join_decision_record(
            join_id,
            "BLOCKED",
            _join_failure_reasons(required, states),
            blocking_nodes=required,
        )

    unsatisfied = [
        node_id
        for node_id in required
        if states[node_id]["status"] not in _SUCCESS_STATUSES
    ]
    failed = [
        node_id
        for node_id in required
        if states[node_id]["status"] in _JOIN_FAILURE_STATUSES
    ]
    if failed:
        return _join_decision_record(
            join_id,
            "BLOCKED",
            _join_failure_reasons(failed, states),
            blocking_nodes=unsatisfied,
        )
    pending = [
        node_id
        for node_id in required
        if states[node_id]["status"] not in _SUCCESS_STATUSES
    ]
    if pending:
        return _join_decision_record(
            join_id,
            "WAITING_NODE",
            ["JOIN_NODE_PENDING"],
            blocking_nodes=pending,
        )
    if policy in _AUTOMATIC_JOIN_POLICIES:
        return _join_decision_record(join_id, "SATISFIED", ["JOIN_SATISFIED"])

    decision = external_decisions.get(join_id)
    if decision is None or decision["decision"] == "PENDING":
        return _join_decision_record(
            join_id,
            "REQUIRES_EXTERNAL_DECISION",
            ["EXTERNAL_DECISION_MISSING"],
        )
    if decision["decision"] == "SATISFIED":
        return _join_decision_record(join_id, "SATISFIED", ["JOIN_SATISFIED"])
    authority = decision["authority_ref"]
    refs = [authority]
    refs.extend(
        reference
        for reference in sorted(decision["evidence_refs"])
        if reference != authority
    )
    return _join_decision_record(
        join_id,
        "REJECTED",
        ["EXTERNAL_DECISION_REJECTED"],
        blocking_refs=refs,
    )


def _graph_disposition(
    graph: Mapping[str, Any],
    node_decisions: list[dict[str, Any]],
    join_decisions: list[dict[str, Any]],
) -> str:
    node_dispositions = {item["node_id"]: item["disposition"] for item in node_decisions}
    node_classifications = {
        node["id"]: node["classification"] for node in graph["nodes"]
    }
    values = set(node_dispositions.values())
    if "IN_PROGRESS" in values:
        return "IN_PROGRESS"
    if "READY" in values:
        return "READY"
    if "NEEDS_CORRECTION" in values:
        return "NEEDS_CORRECTION"
    if "HANDOFF_REQUIRED" in values:
        return "HANDOFF_REQUIRED"
    if values.intersection({"WAITING_DEPENDENCY", "WAITING_RESOURCE"}) or any(
        item["disposition"] in {"WAITING_NODE", "REQUIRES_EXTERNAL_DECISION"}
        for item in join_decisions
    ):
        return "WAITING"
    if any(
        item["disposition"] in {"BLOCKED", "REJECTED"} for item in join_decisions
    ) or any(
        item["disposition"] == "BLOCKED"
        or (
            item["disposition"] == "CANCELLED"
            and node_classifications[item["node_id"]] == "required"
        )
        for item in node_decisions
    ):
        return "BLOCKED"

    required_complete = all(
        node_dispositions[node["id"]] == "COMPLETED"
        for node in graph["nodes"]
        if node["classification"] == "required"
    )
    optional_closed = all(
        node_dispositions[node["id"]] in {"COMPLETED", "CANCELLED"}
        for node in graph["nodes"]
        if node["classification"] == "optional"
    )
    joins_complete = all(
        item["disposition"] == "SATISFIED" for item in join_decisions
    )
    if required_complete and optional_closed and joins_complete:
        return "COMPLETED"
    return "BLOCKED"


def _summary(
    node_decisions: list[dict[str, Any]],
    join_decisions: list[dict[str, Any]],
) -> dict[str, int]:
    node_names = {
        "READY": "ready_node_count",
        "WAITING_DEPENDENCY": "waiting_dependency_node_count",
        "WAITING_RESOURCE": "waiting_resource_node_count",
        "IN_PROGRESS": "in_progress_node_count",
        "NEEDS_CORRECTION": "needs_correction_node_count",
        "HANDOFF_REQUIRED": "handoff_required_node_count",
        "BLOCKED": "blocked_node_count",
        "COMPLETED": "completed_node_count",
        "CANCELLED": "cancelled_node_count",
    }
    join_names = {
        "SATISFIED": "satisfied_join_count",
        "WAITING_NODE": "waiting_node_join_count",
        "REQUIRES_EXTERNAL_DECISION": "requires_external_decision_join_count",
        "REJECTED": "rejected_join_count",
        "BLOCKED": "blocked_join_count",
    }
    summary = {
        "node_decision_count": len(node_decisions),
        "join_decision_count": len(join_decisions),
        **{field: 0 for field in node_names.values()},
        **{field: 0 for field in join_names.values()},
    }
    for item in node_decisions:
        summary[node_names[item["disposition"]]] += 1
    for item in join_decisions:
        summary[join_names[item["disposition"]]] += 1
    return summary


def _valid_identity_list(value: Any, maximum: int) -> bool:
    return (
        type(value) is list
        and len(value) <= maximum
        and all(type(item) is str and bool(item) for item in value)
        and len(value) == len(set(value))
    )


def _valid_result_reference_list(value: Any) -> bool:
    if type(value) is not list or len(value) > MAX_BLOCKING_REFS:
        return False
    if len(value) != len(set(value)):
        return False
    collector = _IssueCollector()
    for index, reference in enumerate(value):
        _validate_reference(reference, f"$.refs[{index}]", collector)
    return not collector.result()


def _result_is_structurally_valid(result: Any) -> bool:
    if type(result) is not dict or set(result) != {
        "schema_id",
        "schema_version",
        "graph_digest",
        "graph_generation",
        "input_digest",
        "graph_disposition",
        "node_decisions",
        "join_decisions",
        "summary",
    }:
        return False
    if (
        result["schema_id"] != RESULT_SCHEMA_ID
        or result["schema_version"] != 1
        or type(result["graph_digest"]) is not str
        or _DIGEST_PATTERN.fullmatch(result["graph_digest"]) is None
        or type(result["input_digest"]) is not str
        or _DIGEST_PATTERN.fullmatch(result["input_digest"]) is None
        or type(result["graph_generation"]) is not int
        or result["graph_generation"] < 1
        or result["graph_disposition"] not in _GRAPH_DISPOSITIONS
    ):
        return False
    nodes = result["node_decisions"]
    joins = result["join_decisions"]
    if (
        type(nodes) is not list
        or not 1 <= len(nodes) <= MAX_GRAPH_NODES
        or type(joins) is not list
        or len(joins) > MAX_GRAPH_JOINS
    ):
        return False
    if [item.get("node_id") for item in nodes] != sorted(
        item.get("node_id") for item in nodes
    ) or [item.get("join_id") for item in joins] != sorted(
        item.get("join_id") for item in joins
    ):
        return False
    for item in nodes:
        if type(item) is not dict or set(item) != {
            "node_id",
            "disposition",
            "reason_codes",
            "blocking_node_ids",
            "blocking_resource_ids",
            "blocking_refs",
        }:
            return False
        if (
            type(item["node_id"]) is not str
            or not item["node_id"]
            or item["disposition"] not in _NODE_DISPOSITIONS
            or type(item["reason_codes"]) is not list
            or not 1 <= len(item["reason_codes"]) <= 16
            or len(item["reason_codes"]) != len(set(item["reason_codes"]))
            or not set(item["reason_codes"]).issubset(_REASON_CODES)
            or not _valid_identity_list(
                item["blocking_node_ids"], MAX_BLOCKING_NODE_IDS
            )
            or not _valid_identity_list(
                item["blocking_resource_ids"], MAX_BLOCKING_RESOURCE_IDS
            )
            or not _valid_result_reference_list(item["blocking_refs"])
        ):
            return False
        if item["disposition"] in {"READY", "COMPLETED"} and any(
            (
                item["blocking_node_ids"],
                item["blocking_resource_ids"],
                item["blocking_refs"],
            )
        ):
            return False
        if (
            item["disposition"] == "WAITING_DEPENDENCY"
            and not item["blocking_node_ids"]
        ):
            return False
        if (
            item["disposition"] == "WAITING_RESOURCE"
            and not item["blocking_resource_ids"]
        ):
            return False
    for item in joins:
        if type(item) is not dict or set(item) != {
            "join_id",
            "disposition",
            "reason_codes",
            "blocking_node_ids",
            "blocking_refs",
        }:
            return False
        if (
            type(item["join_id"]) is not str
            or not item["join_id"]
            or item["disposition"] not in _JOIN_DISPOSITIONS
            or type(item["reason_codes"]) is not list
            or not 1 <= len(item["reason_codes"]) <= 16
            or len(item["reason_codes"]) != len(set(item["reason_codes"]))
            or not set(item["reason_codes"]).issubset(_REASON_CODES)
            or not _valid_identity_list(
                item["blocking_node_ids"], MAX_BLOCKING_NODE_IDS
            )
            or not _valid_result_reference_list(item["blocking_refs"])
        ):
            return False
        if item["disposition"] == "SATISFIED" and any(
            (item["blocking_node_ids"], item["blocking_refs"])
        ):
            return False
        if (
            item["disposition"] in {"WAITING_NODE", "BLOCKED"}
            and not item["blocking_node_ids"]
        ):
            return False
        if item["disposition"] == "REJECTED" and (
            item["blocking_node_ids"] or not item["blocking_refs"]
        ):
            return False
    return result["summary"] == _summary(nodes, joins)


def _resolve_ready_payload(
    graph: Any,
    resolution_input: Any,
) -> dict[str, Any] | ReadyResolutionOutcome:
    try:
        _canonical_json_bytes(resolution_input, limit=MAX_INPUT_CANONICAL_BYTES)
    except _CanonicalSizeExceeded:
        return _failure(
            "INPUT_TOO_LARGE",
            [ReadyResolutionIssue("$", "CANONICAL_SIZE_EXCEEDED")],
        )
    except _InvalidUnicodeScalar:
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [ReadyResolutionIssue("$", "INVALID_UNICODE_SCALAR")],
        )
    except _CanonicalJSONError:
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [ReadyResolutionIssue("$", "STRICT_JSON_REQUIRED")],
        )

    input_issues = validate_ready_resolution_input(resolution_input)
    if input_issues:
        return _failure("REQUIRED_INPUT_INVALID", input_issues)

    try:
        _canonical_json_bytes(graph, limit=MAX_GRAPH_CANONICAL_BYTES)
    except _CanonicalSizeExceeded:
        return _failure(
            "GRAPH_TOO_LARGE",
            [ReadyResolutionIssue("$", "CANONICAL_SIZE_EXCEEDED")],
        )
    except _InvalidUnicodeScalar:
        return _failure(
            "GRAPH_INVALID",
            [ReadyResolutionIssue("$", "INVALID_UNICODE_SCALAR")],
        )
    except _CanonicalJSONError:
        return _failure(
            "GRAPH_INVALID",
            [ReadyResolutionIssue("$", "STRICT_JSON_REQUIRED")],
        )

    admission_issues = _graph_admission_issues(graph)
    if admission_issues:
        return _failure("RESOLUTION_LIMIT_EXCEEDED", admission_issues)

    try:
        graph_validation = validate_graph_contract(graph)
    except (KeyError, TypeError, ValueError, RecursionError):
        return _failure(
            "GRAPH_INVALID",
            [ReadyResolutionIssue("$", "GRAPH_VALIDATION_FAILED")],
        )
    if not graph_validation.valid:
        return _failure("GRAPH_INVALID", _graph_validation_issues(graph_validation))

    try:
        graph_digest = graph_validation.semantic_digest
    except (KeyError, TypeError, ValueError, RecursionError):
        return _failure(
            "GRAPH_INVALID",
            [ReadyResolutionIssue("$", "GRAPH_DIGEST_FAILED")],
        )
    graph_generation = _mathematical_integer(graph["generation"])
    if graph_digest is None or graph_generation is None:
        return _failure(
            "GRAPH_INVALID",
            [ReadyResolutionIssue("$", "GRAPH_DIGEST_FAILED")],
        )
    binding_issues = _IssueCollector()
    if resolution_input["graph_digest"] != graph_digest:
        binding_issues.add("$.graph_digest", "GRAPH_DIGEST_MISMATCH")
    if resolution_input["graph_generation"] != graph_generation:
        binding_issues.add("$.graph_generation", "GRAPH_GENERATION_MISMATCH")
    if binding_issues.result():
        return _failure(
            "GRAPH_BINDING_MISMATCH",
            binding_issues.result(),
            graph_digest=graph_digest,
            graph_generation=graph_generation,
        )

    try:
        semantic_graph = _normalized_json_value(graph)
        semantic_input = _normalized_json_value(resolution_input)
    except _InvalidUnicodeScalar:
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [ReadyResolutionIssue("$", "INVALID_UNICODE_SCALAR")],
            graph_digest=graph_digest,
            graph_generation=graph_generation,
        )
    except _CanonicalJSONError:
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [ReadyResolutionIssue("$", "STRICT_JSON_REQUIRED")],
            graph_digest=graph_digest,
            graph_generation=graph_generation,
        )

    graph_nodes = {item["id"]: item for item in semantic_graph["nodes"]}
    states = {item["node_id"]: item for item in semantic_input["node_states"]}
    coverage_issues = _IssueCollector()
    missing = set(graph_nodes) - set(states)
    unknown = set(states) - set(graph_nodes)
    if missing:
        coverage_issues.add("$.node_states", "NODE_STATE_MISSING")
    for index, item in enumerate(semantic_input["node_states"]):
        if item["node_id"] in unknown:
            coverage_issues.add(
                f"$.node_states[{index}].node_id",
                "UNKNOWN_NODE_ID",
            )
    if coverage_issues.result():
        return _failure(
            "REQUIRED_INPUT_INVALID",
            coverage_issues.result(),
            graph_digest=graph_digest,
            graph_generation=graph_generation,
        )

    graph_joins = {item["id"]: item for item in semantic_graph["joins"]}
    external_issues = _IssueCollector()
    for index, item in enumerate(semantic_input["external_join_decisions"]):
        declared = graph_joins.get(item["join_id"])
        if declared is None:
            external_issues.add(
                f"$.external_join_decisions[{index}].join_id",
                "UNKNOWN_JOIN_ID",
            )
        elif declared["policy"] not in _EXTERNAL_JOIN_POLICIES:
            external_issues.add(
                f"$.external_join_decisions[{index}].join_id",
                "EXTERNAL_DECISION_NOT_ALLOWED",
            )
    if external_issues.result():
        return _failure(
            "REQUIRED_INPUT_INVALID",
            external_issues.result(),
            graph_digest=graph_digest,
            graph_generation=graph_generation,
        )

    input_digest = canonical_ready_input_digest(resolution_input)
    if input_digest is None:
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [ReadyResolutionIssue("$", "INPUT_DIGEST_UNAVAILABLE")],
            graph_digest=graph_digest,
            graph_generation=graph_generation,
        )

    resources = {
        item["resource_id"]: item
        for item in semantic_input["resource_availability"]
    }
    external_decisions = {
        item["join_id"]: item
        for item in semantic_input["external_join_decisions"]
    }
    node_decisions = [
        _resolve_node(graph_nodes[node_id], states, resources)
        for node_id in sorted(graph_nodes)
    ]
    join_decisions = [
        _resolve_join(graph_joins[join_id], graph_nodes, states, external_decisions)
        for join_id in sorted(graph_joins)
    ]
    result: dict[str, Any] = {
        "schema_id": RESULT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "graph_digest": graph_digest,
        "graph_generation": graph_generation,
        "input_digest": input_digest,
        "graph_disposition": _graph_disposition(
            semantic_graph, node_decisions, join_decisions
        ),
        "node_decisions": node_decisions,
        "join_decisions": join_decisions,
        "summary": _summary(node_decisions, join_decisions),
    }
    if not _result_is_structurally_valid(result):
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [ReadyResolutionIssue("$", "RESULT_STRUCTURE_INVALID")],
            graph_digest=graph_digest,
            graph_generation=graph_generation,
            input_digest=input_digest,
        )
    try:
        _canonical_json_bytes(result, limit=MAX_RESULT_CANONICAL_BYTES)
    except _CanonicalSizeExceeded:
        return _failure(
            "RESULT_TOO_LARGE",
            [ReadyResolutionIssue("$", "CANONICAL_SIZE_EXCEEDED")],
            graph_digest=graph_digest,
            graph_generation=graph_generation,
            input_digest=input_digest,
        )
    except _CanonicalJSONError:
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [ReadyResolutionIssue("$", "RESULT_STRUCTURE_INVALID")],
            graph_digest=graph_digest,
            graph_generation=graph_generation,
            input_digest=input_digest,
        )
    return result


def resolve_ready_nodes(
    graph: Any,
    resolution_input: Any,
) -> ReadyResolutionOutcome:
    """Resolve node and join readiness without side effects or runtime mutation."""

    resolved = _resolve_ready_payload(graph, resolution_input)
    if isinstance(resolved, ReadyResolutionOutcome):
        return resolved
    return ReadyResolutionOutcome._from_result(graph, resolution_input, resolved)


__all__ = [
    "ReadyResolutionIssue",
    "ReadyResolutionOutcome",
    "canonical_ready_input_digest",
    "resolve_ready_nodes",
    "validate_ready_resolution_input",
]
