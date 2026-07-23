"""Internal atomic runtime state store.

The module is inert at import time.  Files are created only by explicit writer
acquisition, initialization, or mutation calls.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Callable, Mapping, Sequence

from .graph_contract import (
    NODE_STATUSES as GRAPH_NODE_STATUSES,
    canonical_graph_digest,
    validate_graph_contract,
    validate_node_transition,
)


STATE_SCHEMA_ID = "urn:sagekit:runtime-state-contract:v1:state"
EVENT_SCHEMA_ID = "urn:sagekit:runtime-state-contract:v1:event"
LOCK_SCHEMA_ID = "urn:sagekit:runtime-store:v1:writer-lock"
SCHEMA_VERSION = 1

MAX_SAFE_INTEGER = 9007199254740991
MAX_GRAPH_GENERATION = 2147483647
MAX_EVENT_BYTES = 128 * 1024
MAX_GRAPH_BYTES = 8 * 1024 * 1024
MAX_STATE_BYTES = 16 * 1024 * 1024
MAX_EVENTS_BYTES = 64 * 1024 * 1024
MAX_LOCK_BYTES = 16 * 1024

IDENTITY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,255}$"
_IDENTITY_RE = re.compile(IDENTITY_PATTERN)
_DERIVED_ATTEMPT_RE = re.compile(r"^attempt:[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE_RE = re.compile(r"^(?![A-Za-z]:[\\/])(?!/)(?!https?://)(?!.*[\r\n]).+$")
_LABEL_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_REASON_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,127}$")
_RFC3339_RE = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]{1,9})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)

RUN_STATUSES = frozenset(
    {
        "INITIALIZED",
        "RUNNING",
        "WAITING_RESOURCE",
        "NEEDS_CORRECTION",
        "HANDOFF",
        "BLOCKED",
        "COMPLETED",
        "CANCELLED",
        "RECOVERING",
    }
)
NODE_STATUSES = frozenset(GRAPH_NODE_STATUSES)
EVENT_TYPES = frozenset(
    {
        "RUN_INITIALIZED",
        "GRAPH_BOUND",
        "RUN_STARTED",
        "NODE_READY",
        "NODE_STARTED",
        "NODE_WAITING_RESOURCE",
        "NODE_RESULT_RECORDED",
        "NODE_TRANSITIONED",
        "RECOVERY_STARTED",
        "RECOVERY_COMPLETED",
        "RUN_HANDOFF",
        "RUN_BLOCKED",
        "RUN_COMPLETED",
        "RUN_CANCELLED",
    }
)

_STATE_REQUIRED_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "run_id",
        "graph_digest",
        "graph_generation",
        "revision",
        "last_event_sequence",
        "run_status",
        "authority_id",
        "controller_id",
        "node_states",
    }
)
_STATE_FIELDS = _STATE_REQUIRED_FIELDS | {"handoff_ref", "recovery_status"}
_NODE_STATE_REQUIRED_FIELDS = frozenset(
    {
        "node_id",
        "status",
        "attempt_id",
        "last_event_sequence",
        "evidence_refs",
    }
)
_NODE_STATE_FIELDS = _NODE_STATE_REQUIRED_FIELDS | {
    "result_digest",
    "blocker_reason",
}
_EVENT_REQUIRED_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "event_id",
        "run_id",
        "sequence",
        "graph_digest",
        "event_type",
        "authority_id",
        "actor_id",
        "observed_at",
        "reason_code",
        "evidence_refs",
        "artifact_refs",
    }
)
_EVENT_FIELDS = _EVENT_REQUIRED_FIELDS | {
    "node_id",
    "attempt_id",
    "previous_status",
    "next_status",
    "result_digest",
    "duration_ms",
}
_LOCK_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "run_id",
        "graph_digest",
        "authority_id",
        "controller_id",
        "writer_id",
    }
)
_ATTEMPT_REQUIRED_STATUSES = frozenset(
    {
        "RUNNING",
        "SUCCEEDED",
        "NO_ACTION_REQUIRED",
        "FAILED",
        "NEEDS_CORRECTION",
        "DONE_WITH_CONCERNS",
    }
)
_NODE_SCOPED_EVENTS = frozenset(
    {
        "NODE_READY",
        "NODE_STARTED",
        "NODE_WAITING_RESOURCE",
        "NODE_RESULT_RECORDED",
        "NODE_TRANSITIONED",
    }
)


class RuntimeStoreStatus(str, Enum):
    NOT_INITIALIZED = "NOT_INITIALIZED"
    VALID = "VALID"
    LOCKED = "LOCKED"
    LOCK_INTEGRITY_ERROR = "LOCK_INTEGRITY_ERROR"
    INCOMPLETE = "INCOMPLETE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CORRUPT = "CORRUPT"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"


@dataclass(frozen=True, order=True)
class RuntimeStoreIssue:
    code: str
    message: str


@dataclass(frozen=True)
class RuntimeStoreCapabilities:
    file_fsync: bool = True
    atomic_replace: str = "os.replace"
    temporary_scope: str = "same-directory"
    directory_fsync: str = "NOT_PROBED"


@dataclass(frozen=True)
class RuntimeStoreInspection:
    status: RuntimeStoreStatus
    issues: tuple[RuntimeStoreIssue, ...] = ()
    capabilities: RuntimeStoreCapabilities = RuntimeStoreCapabilities()


class RuntimeStoreError(RuntimeError):
    """Base error for the internal runtime store."""


class RuntimeStoreBusy(RuntimeStoreError):
    """Raised when another writer lock already exists."""


class RuntimeStoreIntegrityError(RuntimeStoreError):
    """Raised when a contract, path, binding, or lock fails closed."""


class RuntimeStoreIncomplete(RuntimeStoreError):
    """Raised when an I/O failure leaves an incomplete or recoverable boundary."""

    def __init__(
        self,
        message: str,
        *,
        status: RuntimeStoreStatus = RuntimeStoreStatus.INCOMPLETE,
    ) -> None:
        self.status = status
        super().__init__(message)


@dataclass
class RuntimeWriter:
    root: Path
    runtime_directory: Path
    run_id: str
    graph_digest: str
    authority_id: str
    controller_id: str
    writer_id: str
    _lock_bytes: bytes
    _lock_identity: tuple[int, int, int, int, int]
    _runtime_identity: tuple[int, int]
    _released: bool = False


@dataclass(frozen=True)
class _RuntimePaths:
    root: Path
    control: Path
    runtime: Path
    graph: Path
    state: Path
    events: Path
    lock: Path


@dataclass(frozen=True)
class _InspectionData:
    report: RuntimeStoreInspection
    graph: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    events: tuple[dict[str, Any], ...] = ()
    event_bytes: bytes | None = None


def _issue(
    status: RuntimeStoreStatus,
    code: str,
    message: str,
) -> RuntimeStoreInspection:
    return RuntimeStoreInspection(
        status=status,
        issues=(RuntimeStoreIssue(code=code, message=message),),
    )


def _canonical_json_bytes(payload: Any) -> bytes:
    try:
        text = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeStoreIntegrityError(f"payload is not canonical JSON: {exc}") from exc
    return (text + "\n").encode("utf-8")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json_loads(data: bytes, label: str) -> Any:
    try:
        text = data.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeStoreIntegrityError(f"{label} is not strict UTF-8 JSON: {exc}") from exc


def _require_exact_mapping(
    value: Any,
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise RuntimeStoreIntegrityError(f"{label} must be an object")
    fields = frozenset(value)
    missing = sorted(required - fields)
    extra = sorted(fields - allowed)
    if missing or extra:
        raise RuntimeStoreIntegrityError(
            f"{label} fields are not exact; missing={missing}, extra={extra}"
        )
    return value


def _require_string(
    value: Any,
    label: str,
    *,
    minimum: int = 1,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if type(value) is not str:
        raise RuntimeStoreIntegrityError(f"{label} must be a string")
    if not minimum <= len(value) <= maximum:
        raise RuntimeStoreIntegrityError(f"{label} length is outside its bound")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise RuntimeStoreIntegrityError(f"{label} has an invalid format")
    return value


def _require_identity(value: Any, label: str) -> str:
    return _require_string(
        value,
        label,
        maximum=256,
        pattern=_IDENTITY_RE,
    )


def _require_sha256(value: Any, label: str) -> str:
    return _require_string(
        value,
        label,
        minimum=64,
        maximum=64,
        pattern=_SHA256_RE,
    )


def _require_integer(
    value: Any,
    label: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int:
        raise RuntimeStoreIntegrityError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise RuntimeStoreIntegrityError(f"{label} is outside its bound")
    return value


def _require_reference(value: Any, label: str) -> str:
    return _require_string(
        value,
        label,
        maximum=1024,
        pattern=_REFERENCE_RE,
    )


def _require_reference_array(value: Any, label: str) -> list[str]:
    if type(value) is not list:
        raise RuntimeStoreIntegrityError(f"{label} must be an array")
    if len(value) > 100:
        raise RuntimeStoreIntegrityError(f"{label} exceeds 100 items")
    references = [
        _require_reference(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    ]
    if len(references) != len(set(references)):
        raise RuntimeStoreIntegrityError(f"{label} must contain unique references")
    return references


def _require_enum(
    value: Any,
    choices: frozenset[str],
    label: str,
) -> str:
    if type(value) is not str or value not in choices:
        raise RuntimeStoreIntegrityError(f"{label} is not an allowed value")
    return value


def _derive_identity(kind: str, values: tuple[Any, ...]) -> str:
    material = json.dumps(
        {"domain": f"sagekit-runtime-{kind}-v1", "values": values},
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"{kind}:{hashlib.sha256(material).hexdigest()}"


def derive_run_id(
    graph_digest: str,
    authority_id: str,
    controller_id: str,
    run_key: str,
) -> str:
    _require_sha256(graph_digest, "graph_digest")
    _require_identity(authority_id, "authority_id")
    _require_identity(controller_id, "controller_id")
    _require_identity(run_key, "run_key")
    return _derive_identity(
        "run",
        (graph_digest, authority_id, controller_id, run_key),
    )


def derive_event_id(run_id: str, sequence: int) -> str:
    _require_identity(run_id, "run_id")
    _require_integer(
        sequence,
        "sequence",
        minimum=1,
        maximum=MAX_SAFE_INTEGER,
    )
    return _derive_identity("event", (run_id, sequence))


def derive_attempt_id(run_id: str, node_id: str, attempt_number: int) -> str:
    _require_identity(run_id, "run_id")
    _require_identity(node_id, "node_id")
    _require_integer(
        attempt_number,
        "attempt_number",
        minimum=1,
        maximum=MAX_SAFE_INTEGER,
    )
    return _derive_identity("attempt", (run_id, node_id, attempt_number))


def _path_is_within(
    root: str | os.PathLike[str],
    candidate: str | os.PathLike[str],
    *,
    path_module: Any = os.path,
) -> bool:
    root_value = path_module.normcase(path_module.abspath(path_module.normpath(root)))
    candidate_value = path_module.normcase(
        path_module.abspath(path_module.normpath(candidate))
    )
    try:
        return path_module.commonpath((root_value, candidate_value)) == root_value
    except ValueError:
        return False


def _canonical_root(root: str | os.PathLike[str]) -> Path:
    path = Path(root)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RuntimeStoreError(f"project root does not exist: {path}") from exc
    if not resolved.is_dir():
        raise RuntimeStoreError(f"project root is not a directory: {resolved}")
    return resolved


def _paths(root: str | os.PathLike[str]) -> _RuntimePaths:
    resolved = _canonical_root(root)
    control = resolved / ".sagekit"
    runtime = control / "runtime"
    return _RuntimePaths(
        root=resolved,
        control=control,
        runtime=runtime,
        graph=runtime / "graph.json",
        state=runtime / "state.json",
        events=runtime / "events.jsonl",
        lock=runtime / "writer.lock",
    )


def _is_reparse(result: os.stat_result) -> bool:
    attributes = getattr(result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(result.st_mode) or bool(
        reparse_flag and attributes & reparse_flag
    )


def _entry_lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _validate_directory_component(
    root: Path,
    path: Path,
    label: str,
) -> bool:
    result = _entry_lstat(path)
    if result is None:
        return False
    if _is_reparse(result):
        raise RuntimeStoreIntegrityError(f"{label} is a symlink or reparse point")
    if not stat.S_ISDIR(result.st_mode):
        raise RuntimeStoreIntegrityError(f"{label} is not a directory")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RuntimeStoreIntegrityError(f"{label} cannot be resolved safely") from exc
    if not _path_is_within(root, resolved):
        raise RuntimeStoreIntegrityError(f"{label} escapes the project root")
    return True


def _ensure_runtime_directory(paths: _RuntimePaths, *, create: bool) -> bool:
    control_exists = _validate_directory_component(
        paths.root, paths.control, ".sagekit"
    )
    if not control_exists:
        if not create:
            return False
        try:
            paths.control.mkdir(mode=0o700)
        except FileExistsError:
            pass
        _validate_directory_component(paths.root, paths.control, ".sagekit")

    runtime_exists = _validate_directory_component(
        paths.root, paths.runtime, "runtime directory"
    )
    if not runtime_exists:
        if not create:
            return False
        try:
            paths.runtime.mkdir(mode=0o700)
        except FileExistsError:
            pass
        _validate_directory_component(
            paths.root, paths.runtime, "runtime directory"
        )
    return True


def _file_identity(result: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        result.st_dev,
        result.st_ino,
        result.st_size,
        result.st_mtime_ns,
        result.st_ctime_ns,
    )


def _directory_identity(result: os.stat_result) -> tuple[int, int]:
    return (result.st_dev, result.st_ino)


def _assert_directory_identity(
    directory: Path,
    expected: tuple[int, int],
) -> None:
    result = _entry_lstat(directory)
    if (
        result is None
        or _is_reparse(result)
        or not stat.S_ISDIR(result.st_mode)
        or _directory_identity(result) != expected
    ):
        raise RuntimeStoreIntegrityError(
            "runtime directory identity changed or became unsafe"
        )


def _read_regular_bytes(
    path: Path,
    *,
    maximum: int,
    require_single_link: bool = True,
) -> tuple[bytes, tuple[int, int, int, int, int]]:
    before = _entry_lstat(path)
    if before is None:
        raise RuntimeStoreIntegrityError(f"required file is missing: {path.name}")
    if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise RuntimeStoreIntegrityError(f"{path.name} is not a safe regular file")
    if require_single_link and before.st_nlink != 1:
        raise RuntimeStoreIntegrityError(f"{path.name} has an unsafe hard-link count")

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeStoreIntegrityError(f"{path.name} cannot be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        if _file_identity(opened)[:3] != _file_identity(before)[:3]:
            raise RuntimeStoreIntegrityError(f"{path.name} changed while opening")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(maximum + 1)
    finally:
        os.close(descriptor)
    if len(data) > maximum:
        raise RuntimeStoreIntegrityError(f"{path.name} exceeds its size bound")
    after = _entry_lstat(path)
    if after is None or _file_identity(after) != _file_identity(before):
        raise RuntimeStoreIntegrityError(f"{path.name} changed while reading")
    return data, _file_identity(after)


def _validate_graph(graph: Any) -> str:
    result = validate_graph_contract(graph)
    if not result.valid or result.semantic_digest is None:
        details = ", ".join(
            f"{issue.code}@{issue.path}" for issue in result.issues[:5]
        )
        raise RuntimeStoreIntegrityError(f"graph contract is invalid: {details}")
    digest = canonical_graph_digest(graph)
    if digest != result.semantic_digest:
        raise RuntimeStoreIntegrityError("graph digest authority is inconsistent")
    return digest


def validate_runtime_state(
    payload: Any,
    graph: Any,
    *,
    run_id: str | None = None,
    graph_digest: str | None = None,
    authority_id: str | None = None,
    controller_id: str | None = None,
) -> None:
    state = _require_exact_mapping(
        payload,
        required=_STATE_REQUIRED_FIELDS,
        allowed=_STATE_FIELDS,
        label="runtime state",
    )
    if state["schema_id"] != STATE_SCHEMA_ID:
        raise RuntimeStoreIntegrityError("runtime state schema identity is invalid")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise RuntimeStoreIntegrityError("runtime state schema version is invalid")
    _require_identity(state["run_id"], "state.run_id")
    _require_sha256(state["graph_digest"], "state.graph_digest")
    _require_integer(
        state["graph_generation"],
        "state.graph_generation",
        minimum=1,
        maximum=MAX_GRAPH_GENERATION,
    )
    _require_integer(
        state["revision"],
        "state.revision",
        minimum=0,
        maximum=MAX_SAFE_INTEGER,
    )
    last_event = _require_integer(
        state["last_event_sequence"],
        "state.last_event_sequence",
        minimum=0,
        maximum=MAX_SAFE_INTEGER,
    )
    _require_enum(state["run_status"], RUN_STATUSES, "state.run_status")
    _require_identity(state["authority_id"], "state.authority_id")
    _require_identity(state["controller_id"], "state.controller_id")
    if "handoff_ref" in state:
        _require_reference(state["handoff_ref"], "state.handoff_ref")
    if "recovery_status" in state:
        _require_string(
            state["recovery_status"],
            "state.recovery_status",
            maximum=64,
            pattern=_LABEL_RE,
        )

    graph_digest_value = _validate_graph(graph)
    graph_nodes = [item["id"] for item in graph["nodes"]]
    node_values = state["node_states"]
    if type(node_values) is not list:
        raise RuntimeStoreIntegrityError("state.node_states must be an array")
    if not 1 <= len(node_values) <= 10000:
        raise RuntimeStoreIntegrityError("state.node_states is outside its item bound")

    node_ids: list[str] = []
    serialized_nodes: set[bytes] = set()
    for index, value in enumerate(node_values):
        label = f"state.node_states[{index}]"
        node_state = _require_exact_mapping(
            value,
            required=_NODE_STATE_REQUIRED_FIELDS,
            allowed=_NODE_STATE_FIELDS,
            label=label,
        )
        node_id = _require_identity(node_state["node_id"], f"{label}.node_id")
        node_ids.append(node_id)
        status_value = _require_enum(
            node_state["status"], NODE_STATUSES, f"{label}.status"
        )
        attempt = node_state["attempt_id"]
        if attempt is not None:
            _require_string(
                attempt,
                f"{label}.attempt_id",
                maximum=256,
                pattern=_DERIVED_ATTEMPT_RE,
            )
        if status_value in _ATTEMPT_REQUIRED_STATUSES and attempt is None:
            raise RuntimeStoreIntegrityError(
                f"{label}.attempt_id is required for {status_value}"
            )
        node_sequence = _require_integer(
            node_state["last_event_sequence"],
            f"{label}.last_event_sequence",
            minimum=0,
            maximum=MAX_SAFE_INTEGER,
        )
        if node_sequence > last_event:
            raise RuntimeStoreIntegrityError(
                f"{label}.last_event_sequence exceeds the state sequence"
            )
        _require_reference_array(node_state["evidence_refs"], f"{label}.evidence_refs")
        if "result_digest" in node_state:
            _require_identity(node_state["result_digest"], f"{label}.result_digest")
        if "blocker_reason" in node_state:
            reason = _require_string(
                node_state["blocker_reason"],
                f"{label}.blocker_reason",
                maximum=4096,
            )
            if "\r" in reason or "\n" in reason or not reason.strip():
                raise RuntimeStoreIntegrityError(
                    f"{label}.blocker_reason must be bounded single-line text"
                )
        encoded = _canonical_json_bytes(node_state)
        if encoded in serialized_nodes:
            raise RuntimeStoreIntegrityError("state.node_states must be unique")
        serialized_nodes.add(encoded)

    if len(node_ids) != len(set(node_ids)):
        raise RuntimeStoreIntegrityError("state node identities must be unique")
    if set(node_ids) != set(graph_nodes):
        raise RuntimeStoreIntegrityError(
            "state node identities must exactly match graph node identities"
        )
    if state["graph_generation"] != graph["generation"]:
        raise RuntimeStoreIntegrityError("state graph generation does not match graph")
    if state["graph_digest"] != graph_digest_value:
        raise RuntimeStoreIntegrityError("state graph digest does not match graph")
    if run_id is not None and state["run_id"] != run_id:
        raise RuntimeStoreIntegrityError("state run binding is invalid")
    if graph_digest is not None and state["graph_digest"] != graph_digest:
        raise RuntimeStoreIntegrityError("state graph binding is invalid")
    if authority_id is not None and state["authority_id"] != authority_id:
        raise RuntimeStoreIntegrityError("state authority binding is invalid")
    if controller_id is not None and state["controller_id"] != controller_id:
        raise RuntimeStoreIntegrityError("state controller binding is invalid")
    if len(_canonical_json_bytes(state)) > MAX_STATE_BYTES:
        raise RuntimeStoreIntegrityError("runtime state exceeds its size bound")


def validate_runtime_event(
    payload: Any,
    graph: Any,
    *,
    run_id: str | None = None,
    graph_digest: str | None = None,
    authority_id: str | None = None,
    actor_id: str | None = None,
) -> None:
    event = _require_exact_mapping(
        payload,
        required=_EVENT_REQUIRED_FIELDS,
        allowed=_EVENT_FIELDS,
        label="runtime event",
    )
    if event["schema_id"] != EVENT_SCHEMA_ID:
        raise RuntimeStoreIntegrityError("runtime event schema identity is invalid")
    if type(event["schema_version"]) is not int or event["schema_version"] != 1:
        raise RuntimeStoreIntegrityError("runtime event schema version is invalid")
    _require_identity(event["event_id"], "event.event_id")
    event_run = _require_identity(event["run_id"], "event.run_id")
    sequence = _require_integer(
        event["sequence"],
        "event.sequence",
        minimum=1,
        maximum=MAX_SAFE_INTEGER,
    )
    _require_sha256(event["graph_digest"], "event.graph_digest")
    event_type = _require_enum(event["event_type"], EVENT_TYPES, "event.event_type")
    _require_identity(event["authority_id"], "event.authority_id")
    _require_identity(event["actor_id"], "event.actor_id")
    observed_at = _require_string(
        event["observed_at"],
        "event.observed_at",
        minimum=20,
        maximum=64,
        pattern=_RFC3339_RE,
    )
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeStoreIntegrityError("event.observed_at is not a real date-time") from exc
    _require_string(
        event["reason_code"],
        "event.reason_code",
        maximum=128,
        pattern=_REASON_RE,
    )
    _require_reference_array(event["evidence_refs"], "event.evidence_refs")
    _require_reference_array(event["artifact_refs"], "event.artifact_refs")

    graph_value = _validate_graph(graph)
    graph_nodes = {item["id"] for item in graph["nodes"]}
    if "node_id" in event:
        node_id = _require_identity(event["node_id"], "event.node_id")
        if node_id not in graph_nodes:
            raise RuntimeStoreIntegrityError("event node is not declared by the graph")
    if "attempt_id" in event:
        _require_string(
            event["attempt_id"],
            "event.attempt_id",
            maximum=256,
            pattern=_DERIVED_ATTEMPT_RE,
        )
    if "previous_status" in event:
        _require_enum(
            event["previous_status"], NODE_STATUSES, "event.previous_status"
        )
    if "next_status" in event:
        _require_enum(event["next_status"], NODE_STATUSES, "event.next_status")
    if "result_digest" in event:
        _require_identity(event["result_digest"], "event.result_digest")
    if "duration_ms" in event:
        _require_integer(
            event["duration_ms"],
            "event.duration_ms",
            minimum=0,
            maximum=MAX_SAFE_INTEGER,
        )

    if event_type in _NODE_SCOPED_EVENTS and "node_id" not in event:
        raise RuntimeStoreIntegrityError(f"{event_type} requires node_id")
    if event_type in {"NODE_STARTED", "NODE_RESULT_RECORDED"} and "attempt_id" not in event:
        raise RuntimeStoreIntegrityError(f"{event_type} requires attempt_id")
    if event_type == "NODE_TRANSITIONED" and not {
        "previous_status",
        "next_status",
    }.issubset(event):
        raise RuntimeStoreIntegrityError("NODE_TRANSITIONED requires status facts")
    if event_type == "NODE_RESULT_RECORDED" and "result_digest" not in event:
        raise RuntimeStoreIntegrityError("NODE_RESULT_RECORDED requires result_digest")
    if ("attempt_id" in event or "result_digest" in event) and "node_id" not in event:
        raise RuntimeStoreIntegrityError("attempt and result facts require node_id")

    if event["event_id"] != derive_event_id(event_run, sequence):
        raise RuntimeStoreIntegrityError("event identity does not match run and sequence")
    if event["graph_digest"] != graph_value:
        raise RuntimeStoreIntegrityError("event graph digest does not match graph")
    if run_id is not None and event_run != run_id:
        raise RuntimeStoreIntegrityError("event run binding is invalid")
    if graph_digest is not None and event["graph_digest"] != graph_digest:
        raise RuntimeStoreIntegrityError("event graph binding is invalid")
    if authority_id is not None and event["authority_id"] != authority_id:
        raise RuntimeStoreIntegrityError("event authority binding is invalid")
    if actor_id is not None and event["actor_id"] != actor_id:
        raise RuntimeStoreIntegrityError("event actor binding is invalid")
    if len(_canonical_json_bytes(event)) > MAX_EVENT_BYTES:
        raise RuntimeStoreIntegrityError("runtime event exceeds its size bound")


def _validate_lock_payload(
    payload: Any,
    *,
    writer: RuntimeWriter | None = None,
) -> None:
    lock = _require_exact_mapping(
        payload,
        required=_LOCK_FIELDS,
        allowed=_LOCK_FIELDS,
        label="writer lock",
    )
    if lock["schema_id"] != LOCK_SCHEMA_ID:
        raise RuntimeStoreIntegrityError("writer lock schema identity is invalid")
    if type(lock["schema_version"]) is not int or lock["schema_version"] != 1:
        raise RuntimeStoreIntegrityError("writer lock schema version is invalid")
    _require_identity(lock["run_id"], "lock.run_id")
    _require_sha256(lock["graph_digest"], "lock.graph_digest")
    _require_identity(lock["authority_id"], "lock.authority_id")
    _require_identity(lock["controller_id"], "lock.controller_id")
    _require_identity(lock["writer_id"], "lock.writer_id")
    if writer is not None:
        expected = {
            "schema_id": LOCK_SCHEMA_ID,
            "schema_version": 1,
            "run_id": writer.run_id,
            "graph_digest": writer.graph_digest,
            "authority_id": writer.authority_id,
            "controller_id": writer.controller_id,
            "writer_id": writer.writer_id,
        }
        if lock != expected:
            raise RuntimeStoreIntegrityError("writer lock no longer matches its handle")


def _directory_fsync(
    directory: Path,
    expected_identity: tuple[int, int] | None = None,
) -> bool:
    if expected_identity is not None:
        _assert_directory_identity(directory, expected_identity)
    if os.name == "nt":
        return False
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as exc:
        if exc.errno in {
            errno.EACCES,
            errno.EINVAL,
            errno.ENOTSUP,
            getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
        }:
            return False
        raise
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if exc.errno in {
            errno.EBADF,
            errno.EINVAL,
            errno.ENOTSUP,
            getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
        }:
            return False
        raise
    finally:
        os.close(descriptor)
    return True


def _replace_file(
    source: Path,
    target: Path,
    *,
    expected_directory_identity: tuple[int, int] | None = None,
    writer: RuntimeWriter | None = None,
) -> None:
    if writer is not None:
        _verify_writer(writer)
    if source.parent != target.parent:
        raise RuntimeStoreIntegrityError("atomic replace requires a same-directory temp")
    if expected_directory_identity is not None:
        _assert_directory_identity(target.parent, expected_directory_identity)
    existing = _entry_lstat(target)
    if existing is not None and (
        _is_reparse(existing) or not stat.S_ISREG(existing.st_mode)
    ):
        raise RuntimeStoreIntegrityError(f"{target.name} is not a safe replace target")
    os.replace(source, target)


def _write_temp(
    target: Path,
    payload: bytes,
    owner_token: str,
    *,
    expected_directory_identity: tuple[int, int] | None = None,
    writer: RuntimeWriter | None = None,
) -> Path:
    if writer is not None:
        _verify_writer(writer)
    if expected_directory_identity is not None:
        _assert_directory_identity(target.parent, expected_directory_identity)
    descriptor, name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.{owner_token}.",
        suffix=".tmp",
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if expected_directory_identity is not None:
            _assert_directory_identity(target.parent, expected_directory_identity)
        return temporary
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _owner_token(writer_id: str) -> str:
    return hashlib.sha256(writer_id.encode("utf-8")).hexdigest()[:20]


def _remove_owned_lock(
    path: Path,
    *,
    runtime_identity: tuple[int, int],
    expected_identity: tuple[int, int, int, int, int],
    expected_bytes: bytes | None,
    owner_token: str,
) -> None:
    """Move an owned lock out of authority position before deleting it.

    A replacement raced into the lock path is never unlinked.  If the rename
    captures an unknown inode, it is restored when the authority path is still
    free and otherwise retained as evidence in the owner-specific quarantine.
    """

    _assert_directory_identity(path.parent, runtime_identity)
    quarantine = path.parent / f".writer.lock.release.{owner_token}.tmp"
    if _entry_lstat(quarantine) is not None:
        raise RuntimeStoreIntegrityError(
            "writer lock release quarantine already exists"
        )
    try:
        os.rename(path, quarantine)
    except FileNotFoundError as exc:
        raise RuntimeStoreIntegrityError(
            "writer lock disappeared before release"
        ) from exc

    moved_is_owned = False
    try:
        _assert_directory_identity(path.parent, runtime_identity)
        moved_bytes, moved_identity = _read_regular_bytes(
            quarantine,
            maximum=MAX_LOCK_BYTES,
        )
        moved_is_owned = (
            moved_identity[:2] == expected_identity[:2]
            and (expected_bytes is None or moved_bytes == expected_bytes)
        )
        if not moved_is_owned:
            raise RuntimeStoreIntegrityError(
                "writer lock was replaced during release"
            )
        final = _entry_lstat(quarantine)
        if final is None or _file_identity(final)[:2] != expected_identity[:2]:
            raise RuntimeStoreIntegrityError(
                "writer lock quarantine changed before deletion"
            )
        quarantine.unlink()
        _directory_fsync(path.parent, runtime_identity)
    except Exception:
        if _entry_lstat(quarantine) is not None and _entry_lstat(path) is None:
            try:
                os.rename(quarantine, path)
            except OSError:
                pass
        raise


def acquire_runtime_writer(
    root: str | os.PathLike[str],
    graph: Any,
    *,
    authority_id: str,
    controller_id: str,
    run_key: str,
    writer_id: str,
) -> RuntimeWriter:
    graph_digest = _validate_graph(graph)
    _require_identity(authority_id, "authority_id")
    _require_identity(controller_id, "controller_id")
    _require_identity(run_key, "run_key")
    _require_identity(writer_id, "writer_id")
    run_id = derive_run_id(
        graph_digest,
        authority_id,
        controller_id,
        run_key,
    )

    paths = _paths(root)
    _ensure_runtime_directory(paths, create=True)
    runtime_result = paths.runtime.lstat()
    runtime_identity = _directory_identity(runtime_result)
    _assert_directory_identity(paths.runtime, runtime_identity)
    payload = {
        "schema_id": LOCK_SCHEMA_ID,
        "schema_version": 1,
        "run_id": run_id,
        "graph_digest": graph_digest,
        "authority_id": authority_id,
        "controller_id": controller_id,
        "writer_id": writer_id,
    }
    encoded = _canonical_json_bytes(payload)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(paths.lock, flags, 0o600)
    except FileExistsError as exc:
        raise RuntimeStoreBusy("runtime writer lock already exists") from exc
    created_identity = _file_identity(os.fstat(descriptor))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            written = stream.write(encoded)
            if written != len(encoded):
                raise OSError("writer lock write was incomplete")
            stream.flush()
            os.fsync(stream.fileno())
        lock_result = paths.lock.lstat()
        lock_identity = _file_identity(lock_result)
        if lock_identity[:2] != created_identity[:2]:
            raise RuntimeStoreIntegrityError("writer lock changed during acquisition")
        _directory_fsync(paths.runtime, runtime_identity)
    except Exception:
        current = _entry_lstat(paths.lock)
        if current is not None and _file_identity(current)[:2] == created_identity[:2]:
            try:
                _remove_owned_lock(
                    paths.lock,
                    runtime_identity=runtime_identity,
                    expected_identity=_file_identity(current),
                    expected_bytes=None,
                    owner_token=_owner_token(writer_id),
                )
            except RuntimeStoreIntegrityError:
                pass
        raise
    writer = RuntimeWriter(
        root=paths.root,
        runtime_directory=paths.runtime,
        run_id=run_id,
        graph_digest=graph_digest,
        authority_id=authority_id,
        controller_id=controller_id,
        writer_id=writer_id,
        _lock_bytes=encoded,
        _lock_identity=lock_identity,
        _runtime_identity=runtime_identity,
    )
    existing = _inspect_runtime_store(paths.root)
    if existing.report.status is not RuntimeStoreStatus.LOCKED:
        _remove_owned_lock(
            paths.lock,
            runtime_identity=runtime_identity,
            expected_identity=lock_identity,
            expected_bytes=encoded,
            owner_token=_owner_token(writer_id),
        )
        writer._released = True
        raise RuntimeStoreIntegrityError(
            "existing runtime store does not match requested writer: "
            f"{existing.report.status.value}"
        )
    return writer


def _verify_writer(writer: RuntimeWriter) -> _RuntimePaths:
    if type(writer) is not RuntimeWriter:
        raise RuntimeStoreIntegrityError("writer handle type is invalid")
    if writer._released:
        raise RuntimeStoreIntegrityError("writer handle has been released")
    paths = _paths(writer.root)
    if paths.runtime != writer.runtime_directory:
        raise RuntimeStoreIntegrityError("writer root binding has changed")
    _ensure_runtime_directory(paths, create=False)
    _assert_directory_identity(paths.runtime, writer._runtime_identity)
    data, identity = _read_regular_bytes(paths.lock, maximum=MAX_LOCK_BYTES)
    if identity != writer._lock_identity:
        raise RuntimeStoreIntegrityError("writer lock was replaced or modified")
    if data != writer._lock_bytes:
        raise RuntimeStoreIntegrityError("writer lock bytes no longer match")
    payload = _strict_json_loads(data, "writer lock")
    if _canonical_json_bytes(payload) != data:
        raise RuntimeStoreIntegrityError("writer lock is not canonical")
    _validate_lock_payload(payload, writer=writer)
    return paths


def release_runtime_writer(writer: RuntimeWriter) -> None:
    if type(writer) is not RuntimeWriter:
        raise RuntimeStoreIntegrityError("writer handle type is invalid")
    if writer._released:
        return
    paths = _paths(writer.root)
    _ensure_runtime_directory(paths, create=False)
    _assert_directory_identity(paths.runtime, writer._runtime_identity)
    if _entry_lstat(paths.lock) is None:
        raise RuntimeStoreIntegrityError(
            "writer lock is missing before first release"
        )
    data, identity = _read_regular_bytes(paths.lock, maximum=MAX_LOCK_BYTES)
    if identity != writer._lock_identity or data != writer._lock_bytes:
        raise RuntimeStoreIntegrityError("refusing to release an unknown writer lock")
    payload = _strict_json_loads(data, "writer lock")
    if _canonical_json_bytes(payload) != data:
        raise RuntimeStoreIntegrityError("refusing to release a malformed writer lock")
    _validate_lock_payload(payload, writer=writer)
    _remove_owned_lock(
        paths.lock,
        runtime_identity=writer._runtime_identity,
        expected_identity=writer._lock_identity,
        expected_bytes=writer._lock_bytes,
        owner_token=_owner_token(writer.writer_id),
    )
    writer._released = True


def _clock_value(clock: Callable[[], Any] | None) -> str:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeStoreIntegrityError("clock must return an aware datetime")
        text = value.isoformat()
        if text.endswith("+00:00"):
            text = text[:-6] + "Z"
        return text
    if type(value) is str:
        return value
    raise RuntimeStoreIntegrityError("clock must return RFC3339 text or datetime")


def _initial_payloads(
    writer: RuntimeWriter,
    graph: Mapping[str, Any],
    observed_at: str,
) -> tuple[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]]:
    state = {
        "schema_id": STATE_SCHEMA_ID,
        "schema_version": 1,
        "run_id": writer.run_id,
        "graph_digest": writer.graph_digest,
        "graph_generation": graph["generation"],
        "revision": 0,
        "last_event_sequence": 2,
        "run_status": "INITIALIZED",
        "authority_id": writer.authority_id,
        "controller_id": writer.controller_id,
        "node_states": [
            {
                "node_id": item["id"],
                "status": "PENDING",
                "attempt_id": None,
                "last_event_sequence": 0,
                "evidence_refs": [],
            }
            for item in graph["nodes"]
        ],
    }
    event_one = {
        "schema_id": EVENT_SCHEMA_ID,
        "schema_version": 1,
        "event_id": derive_event_id(writer.run_id, 1),
        "run_id": writer.run_id,
        "sequence": 1,
        "graph_digest": writer.graph_digest,
        "event_type": "RUN_INITIALIZED",
        "authority_id": writer.authority_id,
        "actor_id": writer.controller_id,
        "observed_at": observed_at,
        "reason_code": "RUN_CREATED",
        "evidence_refs": [],
        "artifact_refs": [],
    }
    event_two = {
        "schema_id": EVENT_SCHEMA_ID,
        "schema_version": 1,
        "event_id": derive_event_id(writer.run_id, 2),
        "run_id": writer.run_id,
        "sequence": 2,
        "graph_digest": writer.graph_digest,
        "event_type": "GRAPH_BOUND",
        "authority_id": writer.authority_id,
        "actor_id": writer.controller_id,
        "observed_at": observed_at,
        "reason_code": "GRAPH_ACCEPTED",
        "evidence_refs": [],
        "artifact_refs": [],
    }
    return state, (event_one, event_two)


def initialize_runtime_store(
    writer: RuntimeWriter,
    graph: Any,
    *,
    clock: Callable[[], Any] | None = None,
) -> RuntimeStoreInspection:
    paths = _verify_writer(writer)
    graph_digest = _validate_graph(graph)
    if graph_digest != writer.graph_digest:
        raise RuntimeStoreIntegrityError(
            "initialization graph does not match writer authority"
        )
    observed_at = _clock_value(clock)
    state, events = _initial_payloads(writer, graph, observed_at)
    validate_runtime_state(
        state,
        graph,
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        controller_id=writer.controller_id,
    )
    for event in events:
        validate_runtime_event(
            event,
            graph,
            run_id=writer.run_id,
            graph_digest=writer.graph_digest,
            authority_id=writer.authority_id,
            actor_id=writer.controller_id,
        )

    graph_bytes = _canonical_json_bytes(graph)
    if len(graph_bytes) > MAX_GRAPH_BYTES:
        raise RuntimeStoreIntegrityError("graph snapshot exceeds its size bound")
    event_bytes = b"".join(_canonical_json_bytes(event) for event in events)
    state_bytes = _canonical_json_bytes(state)
    for target in (paths.graph, paths.events, paths.state):
        if _entry_lstat(target) is not None:
            raise RuntimeStoreIntegrityError(
                f"runtime store already contains {target.name}"
            )

    owner = _owner_token(writer.writer_id)
    temporaries: list[Path] = []
    committed_any = False
    committed_state = False
    directory_results: list[bool] = []
    try:
        _verify_writer(writer)
        graph_temp = _write_temp(
            paths.graph,
            graph_bytes,
            owner,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        temporaries.append(graph_temp)
        _verify_writer(writer)
        events_temp = _write_temp(
            paths.events,
            event_bytes,
            owner,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        temporaries.append(events_temp)
        _verify_writer(writer)
        state_temp = _write_temp(
            paths.state,
            state_bytes,
            owner,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        temporaries.append(state_temp)

        _verify_writer(writer)
        _replace_file(
            graph_temp,
            paths.graph,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        committed_any = True
        temporaries.remove(graph_temp)
        _verify_writer(writer)
        _replace_file(
            events_temp,
            paths.events,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        temporaries.remove(events_temp)
        directory_results.append(
            _directory_fsync(paths.runtime, writer._runtime_identity)
        )
        _verify_writer(writer)
        _replace_file(
            state_temp,
            paths.state,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        committed_state = True
        temporaries.remove(state_temp)
        directory_results.append(
            _directory_fsync(paths.runtime, writer._runtime_identity)
        )
    except RuntimeStoreIntegrityError as exc:
        if not committed_any:
            raise
        raise RuntimeStoreIncomplete(
            f"runtime initialization did not commit completely: {exc}",
            status=(
                RuntimeStoreStatus.RECOVERY_REQUIRED
                if committed_state
                else RuntimeStoreStatus.INCOMPLETE
            ),
        ) from exc
    except Exception as exc:
        status = (
            RuntimeStoreStatus.RECOVERY_REQUIRED
            if committed_state
            else RuntimeStoreStatus.INCOMPLETE
        )
        raise RuntimeStoreIncomplete(
            f"runtime initialization did not commit completely: {exc}",
            status=status,
        ) from exc
    finally:
        for temporary in temporaries:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    details = _inspect_runtime_store(paths.root)
    if details.report.status is not RuntimeStoreStatus.LOCKED:
        raise RuntimeStoreIncomplete(
            "runtime initialization committed but consistency inspection failed",
            status=details.report.status,
        )
    directory_capability = (
        "SUPPORTED"
        if directory_results and all(directory_results)
        else "UNAVAILABLE"
    )
    return replace(
        details.report,
        capabilities=replace(
            details.report.capabilities,
            directory_fsync=directory_capability,
        ),
    )


def _parse_event_log(
    data: bytes,
    graph: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> tuple[tuple[dict[str, Any], ...], RuntimeStoreInspection | None]:
    if not data:
        return (), _issue(
            RuntimeStoreStatus.CORRUPT,
            "EVENT_LOG_EMPTY",
            "initialized event log is empty",
        )
    if not data.endswith(b"\n"):
        return (), _issue(
            RuntimeStoreStatus.RECOVERY_REQUIRED,
            "EVENT_LOG_TORN",
            "event log is not newline terminated",
        )
    raw_lines = data.splitlines(keepends=True)
    events: list[dict[str, Any]] = []
    for index, raw_line in enumerate(raw_lines):
        sequence = index + 1
        if len(raw_line) > MAX_EVENT_BYTES:
            return (), _issue(
                RuntimeStoreStatus.CORRUPT,
                "EVENT_TOO_LARGE",
                f"event line {sequence} exceeds its size bound",
            )
        try:
            event = _strict_json_loads(raw_line, f"event line {sequence}")
        except RuntimeStoreIntegrityError:
            status = (
                RuntimeStoreStatus.RECOVERY_REQUIRED
                if index == len(raw_lines) - 1
                else RuntimeStoreStatus.CORRUPT
            )
            return (), _issue(
                status,
                "EVENT_LOG_MALFORMED",
                f"event line {sequence} is malformed",
            )
        try:
            canonical = _canonical_json_bytes(event)
        except RuntimeStoreIntegrityError:
            return (), _issue(
                RuntimeStoreStatus.CORRUPT,
                "EVENT_NOT_CANONICAL",
                f"event line {sequence} is not canonical",
            )
        if canonical != raw_line:
            return (), _issue(
                RuntimeStoreStatus.CORRUPT,
                "EVENT_NOT_CANONICAL",
                f"event line {sequence} is not canonical",
            )
        if type(event) is dict:
            if event.get("run_id") != binding["run_id"]:
                return (), _issue(
                    RuntimeStoreStatus.AUTHORITY_MISMATCH,
                    "RUN_MISMATCH",
                    f"event line {sequence} has a different run",
                )
            if event.get("authority_id") != binding["authority_id"]:
                return (), _issue(
                    RuntimeStoreStatus.AUTHORITY_MISMATCH,
                    "AUTHORITY_MISMATCH",
                    f"event line {sequence} has a different authority",
                )
            if event.get("actor_id") != binding["controller_id"]:
                return (), _issue(
                    RuntimeStoreStatus.AUTHORITY_MISMATCH,
                    "ACTOR_MISMATCH",
                    f"event line {sequence} has a different controller actor",
                )
            if event.get("graph_digest") != binding["graph_digest"]:
                return (), _issue(
                    RuntimeStoreStatus.CORRUPT,
                    "EVENT_GRAPH_MISMATCH",
                    f"event line {sequence} has a different graph digest",
                )
        try:
            validate_runtime_event(
                event,
                graph,
                run_id=binding["run_id"],
                graph_digest=binding["graph_digest"],
                authority_id=binding["authority_id"],
                actor_id=binding["controller_id"],
            )
        except RuntimeStoreIntegrityError as exc:
            return (), _issue(
                RuntimeStoreStatus.CORRUPT,
                "EVENT_INVALID",
                f"event line {sequence} is invalid: {exc}",
            )
        if event["sequence"] != sequence:
            return (), _issue(
                RuntimeStoreStatus.CORRUPT,
                "EVENT_SEQUENCE_INVALID",
                f"event line {sequence} is duplicate, missing, or out of order",
            )
        events.append(event)
    return tuple(events), None


def _inspect_lock(
    paths: _RuntimePaths,
) -> tuple[dict[str, Any] | None, RuntimeStoreInspection | None]:
    if _entry_lstat(paths.lock) is None:
        return None, None
    try:
        data, _ = _read_regular_bytes(paths.lock, maximum=MAX_LOCK_BYTES)
        payload = _strict_json_loads(data, "writer lock")
        if _canonical_json_bytes(payload) != data:
            raise RuntimeStoreIntegrityError("writer lock is not canonical")
        _validate_lock_payload(payload)
        return payload, None
    except RuntimeStoreIntegrityError as exc:
        return None, _issue(
            RuntimeStoreStatus.LOCK_INTEGRITY_ERROR,
            "LOCK_INTEGRITY_ERROR",
            str(exc),
        )


def _inspect_runtime_store(
    root: str | os.PathLike[str],
) -> _InspectionData:
    paths = _paths(root)
    try:
        exists = _ensure_runtime_directory(paths, create=False)
    except RuntimeStoreIntegrityError as exc:
        return _InspectionData(
            _issue(RuntimeStoreStatus.CORRUPT, "UNSAFE_RUNTIME_PATH", str(exc))
        )
    if not exists:
        return _InspectionData(
            RuntimeStoreInspection(RuntimeStoreStatus.NOT_INITIALIZED)
        )

    lock, lock_problem = _inspect_lock(paths)
    present = {
        "graph": _entry_lstat(paths.graph) is not None,
        "state": _entry_lstat(paths.state) is not None,
        "events": _entry_lstat(paths.events) is not None,
    }
    present_count = sum(present.values())
    if present_count == 0:
        if lock_problem is not None:
            return _InspectionData(lock_problem)
        if lock is not None:
            return _InspectionData(RuntimeStoreInspection(RuntimeStoreStatus.LOCKED))
        return _InspectionData(
            RuntimeStoreInspection(RuntimeStoreStatus.NOT_INITIALIZED)
        )
    if present_count != 3:
        missing = ", ".join(sorted(name for name, value in present.items() if not value))
        return _InspectionData(
            _issue(
                RuntimeStoreStatus.INCOMPLETE,
                "STORE_INCOMPLETE",
                f"runtime store is missing: {missing}",
            )
        )

    try:
        graph_bytes, _ = _read_regular_bytes(
            paths.graph, maximum=MAX_GRAPH_BYTES
        )
        graph = _strict_json_loads(graph_bytes, "graph snapshot")
        if _canonical_json_bytes(graph) != graph_bytes:
            raise RuntimeStoreIntegrityError("graph snapshot is not canonical")
        graph_digest = _validate_graph(graph)
    except RuntimeStoreIntegrityError as exc:
        return _InspectionData(
            _issue(RuntimeStoreStatus.CORRUPT, "GRAPH_INVALID", str(exc))
        )

    try:
        state_bytes, _ = _read_regular_bytes(
            paths.state, maximum=MAX_STATE_BYTES
        )
        state = _strict_json_loads(state_bytes, "runtime state")
        if _canonical_json_bytes(state) != state_bytes:
            raise RuntimeStoreIntegrityError("runtime state is not canonical")
        validate_runtime_state(
            state,
            graph,
            graph_digest=graph_digest,
        )
    except RuntimeStoreIntegrityError as exc:
        return _InspectionData(
            _issue(RuntimeStoreStatus.CORRUPT, "STATE_INVALID", str(exc)),
            graph=graph,
        )

    try:
        event_bytes, _ = _read_regular_bytes(
            paths.events, maximum=MAX_EVENTS_BYTES
        )
    except RuntimeStoreIntegrityError as exc:
        return _InspectionData(
            _issue(RuntimeStoreStatus.CORRUPT, "EVENT_LOG_UNSAFE", str(exc)),
            graph=graph,
            state=state,
        )
    events, event_problem = _parse_event_log(event_bytes, graph, state)
    if event_problem is not None:
        return _InspectionData(
            event_problem,
            graph=graph,
            state=state,
            event_bytes=event_bytes,
        )
    if len(events) < 2 or [events[0]["event_type"], events[1]["event_type"]] != [
        "RUN_INITIALIZED",
        "GRAPH_BOUND",
    ]:
        return _InspectionData(
            _issue(
                RuntimeStoreStatus.CORRUPT,
                "INITIAL_EVENTS_INVALID",
                "event log does not begin with the required initialization events",
            ),
            graph=graph,
            state=state,
            events=events,
            event_bytes=event_bytes,
        )
    if state["last_event_sequence"] < len(events):
        return _InspectionData(
            _issue(
                RuntimeStoreStatus.RECOVERY_REQUIRED,
                "STATE_BEHIND_EVENTS",
                "event log is ahead of the committed state",
            ),
            graph=graph,
            state=state,
            events=events,
            event_bytes=event_bytes,
        )
    if state["last_event_sequence"] > len(events):
        return _InspectionData(
            _issue(
                RuntimeStoreStatus.CORRUPT,
                "STATE_AHEAD_OF_EVENTS",
                "committed state refers to missing events",
            ),
            graph=graph,
            state=state,
            events=events,
            event_bytes=event_bytes,
        )
    try:
        _validate_history_consistency(graph, state, events)
    except RuntimeStoreIntegrityError as exc:
        return _InspectionData(
            _issue(
                RuntimeStoreStatus.CORRUPT,
                "HISTORY_STATE_INCONSISTENT",
                str(exc),
            ),
            graph=graph,
            state=state,
            events=events,
            event_bytes=event_bytes,
        )

    if lock_problem is not None:
        return _InspectionData(
            lock_problem,
            graph=graph,
            state=state,
            events=events,
            event_bytes=event_bytes,
        )
    if lock is not None:
        expected_lock_binding = (
            state["run_id"],
            state["graph_digest"],
            state["authority_id"],
            state["controller_id"],
        )
        actual_lock_binding = (
            lock["run_id"],
            lock["graph_digest"],
            lock["authority_id"],
            lock["controller_id"],
        )
        if actual_lock_binding != expected_lock_binding:
            return _InspectionData(
                _issue(
                    RuntimeStoreStatus.LOCK_INTEGRITY_ERROR,
                    "LOCK_INTEGRITY_ERROR",
                    "writer lock does not match the committed store",
                ),
                graph=graph,
                state=state,
                events=events,
                event_bytes=event_bytes,
            )
        status = RuntimeStoreStatus.LOCKED
    else:
        status = RuntimeStoreStatus.VALID
    return _InspectionData(
        RuntimeStoreInspection(status),
        graph=graph,
        state=state,
        events=events,
        event_bytes=event_bytes,
    )


def inspect_runtime_store(
    root: str | os.PathLike[str],
) -> RuntimeStoreInspection:
    return _inspect_runtime_store(root).report


_RUN_EVENT_STATUSES = {
    "RUN_STARTED": "RUNNING",
    "RUN_HANDOFF": "HANDOFF",
    "RUN_BLOCKED": "BLOCKED",
    "RUN_COMPLETED": "COMPLETED",
    "RUN_CANCELLED": "CANCELLED",
    "RECOVERY_STARTED": "RECOVERING",
}
_EVENT_OPTIONAL_FIELDS = {
    "RUN_INITIALIZED": frozenset({"duration_ms"}),
    "GRAPH_BOUND": frozenset({"duration_ms"}),
    "RUN_STARTED": frozenset({"duration_ms"}),
    "RUN_HANDOFF": frozenset({"duration_ms"}),
    "RUN_BLOCKED": frozenset({"duration_ms"}),
    "RUN_COMPLETED": frozenset({"duration_ms"}),
    "RUN_CANCELLED": frozenset({"duration_ms"}),
    "RECOVERY_STARTED": frozenset({"duration_ms"}),
    "RECOVERY_COMPLETED": frozenset({"duration_ms"}),
    "NODE_READY": frozenset(
        {"node_id", "previous_status", "next_status", "duration_ms"}
    ),
    "NODE_STARTED": frozenset(
        {
            "node_id",
            "attempt_id",
            "previous_status",
            "next_status",
            "duration_ms",
        }
    ),
    "NODE_WAITING_RESOURCE": frozenset(
        {"node_id", "previous_status", "next_status", "duration_ms"}
    ),
    "NODE_RESULT_RECORDED": frozenset(
        {"node_id", "attempt_id", "result_digest", "duration_ms"}
    ),
    "NODE_TRANSITIONED": frozenset(
        {
            "node_id",
            "attempt_id",
            "previous_status",
            "next_status",
            "duration_ms",
        }
    ),
}


def _append_unique_references(
    existing: list[str],
    additions: list[str],
) -> list[str]:
    result = list(existing)
    seen = set(result)
    for item in additions:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _require_transition(
    previous: str,
    next_status: str,
) -> None:
    decision = validate_node_transition(previous, next_status)
    if not decision.allowed:
        raise RuntimeStoreIntegrityError(
            f"node transition is not allowed: {decision.reason}"
        )


def _expected_state_after_event(
    current: Mapping[str, Any],
    event: Mapping[str, Any],
    attempt_counts: dict[str, int],
) -> dict[str, Any]:
    event_type = event["event_type"]
    optional = frozenset(event) - _EVENT_REQUIRED_FIELDS
    allowed_optional = _EVENT_OPTIONAL_FIELDS[event_type]
    unexpected = sorted(optional - allowed_optional)
    if unexpected:
        raise RuntimeStoreIntegrityError(
            f"{event_type} carries unrelated optional fields: {unexpected}"
        )

    expected = copy.deepcopy(current)
    expected["revision"] += 1
    expected["last_event_sequence"] = event["sequence"]
    if event_type in _RUN_EVENT_STATUSES:
        expected["run_status"] = _RUN_EVENT_STATUSES[event_type]
    if event_type == "RECOVERY_STARTED":
        expected["recovery_status"] = "IN_PROGRESS"
    elif event_type == "RECOVERY_COMPLETED":
        expected["recovery_status"] = "RECOVERED"
    if event_type in {"RUN_INITIALIZED", "GRAPH_BOUND"}:
        raise RuntimeStoreIntegrityError(
            "initialization events cannot be appended after initialization"
        )

    if event_type not in _NODE_SCOPED_EVENTS:
        return expected

    node_id = event["node_id"]
    node_states = {
        item["node_id"]: item for item in expected["node_states"]
    }
    node_state = node_states[node_id]
    previous = node_state["status"]
    next_status: str | None = None
    if event_type == "NODE_READY":
        next_status = "READY"
    elif event_type == "NODE_STARTED":
        next_status = "RUNNING"
        next_attempt_number = attempt_counts[node_id] + 1
        expected_attempt = derive_attempt_id(
            event["run_id"],
            node_id,
            next_attempt_number,
        )
        if event["attempt_id"] != expected_attempt:
            raise RuntimeStoreIntegrityError(
                "NODE_STARTED attempt identity is not the next derived attempt"
            )
        attempt_counts[node_id] = next_attempt_number
        node_state["attempt_id"] = expected_attempt
    elif event_type == "NODE_WAITING_RESOURCE":
        next_status = "WAITING_RESOURCE"
    elif event_type == "NODE_TRANSITIONED":
        if event["previous_status"] != previous:
            raise RuntimeStoreIntegrityError(
                "transition previous status does not match observed state"
            )
        next_status = event["next_status"]
        event_attempt = event.get("attempt_id")
        if event_attempt is not None:
            if node_state["attempt_id"] is None:
                next_attempt_number = attempt_counts[node_id] + 1
                expected_attempt = derive_attempt_id(
                    event["run_id"],
                    node_id,
                    next_attempt_number,
                )
                if event_attempt != expected_attempt:
                    raise RuntimeStoreIntegrityError(
                        "transition attempt is not the next derived attempt"
                    )
                attempt_counts[node_id] = next_attempt_number
                node_state["attempt_id"] = event_attempt
            elif event_attempt != node_state["attempt_id"]:
                raise RuntimeStoreIntegrityError(
                    "transition attempt does not match active attempt"
                )
        if (
            next_status in _ATTEMPT_REQUIRED_STATUSES
            and node_state["attempt_id"] is None
        ):
            raise RuntimeStoreIntegrityError(
                f"{next_status} transition requires a bound attempt"
            )
    elif event_type == "NODE_RESULT_RECORDED":
        if node_state["attempt_id"] != event["attempt_id"]:
            raise RuntimeStoreIntegrityError(
                "result event does not match the active attempt"
            )
        node_state["result_digest"] = event["result_digest"]

    if next_status is not None:
        if "previous_status" in event and event["previous_status"] != previous:
            raise RuntimeStoreIntegrityError(
                "event previous status does not match observed state"
            )
        if "next_status" in event and event["next_status"] != next_status:
            raise RuntimeStoreIntegrityError(
                "event next status does not match its event type"
            )
        _require_transition(previous, next_status)
        node_state["status"] = next_status

    node_state["last_event_sequence"] = event["sequence"]
    node_state["evidence_refs"] = _append_unique_references(
        node_state["evidence_refs"],
        event["evidence_refs"],
    )
    return expected


def _initial_expected_state(
    graph: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_id": STATE_SCHEMA_ID,
        "schema_version": 1,
        "run_id": binding["run_id"],
        "graph_digest": binding["graph_digest"],
        "graph_generation": graph["generation"],
        "revision": 0,
        "last_event_sequence": 2,
        "run_status": "INITIALIZED",
        "authority_id": binding["authority_id"],
        "controller_id": binding["controller_id"],
        "node_states": [
            {
                "node_id": item["id"],
                "status": "PENDING",
                "attempt_id": None,
                "last_event_sequence": 0,
                "evidence_refs": [],
            }
            for item in graph["nodes"]
        ],
    }


def _validate_history_consistency(
    graph: Mapping[str, Any],
    state: Mapping[str, Any],
    events: tuple[Mapping[str, Any], ...],
) -> tuple[dict[str, Any], dict[str, int]]:
    expected, attempt_counts, _, _ = _replay_event_history(
        graph,
        events,
        run_id=state["run_id"],
        graph_digest=state["graph_digest"],
        authority_id=state["authority_id"],
        controller_id=state["controller_id"],
    )
    if _canonical_json_bytes(expected) != _canonical_json_bytes(state):
        raise RuntimeStoreIntegrityError(
            "committed state is not the exact event-supported snapshot"
        )
    return expected, attempt_counts


def _replay_event_history(
    graph: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    graph_digest: str,
    authority_id: str,
    controller_id: str,
) -> tuple[dict[str, Any], dict[str, int], bool, bool]:
    """Return the one canonical state projection for a complete event history."""

    actual_graph_digest = _validate_graph(graph)
    if actual_graph_digest != graph_digest:
        raise RuntimeStoreIntegrityError(
            "replay graph does not match the expected graph digest"
        )
    binding = {
        "run_id": run_id,
        "graph_digest": graph_digest,
        "authority_id": authority_id,
        "controller_id": controller_id,
    }
    if len(events) < 2:
        raise RuntimeStoreIntegrityError(
            "event history lacks initialization records"
        )
    for expected_sequence, event in enumerate(events, start=1):
        validate_runtime_event(
            event,
            graph,
            run_id=run_id,
            graph_digest=graph_digest,
            authority_id=authority_id,
            actor_id=controller_id,
        )
        if event["sequence"] != expected_sequence:
            raise RuntimeStoreIntegrityError(
                "event history sequence is duplicate, missing, or out of order"
            )
    initial_expectations = (
        ("RUN_INITIALIZED", "RUN_CREATED"),
        ("GRAPH_BOUND", "GRAPH_ACCEPTED"),
    )
    for event, (event_type, reason_code) in zip(
        events[:2], initial_expectations
    ):
        if (
            event["event_type"] != event_type
            or event["reason_code"] != reason_code
            or event["evidence_refs"]
            or event["artifact_refs"]
            or frozenset(event) != _EVENT_REQUIRED_FIELDS
        ):
            raise RuntimeStoreIntegrityError(
                "initialization event facts are not exact"
            )

    expected = _initial_expected_state(graph, binding)
    attempt_counts = {item["id"]: 0 for item in graph["nodes"]}
    recovery_in_progress = False
    recovery_completed = False
    pre_recovery_run_status: str | None = None
    for event in events[2:]:
        if event["event_type"] == "RECOVERY_STARTED":
            if recovery_in_progress:
                raise RuntimeStoreIntegrityError(
                    "recovery start cannot be nested or duplicated"
                )
            recovery_in_progress = True
            pre_recovery_run_status = expected["run_status"]
        elif event["event_type"] == "RECOVERY_COMPLETED":
            if not recovery_in_progress:
                raise RuntimeStoreIntegrityError(
                    "recovery completion has no matching start"
                )
            recovery_in_progress = False
            recovery_completed = True
        expected = _expected_state_after_event(
            expected,
            event,
            attempt_counts,
        )
        if event["event_type"] == "RECOVERY_COMPLETED":
            if pre_recovery_run_status is None:
                raise RuntimeStoreIntegrityError(
                    "recovery completion lacks a prior run status"
                )
            expected["run_status"] = pre_recovery_run_status
            pre_recovery_run_status = None
    validate_runtime_state(
        expected,
        graph,
        run_id=run_id,
        graph_digest=graph_digest,
        authority_id=authority_id,
        controller_id=controller_id,
    )
    return expected, attempt_counts, recovery_in_progress, recovery_completed


def _validate_state_update(
    writer: RuntimeWriter,
    graph: Mapping[str, Any],
    current: Mapping[str, Any],
    history: tuple[Mapping[str, Any], ...],
    event: Mapping[str, Any],
    updated: Mapping[str, Any],
) -> None:
    _validate_history_consistency(
        graph,
        current,
        history,
    )
    expected, _, _, _ = _replay_event_history(
        graph,
        history + (event,),
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        controller_id=writer.controller_id,
    )
    if _canonical_json_bytes(expected) != _canonical_json_bytes(updated):
        raise RuntimeStoreIntegrityError(
            "updated state contains fields not supported by the event"
        )
    if event["run_id"] != writer.run_id:
        raise RuntimeStoreIntegrityError("event run does not match writer")
    if event["graph_digest"] != writer.graph_digest:
        raise RuntimeStoreIntegrityError("event graph does not match writer")
    if event["authority_id"] != writer.authority_id:
        raise RuntimeStoreIntegrityError("event authority does not match writer")
    if event["actor_id"] != writer.controller_id:
        raise RuntimeStoreIntegrityError("event actor does not match writer controller")


def _append_event_bytes(
    path: Path,
    payload: bytes,
    *,
    expected_directory_identity: tuple[int, int] | None = None,
    writer: RuntimeWriter | None = None,
) -> None:
    if writer is not None:
        _verify_writer(writer)
    if expected_directory_identity is not None:
        _assert_directory_identity(path.parent, expected_directory_identity)
    before = _entry_lstat(path)
    if before is None or _is_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise RuntimeStoreIntegrityError("event log is not a safe regular file")
    if before.st_nlink != 1:
        raise RuntimeStoreIntegrityError("event log has an unsafe hard-link count")
    flags = os.O_WRONLY | os.O_APPEND
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if _file_identity(opened)[:3] != _file_identity(before)[:3]:
            raise RuntimeStoreIntegrityError("event log changed while opening")
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise OSError("event append was incomplete")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def append_runtime_event(
    writer: RuntimeWriter,
    event: Any,
    updated_state: Any,
) -> RuntimeStoreInspection:
    paths = _verify_writer(writer)
    details = _inspect_runtime_store(paths.root)
    if details.report.status is not RuntimeStoreStatus.LOCKED:
        if details.report.status is RuntimeStoreStatus.RECOVERY_REQUIRED:
            raise RuntimeStoreIncomplete(
                "runtime store requires recovery before mutation",
                status=RuntimeStoreStatus.RECOVERY_REQUIRED,
            )
        raise RuntimeStoreIntegrityError(
            f"runtime store is not safely mutable: {details.report.status.value}"
        )
    if details.graph is None or details.state is None or details.event_bytes is None:
        raise RuntimeStoreIntegrityError("runtime inspection omitted required data")
    graph = details.graph
    current = details.state
    validate_runtime_event(
        event,
        graph,
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        actor_id=writer.controller_id,
    )
    validate_runtime_state(
        updated_state,
        graph,
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        controller_id=writer.controller_id,
    )
    if event["sequence"] != current["last_event_sequence"] + 1:
        raise RuntimeStoreIntegrityError("event sequence must be exactly last plus one")
    if event["event_id"] != derive_event_id(writer.run_id, event["sequence"]):
        raise RuntimeStoreIntegrityError("event identity does not match next sequence")
    _validate_state_update(
        writer,
        graph,
        current,
        details.events,
        event,
        updated_state,
    )
    event_bytes = _canonical_json_bytes(event)
    if len(event_bytes) > MAX_EVENT_BYTES:
        raise RuntimeStoreIntegrityError("runtime event exceeds its size bound")
    state_bytes = _canonical_json_bytes(updated_state)

    owner = _owner_token(writer.writer_id)
    state_temp: Path | None = None
    event_appended = False
    directory_results: list[bool] = []
    try:
        state_temp = _write_temp(
            paths.state,
            state_bytes,
            owner,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        _verify_writer(writer)
        current_event_bytes, _ = _read_regular_bytes(
            paths.events, maximum=MAX_EVENTS_BYTES
        )
        if current_event_bytes != details.event_bytes:
            raise RuntimeStoreIntegrityError(
                "event log changed after consistency inspection"
            )
        if len(current_event_bytes) + len(event_bytes) > MAX_EVENTS_BYTES:
            raise RuntimeStoreIntegrityError(
                "event log would exceed its total size bound"
            )
        event_appended = True
        _append_event_bytes(
            paths.events,
            event_bytes,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        _verify_writer(writer)
        _replace_file(
            state_temp,
            paths.state,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        state_temp = None
        directory_results.append(
            _directory_fsync(paths.runtime, writer._runtime_identity)
        )
    except RuntimeStoreIntegrityError as exc:
        if not event_appended:
            raise
        raise RuntimeStoreIncomplete(
            f"runtime event mutation did not commit completely: {exc}",
            status=RuntimeStoreStatus.RECOVERY_REQUIRED,
        ) from exc
    except Exception as exc:
        status = (
            RuntimeStoreStatus.RECOVERY_REQUIRED
            if event_appended
            else RuntimeStoreStatus.INCOMPLETE
        )
        raise RuntimeStoreIncomplete(
            f"runtime event mutation did not commit completely: {exc}",
            status=status,
        ) from exc
    finally:
        if state_temp is not None:
            try:
                state_temp.unlink()
            except FileNotFoundError:
                pass

    result = _inspect_runtime_store(paths.root)
    if result.report.status is not RuntimeStoreStatus.LOCKED:
        raise RuntimeStoreIncomplete(
            "runtime mutation committed but consistency inspection failed",
            status=result.report.status,
        )
    directory_capability = (
        "SUPPORTED"
        if directory_results and all(directory_results)
        else "UNAVAILABLE"
    )
    return replace(
        result.report,
        capabilities=replace(
            result.report.capabilities,
            directory_fsync=directory_capability,
        ),
    )


def _commit_runtime_recovery(
    writer: RuntimeWriter,
    *,
    expected_graph_bytes: bytes,
    expected_state_bytes: bytes | None,
    expected_event_bytes: bytes,
    recovery_events: Sequence[Mapping[str, Any]],
    recovered_state: Mapping[str, Any],
) -> RuntimeStoreInspection:
    """Commit a pre-assessed recovery with append-only, state-last ordering."""

    paths = _verify_writer(writer)
    graph_bytes, _ = _read_regular_bytes(paths.graph, maximum=MAX_GRAPH_BYTES)
    if graph_bytes != expected_graph_bytes:
        raise RuntimeStoreIntegrityError("graph changed after recovery assessment")
    event_bytes, _ = _read_regular_bytes(paths.events, maximum=MAX_EVENTS_BYTES)
    if event_bytes != expected_event_bytes:
        raise RuntimeStoreIntegrityError("events changed after recovery assessment")
    state_entry = _entry_lstat(paths.state)
    if expected_state_bytes is None:
        if state_entry is not None:
            raise RuntimeStoreIntegrityError("state changed after recovery assessment")
    else:
        state_bytes, _ = _read_regular_bytes(paths.state, maximum=MAX_STATE_BYTES)
        if state_bytes != expected_state_bytes:
            raise RuntimeStoreIntegrityError("state changed after recovery assessment")

    graph = _strict_json_loads(graph_bytes, "graph snapshot")
    binding = {
        "run_id": writer.run_id,
        "graph_digest": writer.graph_digest,
        "authority_id": writer.authority_id,
        "controller_id": writer.controller_id,
    }
    history, event_problem = _parse_event_log(event_bytes, graph, binding)
    if event_problem is not None:
        raise RuntimeStoreIntegrityError(
            f"event history is not recoverable: {event_problem.issues[0].code}"
        )
    combined = tuple(history) + tuple(copy.deepcopy(list(recovery_events)))
    expected, _, _, _ = _replay_event_history(
        graph,
        combined,
        run_id=writer.run_id,
        graph_digest=writer.graph_digest,
        authority_id=writer.authority_id,
        controller_id=writer.controller_id,
    )
    if _canonical_json_bytes(expected) != _canonical_json_bytes(recovered_state):
        raise RuntimeStoreIntegrityError(
            "recovery state is not the canonical event projection"
        )
    state_payload = _canonical_json_bytes(recovered_state)
    event_payloads = tuple(
        _canonical_json_bytes(event) for event in recovery_events
    )
    if len(event_bytes) + sum(map(len, event_payloads)) > MAX_EVENTS_BYTES:
        raise RuntimeStoreIntegrityError(
            "recovery events would exceed the event log size bound"
        )

    owner = _owner_token(writer.writer_id)
    state_temp: Path | None = None
    append_attempted = False
    committed_event_bytes = event_bytes
    try:
        state_temp = _write_temp(
            paths.state,
            state_payload,
            owner,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        _verify_writer(writer)
        current_graph_bytes, _ = _read_regular_bytes(
            paths.graph, maximum=MAX_GRAPH_BYTES
        )
        current_event_bytes, _ = _read_regular_bytes(
            paths.events, maximum=MAX_EVENTS_BYTES
        )
        if (
            current_graph_bytes != expected_graph_bytes
            or current_event_bytes != expected_event_bytes
        ):
            raise RuntimeStoreIntegrityError(
                "graph or events changed during recovery preparation"
            )
        for payload in event_payloads:
            _verify_writer(writer)
            current_event_bytes, _ = _read_regular_bytes(
                paths.events, maximum=MAX_EVENTS_BYTES
            )
            if current_event_bytes != committed_event_bytes:
                raise RuntimeStoreIntegrityError(
                    "events changed during recovery commit"
                )
            append_attempted = True
            _append_event_bytes(
                paths.events,
                payload,
                expected_directory_identity=writer._runtime_identity,
                writer=writer,
            )
            committed_event_bytes += payload
        _verify_writer(writer)
        final_graph_bytes, _ = _read_regular_bytes(
            paths.graph, maximum=MAX_GRAPH_BYTES
        )
        final_event_bytes, _ = _read_regular_bytes(
            paths.events, maximum=MAX_EVENTS_BYTES
        )
        if (
            final_graph_bytes != expected_graph_bytes
            or final_event_bytes != committed_event_bytes
        ):
            raise RuntimeStoreIntegrityError(
                "graph or events changed before recovery state commit"
            )
        final_state_entry = _entry_lstat(paths.state)
        if expected_state_bytes is None:
            if final_state_entry is not None:
                raise RuntimeStoreIntegrityError(
                    "state changed before recovery state commit"
                )
        else:
            final_state_bytes, _ = _read_regular_bytes(
                paths.state,
                maximum=MAX_STATE_BYTES,
            )
            if final_state_bytes != expected_state_bytes:
                raise RuntimeStoreIntegrityError(
                    "state changed before recovery state commit"
                )
        _replace_file(
            state_temp,
            paths.state,
            expected_directory_identity=writer._runtime_identity,
            writer=writer,
        )
        state_temp = None
        _directory_fsync(paths.runtime, writer._runtime_identity)
    except Exception as exc:
        if isinstance(exc, RuntimeStoreIncomplete):
            raise
        if append_attempted or isinstance(exc, OSError):
            raise RuntimeStoreIncomplete(
                f"runtime recovery did not commit completely: {exc}",
                status=RuntimeStoreStatus.RECOVERY_REQUIRED,
            ) from exc
        raise
    finally:
        if state_temp is not None:
            try:
                state_temp.unlink()
            except FileNotFoundError:
                pass

    result = _inspect_runtime_store(paths.root)
    if result.report.status is not RuntimeStoreStatus.LOCKED:
        raise RuntimeStoreIncomplete(
            "runtime recovery committed but consistency inspection failed",
            status=result.report.status,
        )
    return result.report


__all__ = [
    "RuntimeStoreBusy",
    "RuntimeStoreError",
    "RuntimeStoreIncomplete",
    "RuntimeStoreInspection",
    "RuntimeStoreIntegrityError",
    "RuntimeStoreStatus",
    "RuntimeWriter",
    "acquire_runtime_writer",
    "append_runtime_event",
    "derive_attempt_id",
    "derive_event_id",
    "derive_run_id",
    "initialize_runtime_store",
    "inspect_runtime_store",
    "release_runtime_writer",
    "validate_runtime_event",
    "validate_runtime_state",
]
