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
    "240c98234e04e1c97414dae86fadd6a94de16649f71c2dc023e1a2ddf04cbe2a"
)

_OPERATIONS = frozenset(GRAPH_EVOLUTION_OPERATIONS)
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
_LOCATION = re.compile(
    r"^\$(?:(?:\.[A-Za-z_][A-Za-z0-9_]*)|\[[0-9]{1,7}\])*$"
)
_URI_OR_ROOT = re.compile(
    r"^(?:[A-Za-z]:|[/\\]|(?:file|https?|unc):)",
    re.IGNORECASE,
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
    if value["permission"] not in _PERMISSIONS:
        issues.append(_issue(f"{location}.permission", "INVALID_PERMISSION"))


def _validate_common(
    value: dict[str, Any],
    issues: list[GraphEvolutionValidationIssue],
) -> None:
    if value.get("operation") not in _OPERATIONS:
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
    if value.get("change_class") not in _CHANGE_CLASSES:
        issues.append(_issue("$.change_class", "INVALID_CHANGE_CLASS"))
    if value.get("reason_code") not in _REASON_CODES:
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
    if _exact_fields(document, _REQUEST_FIELDS, _REQUEST_FIELDS, "$", issues):
        _validate_schema_identity(document, "request", issues)
        if not _is_reference(document["request_id"]):
            issues.append(_issue("$.request_id", "INVALID_REFERENCE"))
        _validate_common(document, issues)
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
        if evaluator["permission"] not in _PERMISSIONS:
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
    allowed = required if operation == "NO_CHANGE" else required | _PROPOSAL_TARGET_FIELDS
    if not _exact_fields(document, required, allowed, "$", issues):
        return _result(issues)
    _validate_schema_identity(document, "proposal", issues)
    if not _is_reference(document["proposal_id"]):
        issues.append(_issue("$.proposal_id", "INVALID_REFERENCE"))
    if not _is_reference(document["request_id"]):
        issues.append(_issue("$.request_id", "INVALID_REFERENCE"))
    _validate_common(document, issues)
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
    if document["decision"] not in {"ACCEPTED", "REJECTED"}:
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
        if evaluator["decision"] not in {"APPROVE", "REJECT"}:
            issues.append(_issue("$.evaluator.decision", "INVALID_DECISION"))
        expected = (
            "APPROVE" if document["decision"] == "ACCEPTED" else "REJECT"
        )
        if evaluator["decision"] != expected:
            issues.append(_issue("$.evaluator.decision", "DECISION_MISMATCH"))
        if not _is_reference(evaluator["decision_ref"]):
            issues.append(_issue("$.evaluator.decision_ref", "INVALID_REFERENCE"))
    if document["reason_code"] not in _REASON_CODES:
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
    if document["operation"] not in _OPERATIONS:
        issues.append(_issue("$.operation", "INVALID_OPERATION"))
    if document["outcome"] not in {"ACCEPTED", "REJECTED", "NO_CHANGE"}:
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
    if operation == "NO_CHANGE":
        if outcome != "NO_CHANGE" or document["message_code"] != "NO_CHANGE_ACCEPTED":
            issues.append(_issue("$.outcome", "NO_CHANGE_OUTCOME_REQUIRED"))
        for name in _RESULT_TARGET_FIELDS:
            if name in document:
                issues.append(_issue(f"$.{name}", "NO_CHANGE_TARGET_FORBIDDEN"))
    elif outcome == "ACCEPTED":
        if document["message_code"] != "EVOLUTION_ACCEPTED":
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
    elif outcome == "REJECTED":
        if document["message_code"] != "EVOLUTION_REJECTED":
            issues.append(_issue("$.message_code", "MESSAGE_MISMATCH"))
        for name in _RESULT_TARGET_FIELDS:
            if name in document:
                issues.append(_issue(f"$.{name}", "REJECTED_TARGET_FORBIDDEN"))
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
    if error_code not in _ERROR_CODES:
        issues.append(_issue("$.error_code", "INVALID_ERROR_CODE"))
    elif document["message_code"] != _ERROR_MESSAGES[error_code]:
        issues.append(_issue("$.message_code", "MESSAGE_MISMATCH"))
    if document["document_kind"] not in _SCHEMA_IDS:
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
                or _LOCATION.fullmatch(item["location"]) is None
            ):
                issues.append(_issue(f"{location}.location", "INVALID_LOCATION"))
            if not _is_id(item["issue_code"]):
                issues.append(_issue(f"{location}.issue_code", "INVALID_ISSUE_CODE"))
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
    "validate_graph_evolution_acceptance",
    "validate_graph_evolution_document",
    "validate_graph_evolution_error",
    "validate_graph_evolution_outcome",
    "validate_graph_evolution_preauthorization",
    "validate_graph_evolution_proposal",
    "validate_graph_evolution_request",
    "validate_graph_evolution_result",
]
