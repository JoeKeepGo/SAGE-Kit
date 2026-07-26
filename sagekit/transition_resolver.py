"""Pure, bounded Transition Resolution Contract v1 resolver.

The resolver decides one supplied Graph and transition snapshot.  It does not
read current runtime state, apply a transition, mutate the Graph, acquire
authority, or activate proposed nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from .graph_contract import (
    NODE_STATUSES,
    validate_graph_contract,
    validate_node_result,
    validate_node_transition,
)


INPUT_SCHEMA_ID = "urn:sagekit:transition-resolution:v1:input"
RESULT_SCHEMA_ID = "urn:sagekit:transition-resolution:v1:result"
ERROR_SCHEMA_ID = "urn:sagekit:transition-resolution:v1:error"
SCHEMA_VERSION = 1

NODE_RESULT_DIGEST_DOMAIN = b"sagekit-node-result-v1\0"
TRANSITION_INPUT_DIGEST_DOMAIN = b"sagekit-transition-resolution-input-v1\0"

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

_INPUT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "graph_id",
        "graph_generation",
        "graph_digest",
        "run_id",
        "authority_id",
        "controller_id",
        "node_id",
        "attempt_id",
        "state_revision",
        "last_event_sequence",
        "previous_status",
        "node_result",
    }
)
_IDENTITY_FIELDS = (
    "graph_id",
    "run_id",
    "authority_id",
    "controller_id",
    "node_id",
    "attempt_id",
)
_ERROR_CODES = frozenset(
    {
        "REQUIRED_INPUT_INVALID",
        "INPUT_TOO_LARGE",
        "GRAPH_TOO_LARGE",
        "RESOLUTION_LIMIT_EXCEEDED",
        "GRAPH_INVALID",
        "GRAPH_BINDING_MISMATCH",
        "NODE_BINDING_MISMATCH",
        "NODE_RESULT_INVALID",
        "TRANSITION_NOT_ALLOWED",
        "AUTHORITY_CHANGE_STATUS_INVALID",
        "RESULT_TOO_LARGE",
    }
)
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SIMPLE_PATH_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ISSUE_PATH = re.compile(
    r"^\$(?:(?:\.[A-Za-z_][A-Za-z0-9_]*)|\[[0-9]{1,7}\])*$"
)
_ISSUE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@dataclass(frozen=True, order=True)
class TransitionResolutionIssue:
    """A bounded observable transition-resolution issue."""

    path: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "code": self.code,
            "message": self.message,
        }


class TransitionResolutionOutcome:
    """Resolver-created immutable snapshot of one complete Result or Error."""

    __slots__ = ("_result_snapshot", "_error_snapshot", "_sealed")

    def __init__(
        self,
        *_args: Any,
        **_kwargs: Any,
    ) -> None:
        raise ValueError("TransitionResolutionOutcome is resolver-created")

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("TransitionResolutionOutcome is immutable")

    def __delattr__(self, _name: str) -> None:
        raise AttributeError("TransitionResolutionOutcome is immutable")

    @classmethod
    def _from_error(
        cls,
        error: Mapping[str, Any],
    ) -> TransitionResolutionOutcome:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", None)
        object.__setattr__(instance, "_error_snapshot", _freeze_json(error))
        object.__setattr__(instance, "_sealed", True)
        return instance

    @classmethod
    def _from_validated_source(
        cls,
        graph: Any,
        transition_input: Any,
        result: Mapping[str, Any],
    ) -> TransitionResolutionOutcome:
        validation = _validate_transition_resolution(graph, transition_input)
        if (
            validation.error_code is not None
            or validation.normalized_input is None
        ):
            raise ValueError("success source is not a valid transition")
        expected = _build_transition_result(
            validation.normalized_input,
        )
        _canonical_json_size(expected, limit=MAX_RESULT_CANONICAL_BYTES)
        if type(result) is not dict or result != expected:
            raise ValueError("result does not match its validated source")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", _freeze_json(expected))
        object.__setattr__(instance, "_error_snapshot", None)
        object.__setattr__(instance, "_sealed", True)
        return instance

    @classmethod
    def _from_result(
        cls,
        result: Mapping[str, Any],
    ) -> TransitionResolutionOutcome:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", _freeze_json(result))
        object.__setattr__(instance, "_error_snapshot", None)
        object.__setattr__(instance, "_sealed", True)
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
        if not isinstance(other, TransitionResolutionOutcome):
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


class _CanonicalSizeExceeded(_CanonicalJSONError):
    pass


@dataclass(frozen=True)
class _ResolutionValidation:
    error_code: str | None
    issues: tuple[TransitionResolutionIssue, ...]
    normalized_input: dict[str, Any] | None = None
    graph_digest: str | None = None


class _IssueCollector:
    """Keep a deterministic bounded reservoir plus one aggregation issue."""

    __slots__ = ("_issues", "_overflow")

    def __init__(self) -> None:
        self._issues: set[TransitionResolutionIssue] = set()
        self._overflow = False

    def add(self, path: str, code: str, message: str) -> None:
        issue = TransitionResolutionIssue(
            _safe_issue_path(path),
            _safe_issue_code(code),
            _safe_issue_message(message),
        )
        if issue in self._issues:
            return
        capacity = max(1, MAX_ISSUES - 1)
        if len(self._issues) < capacity:
            self._issues.add(issue)
            return
        self._overflow = True
        largest = max(self._issues)
        if issue < largest:
            self._issues.remove(largest)
            self._issues.add(issue)

    def result(self) -> tuple[TransitionResolutionIssue, ...]:
        issues = set(self._issues)
        if self._overflow and MAX_ISSUES > 1:
            issues.add(
                TransitionResolutionIssue(
                    "$",
                    "ADDITIONAL_ISSUES_OMITTED",
                    "The issue limit was reached; additional issues were omitted.",
                )
            )
        return tuple(sorted(issues))[:MAX_ISSUES]


def _safe_issue_path(path: Any) -> str:
    if type(path) is not str or _ISSUE_PATH.fullmatch(path) is None:
        return "$"
    return path[:1024]


def _safe_issue_code(code: Any) -> str:
    if type(code) is not str:
        return "RESOLUTION_FAILED"
    normalized = re.sub(r"[^A-Z0-9_]", "_", code.upper())[:64]
    if _ISSUE_CODE.fullmatch(normalized) is None:
        return "RESOLUTION_FAILED"
    return normalized


def _safe_issue_message(message: Any) -> str:
    if type(message) is not str:
        return "Transition resolution failed."
    bounded = message.replace("\r", " ").replace("\n", " ")[:1024]
    return bounded or "Transition resolution failed."


def _normalized_string(value: str) -> str:
    if not any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        return value
    output: list[str] = []
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(value):
                raise _CanonicalJSONError("unpaired high surrogate")
            low = ord(value[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise _CanonicalJSONError("unpaired high surrogate")
            scalar = 0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00)
            output.append(chr(scalar))
            index += 2
            continue
        if 0xDC00 <= codepoint <= 0xDFFF:
            raise _CanonicalJSONError("unpaired low surrogate")
        output.append(value[index])
        index += 1
    return "".join(output)


def _mathematical_integer(value: Any) -> int | None:
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def _integer_text(value: int) -> str:
    """Encode an integer without depending on Python's int-to-str digit limit."""

    return format(Decimal(value), "f")


def _normalize_json_value(value: Any, active: set[int] | None = None) -> Any:
    """Copy strict JSON while normalizing integer numbers and scalar strings."""

    if active is None:
        active = set()
    if value is None or type(value) is bool:
        return value
    integer = _mathematical_integer(value)
    if integer is not None:
        return integer
    if type(value) is float:
        raise _CanonicalJSONError("only finite mathematical integers are admitted")
    if type(value) is str:
        return _normalized_string(value)
    if type(value) is list:
        identity = id(value)
        if identity in active:
            raise _CanonicalJSONError("cyclic array")
        active.add(identity)
        try:
            return [_normalize_json_value(item, active) for item in value]
        finally:
            active.remove(identity)
    if type(value) is dict:
        identity = id(value)
        if identity in active:
            raise _CanonicalJSONError("cyclic object")
        active.add(identity)
        normalized: dict[str, Any] = {}
        try:
            for key, item in value.items():
                if type(key) is not str:
                    raise _CanonicalJSONError("object keys must be strings")
                normalized_key = _normalized_string(key)
                if normalized_key in normalized:
                    raise _CanonicalJSONError(
                        "object keys collapse to one Unicode scalar sequence"
                    )
                normalized[normalized_key] = _normalize_json_value(item, active)
        finally:
            active.remove(identity)
        return normalized
    raise _CanonicalJSONError("value is not strict JSON")


def _canonical_json_size(value: Any, *, limit: int) -> int:
    """Count canonical bytes with bounded work and no canonical materialization.

    Object member order does not affect JSON byte length, so admission counting
    deliberately avoids key sorting.  Full scalar validation and canonical key
    ordering still occur later for admitted values and digest construction.
    """

    count = 0
    active: set[int] = set()

    def add(amount: int) -> None:
        nonlocal count
        if amount < 0 or count + amount > limit:
            raise _CanonicalSizeExceeded
        count += amount

    def count_string(raw: str) -> None:
        add(1)
        index = 0
        while index < len(raw):
            codepoint = ord(raw[index])
            if codepoint in (0x22, 0x5C):
                add(2)
            elif codepoint in (0x08, 0x09, 0x0A, 0x0C, 0x0D):
                add(2)
            elif codepoint <= 0x1F:
                add(6)
            elif 0xD800 <= codepoint <= 0xDBFF:
                if index + 1 >= len(raw):
                    raise _CanonicalJSONError("unpaired high surrogate")
                low = ord(raw[index + 1])
                if not 0xDC00 <= low <= 0xDFFF:
                    raise _CanonicalJSONError("unpaired high surrogate")
                add(4)
                index += 1
            elif 0xDC00 <= codepoint <= 0xDFFF:
                raise _CanonicalJSONError("unpaired low surrogate")
            elif codepoint <= 0x7F:
                add(1)
            elif codepoint <= 0x7FF:
                add(2)
            elif codepoint <= 0xFFFF:
                add(3)
            else:
                add(4)
            index += 1
        add(1)

    def count_integer(integer: int) -> None:
        magnitude = abs(integer)
        sign_length = 1 if integer < 0 else 0
        if magnitude == 0:
            add(sign_length + 1)
            return
        lower_bound = (
            ((magnitude.bit_length() - 1) * 30102) // 100000
        ) + 1
        if count + sign_length + lower_bound > limit:
            raise _CanonicalSizeExceeded
        add(len(_integer_text(integer).encode("ascii")))

    stack: list[tuple[Any, ...]] = [("value", value)]
    while stack:
        frame = stack.pop()
        action = frame[0]
        if action == "raw":
            add(frame[1])
            continue
        if action == "string":
            count_string(frame[1])
            continue
        if action == "array":
            iterator, first, identity = frame[1:]
            try:
                child = next(iterator)
            except StopIteration:
                add(1)
                active.remove(identity)
                continue
            if not first:
                add(1)
            stack.append(("array", iterator, False, identity))
            stack.append(("value", child))
            continue
        if action == "object":
            iterator, first, identity = frame[1:]
            try:
                key, child = next(iterator)
            except StopIteration:
                add(1)
                active.remove(identity)
                continue
            if type(key) is not str:
                raise _CanonicalJSONError("object keys must be strings")
            if not first:
                add(1)
            count_string(key)
            add(1)
            stack.append(("object", iterator, False, identity))
            stack.append(("value", child))
            continue
        item = frame[1]
        if item is None:
            add(4)
        elif item is True:
            add(4)
        elif item is False:
            add(5)
        else:
            integer = _mathematical_integer(item)
            if integer is not None:
                count_integer(integer)
            elif type(item) is float:
                raise _CanonicalJSONError(
                    "only finite mathematical integers are admitted"
                )
            elif type(item) is str:
                count_string(item)
            elif type(item) is list:
                identity = id(item)
                if identity in active:
                    raise _CanonicalJSONError("cyclic array")
                active.add(identity)
                add(1)
                stack.append(("array", iter(item), True, identity))
            elif type(item) is dict:
                identity = id(item)
                if identity in active:
                    raise _CanonicalJSONError("cyclic object")
                active.add(identity)
                add(1)
                stack.append(("object", iter(item.items()), True, identity))
            else:
                raise _CanonicalJSONError("value is not strict JSON")
    return count


def _canonical_json_bytes(value: Any, *, limit: int | None = None) -> bytes:
    """Encode contract canonical JSON, stopping before retaining limit + 1."""

    output = bytearray()
    active: set[int] = set()

    def emit(data: bytes) -> None:
        if limit is not None and len(output) + len(data) > limit:
            raise _CanonicalSizeExceeded
        output.extend(data)

    def emit_string(raw: str) -> None:
        value = _normalized_string(raw)
        emit(b'"')
        for character in value:
            codepoint = ord(character)
            if character == '"':
                emit(b'\\"')
            elif character == "\\":
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
                emit(character.encode("utf-8"))
        emit(b'"')

    def encode(item: Any) -> None:
        if item is None:
            emit(b"null")
        elif item is True:
            emit(b"true")
        elif item is False:
            emit(b"false")
        else:
            integer = _mathematical_integer(item)
            if integer is not None:
                try:
                    emit(_integer_text(integer).encode("ascii"))
                except ValueError as exc:
                    raise _CanonicalJSONError("integer encoding failed") from exc
            elif type(item) is float:
                raise _CanonicalJSONError(
                    "only finite mathematical integers are admitted"
                )
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
                identity = id(item)
                if identity in active:
                    raise _CanonicalJSONError("cyclic object")
                active.add(identity)
                try:
                    keys: list[tuple[str, str]] = []
                    seen: set[str] = set()
                    for key in item:
                        if type(key) is not str:
                            raise _CanonicalJSONError(
                                "object keys must be strings"
                            )
                        normalized_key = _normalized_string(key)
                        if normalized_key in seen:
                            raise _CanonicalJSONError(
                                "object keys collapse to one Unicode scalar sequence"
                            )
                        seen.add(normalized_key)
                        keys.append((normalized_key, key))
                    keys.sort(key=lambda pair: tuple(ord(char) for char in pair[0]))
                    emit(b"{")
                    for index, (normalized_key, original_key) in enumerate(keys):
                        if index:
                            emit(b",")
                        emit_string(normalized_key)
                        emit(b":")
                        encode(item[original_key])
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


def _canonical_string_chunks(raw: str):
    yield b'"'
    index = 0
    while index < len(raw):
        codepoint = ord(raw[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(raw):
                raise _CanonicalJSONError("unpaired high surrogate")
            low = ord(raw[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise _CanonicalJSONError("unpaired high surrogate")
            codepoint = (
                0x10000
                + ((codepoint - 0xD800) << 10)
                + (low - 0xDC00)
            )
            character = chr(codepoint)
            index += 2
        elif 0xDC00 <= codepoint <= 0xDFFF:
            raise _CanonicalJSONError("unpaired low surrogate")
        else:
            character = raw[index]
            index += 1
        if character == '"':
            yield b'\\"'
        elif character == "\\":
            yield b"\\\\"
        elif codepoint == 0x08:
            yield b"\\b"
        elif codepoint == 0x09:
            yield b"\\t"
        elif codepoint == 0x0A:
            yield b"\\n"
        elif codepoint == 0x0C:
            yield b"\\f"
        elif codepoint == 0x0D:
            yield b"\\r"
        elif codepoint <= 0x1F:
            yield f"\\u{codepoint:04x}".encode("ascii")
        else:
            yield character.encode("utf-8")
    yield b'"'


def _canonical_json_digest(
    value: Any,
    *,
    domain: bytes,
    limit: int,
) -> str:
    """Hash canonical JSON iteratively without retaining the encoded value."""

    digest = hashlib.sha256()
    digest.update(domain)
    count = 0
    active: set[int] = set()
    stack: list[tuple[str, Any]] = [("value", value)]

    def emit(chunk: bytes) -> None:
        nonlocal count
        if count + len(chunk) > limit:
            raise _CanonicalSizeExceeded
        count += len(chunk)
        digest.update(chunk)

    while stack:
        action, item = stack.pop()
        if action == "raw":
            emit(item)
            continue
        if action == "string":
            for chunk in _canonical_string_chunks(item):
                emit(chunk)
            continue
        if action == "leave":
            active.remove(item)
            continue
        if item is None:
            emit(b"null")
        elif item is True:
            emit(b"true")
        elif item is False:
            emit(b"false")
        else:
            integer = _mathematical_integer(item)
            if integer is not None:
                emit(_integer_text(integer).encode("ascii"))
            elif type(item) is float:
                raise _CanonicalJSONError(
                    "only finite mathematical integers are admitted"
                )
            elif type(item) is str:
                stack.append(("string", item))
            elif type(item) is list:
                identity = id(item)
                if identity in active:
                    raise _CanonicalJSONError("cyclic array")
                active.add(identity)
                actions: list[tuple[str, Any]] = [("raw", b"[")]
                for index, child in enumerate(item):
                    if index:
                        actions.append(("raw", b","))
                    actions.append(("value", child))
                actions.extend((("raw", b"]"), ("leave", identity)))
                stack.extend(reversed(actions))
            elif type(item) is dict:
                identity = id(item)
                if identity in active:
                    raise _CanonicalJSONError("cyclic object")
                active.add(identity)
                keys: list[tuple[str, str]] = []
                seen: set[str] = set()
                for key in item:
                    if type(key) is not str:
                        raise _CanonicalJSONError(
                            "object keys must be strings"
                        )
                    normalized_key = _normalized_string(key)
                    if normalized_key in seen:
                        raise _CanonicalJSONError(
                            "object keys collapse to one Unicode scalar sequence"
                        )
                    seen.add(normalized_key)
                    keys.append((normalized_key, key))
                keys.sort(
                    key=lambda pair: tuple(ord(char) for char in pair[0])
                )
                actions = [("raw", b"{")]
                for index, (normalized_key, original_key) in enumerate(keys):
                    if index:
                        actions.append(("raw", b","))
                    actions.extend(
                        (
                            ("string", normalized_key),
                            ("raw", b":"),
                            ("value", item[original_key]),
                        )
                    )
                actions.extend((("raw", b"}"), ("leave", identity)))
                stack.extend(reversed(actions))
            else:
                raise _CanonicalJSONError("value is not strict JSON")
    return digest.hexdigest()


def _field_path(field: Any) -> str:
    if type(field) is str and _SIMPLE_PATH_KEY.fullmatch(field):
        return f"$.{field}"
    return "$"


def _input_structure_issues(
    transition_input: Any,
) -> tuple[TransitionResolutionIssue, ...]:
    issues = _IssueCollector()
    if type(transition_input) is not dict:
        issues.add("$", "INVALID_TYPE", "Transition input must be an object.")
        return issues.result()

    present = {key for key in transition_input if type(key) is str}
    for field in sorted(_INPUT_FIELDS - present):
        issues.add(
            _field_path(field),
            "REQUIRED_FIELD_MISSING",
            "A required transition input field is missing.",
        )
    for field in sorted(
        key
        for key in transition_input
        if type(key) is str and key not in _INPUT_FIELDS
    ):
        issues.add(
            _field_path(field),
            "UNKNOWN_FIELD",
            "The transition input contains a field that is not allowed.",
        )
    if any(type(key) is not str for key in transition_input):
        issues.add(
            "$",
            "INVALID_FIELD_NAME",
            "Transition input field names must be strings.",
        )

    if "schema_id" in transition_input and (
        type(transition_input["schema_id"]) is not str
        or transition_input["schema_id"] != INPUT_SCHEMA_ID
    ):
        issues.add(
            "$.schema_id",
            "VALUE_NOT_ALLOWED",
            "The transition input schema identity is not supported.",
        )
    if "schema_version" in transition_input:
        version = _mathematical_integer(transition_input["schema_version"])
        if version != SCHEMA_VERSION:
            issues.add(
                "$.schema_version",
                "VALUE_NOT_ALLOWED",
                "The transition input schema version is not supported.",
            )
    for field in _IDENTITY_FIELDS:
        if field in transition_input and (
            type(transition_input[field]) is not str
            or not transition_input[field]
        ):
            issues.add(
                _field_path(field),
                "VALUE_NOT_ALLOWED",
                "The transition identity must be a non-empty string.",
            )
    if "graph_generation" in transition_input:
        generation = _mathematical_integer(transition_input["graph_generation"])
        if generation is None or generation < 1:
            issues.add(
                "$.graph_generation",
                "VALUE_NOT_ALLOWED",
                "Graph generation must be an allowed positive integer.",
            )
    if "graph_digest" in transition_input and (
        type(transition_input["graph_digest"]) is not str
        or _DIGEST_PATTERN.fullmatch(transition_input["graph_digest"]) is None
    ):
        issues.add(
            "$.graph_digest",
            "VALUE_NOT_ALLOWED",
            "Graph digest must be a lowercase SHA-256 value.",
        )
    for field in ("state_revision", "last_event_sequence"):
        if field not in transition_input:
            continue
        sequence = _mathematical_integer(transition_input[field])
        if sequence is None or not 0 <= sequence <= 9007199254740991:
            issues.add(
                _field_path(field),
                "VALUE_NOT_ALLOWED",
                "Snapshot sequence values must be allowed non-negative integers.",
            )
    if "previous_status" in transition_input and (
        type(transition_input["previous_status"]) is not str
        or transition_input["previous_status"] not in NODE_STATUSES
    ):
        issues.add(
            "$.previous_status",
            "VALUE_NOT_ALLOWED",
            "Previous status must be an existing node status.",
        )
    if "node_result" in transition_input and type(
        transition_input["node_result"]
    ) is not dict:
        issues.add(
            "$.node_result",
            "INVALID_TYPE",
            "Node Result must be a complete object.",
        )
    return issues.result()


def _mapped_validation_issues(
    validation: Any,
    *,
    message: str,
    prefix: str = "",
) -> tuple[TransitionResolutionIssue, ...]:
    collector = _IssueCollector()
    for issue in validation.issues:
        path = issue.path
        if prefix and path.startswith("$"):
            path = prefix + path[1:]
        collector.add(path, issue.code, message)
    return collector.result()


def _graph_admission_issues(
    graph: Any,
) -> tuple[TransitionResolutionIssue, ...]:
    issues = _IssueCollector()
    if type(graph) is not dict:
        return ()
    nodes = graph.get("nodes")
    joins = graph.get("joins")
    if type(nodes) is list:
        if len(nodes) > MAX_GRAPH_NODES:
            issues.add(
                "$.nodes",
                "RESOLUTION_LIMIT_EXCEEDED",
                "Graph node cardinality exceeds the resolver admission limit.",
            )
        else:
            for index, item in enumerate(nodes):
                if type(item) is not dict:
                    continue
                dependencies = item.get("depends_on")
                resources = item.get("resources")
                if (
                    type(dependencies) is list
                    and len(dependencies) > MAX_NODE_DEPENDENCIES
                ):
                    issues.add(
                        f"$.nodes[{index}].depends_on",
                        "RESOLUTION_LIMIT_EXCEEDED",
                        "Node dependency cardinality exceeds the resolver admission limit.",
                    )
                if (
                    type(resources) is list
                    and len(resources) > MAX_NODE_RESOURCES
                ):
                    issues.add(
                        f"$.nodes[{index}].resources",
                        "RESOLUTION_LIMIT_EXCEEDED",
                        "Node resource cardinality exceeds the resolver admission limit.",
                    )
    if type(joins) is list:
        if len(joins) > MAX_GRAPH_JOINS:
            issues.add(
                "$.joins",
                "RESOLUTION_LIMIT_EXCEEDED",
                "Graph join cardinality exceeds the resolver admission limit.",
            )
        else:
            for index, item in enumerate(joins):
                if type(item) is not dict:
                    continue
                requires = item.get("requires")
                if type(requires) is list and len(requires) > MAX_JOIN_REQUIRES:
                    issues.add(
                        f"$.joins[{index}].requires",
                        "RESOLUTION_LIMIT_EXCEEDED",
                        "Join requirement cardinality exceeds the resolver admission limit.",
                    )
    return issues.result()


def _admit_graph(graph: Any) -> _ResolutionValidation:
    """Apply the resolver's bounded Graph admission before Graph validation."""

    try:
        _canonical_json_size(graph, limit=MAX_GRAPH_CANONICAL_BYTES)
    except _CanonicalSizeExceeded:
        return _ResolutionValidation(
            "GRAPH_TOO_LARGE",
            (
                TransitionResolutionIssue(
                    "$",
                    "CANONICAL_SIZE_EXCEEDED",
                    "Graph canonical bytes exceed the resolver admission limit.",
                ),
            ),
        )
    except _CanonicalJSONError:
        return _ResolutionValidation(
            "GRAPH_INVALID",
            (
                TransitionResolutionIssue(
                    "$",
                    "STRICT_JSON_REQUIRED",
                    "Graph must contain only strict canonical JSON values.",
                ),
            ),
        )

    admission_issues = _graph_admission_issues(graph)
    if admission_issues:
        return _ResolutionValidation(
            "RESOLUTION_LIMIT_EXCEEDED",
            admission_issues,
        )

    try:
        graph_validation = validate_graph_contract(graph)
    except (KeyError, TypeError, ValueError, RecursionError):
        return _ResolutionValidation(
            "GRAPH_INVALID",
            (
                TransitionResolutionIssue(
                    "$",
                    "GRAPH_VALIDATION_FAILED",
                    "Graph Contract v1 validation could not be completed.",
                ),
            ),
        )
    if not graph_validation.valid:
        return _ResolutionValidation(
            "GRAPH_INVALID",
            _mapped_validation_issues(
                graph_validation,
                message="The supplied Graph does not satisfy Graph Contract v1.",
            ),
        )
    graph_digest = graph_validation.semantic_digest
    if graph_digest is None:
        return _ResolutionValidation(
            "GRAPH_INVALID",
            (
                TransitionResolutionIssue(
                    "$",
                    "GRAPH_DIGEST_FAILED",
                    "The valid Graph digest could not be calculated.",
                ),
            ),
        )
    return _ResolutionValidation(
        None,
        (),
        graph_digest=graph_digest,
    )


def _failure(
    error_code: str,
    issues: tuple[TransitionResolutionIssue, ...]
    | list[TransitionResolutionIssue],
) -> TransitionResolutionOutcome:
    if error_code not in _ERROR_CODES:
        raise ValueError("unsupported Transition Resolution error code")
    ordered = tuple(sorted(set(issues)))[:MAX_ISSUES]
    if not ordered:
        ordered = (
            TransitionResolutionIssue(
                "$",
                "RESOLUTION_FAILED",
                "Transition resolution failed.",
            ),
        )
    error: dict[str, Any] = {
        "schema_id": ERROR_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "error_code": error_code,
        "issues": [issue.as_dict() for issue in ordered],
    }
    try:
        _canonical_json_size(error, limit=MAX_ERROR_CANONICAL_BYTES)
    except _CanonicalJSONError:
        error = {
            "schema_id": ERROR_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "error_code": error_code,
            "issues": [
                {
                    "path": "$",
                    "code": "ERROR_SIZE_LIMIT",
                    "message": "The bounded error representation was unavailable.",
                }
            ],
        }
    return TransitionResolutionOutcome._from_error(error)


def canonical_node_result_digest(graph: Any, node_result: Any) -> str | None:
    """Return a digest only for a Node Result valid for the supplied Graph."""

    try:
        graph_admission = _admit_graph(graph)
        if graph_admission.error_code is not None:
            return None
        _canonical_json_size(
            node_result,
            limit=MAX_INPUT_CANONICAL_BYTES,
        )
        graph_view = _graph_identity_view(graph)
        node_view = _node_result_identity_view(node_result)
        validation = validate_node_result(node_view, graph_view)
        if not validation.valid:
            return None
        return _canonical_json_digest(
            node_result,
            domain=NODE_RESULT_DIGEST_DOMAIN,
            limit=MAX_INPUT_CANONICAL_BYTES,
        )
    except (
        _CanonicalJSONError,
        KeyError,
        TypeError,
        ValueError,
        RecursionError,
    ):
        return None


def _canonical_transition_input_digest_raw(
    normalized_input: dict[str, Any],
) -> str:
    return _canonical_json_digest(
        normalized_input,
        domain=TRANSITION_INPUT_DIGEST_DOMAIN,
        limit=MAX_INPUT_CANONICAL_BYTES,
    )


def _normalized_scalar(value: Any) -> Any:
    if type(value) is str:
        return _normalized_string(value)
    integer = _mathematical_integer(value)
    return integer if integer is not None else value


def _node_result_identity_view(node_result: Any) -> Any:
    if type(node_result) is not dict:
        return node_result
    view = dict(node_result)
    if type(view.get("node_id")) is str:
        view["node_id"] = _normalized_string(view["node_id"])
    proposed = view.get("proposed_next_nodes")
    if type(proposed) is list:
        view["proposed_next_nodes"] = [
            _normalized_string(item) if type(item) is str else item
            for item in proposed
        ]
    return view


def _graph_identity_view(graph: Any) -> Any:
    if type(graph) is not dict:
        return graph
    view = dict(graph)
    if type(view.get("graph_id")) is str:
        view["graph_id"] = _normalized_string(view["graph_id"])
    nodes = view.get("nodes")
    if type(nodes) is list:
        node_views: list[Any] = []
        for item in nodes:
            if type(item) is not dict:
                node_views.append(item)
                continue
            node_view = dict(item)
            if type(node_view.get("id")) is str:
                node_view["id"] = _normalized_string(node_view["id"])
            node_views.append(node_view)
        view["nodes"] = node_views
    return view


def _transition_input_identity_view(transition_input: dict[str, Any]) -> dict[str, Any]:
    view = dict(transition_input)
    for field in (
        "schema_id",
        "graph_id",
        "graph_digest",
        "run_id",
        "authority_id",
        "controller_id",
        "node_id",
        "attempt_id",
        "previous_status",
    ):
        if type(view.get(field)) is str:
            view[field] = _normalized_string(view[field])
    for field in (
        "schema_version",
        "graph_generation",
        "state_revision",
        "last_event_sequence",
    ):
        if field in view:
            view[field] = _normalized_scalar(view[field])
    view["node_result"] = _node_result_identity_view(view["node_result"])
    return view


def _graph_binding_issues(
    graph: Mapping[str, Any],
    graph_digest: str,
    transition_input: Any,
) -> tuple[TransitionResolutionIssue, ...]:
    if type(transition_input) is not dict:
        return ()
    values = (
        transition_input.get("graph_id"),
        transition_input.get("graph_generation"),
        transition_input.get("graph_digest"),
    )
    if (
        type(values[0]) is not str
        or _mathematical_integer(values[1]) is None
        or type(values[2]) is not str
    ):
        return ()
    try:
        input_graph_id = _normalized_string(values[0])
        graph_id = _normalized_string(graph.get("graph_id"))
    except (TypeError, _CanonicalJSONError):
        return ()
    issues = _IssueCollector()
    if input_graph_id != graph_id:
        issues.add(
            "$.graph_id",
            "GRAPH_ID_MISMATCH",
            "Transition input Graph identity does not match the supplied Graph.",
        )
    if _mathematical_integer(values[1]) != _mathematical_integer(
        graph.get("generation")
    ):
        issues.add(
            "$.graph_generation",
            "GRAPH_GENERATION_MISMATCH",
            "Transition input Graph generation does not match the supplied Graph.",
        )
    if values[2] != graph_digest:
        issues.add(
            "$.graph_digest",
            "GRAPH_DIGEST_MISMATCH",
            "Transition input Graph digest does not match the supplied Graph.",
        )
    return issues.result()


def _validate_transition_resolution(
    graph: Any,
    transition_input: Any,
) -> _ResolutionValidation:
    graph_admission = _admit_graph(graph)
    if graph_admission.error_code is not None:
        return graph_admission
    graph_digest = graph_admission.graph_digest
    if graph_digest is None:
        raise AssertionError("successful Graph admission must retain its digest")

    try:
        _canonical_json_size(
            transition_input,
            limit=MAX_INPUT_CANONICAL_BYTES,
        )
    except _CanonicalSizeExceeded:
        return _ResolutionValidation(
            "INPUT_TOO_LARGE",
            (
                TransitionResolutionIssue(
                    "$",
                    "CANONICAL_SIZE_EXCEEDED",
                    "Transition input canonical bytes exceed the contract limit.",
                ),
            ),
            graph_digest=graph_digest,
        )
    except _CanonicalJSONError:
        return _ResolutionValidation(
            "REQUIRED_INPUT_INVALID",
            (
                TransitionResolutionIssue(
                    "$",
                    "STRICT_JSON_REQUIRED",
                    "Transition input must contain only strict canonical JSON values.",
                ),
            ),
            graph_digest=graph_digest,
        )

    input_issues = _input_structure_issues(transition_input)
    if input_issues:
        return _ResolutionValidation(
            "REQUIRED_INPUT_INVALID",
            input_issues,
            graph_digest=graph_digest,
        )
    binding_issues = _graph_binding_issues(
        graph,
        graph_digest,
        transition_input,
    )
    if binding_issues:
        return _ResolutionValidation(
            "GRAPH_BINDING_MISMATCH",
            binding_issues,
            graph_digest=graph_digest,
        )

    try:
        normalized = _transition_input_identity_view(transition_input)
        graph_view = _graph_identity_view(graph)
    except (_CanonicalJSONError, TypeError, ValueError):
        return _ResolutionValidation(
            "REQUIRED_INPUT_INVALID",
            (
                TransitionResolutionIssue(
                    "$",
                    "STRICT_JSON_REQUIRED",
                    "Transition input must contain only valid Unicode scalar sequences.",
                ),
            ),
            graph_digest=graph_digest,
        )

    node_payload = normalized["node_result"]
    try:
        node_validation = validate_node_result(node_payload, graph_view)
    except (KeyError, TypeError, ValueError, RecursionError):
        return _ResolutionValidation(
            "NODE_RESULT_INVALID",
            (
                TransitionResolutionIssue(
                    "$.node_result",
                    "NODE_RESULT_VALIDATION_FAILED",
                    "Node Result validation could not be completed.",
                ),
            ),
            graph_digest=graph_digest,
        )
    if not node_validation.valid:
        return _ResolutionValidation(
            "NODE_RESULT_INVALID",
            _mapped_validation_issues(
                node_validation,
                message="Node Result does not satisfy Node Result v1.",
                prefix="$.node_result",
            ),
            graph_digest=graph_digest,
        )

    if normalized["node_id"] != node_payload.get("node_id"):
        return _ResolutionValidation(
            "NODE_BINDING_MISMATCH",
            (
                TransitionResolutionIssue(
                    "$.node_result.node_id",
                    "NODE_BINDING_MISMATCH",
                    "Node Result identity does not match the transition input node.",
                ),
            ),
            graph_digest=graph_digest,
        )

    if (
        node_payload.get("authority_change") is True
        and node_payload.get("status") != "HANDOFF"
    ):
        return _ResolutionValidation(
            "AUTHORITY_CHANGE_STATUS_INVALID",
            (
                TransitionResolutionIssue(
                    "$.node_result.status",
                    "AUTHORITY_CHANGE_STATUS_INVALID",
                    "Authority-change requests require the HANDOFF status.",
                ),
            ),
            graph_digest=graph_digest,
        )

    transition = validate_node_transition(
        normalized["previous_status"],
        node_payload["status"],
    )
    if not transition.allowed:
        return _ResolutionValidation(
            "TRANSITION_NOT_ALLOWED",
            (
                TransitionResolutionIssue(
                    "$.previous_status",
                    "TRANSITION_NOT_ALLOWED",
                    "The exact proposed node transition is not allowed.",
                ),
            ),
            graph_digest=graph_digest,
        )

    return _ResolutionValidation(
        None,
        (),
        normalized_input=normalized,
        graph_digest=graph_digest,
    )


def canonical_transition_input_digest(
    graph: Any,
    transition_input: Any,
) -> str | None:
    """Return a digest only for a fully admissible graph-bound transition."""

    validation = _validate_transition_resolution(graph, transition_input)
    if validation.error_code is not None or validation.normalized_input is None:
        return None
    try:
        return _canonical_transition_input_digest_raw(
            validation.normalized_input
        )
    except (_CanonicalJSONError, RecursionError):
        return None


def validate_transition_resolution_input(
    graph: Any,
    transition_input: Any,
) -> tuple[TransitionResolutionIssue, ...]:
    """Return issues from the complete ordered resolver validation pipeline."""

    return _validate_transition_resolution(graph, transition_input).issues


def _build_transition_result(
    normalized_input: dict[str, Any],
) -> dict[str, Any]:
    node_payload = normalized_input["node_result"]
    input_digest = _canonical_transition_input_digest_raw(normalized_input)
    node_result_digest = _canonical_json_digest(
        node_payload,
        domain=NODE_RESULT_DIGEST_DOMAIN,
        limit=MAX_INPUT_CANONICAL_BYTES,
    )

    authority_change = node_payload["authority_change"]
    if authority_change is True:
        disposition = "APPLY_HANDOFF_AND_REQUEST_AUTHORITY"
        reason_code = "AUTHORITY_CHANGE_HANDOFF_REQUIRED"
        authority_decision_required = True
    else:
        disposition = "APPLY_TRANSITION"
        reason_code = "NODE_RESULT_STATUS_APPLIED"
        authority_decision_required = False

    return {
        "schema_id": RESULT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "disposition": disposition,
        "input_digest": input_digest,
        "node_result_digest": node_result_digest,
        "graph_id": normalized_input["graph_id"],
        "graph_generation": normalized_input["graph_generation"],
        "graph_digest": normalized_input["graph_digest"],
        "run_id": normalized_input["run_id"],
        "authority_id": normalized_input["authority_id"],
        "controller_id": normalized_input["controller_id"],
        "node_id": normalized_input["node_id"],
        "attempt_id": normalized_input["attempt_id"],
        "state_revision": normalized_input["state_revision"],
        "last_event_sequence": normalized_input["last_event_sequence"],
        "previous_status": normalized_input["previous_status"],
        "next_status": node_payload["status"],
        "reason_code": reason_code,
        "transition_allowed": True,
        "authority_decision_required": authority_decision_required,
        "grants_execution_authority": False,
        "grants_graph_mutation_authority": False,
        "grants_gate_authority": False,
        "grants_write_authority": False,
    }


def resolve_node_transition(
    graph: Any,
    transition_input: Any,
) -> TransitionResolutionOutcome:
    """Resolve one immutable snapshot without applying or authorizing it."""

    validation = _validate_transition_resolution(graph, transition_input)
    if validation.error_code is not None:
        return _failure(validation.error_code, validation.issues)
    if validation.normalized_input is None:
        raise AssertionError("successful validation must retain normalized input")
    normalized_input = validation.normalized_input

    try:
        result = _build_transition_result(normalized_input)
    except (_CanonicalJSONError, RecursionError):
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [
                TransitionResolutionIssue(
                    "$",
                    "INPUT_DIGEST_UNAVAILABLE",
                    "The validated transition input digest was unavailable.",
                )
            ],
        )
    try:
        _canonical_json_size(result, limit=MAX_RESULT_CANONICAL_BYTES)
    except _CanonicalSizeExceeded:
        return _failure(
            "RESULT_TOO_LARGE",
            [
                TransitionResolutionIssue(
                    "$",
                    "CANONICAL_SIZE_EXCEEDED",
                    "Transition Result canonical bytes exceed the contract limit.",
                )
            ],
        )
    except _CanonicalJSONError:
        return _failure(
            "RESULT_TOO_LARGE",
            [
                TransitionResolutionIssue(
                    "$",
                    "RESULT_ENCODING_FAILED",
                    "The complete Transition Result could not be encoded.",
                )
            ],
        )
    try:
        return TransitionResolutionOutcome._from_result(result)
    except (KeyError, TypeError, ValueError, _CanonicalJSONError):
        return _failure(
            "REQUIRED_INPUT_INVALID",
            [
                TransitionResolutionIssue(
                    "$",
                    "RESULT_SOURCE_VALIDATION_FAILED",
                    "The Result could not be rebound to its validated source.",
                )
            ],
        )


__all__ = [
    "TransitionResolutionIssue",
    "TransitionResolutionOutcome",
    "canonical_node_result_digest",
    "canonical_transition_input_digest",
    "resolve_node_transition",
    "validate_transition_resolution_input",
]
