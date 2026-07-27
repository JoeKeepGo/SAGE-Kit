from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Callable

from .graph_contract import validate_graph_contract


GRAPH_EVOLUTION_SCHEMA_VERSION = 1
GRAPH_EVOLUTION_OPERATIONS = (
    "ADD_CORRECTIVE",
    "ADD_VERIFICATION",
    "ADD_INVESTIGATION",
    "SPLIT_PENDING",
    "DISABLE_OPTIONAL_PENDING",
    "NO_CHANGE",
)
STAGE5_LINEAGE_CONTRACT_SHA256 = (
    "07855701085c5822e174f4f9220f2c8aa8b44c0497f06f854a91a5222f164bdc"
)

_OPERATIONS = frozenset(GRAPH_EVOLUTION_OPERATIONS)
_MUTATING_OPERATIONS = _OPERATIONS - {"NO_CHANGE"}
_CHANGE_CLASSES = frozenset({"C0", "C1", "C2", "C3"})
_PERMISSIONS = frozenset(
    {
        "READ_ONLY_REVIEW",
        "WRITE_AUTHORIZED",
        "CORRECTIVE_AUTHORIZED",
        "ENVIRONMENT_WRITE_AUTHORIZED",
        "SUBMIT_AUTHORIZED",
    }
)
_REASON_CODES = frozenset(
    {
        "OBSERVED_FAILURE",
        "VERIFICATION_GAP",
        "BLOCKING_UNCERTAINTY",
        "NODE_TOO_BROAD",
        "OPTIONAL_NODE_NO_LONGER_DECISIVE",
        "EXISTING_GRAPH_SUFFICIENT",
        "NO_PROGRESS",
        "AUTHORITY_CHANGE_REQUIRED",
        "WITHIN_PREAUTHORIZATION",
        "EVALUATOR_REJECTED",
        "BUDGET_EXHAUSTED",
        "CONTRACT_CHANGED",
    }
)
_STOP_CONDITIONS = frozenset(
    {
        "BUDGET_EXHAUSTED",
        "NO_PROGRESS",
        "EVALUATOR_REJECTED",
        "AUTHORITY_CHANGED",
        "CONTRACT_CHANGED",
        "PERMISSION_EXPANSION",
        "GATE_OR_VERIFIER_REMOVAL",
    }
)
_SCHEMA_IDS = {
    "request": "urn:sagekit:graph-evolution:v1:request",
    "preauthorization": "urn:sagekit:graph-evolution:v1:preauthorization",
    "proposal": "urn:sagekit:graph-evolution:v1:proposal",
    "acceptance": "urn:sagekit:graph-evolution:v1:acceptance",
    "result": "urn:sagekit:graph-evolution:v1:result",
    "error": "urn:sagekit:graph-evolution:v1:error",
}
_DOMAINS = {
    kind: f"sagekit-graph-evolution-{kind}-v1\0".encode("utf-8")
    for kind in _SCHEMA_IDS
}
_MAX_CANONICAL_BYTES = {
    "request": 1024 * 1024,
    "preauthorization": 1024 * 1024,
    "proposal": 8 * 1024 * 1024,
    "acceptance": 1024 * 1024,
    "result": 1024 * 1024,
    "error": 1024 * 1024,
}
_MAX_REFERENCES = 100
_MAX_PATHS = 100
_MAX_ALLOWLIST_ITEMS = 1000
_MAX_ISSUES = 100
_MAX_ID_LENGTH = 256
_MAX_REFERENCE_LENGTH = 512
_MAX_PATH_LENGTH = 512
_MAX_GENERATION_BUDGET = 100
_MAX_OPERATION_BUDGET = 100
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MACHINE_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_LOCATION = re.compile(
    r"^\$(?:(?:\.[A-Za-z_][A-Za-z0-9_]*)|\[[0-9]{1,7}\])*$"
)
_URI_OR_ROOT = re.compile(
    r"^(?:[A-Za-z]:|[/\\]|[A-Za-z][A-Za-z0-9+.-]*:)",
)

_COMMON_FIELDS = frozenset(
    {
        "operation",
        "graph_id",
        "parent_generation",
        "parent_graph_digest",
        "authority",
        "proposer",
        "node_id",
        "change_class",
        "reason_code",
        "evidence_refs",
        "decision_refs",
        "affected_paths",
        "stage5_lineage_digest",
    }
)
_REQUEST_FIELDS = _COMMON_FIELDS | {
    "schema_id",
    "schema_version",
    "request_id",
}
_OPERATION_CONTEXT_FIELDS = frozenset(
    {"finding_ref", "root_cause_ref", "subject_status"}
)
_REQUEST_ALLOWED_FIELDS = _REQUEST_FIELDS | _OPERATION_CONTEXT_FIELDS
_PREAUTHORIZATION_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "preauthorization_id",
        "graph_id",
        "parent_generation",
        "parent_graph_digest",
        "authority",
        "allowed_operations",
        "allowed_change_classes",
        "allowed_node_ids",
        "allowed_roles",
        "allowed_permissions",
        "allowed_paths",
        "generation_budget",
        "operation_budgets",
        "evaluator",
        "stop_conditions",
    }
)
_PROPOSAL_REQUIRED_FIELDS = _REQUEST_FIELDS | {
    "proposal_id",
    "request_digest",
    "preauthorization_digest",
}
_PROPOSAL_ALLOWED_FIELDS = (
    _PROPOSAL_REQUIRED_FIELDS | _OPERATION_CONTEXT_FIELDS
)
_PROPOSAL_TARGET_FIELDS = frozenset(
    {"target_generation", "target_graph", "target_graph_digest"}
)
_ACCEPTANCE_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "acceptance_id",
        "proposal_digest",
        "preauthorization_digest",
        "decision",
        "authority",
        "evaluator",
        "reason_code",
        "decision_refs",
    }
)
_RESULT_REQUIRED_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "request_digest",
        "preauthorization_digest",
        "proposal_digest",
        "acceptance_digest",
        "operation",
        "outcome",
        "graph_id",
        "parent_generation",
        "parent_graph_digest",
        "message_code",
    }
)
_RESULT_TARGET_FIELDS = frozenset(
    {"target_generation", "target_graph_digest"}
)
_ERROR_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "error_code",
        "message_code",
        "document_kind",
        "document_digest",
        "issues",
    }
)
_ERROR_CODES = frozenset(
    {
        "INPUT_INVALID",
        "INPUT_TOO_LARGE",
        "GRAPH_INVALID",
        "GRAPH_BINDING_MISMATCH",
        "RESULT_ERROR_EXCLUSIVITY",
    }
)
_ERROR_MESSAGES = {
    "INPUT_INVALID": "STRICT_DOCUMENT_REQUIRED",
    "INPUT_TOO_LARGE": "DOCUMENT_BYTE_BUDGET_EXCEEDED",
    "GRAPH_INVALID": "VALID_TARGET_GRAPH_REQUIRED",
    "GRAPH_BINDING_MISMATCH": "TARGET_GRAPH_BINDING_REQUIRED",
    "RESULT_ERROR_EXCLUSIVITY": "EXACTLY_ONE_OUTCOME_REQUIRED",
}


@dataclass(frozen=True, order=True)
class GraphEvolutionValidationIssue:
    """One bounded machine-readable contract validation issue."""

    location: str
    issue_code: str

    def as_dict(self) -> dict[str, str]:
        return {
            "issue_code": self.issue_code,
            "location": self.location,
        }


@dataclass(frozen=True)
class GraphEvolutionValidationResult:
    """Pure validation result with a digest only for a valid document."""

    valid: bool
    issues: tuple[GraphEvolutionValidationIssue, ...]
    digest: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "issues": [issue.as_dict() for issue in self.issues],
            "valid": self.valid,
        }


class GraphEvolutionContractError(ValueError):
    """Raised when a canonical digest is requested for an invalid document."""

    def __init__(
        self,
        kind: str,
        issues: tuple[GraphEvolutionValidationIssue, ...] = (),
    ) -> None:
        self.kind = kind
        self.issues = issues
        summary = ", ".join(
            f"{issue.issue_code}@{issue.location}" for issue in issues[:5]
        )
        if not summary:
            summary = "unsupported document kind"
        super().__init__(f"graph evolution {kind!r} is invalid: {summary}")


class _StrictDocumentError(ValueError):
    pass


class _DuplicateNameError(ValueError):
    pass


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise _DuplicateNameError(key)
        output[key] = value
    return output


def _normalize_json(value: Any, active: set[int] | None = None) -> Any:
    if active is None:
        active = set()
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        raise _StrictDocumentError("non-integer number")
    if type(value) is str:
        output: list[str] = []
        index = 0
        while index < len(value):
            codepoint = ord(value[index])
            if 0xD800 <= codepoint <= 0xDBFF:
                if index + 1 >= len(value):
                    raise _StrictDocumentError("unpaired surrogate")
                low = ord(value[index + 1])
                if not 0xDC00 <= low <= 0xDFFF:
                    raise _StrictDocumentError("unpaired surrogate")
                output.append(
                    chr(0x10000 + ((codepoint - 0xD800) << 10) + low - 0xDC00)
                )
                index += 2
                continue
            if 0xDC00 <= codepoint <= 0xDFFF:
                raise _StrictDocumentError("unpaired surrogate")
            output.append(value[index])
            index += 1
        return "".join(output)
    if type(value) not in (dict, list):
        raise _StrictDocumentError("non-JSON value")
    identity = id(value)
    if identity in active:
        raise _StrictDocumentError("cyclic value")
    active.add(identity)
    try:
        if type(value) is list:
            return [_normalize_json(item, active) for item in value]
        output_object: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise _StrictDocumentError("non-string object name")
            normalized_key = _normalize_json(key, active)
            if normalized_key in output_object:
                raise _StrictDocumentError("duplicate normalized object name")
            output_object[normalized_key] = _normalize_json(item, active)
        return output_object
    finally:
        active.remove(identity)


def _parse_document(value: Any) -> dict[str, Any]:
    if type(value) in (str, bytes, bytearray):
        try:
            text = (
                bytes(value).decode("utf-8")
                if type(value) in (bytes, bytearray)
                else value
            )
            value = json.loads(
                text,
                object_pairs_hook=_object_pairs,
                parse_float=lambda _value: (_ for _ in ()).throw(
                    _StrictDocumentError("non-integer number")
                ),
                parse_constant=lambda _value: (_ for _ in ()).throw(
                    _StrictDocumentError("non-finite number")
                ),
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            _DuplicateNameError,
            _StrictDocumentError,
            ValueError,
        ) as exc:
            raise _StrictDocumentError("strict JSON required") from exc
    normalized = _normalize_json(value)
    if type(normalized) is not dict:
        raise _StrictDocumentError("top-level object required")
    return normalized


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise _StrictDocumentError("canonical JSON required") from exc


def _issue(
    location: str,
    issue_code: str,
) -> GraphEvolutionValidationIssue:
    if _LOCATION.fullmatch(location) is None:
        location = "$"
    return GraphEvolutionValidationIssue(location, issue_code)


def _result(
    issues: list[GraphEvolutionValidationIssue],
    *,
    kind: str | None = None,
    document: dict[str, Any] | None = None,
) -> GraphEvolutionValidationResult:
    ordered = tuple(sorted(set(issues)))[:_MAX_ISSUES]
    if ordered or kind is None or document is None:
        return GraphEvolutionValidationResult(not ordered, ordered)
    digest = hashlib.sha256(_DOMAINS[kind] + _canonical_bytes(document)).hexdigest()
    return GraphEvolutionValidationResult(True, (), digest)


def _exact_fields(
    value: Any,
    required: frozenset[str],
    allowed: frozenset[str],
    location: str,
    issues: list[GraphEvolutionValidationIssue],
) -> bool:
    if type(value) is not dict:
        issues.append(_issue(location, "OBJECT_REQUIRED"))
        return False
    for name in sorted(required - set(value)):
        issues.append(_issue(f"{location}.{name}", "REQUIRED_FIELD"))
    for name in sorted(set(value) - allowed):
        issues.append(_issue(f"{location}.{name}", "UNKNOWN_FIELD"))
    return not (required - set(value) or set(value) - allowed)


def _is_id(value: Any) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= _MAX_ID_LENGTH
        and "\r" not in value
        and "\n" not in value
    )


def _is_digest(value: Any) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _is_reference(value: Any) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= _MAX_REFERENCE_LENGTH
        and "\r" not in value
        and "\n" not in value
        and "\\" not in value
        and _URI_OR_ROOT.search(value) is None
    )


def _is_path(value: Any, *, pattern: bool = False) -> bool:
    if (
        type(value) is not str
        or not 1 <= len(value) <= _MAX_PATH_LENGTH
        or "\r" in value
        or "\n" in value
        or "\\" in value
        or _URI_OR_ROOT.search(value) is not None
    ):
        return False
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    if not pattern and any("*" in part for part in parts):
        return False
    if pattern and any("*" in part and part not in ("*", "**") for part in parts):
        return False
    return True


def _validate_schema_identity(
    value: dict[str, Any],
    kind: str,
    issues: list[GraphEvolutionValidationIssue],
) -> None:
    if value.get("schema_id") != _SCHEMA_IDS[kind]:
        issues.append(_issue("$.schema_id", "SCHEMA_ID_MISMATCH"))
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != GRAPH_EVOLUTION_SCHEMA_VERSION
    ):
        issues.append(_issue("$.schema_version", "SCHEMA_VERSION_MISMATCH"))


def _validate_string_array(
    value: Any,
    location: str,
    issues: list[GraphEvolutionValidationIssue],
    predicate: Callable[[Any], bool],
    *,
    minimum: int = 0,
    maximum: int,
    allowed: frozenset[str] | None = None,
) -> None:
    if type(value) is not list:
        issues.append(_issue(location, "ARRAY_REQUIRED"))
        return
    if not minimum <= len(value) <= maximum:
        issues.append(_issue(location, "ARRAY_BOUND_EXCEEDED"))
    seen: set[str] = set()
    for index, item in enumerate(value[: maximum + 1]):
        item_location = f"{location}[{index}]"
        if not predicate(item):
            issues.append(_issue(item_location, "INVALID_VALUE"))
            continue
        if allowed is not None and item not in allowed:
            issues.append(_issue(item_location, "VALUE_NOT_ALLOWED"))
        if item in seen:
            issues.append(_issue(item_location, "DUPLICATE_VALUE"))
        seen.add(item)


def _validate_authority(
    value: Any,
    location: str,
    issues: list[GraphEvolutionValidationIssue],
    *,
    project_manager: bool,
) -> None:
    fields = frozenset({"authority_id", "authority_role", "authority_ref"})
    if not _exact_fields(value, fields, fields, location, issues):
        return
    if not _is_id(value["authority_id"]):
        issues.append(_issue(f"{location}.authority_id", "INVALID_ID"))
    if not _is_id(value["authority_role"]):
        issues.append(_issue(f"{location}.authority_role", "INVALID_ROLE"))
    elif project_manager and value["authority_role"] != "PROJECT_MANAGER":
        issues.append(_issue(f"{location}.authority_role", "PM_AUTHORITY_REQUIRED"))
    if not _is_reference(value["authority_ref"]):
        issues.append(_issue(f"{location}.authority_ref", "INVALID_REFERENCE"))


def _validate_proposer(
    value: Any,
    location: str,
    issues: list[GraphEvolutionValidationIssue],
) -> None:
    fields = frozenset({"node_id", "role", "permission"})
    if not _exact_fields(value, fields, fields, location, issues):
        return
    if not _is_id(value["node_id"]):
        issues.append(_issue(f"{location}.node_id", "INVALID_ID"))
    if not _is_id(value["role"]):
        issues.append(_issue(f"{location}.role", "INVALID_ROLE"))
    if type(value["permission"]) is not str or value["permission"] not in _PERMISSIONS:
        issues.append(_issue(f"{location}.permission", "INVALID_PERMISSION"))


def _validate_common(
    value: dict[str, Any],
    issues: list[GraphEvolutionValidationIssue],
) -> None:
    if (
        type(value.get("operation")) is not str
        or value["operation"] not in _OPERATIONS
    ):
        issues.append(_issue("$.operation", "INVALID_OPERATION"))
    if not _is_id(value.get("graph_id")):
        issues.append(_issue("$.graph_id", "INVALID_ID"))
    if (
        type(value.get("parent_generation")) is not int
        or value["parent_generation"] < 1
    ):
        issues.append(_issue("$.parent_generation", "INVALID_GENERATION"))
    if not _is_digest(value.get("parent_graph_digest")):
        issues.append(_issue("$.parent_graph_digest", "INVALID_DIGEST"))
    _validate_authority(value.get("authority"), "$.authority", issues, project_manager=False)
    _validate_proposer(value.get("proposer"), "$.proposer", issues)
    if not _is_id(value.get("node_id")):
        issues.append(_issue("$.node_id", "INVALID_ID"))
    if (
        type(value.get("change_class")) is not str
        or value["change_class"] not in _CHANGE_CLASSES
    ):
        issues.append(_issue("$.change_class", "INVALID_CHANGE_CLASS"))
    if (
        type(value.get("reason_code")) is not str
        or value["reason_code"] not in _REASON_CODES
    ):
        issues.append(_issue("$.reason_code", "INVALID_REASON_CODE"))
    _validate_string_array(
        value.get("evidence_refs"),
        "$.evidence_refs",
        issues,
        _is_reference,
        maximum=_MAX_REFERENCES,
    )
    _validate_string_array(
        value.get("decision_refs"),
        "$.decision_refs",
        issues,
        _is_reference,
        maximum=_MAX_REFERENCES,
    )
    _validate_string_array(
        value.get("affected_paths"),
        "$.affected_paths",
        issues,
        _is_path,
        maximum=_MAX_PATHS,
    )
    if not _is_digest(value.get("stage5_lineage_digest")):
        issues.append(_issue("$.stage5_lineage_digest", "INVALID_DIGEST"))


def _validate_operation_context(
    value: dict[str, Any],
    issues: list[GraphEvolutionValidationIssue],
) -> None:
    operation = value.get("operation")
    if operation == "ADD_CORRECTIVE":
        for name in ("finding_ref", "root_cause_ref"):
            if name not in value:
                issues.append(_issue(f"$.{name}", "REQUIRED_FIELD"))
            elif not _is_reference(value[name]):
                issues.append(_issue(f"$.{name}", "INVALID_REFERENCE"))
        if type(value.get("evidence_refs")) is list and not value["evidence_refs"]:
            issues.append(_issue("$.evidence_refs", "CORRECTIVE_EVIDENCE_REQUIRED"))
    else:
        for name in ("finding_ref", "root_cause_ref"):
            if name in value:
                issues.append(_issue(f"$.{name}", "OPERATION_FIELD_FORBIDDEN"))

    if (
        type(operation) is str
        and operation in {"SPLIT_PENDING", "DISABLE_OPTIONAL_PENDING"}
    ):
        if value.get("subject_status") != "PENDING":
            issues.append(_issue("$.subject_status", "PENDING_SUBJECT_REQUIRED"))
    elif "subject_status" in value:
        issues.append(_issue("$.subject_status", "OPERATION_FIELD_FORBIDDEN"))


def _prepare(
    kind: str,
    value: Any,
) -> tuple[dict[str, Any] | None, list[GraphEvolutionValidationIssue]]:
    issues: list[GraphEvolutionValidationIssue] = []
    try:
        document = _parse_document(value)
        canonical = _canonical_bytes(document)
    except (RecursionError, _StrictDocumentError):
        return None, [_issue("$", "STRICT_JSON_REQUIRED")]
    if len(canonical) > _MAX_CANONICAL_BYTES[kind]:
        issues.append(_issue("$", "DOCUMENT_BYTE_BUDGET_EXCEEDED"))
    return document, issues


def _admission_failed(
    issues: list[GraphEvolutionValidationIssue],
) -> bool:
    return any(
        issue.issue_code == "DOCUMENT_BYTE_BUDGET_EXCEEDED"
        for issue in issues
    )


def validate_graph_evolution_request(
    value: Any,
) -> GraphEvolutionValidationResult:
    document, issues = _prepare("request", value)
    if document is None:
        return _result(issues)
    if _admission_failed(issues):
        return _result(issues)
    if _exact_fields(
        document,
        _REQUEST_FIELDS,
        _REQUEST_ALLOWED_FIELDS,
        "$",
        issues,
    ):
        _validate_schema_identity(document, "request", issues)
        if not _is_reference(document["request_id"]):
            issues.append(_issue("$.request_id", "INVALID_REFERENCE"))
        _validate_common(document, issues)
        _validate_operation_context(document, issues)
    return _result(issues, kind="request", document=document)


def validate_graph_evolution_preauthorization(
    value: Any,
) -> GraphEvolutionValidationResult:
    document, issues = _prepare("preauthorization", value)
    if document is None:
        return _result(issues)
    if _admission_failed(issues):
        return _result(issues)
    if not _exact_fields(
        document,
        _PREAUTHORIZATION_FIELDS,
        _PREAUTHORIZATION_FIELDS,
        "$",
        issues,
    ):
        return _result(issues)
    _validate_schema_identity(document, "preauthorization", issues)
    if not _is_reference(document["preauthorization_id"]):
        issues.append(_issue("$.preauthorization_id", "INVALID_REFERENCE"))
    if not _is_id(document["graph_id"]):
        issues.append(_issue("$.graph_id", "INVALID_ID"))
    if (
        type(document["parent_generation"]) is not int
        or document["parent_generation"] < 1
    ):
        issues.append(_issue("$.parent_generation", "INVALID_GENERATION"))
    if not _is_digest(document["parent_graph_digest"]):
        issues.append(_issue("$.parent_graph_digest", "INVALID_DIGEST"))
    _validate_authority(
        document["authority"],
        "$.authority",
        issues,
        project_manager=True,
    )
    _validate_string_array(
        document["allowed_operations"],
        "$.allowed_operations",
        issues,
        _is_id,
        minimum=1,
        maximum=len(_OPERATIONS),
        allowed=_OPERATIONS,
    )
    _validate_string_array(
        document["allowed_change_classes"],
        "$.allowed_change_classes",
        issues,
        _is_id,
        minimum=1,
        maximum=len(_CHANGE_CLASSES),
        allowed=_CHANGE_CLASSES,
    )
    _validate_string_array(
        document["allowed_node_ids"],
        "$.allowed_node_ids",
        issues,
        _is_id,
        minimum=1,
        maximum=_MAX_ALLOWLIST_ITEMS,
    )
    _validate_string_array(
        document["allowed_roles"],
        "$.allowed_roles",
        issues,
        _is_id,
        minimum=1,
        maximum=_MAX_ALLOWLIST_ITEMS,
    )
    _validate_string_array(
        document["allowed_permissions"],
        "$.allowed_permissions",
        issues,
        _is_id,
        minimum=1,
        maximum=len(_PERMISSIONS),
        allowed=_PERMISSIONS,
    )
    _validate_string_array(
        document["allowed_paths"],
        "$.allowed_paths",
        issues,
        lambda item: _is_path(item, pattern=True),
        minimum=1,
        maximum=_MAX_ALLOWLIST_ITEMS,
    )

    generation_fields = frozenset(
        {"max_target_generation", "remaining_generations"}
    )
    budget = document["generation_budget"]
    if _exact_fields(
        budget,
        generation_fields,
        generation_fields,
        "$.generation_budget",
        issues,
    ):
        maximum = budget["max_target_generation"]
        remaining = budget["remaining_generations"]
        if (
            type(maximum) is not int
            or type(document["parent_generation"]) is not int
            or maximum <= document["parent_generation"]
        ):
            issues.append(
                _issue(
                    "$.generation_budget.max_target_generation",
                    "INVALID_GENERATION_BUDGET",
                )
            )
        if (
            type(remaining) is not int
            or not 0 <= remaining <= _MAX_GENERATION_BUDGET
            or (
                type(maximum) is int
                and type(document["parent_generation"]) is int
                and remaining > maximum - document["parent_generation"]
            )
        ):
            issues.append(
                _issue(
                    "$.generation_budget.remaining_generations",
                    "INVALID_GENERATION_BUDGET",
                )
            )

    operation_budgets = document["operation_budgets"]
    if _exact_fields(
        operation_budgets,
        _OPERATIONS,
        _OPERATIONS,
        "$.operation_budgets",
        issues,
    ):
        allowed_operations = {
            item
            for item in document["allowed_operations"]
            if type(item) is str
        } if type(document["allowed_operations"]) is list else set()
        for operation in GRAPH_EVOLUTION_OPERATIONS:
            amount = operation_budgets[operation]
            if (
                type(amount) is not int
                or not 0 <= amount <= _MAX_OPERATION_BUDGET
            ):
                issues.append(
                    _issue(
                        f"$.operation_budgets.{operation}",
                        "INVALID_OPERATION_BUDGET",
                    )
                )
            elif (operation in allowed_operations) != (amount > 0):
                issues.append(
                    _issue(
                        f"$.operation_budgets.{operation}",
                        "ALLOWLIST_BUDGET_MISMATCH",
                    )
                )

    evaluator_fields = frozenset(
        {"node_id", "role", "permission", "authority_ref", "independent"}
    )
    evaluator = document["evaluator"]
    allowed_node_ids = (
        document["allowed_node_ids"]
        if type(document["allowed_node_ids"]) is list
        else []
    )
    allowed_roles = (
        document["allowed_roles"]
        if type(document["allowed_roles"]) is list
        else []
    )
    allowed_permissions = (
        document["allowed_permissions"]
        if type(document["allowed_permissions"]) is list
        else []
    )
    if _exact_fields(
        evaluator,
        evaluator_fields,
        evaluator_fields,
        "$.evaluator",
        issues,
    ):
        if not _is_id(evaluator["node_id"]):
            issues.append(_issue("$.evaluator.node_id", "INVALID_ID"))
        elif evaluator["node_id"] not in allowed_node_ids:
            issues.append(_issue("$.evaluator.node_id", "EVALUATOR_NOT_ALLOWED"))
        if not _is_id(evaluator["role"]):
            issues.append(_issue("$.evaluator.role", "INVALID_ROLE"))
        elif evaluator["role"] not in allowed_roles:
            issues.append(_issue("$.evaluator.role", "EVALUATOR_NOT_ALLOWED"))
        if (
            type(evaluator["permission"]) is not str
            or evaluator["permission"] not in _PERMISSIONS
        ):
            issues.append(_issue("$.evaluator.permission", "INVALID_PERMISSION"))
        elif evaluator["permission"] not in allowed_permissions:
            issues.append(_issue("$.evaluator.permission", "EVALUATOR_NOT_ALLOWED"))
        if not _is_reference(evaluator["authority_ref"]):
            issues.append(_issue("$.evaluator.authority_ref", "INVALID_REFERENCE"))
        if evaluator["independent"] is not True:
            issues.append(
                _issue("$.evaluator.independent", "INDEPENDENT_EVALUATOR_REQUIRED")
            )
    _validate_string_array(
        document["stop_conditions"],
        "$.stop_conditions",
        issues,
        _is_id,
        minimum=1,
        maximum=len(_STOP_CONDITIONS),
        allowed=_STOP_CONDITIONS,
    )
    if (
        type(document["stop_conditions"]) is list
        and set(document["stop_conditions"]) != _STOP_CONDITIONS
    ):
        issues.append(
            _issue("$.stop_conditions", "COMPLETE_FAIL_STOP_SET_REQUIRED")
        )
    if (
        type(budget) is dict
        and budget.get("remaining_generations") == 0
        and type(operation_budgets) is dict
    ):
        for operation in sorted(_MUTATING_OPERATIONS):
            if operation_budgets.get(operation) != 0:
                issues.append(
                    _issue(
                        f"$.operation_budgets.{operation}",
                        "EXHAUSTED_MUTATION_BUDGET_REQUIRED",
                    )
                )
    return _result(issues, kind="preauthorization", document=document)


def validate_graph_evolution_proposal(
    value: Any,
) -> GraphEvolutionValidationResult:
    document, issues = _prepare("proposal", value)
    if document is None:
        return _result(issues)
    if _admission_failed(issues):
        return _result(issues)
    operation = document.get("operation")
    required = _PROPOSAL_REQUIRED_FIELDS
    allowed = (
        _PROPOSAL_ALLOWED_FIELDS
        if operation == "NO_CHANGE"
        else _PROPOSAL_ALLOWED_FIELDS | _PROPOSAL_TARGET_FIELDS
    )
    if not _exact_fields(document, required, allowed, "$", issues):
        return _result(issues)
    _validate_schema_identity(document, "proposal", issues)
    if not _is_reference(document["proposal_id"]):
        issues.append(_issue("$.proposal_id", "INVALID_REFERENCE"))
    if not _is_reference(document["request_id"]):
        issues.append(_issue("$.request_id", "INVALID_REFERENCE"))
    _validate_common(document, issues)
    _validate_operation_context(document, issues)
    for name in ("request_digest", "preauthorization_digest"):
        if not _is_digest(document[name]):
            issues.append(_issue(f"$.{name}", "INVALID_DIGEST"))
    if operation == "NO_CHANGE":
        for name in _PROPOSAL_TARGET_FIELDS:
            if name in document:
                issues.append(_issue(f"$.{name}", "NO_CHANGE_TARGET_FORBIDDEN"))
        return _result(issues, kind="proposal", document=document)
    for name in _PROPOSAL_TARGET_FIELDS:
        if name not in document:
            issues.append(_issue(f"$.{name}", "REQUIRED_FIELD"))
    if any(name not in document for name in _PROPOSAL_TARGET_FIELDS):
        return _result(issues)
    target_generation = document["target_generation"]
    if (
        type(target_generation) is not int
        or type(document["parent_generation"]) is not int
        or target_generation != document["parent_generation"] + 1
    ):
        issues.append(_issue("$.target_generation", "INVALID_TARGET_GENERATION"))
    if not _is_digest(document["target_graph_digest"]):
        issues.append(_issue("$.target_graph_digest", "INVALID_DIGEST"))
    graph_result = validate_graph_contract(document["target_graph"])
    if not graph_result.valid or graph_result.semantic_digest is None:
        issues.append(_issue("$.target_graph", "GRAPH_INVALID"))
    else:
        target_graph = document["target_graph"]
        if (
            target_graph.get("graph_id") != document["graph_id"]
            or target_graph.get("generation") != target_generation
            or graph_result.semantic_digest != document["target_graph_digest"]
        ):
            issues.append(_issue("$.target_graph", "GRAPH_BINDING_MISMATCH"))
    return _result(issues, kind="proposal", document=document)


def validate_graph_evolution_acceptance(
    value: Any,
) -> GraphEvolutionValidationResult:
    document, issues = _prepare("acceptance", value)
    if document is None:
        return _result(issues)
    if _admission_failed(issues):
        return _result(issues)
    if not _exact_fields(
        document,
        _ACCEPTANCE_FIELDS,
        _ACCEPTANCE_FIELDS,
        "$",
        issues,
    ):
        return _result(issues)
    _validate_schema_identity(document, "acceptance", issues)
    if not _is_reference(document["acceptance_id"]):
        issues.append(_issue("$.acceptance_id", "INVALID_REFERENCE"))
    for name in ("proposal_digest", "preauthorization_digest"):
        if not _is_digest(document[name]):
            issues.append(_issue(f"$.{name}", "INVALID_DIGEST"))
    if (
        type(document["decision"]) is not str
        or document["decision"] not in {"ACCEPTED", "REJECTED"}
    ):
        issues.append(_issue("$.decision", "INVALID_DECISION"))
    _validate_authority(
        document["authority"],
        "$.authority",
        issues,
        project_manager=True,
    )
    evaluator_fields = frozenset({"node_id", "role", "decision", "decision_ref"})
    evaluator = document["evaluator"]
    if _exact_fields(
        evaluator,
        evaluator_fields,
        evaluator_fields,
        "$.evaluator",
        issues,
    ):
        if not _is_id(evaluator["node_id"]):
            issues.append(_issue("$.evaluator.node_id", "INVALID_ID"))
        if not _is_id(evaluator["role"]):
            issues.append(_issue("$.evaluator.role", "INVALID_ROLE"))
        if (
            type(evaluator["decision"]) is not str
            or evaluator["decision"] not in {"APPROVE", "REJECT"}
        ):
            issues.append(_issue("$.evaluator.decision", "INVALID_DECISION"))
        expected = (
            "APPROVE" if document["decision"] == "ACCEPTED" else "REJECT"
        )
        if evaluator["decision"] != expected:
            issues.append(_issue("$.evaluator.decision", "DECISION_MISMATCH"))
        if not _is_reference(evaluator["decision_ref"]):
            issues.append(_issue("$.evaluator.decision_ref", "INVALID_REFERENCE"))
    if (
        type(document["reason_code"]) is not str
        or document["reason_code"] not in _REASON_CODES
    ):
        issues.append(_issue("$.reason_code", "INVALID_REASON_CODE"))
    _validate_string_array(
        document["decision_refs"],
        "$.decision_refs",
        issues,
        _is_reference,
        minimum=1,
        maximum=_MAX_REFERENCES,
    )
    return _result(issues, kind="acceptance", document=document)


def validate_graph_evolution_result(
    value: Any,
) -> GraphEvolutionValidationResult:
    document, issues = _prepare("result", value)
    if document is None:
        return _result(issues)
    if _admission_failed(issues):
        return _result(issues)
    allowed = _RESULT_REQUIRED_FIELDS | _RESULT_TARGET_FIELDS
    if not _exact_fields(document, _RESULT_REQUIRED_FIELDS, allowed, "$", issues):
        return _result(issues)
    _validate_schema_identity(document, "result", issues)
    for name in (
        "request_digest",
        "preauthorization_digest",
        "proposal_digest",
        "acceptance_digest",
        "parent_graph_digest",
    ):
        if not _is_digest(document[name]):
            issues.append(_issue(f"$.{name}", "INVALID_DIGEST"))
    if (
        type(document["operation"]) is not str
        or document["operation"] not in _OPERATIONS
    ):
        issues.append(_issue("$.operation", "INVALID_OPERATION"))
    if (
        type(document["outcome"]) is not str
        or document["outcome"] not in {"ACCEPTED", "REJECTED", "NO_CHANGE"}
    ):
        issues.append(_issue("$.outcome", "INVALID_OUTCOME"))
    if not _is_id(document["graph_id"]):
        issues.append(_issue("$.graph_id", "INVALID_ID"))
    if (
        type(document["parent_generation"]) is not int
        or document["parent_generation"] < 1
    ):
        issues.append(_issue("$.parent_generation", "INVALID_GENERATION"))

    operation = document["operation"]
    outcome = document["outcome"]
    message_code = document["message_code"]
    if type(message_code) is not str or message_code not in {
        "EVOLUTION_ACCEPTED",
        "EVOLUTION_REJECTED",
        "NO_CHANGE_ACCEPTED",
    }:
        issues.append(_issue("$.message_code", "INVALID_MESSAGE_CODE"))
    if outcome == "REJECTED":
        if message_code != "EVOLUTION_REJECTED":
            issues.append(_issue("$.message_code", "MESSAGE_MISMATCH"))
        for name in _RESULT_TARGET_FIELDS:
            if name in document:
                issues.append(_issue(f"$.{name}", "REJECTED_TARGET_FORBIDDEN"))
    elif operation == "NO_CHANGE":
        if outcome != "NO_CHANGE":
            issues.append(_issue("$.outcome", "NO_CHANGE_OUTCOME_REQUIRED"))
        if message_code != "NO_CHANGE_ACCEPTED":
            issues.append(_issue("$.message_code", "MESSAGE_MISMATCH"))
        for name in _RESULT_TARGET_FIELDS:
            if name in document:
                issues.append(_issue(f"$.{name}", "NO_CHANGE_TARGET_FORBIDDEN"))
    elif type(operation) is str and operation in _MUTATING_OPERATIONS:
        if outcome != "ACCEPTED":
            issues.append(_issue("$.outcome", "MUTATION_OUTCOME_REQUIRED"))
        if message_code != "EVOLUTION_ACCEPTED":
            issues.append(_issue("$.message_code", "MESSAGE_MISMATCH"))
        for name in _RESULT_TARGET_FIELDS:
            if name not in document:
                issues.append(_issue(f"$.{name}", "REQUIRED_FIELD"))
        if "target_generation" in document and (
            type(document["target_generation"]) is not int
            or type(document["parent_generation"]) is not int
            or document["target_generation"] != document["parent_generation"] + 1
        ):
            issues.append(_issue("$.target_generation", "INVALID_TARGET_GENERATION"))
        if "target_graph_digest" in document and not _is_digest(
            document["target_graph_digest"]
        ):
            issues.append(_issue("$.target_graph_digest", "INVALID_DIGEST"))
    return _result(issues, kind="result", document=document)


def validate_graph_evolution_error(
    value: Any,
) -> GraphEvolutionValidationResult:
    document, issues = _prepare("error", value)
    if document is None:
        return _result(issues)
    if _admission_failed(issues):
        return _result(issues)
    required = _ERROR_FIELDS - {"document_digest"}
    if not _exact_fields(document, required, _ERROR_FIELDS, "$", issues):
        return _result(issues)
    _validate_schema_identity(document, "error", issues)
    error_code = document["error_code"]
    if type(error_code) is not str or error_code not in _ERROR_CODES:
        issues.append(_issue("$.error_code", "INVALID_ERROR_CODE"))
    elif document["message_code"] != _ERROR_MESSAGES[error_code]:
        issues.append(_issue("$.message_code", "MESSAGE_MISMATCH"))
    if (
        type(document["document_kind"]) is not str
        or document["document_kind"] not in _SCHEMA_IDS
    ):
        issues.append(_issue("$.document_kind", "INVALID_DOCUMENT_KIND"))
    if "document_digest" in document and not _is_digest(document["document_digest"]):
        issues.append(_issue("$.document_digest", "INVALID_DIGEST"))
    issue_fields = frozenset({"location", "issue_code"})
    issue_values = document["issues"]
    if type(issue_values) is not list:
        issues.append(_issue("$.issues", "ARRAY_REQUIRED"))
    elif len(issue_values) > _MAX_ISSUES:
        issues.append(_issue("$.issues", "ARRAY_BOUND_EXCEEDED"))
    else:
        seen_issues: set[tuple[str, str]] = set()
        for index, item in enumerate(issue_values):
            location = f"$.issues[{index}]"
            if not _exact_fields(
                item,
                issue_fields,
                issue_fields,
                location,
                issues,
            ):
                continue
            if (
                type(item["location"]) is not str
                or not 1 <= len(item["location"]) <= _MAX_REFERENCE_LENGTH
                or _LOCATION.fullmatch(item["location"]) is None
            ):
                issues.append(_issue(f"{location}.location", "INVALID_LOCATION"))
            if (
                type(item["issue_code"]) is not str
                or len(item["issue_code"]) > _MAX_ID_LENGTH
                or _MACHINE_CODE.fullmatch(item["issue_code"]) is None
            ):
                issues.append(_issue(f"{location}.issue_code", "INVALID_ISSUE_CODE"))
            if type(item["location"]) is str and type(item["issue_code"]) is str:
                issue_identity = (item["location"], item["issue_code"])
                if issue_identity in seen_issues:
                    issues.append(_issue(location, "DUPLICATE_ISSUE"))
                seen_issues.add(issue_identity)
    return _result(issues, kind="error", document=document)


_VALIDATORS: dict[str, Callable[[Any], GraphEvolutionValidationResult]] = {
    "request": validate_graph_evolution_request,
    "preauthorization": validate_graph_evolution_preauthorization,
    "proposal": validate_graph_evolution_proposal,
    "acceptance": validate_graph_evolution_acceptance,
    "result": validate_graph_evolution_result,
    "error": validate_graph_evolution_error,
}


def validate_graph_evolution_document(
    kind: str,
    value: Any,
) -> GraphEvolutionValidationResult:
    """Validate one named Graph Evolution document kind."""

    validator = _VALIDATORS.get(kind)
    if validator is None:
        return GraphEvolutionValidationResult(
            False,
            (_issue("$", "INVALID_DOCUMENT_KIND"),),
        )
    return validator(value)


_MISSING = object()


def canonical_graph_evolution_digest(
    kind: str | Any,
    value: Any = _MISSING,
) -> str:
    """Return a domain-separated digest after complete strict validation."""

    if value is _MISSING:
        value = kind
        try:
            parsed = _parse_document(value)
        except (RecursionError, _StrictDocumentError) as exc:
            raise GraphEvolutionContractError("unknown") from exc
        schema_id = parsed.get("schema_id")
        kind = next(
            (
                candidate
                for candidate, expected_schema_id in _SCHEMA_IDS.items()
                if schema_id == expected_schema_id
            ),
            "unknown",
        )
    if type(kind) is not str:
        raise GraphEvolutionContractError("unknown")
    validator = _VALIDATORS.get(kind)
    if validator is None:
        raise GraphEvolutionContractError(kind)
    result = validator(value)
    if not result.valid or result.digest is None:
        raise GraphEvolutionContractError(kind, result.issues)
    return result.digest


def _prefixed_issue(
    prefix: str,
    issue: GraphEvolutionValidationIssue,
) -> GraphEvolutionValidationIssue:
    suffix = issue.location[1:] if issue.location.startswith("$") else ""
    return _issue(f"$.{prefix}{suffix}", issue.issue_code)


def _path_matches_pattern(path: str, pattern: str) -> bool:
    path_parts = path.split("/")
    pattern_parts = pattern.split("/")

    memo: dict[tuple[int, int], bool] = {}

    def matches(path_index: int, pattern_index: int) -> bool:
        key = (path_index, pattern_index)
        if key in memo:
            return memo[key]
        if pattern_index == len(pattern_parts):
            answer = path_index == len(path_parts)
        else:
            part = pattern_parts[pattern_index]
            if part == "**":
                answer = matches(path_index, pattern_index + 1) or (
                    path_index < len(path_parts)
                    and matches(path_index + 1, pattern_index)
                )
            elif path_index == len(path_parts):
                answer = False
            elif part != "*" and part != path_parts[path_index]:
                answer = False
            else:
                answer = matches(path_index + 1, pattern_index + 1)
        memo[key] = answer
        return answer

    return matches(0, 0)


def _graph_items_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def _validate_graph_delta(
    request: dict[str, Any],
    proposal: dict[str, Any],
    parent_graph: dict[str, Any],
    issues: list[GraphEvolutionValidationIssue],
) -> set[str]:
    operation = request["operation"]
    if operation == "NO_CHANGE":
        return set()
    target_graph = proposal["target_graph"]
    invariant_fields = (
        "schema_id",
        "schema_version",
        "graph_id",
        "source_authority",
        "governance_level",
        "autonomy_level",
        "completion_verifier",
        "human_gates",
    )
    for name in invariant_fields:
        if parent_graph.get(name, _MISSING) != target_graph.get(name, _MISSING):
            issues.append(
                _issue(
                    f"$.proposal.target_graph.{name}",
                    "IMMUTABLE_GRAPH_CONTROL_CHANGED",
                )
            )

    parent_nodes = _graph_items_by_id(parent_graph["nodes"])
    target_nodes = _graph_items_by_id(target_graph["nodes"])
    parent_ids = set(parent_nodes)
    target_ids = set(target_nodes)
    added = target_ids - parent_ids
    removed = parent_ids - target_ids
    subject_id = request["node_id"]

    def require_unchanged_parent_nodes(
        excluded: frozenset[str] = frozenset(),
    ) -> None:
        for node_id in sorted(parent_ids - excluded):
            if target_nodes.get(node_id) != parent_nodes[node_id]:
                issues.append(
                    _issue(
                        "$.proposal.target_graph.nodes",
                        "PARENT_NODE_CHANGED",
                    )
                )

    parent_joins = _graph_items_by_id(parent_graph["joins"])
    target_joins = _graph_items_by_id(target_graph["joins"])

    if operation in {
        "ADD_CORRECTIVE",
        "ADD_VERIFICATION",
        "ADD_INVESTIGATION",
    }:
        if added != {subject_id} or removed:
            issues.append(
                _issue("$.proposal.target_graph.nodes", "ONE_NODE_ADDITION_REQUIRED")
            )
        require_unchanged_parent_nodes()
        for join_id, join in parent_joins.items():
            if target_joins.get(join_id) != join:
                issues.append(
                    _issue("$.proposal.target_graph.joins", "PARENT_JOIN_CHANGED")
                )
        new_node = target_nodes.get(subject_id)
        if new_node is not None:
            expected_reason = {
                "ADD_CORRECTIVE": "OBSERVED_FAILURE",
                "ADD_VERIFICATION": "VERIFICATION_GAP",
                "ADD_INVESTIGATION": "BLOCKING_UNCERTAINTY",
            }[operation]
            if request["reason_code"] != expected_reason:
                issues.append(_issue("$.request.reason_code", "OPERATION_REASON_MISMATCH"))
            if operation == "ADD_CORRECTIVE":
                if (
                    new_node["permission"] != "CORRECTIVE_AUTHORIZED"
                    or new_node["classification"] != "required"
                ):
                    issues.append(
                        _issue(
                            "$.proposal.target_graph.nodes",
                            "CORRECTIVE_NODE_REQUIRED",
                        )
                    )
            elif operation == "ADD_VERIFICATION":
                verifier = new_node["verifier"].casefold()
                if (
                    new_node["role"] != "Verifier"
                    or new_node["permission"] != "READ_ONLY_REVIEW"
                    or new_node["classification"] != "required"
                    or "verif" not in verifier
                    or "investigat" in verifier
                ):
                    issues.append(
                        _issue(
                            "$.proposal.target_graph.nodes",
                            "READ_ONLY_VERIFICATION_REQUIRED",
                        )
                    )
            else:
                if (
                    new_node["permission"] != "READ_ONLY_REVIEW"
                    or new_node["classification"] != "optional"
                ):
                    issues.append(
                        _issue(
                            "$.proposal.target_graph.nodes",
                            "OPTIONAL_READ_ONLY_INVESTIGATION_REQUIRED",
                        )
                    )
                for join in target_graph["joins"]:
                    if (
                        subject_id in join["requires"]
                        and join["policy"] != "first-success"
                    ):
                        issues.append(
                            _issue(
                                "$.proposal.target_graph.joins",
                                "INVESTIGATION_REQUIRED_JOIN_FORBIDDEN",
                            )
                        )
    elif operation == "SPLIT_PENDING":
        if request["reason_code"] != "NODE_TOO_BROAD":
            issues.append(_issue("$.request.reason_code", "OPERATION_REASON_MISMATCH"))
        if len(added) != 1 or removed or subject_id not in parent_nodes:
            issues.append(
                _issue("$.proposal.target_graph.nodes", "PENDING_SPLIT_REQUIRED")
            )
        require_unchanged_parent_nodes()
        if subject_id in parent_nodes and target_nodes.get(subject_id) != parent_nodes[
            subject_id
        ]:
            issues.append(
                _issue("$.proposal.target_graph.nodes", "SPLIT_IDENTITY_CHANGED")
            )
        if len(added) == 1 and subject_id in parent_nodes:
            split_node = target_nodes[next(iter(added))]
            source_node = parent_nodes[subject_id]
            for name in ("role", "permission", "verifier", "classification"):
                if split_node[name] != source_node[name]:
                    issues.append(
                        _issue(
                            "$.proposal.target_graph.nodes",
                            "SPLIT_CONTROL_NOT_PRESERVED",
                        )
                    )
        for join_id, join in parent_joins.items():
            target_join = target_joins.get(join_id)
            if join_id in parent_graph["human_gates"]:
                if target_join is None or _canonical_bytes(
                    target_join
                ) != _canonical_bytes(join):
                    issues.append(
                        _issue("$.proposal.target_graph.joins", "PARENT_JOIN_CHANGED")
                    )
                continue
            if target_join is None or target_join["policy"] != join["policy"]:
                issues.append(
                    _issue("$.proposal.target_graph.joins", "PARENT_JOIN_CHANGED")
                )
                continue
            old_requires = set(join["requires"])
            new_requires = set(target_join["requires"])
            if not old_requires.issubset(new_requires) or (
                new_requires - old_requires
            ) - added:
                issues.append(
                    _issue("$.proposal.target_graph.joins", "PARENT_JOIN_CHANGED")
                )
        for join_id in set(parent_graph["human_gates"]) - set(parent_joins):
            if join_id in target_joins:
                issues.append(
                    _issue("$.proposal.target_graph.joins", "PARENT_JOIN_CHANGED")
                )
    elif operation == "DISABLE_OPTIONAL_PENDING":
        if request["reason_code"] != "OPTIONAL_NODE_NO_LONGER_DECISIVE":
            issues.append(_issue("$.request.reason_code", "OPERATION_REASON_MISMATCH"))
        if added or removed != {subject_id} or subject_id not in parent_nodes:
            issues.append(
                _issue("$.proposal.target_graph.nodes", "OPTIONAL_DISABLE_REQUIRED")
            )
        require_unchanged_parent_nodes(frozenset({subject_id}))
        subject = parent_nodes.get(subject_id)
        if subject is not None and subject["classification"] != "optional":
            issues.append(
                _issue("$.request.node_id", "OPTIONAL_SUBJECT_REQUIRED")
            )
        required_policies = {
            "all-required",
            "required-plus-optional",
            "manual-gate",
            "corrective-join",
        }
        for join_id, join in parent_joins.items():
            references_subject = subject_id in join["requires"]
            if references_subject and (
                join["policy"] in required_policies
                or join_id in parent_graph["human_gates"]
            ):
                issues.append(
                    _issue(
                        "$.parent_graph.joins",
                        "REQUIRED_JOIN_OR_GATE_REFERENCES_SUBJECT",
                    )
                )
            target_join = target_joins.get(join_id)
            if not references_subject:
                if target_join != join:
                    issues.append(
                        _issue("$.proposal.target_graph.joins", "PARENT_JOIN_CHANGED")
                    )
                continue
            expected_requires = [
                node_id for node_id in join["requires"] if node_id != subject_id
            ]
            if expected_requires:
                expected_join = dict(join)
                expected_join["requires"] = expected_requires
                if target_join != expected_join:
                    issues.append(
                        _issue("$.proposal.target_graph.joins", "INVALID_DISABLE_DELTA")
                    )
            elif target_join is not None:
                issues.append(
                    _issue("$.proposal.target_graph.joins", "INVALID_DISABLE_DELTA")
                )
        if set(target_joins) - set(parent_joins):
            issues.append(
                _issue("$.proposal.target_graph.joins", "INVALID_DISABLE_DELTA")
            )
    return added


def validate_decision_chain(
    request: Any,
    preauthorization: Any,
    proposal: Any,
    acceptance: Any,
    result: Any,
    parent_graph: Any,
) -> GraphEvolutionValidationResult:
    """Purely validate one digest-bound Graph evolution decision chain."""

    raw_documents = {
        "request": request,
        "preauthorization": preauthorization,
        "proposal": proposal,
        "acceptance": acceptance,
        "result": result,
    }
    documents: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    issues: list[GraphEvolutionValidationIssue] = []
    for kind, raw_document in raw_documents.items():
        validation = _VALIDATORS[kind](raw_document)
        if not validation.valid or validation.digest is None:
            issues.extend(_prefixed_issue(kind, issue) for issue in validation.issues)
            continue
        try:
            documents[kind] = _parse_document(raw_document)
        except (RecursionError, _StrictDocumentError):
            issues.append(_issue(f"$.{kind}", "STRICT_JSON_REQUIRED"))
            continue
        digests[kind] = validation.digest
    if issues:
        return _result(issues)

    try:
        parsed_parent = _parse_document(parent_graph)
    except (RecursionError, _StrictDocumentError):
        return _result([_issue("$.parent_graph", "STRICT_JSON_REQUIRED")])
    parent_validation = validate_graph_contract(parsed_parent)
    if not parent_validation.valid or parent_validation.semantic_digest is None:
        return _result([_issue("$.parent_graph", "PARENT_GRAPH_INVALID")])
    parent_digest = parent_validation.semantic_digest

    req = documents["request"]
    preauth = documents["preauthorization"]
    prop = documents["proposal"]
    accept = documents["acceptance"]
    res = documents["result"]

    def require_equal(
        actual: Any,
        expected: Any,
        location: str,
        issue_code: str = "CHAIN_BINDING_MISMATCH",
    ) -> None:
        if actual != expected:
            issues.append(_issue(location, issue_code))

    for document_name, document in (
        ("request", req),
        ("preauthorization", preauth),
        ("proposal", prop),
        ("result", res),
    ):
        require_equal(
            document["graph_id"],
            parsed_parent["graph_id"],
            f"$.{document_name}.graph_id",
            "PARENT_GRAPH_BINDING_MISMATCH",
        )
        require_equal(
            document["parent_generation"],
            parsed_parent["generation"],
            f"$.{document_name}.parent_generation",
            "PARENT_GRAPH_BINDING_MISMATCH",
        )
        require_equal(
            document["parent_graph_digest"],
            parent_digest,
            f"$.{document_name}.parent_graph_digest",
            "PARENT_GRAPH_BINDING_MISMATCH",
        )

    require_equal(req["authority"], preauth["authority"], "$.request.authority")
    require_equal(accept["authority"], preauth["authority"], "$.acceptance.authority")
    require_equal(
        req["authority"]["authority_id"],
        parsed_parent["source_authority"]["identity"],
        "$.request.authority.authority_id",
        "PARENT_AUTHORITY_MISMATCH",
    )
    require_equal(
        req["authority"]["authority_ref"],
        parsed_parent["source_authority"]["reference"],
        "$.request.authority.authority_ref",
        "PARENT_AUTHORITY_MISMATCH",
    )
    require_equal(
        prop["request_digest"],
        digests["request"],
        "$.proposal.request_digest",
        "DIGEST_BINDING_MISMATCH",
    )
    require_equal(
        prop["preauthorization_digest"],
        digests["preauthorization"],
        "$.proposal.preauthorization_digest",
        "DIGEST_BINDING_MISMATCH",
    )
    require_equal(
        accept["proposal_digest"],
        digests["proposal"],
        "$.acceptance.proposal_digest",
        "DIGEST_BINDING_MISMATCH",
    )
    require_equal(
        accept["preauthorization_digest"],
        digests["preauthorization"],
        "$.acceptance.preauthorization_digest",
        "DIGEST_BINDING_MISMATCH",
    )
    for name, digest_kind in (
        ("request_digest", "request"),
        ("preauthorization_digest", "preauthorization"),
        ("proposal_digest", "proposal"),
        ("acceptance_digest", "acceptance"),
    ):
        require_equal(
            res[name],
            digests[digest_kind],
            f"$.result.{name}",
            "DIGEST_BINDING_MISMATCH",
        )

    for name in _REQUEST_ALLOWED_FIELDS - {"schema_id"}:
        require_equal(
            prop.get(name, _MISSING),
            req.get(name, _MISSING),
            f"$.proposal.{name}",
        )

    operation = req["operation"]
    parent_nodes_by_id = _graph_items_by_id(parsed_parent["nodes"])
    proposer_node = parent_nodes_by_id.get(req["proposer"]["node_id"])
    if proposer_node is None:
        issues.append(_issue("$.request.proposer.node_id", "PROPOSER_NOT_IN_PARENT"))
    else:
        require_equal(
            req["proposer"]["role"],
            proposer_node["role"],
            "$.request.proposer.role",
            "PROPOSER_PARENT_MISMATCH",
        )
        require_equal(
            req["proposer"]["permission"],
            proposer_node["permission"],
            "$.request.proposer.permission",
            "PROPOSER_PARENT_MISMATCH",
        )
    if operation not in preauth["allowed_operations"]:
        issues.append(_issue("$.request.operation", "OPERATION_NOT_PREAUTHORIZED"))
    if req["change_class"] not in preauth["allowed_change_classes"]:
        issues.append(_issue("$.request.change_class", "CLASS_NOT_PREAUTHORIZED"))
    if req["node_id"] not in preauth["allowed_node_ids"]:
        issues.append(_issue("$.request.node_id", "NODE_NOT_PREAUTHORIZED"))
    if req["proposer"]["node_id"] not in preauth["allowed_node_ids"]:
        issues.append(_issue("$.request.proposer.node_id", "NODE_NOT_PREAUTHORIZED"))
    if req["proposer"]["role"] not in preauth["allowed_roles"]:
        issues.append(_issue("$.request.proposer.role", "ROLE_NOT_PREAUTHORIZED"))
    if req["proposer"]["permission"] not in preauth["allowed_permissions"]:
        issues.append(
            _issue("$.request.proposer.permission", "PERMISSION_NOT_PREAUTHORIZED")
        )
    for index, path in enumerate(req["affected_paths"]):
        if not any(
            _path_matches_pattern(path, pattern)
            for pattern in preauth["allowed_paths"]
        ):
            issues.append(
                _issue(
                    f"$.request.affected_paths[{index}]",
                    "PATH_NOT_PREAUTHORIZED",
                )
            )
    if preauth["operation_budgets"][operation] <= 0:
        issues.append(_issue("$.preauthorization.operation_budgets", "BUDGET_EXHAUSTED"))
    if operation in _MUTATING_OPERATIONS:
        if preauth["generation_budget"]["remaining_generations"] <= 0:
            issues.append(
                _issue("$.preauthorization.generation_budget", "BUDGET_EXHAUSTED")
            )
        require_equal(
            prop["target_generation"],
            parsed_parent["generation"] + 1,
            "$.proposal.target_generation",
        )
        if (
            prop["target_generation"]
            > preauth["generation_budget"]["max_target_generation"]
        ):
            issues.append(
                _issue(
                    "$.proposal.target_generation",
                    "GENERATION_NOT_PREAUTHORIZED",
                )
            )

    evaluator = preauth["evaluator"]
    require_equal(
        accept["evaluator"]["node_id"],
        evaluator["node_id"],
        "$.acceptance.evaluator.node_id",
    )
    require_equal(
        accept["evaluator"]["role"],
        evaluator["role"],
        "$.acceptance.evaluator.role",
    )
    evaluator_node = parent_nodes_by_id.get(evaluator["node_id"])
    if evaluator_node is None:
        issues.append(
            _issue("$.preauthorization.evaluator.node_id", "EVALUATOR_NOT_IN_PARENT")
        )
    else:
        require_equal(
            evaluator["role"],
            evaluator_node["role"],
            "$.preauthorization.evaluator.role",
            "EVALUATOR_PARENT_MISMATCH",
        )
        require_equal(
            evaluator["permission"],
            evaluator_node["permission"],
            "$.preauthorization.evaluator.permission",
            "EVALUATOR_PARENT_MISMATCH",
        )

    require_equal(res["operation"], operation, "$.result.operation")
    expected_outcome = (
        "REJECTED"
        if accept["decision"] == "REJECTED"
        else "NO_CHANGE"
        if operation == "NO_CHANGE"
        else "ACCEPTED"
    )
    require_equal(res["outcome"], expected_outcome, "$.result.outcome")
    if expected_outcome == "ACCEPTED":
        require_equal(
            res.get("target_generation"),
            prop["target_generation"],
            "$.result.target_generation",
        )
        require_equal(
            res.get("target_graph_digest"),
            prop["target_graph_digest"],
            "$.result.target_graph_digest",
        )

    added_ids = _validate_graph_delta(req, prop, parsed_parent, issues)
    if operation == "SPLIT_PENDING" and len(added_ids) == 1:
        scoped_node_ids = added_ids | {req["node_id"]}
    elif operation == "DISABLE_OPTIONAL_PENDING":
        scoped_node_ids = {req["node_id"]}
    else:
        scoped_node_ids = added_ids
    target_nodes = (
        _graph_items_by_id(prop["target_graph"]["nodes"])
        if operation in _MUTATING_OPERATIONS
        else {}
    )
    parent_nodes = parent_nodes_by_id
    for node_id in sorted(scoped_node_ids):
        node = target_nodes.get(node_id) or parent_nodes.get(node_id)
        if node is None:
            continue
        if node_id not in preauth["allowed_node_ids"]:
            issues.append(_issue("$.proposal.target_graph.nodes", "NODE_NOT_PREAUTHORIZED"))
        if node["role"] not in preauth["allowed_roles"]:
            issues.append(_issue("$.proposal.target_graph.nodes", "ROLE_NOT_PREAUTHORIZED"))
        if node["permission"] not in preauth["allowed_permissions"]:
            issues.append(
                _issue(
                    "$.proposal.target_graph.nodes",
                    "PERMISSION_NOT_PREAUTHORIZED",
                )
            )
    return _result(issues)


# Explicit long form for callers that prefer the contract family in the name.
validate_graph_evolution_decision_chain = validate_decision_chain


def validate_graph_evolution_outcome(
    *,
    result: Any | None = None,
    error: Any | None = None,
) -> GraphEvolutionValidationResult:
    """Validate that exactly one complete Result or Error is present."""

    if (result is None) == (error is None):
        return GraphEvolutionValidationResult(
            False,
            (_issue("$", "RESULT_ERROR_EXCLUSIVITY"),),
        )
    if result is not None:
        return validate_graph_evolution_result(result)
    return validate_graph_evolution_error(error)


def canonical_graph_evolution_request_digest(value: Any) -> str:
    return canonical_graph_evolution_digest("request", value)


def canonical_graph_evolution_preauthorization_digest(value: Any) -> str:
    return canonical_graph_evolution_digest("preauthorization", value)


def canonical_graph_evolution_proposal_digest(value: Any) -> str:
    return canonical_graph_evolution_digest("proposal", value)


def canonical_graph_evolution_acceptance_digest(value: Any) -> str:
    return canonical_graph_evolution_digest("acceptance", value)


def canonical_graph_evolution_result_digest(value: Any) -> str:
    return canonical_graph_evolution_digest("result", value)


def canonical_graph_evolution_error_digest(value: Any) -> str:
    return canonical_graph_evolution_digest("error", value)


__all__ = [
    "GRAPH_EVOLUTION_OPERATIONS",
    "GRAPH_EVOLUTION_SCHEMA_VERSION",
    "STAGE5_LINEAGE_CONTRACT_SHA256",
    "GraphEvolutionContractError",
    "GraphEvolutionValidationIssue",
    "GraphEvolutionValidationResult",
    "canonical_graph_evolution_acceptance_digest",
    "canonical_graph_evolution_digest",
    "canonical_graph_evolution_error_digest",
    "canonical_graph_evolution_preauthorization_digest",
    "canonical_graph_evolution_proposal_digest",
    "canonical_graph_evolution_request_digest",
    "canonical_graph_evolution_result_digest",
    "validate_decision_chain",
    "validate_graph_evolution_acceptance",
    "validate_graph_evolution_decision_chain",
    "validate_graph_evolution_document",
    "validate_graph_evolution_error",
    "validate_graph_evolution_outcome",
    "validate_graph_evolution_preauthorization",
    "validate_graph_evolution_proposal",
    "validate_graph_evolution_request",
    "validate_graph_evolution_result",
]
