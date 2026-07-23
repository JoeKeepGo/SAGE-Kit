"""Pure in-process validation for Graph Contract v1 and Node Result v1."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import heapq
import json
import re
from typing import Any, Mapping


GRAPH_SCHEMA_ID = "urn:sagekit:graph-contract:v1:graph"
NODE_RESULT_SCHEMA_ID = "urn:sagekit:graph-contract:v1:node-result"
SCHEMA_VERSION = 1

GOVERNANCE_LEVELS = frozenset({"Light", "Standard", "Heavy"})
AUTONOMY_LEVELS = frozenset({"turn-based", "goal-based"})
PERMISSION_MODES = frozenset(
    {
        "READ_ONLY_REVIEW",
        "WRITE_AUTHORIZED",
        "CORRECTIVE_AUTHORIZED",
        "ENVIRONMENT_WRITE_AUTHORIZED",
        "SUBMIT_AUTHORIZED",
    }
)
NODE_CLASSIFICATIONS = frozenset({"required", "optional"})
JOIN_POLICIES = frozenset(
    {
        "all-required",
        "required-plus-optional",
        "first-success",
        "manual-gate",
        "corrective-join",
    }
)
NODE_STATUSES = frozenset(
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
FINDING_SEVERITIES = frozenset({"P0", "P1", "P2", "P3"})

MAX_VALIDATION_ISSUES = 100
MAX_FINDINGS = 100
MAX_BOUNDED_TEXT_LENGTH = 4096

_GRAPH_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "graph_id",
        "generation",
        "source_authority",
        "governance_level",
        "autonomy_level",
        "completion_verifier",
        "human_gates",
        "nodes",
        "joins",
    }
)
_GRAPH_REQUIRED_FIELDS = _GRAPH_FIELDS - {"completion_verifier"}
_SOURCE_AUTHORITY_FIELDS = frozenset({"identity", "reference"})
_NODE_FIELDS = frozenset(
    {
        "id",
        "role",
        "depends_on",
        "permission",
        "verifier",
        "output_contract",
        "resources",
        "classification",
    }
)
_JOIN_FIELDS = frozenset({"id", "requires", "policy"})
_NODE_RESULT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "node_id",
        "status",
        "changed_paths",
        "evidence_refs",
        "findings",
        "authority_change",
        "proposed_next_nodes",
        "inspected_scope",
        "decision",
    }
)
_NODE_RESULT_REQUIRED_FIELDS = _NODE_RESULT_FIELDS - {
    "inspected_scope",
    "decision",
}
_FINDING_FIELDS = frozenset(
    {"finding_id", "severity", "summary", "evidence_refs"}
)
_TERMINAL_STATUSES = frozenset(
    {
        "SUCCEEDED",
        "NO_ACTION_REQUIRED",
        "DONE_WITH_CONCERNS",
        "FAILED",
        "HANDOFF",
        "BLOCKED",
        "CANCELLED",
    }
)
_ALLOWED_TRANSITIONS = {
    "PENDING": frozenset({"READY", "HANDOFF", "BLOCKED", "CANCELLED"}),
    "READY": frozenset(
        {
            "RUNNING",
            "WAITING_RESOURCE",
            "HANDOFF",
            "BLOCKED",
            "CANCELLED",
        }
    ),
    "RUNNING": frozenset(
        {
            "WAITING_RESOURCE",
            "SUCCEEDED",
            "NO_ACTION_REQUIRED",
            "DONE_WITH_CONCERNS",
            "FAILED",
            "NEEDS_CORRECTION",
            "HANDOFF",
            "BLOCKED",
            "CANCELLED",
        }
    ),
    "WAITING_RESOURCE": frozenset(
        {"READY", "RUNNING", "HANDOFF", "BLOCKED", "CANCELLED"}
    ),
    "NEEDS_CORRECTION": frozenset(
        {"READY", "HANDOFF", "BLOCKED", "CANCELLED"}
    ),
}
_SIMPLE_PATH_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, order=True)
class GraphValidationIssue:
    """A bounded, observable validation failure."""

    path: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class GraphValidationResult:
    """Deterministic result shared by Graph and Node Result validation."""

    valid: bool
    issues: tuple[GraphValidationIssue, ...]
    semantic_digest: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "issues": [issue.as_dict() for issue in self.issues],
            "semantic_digest": self.semantic_digest,
            "valid": self.valid,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class NodeTransitionResult:
    """A pure transition decision; it does not mutate or create state."""

    previous_status: str
    next_status: str
    allowed: bool
    reason: str


class GraphContractError(ValueError):
    """Raised when a semantic digest is requested for an invalid Graph."""

    def __init__(self, issues: tuple[GraphValidationIssue, ...]):
        self.issues = issues
        summary = ", ".join(
            f"{issue.code}@{issue.path}" for issue in issues[:5]
        )
        if len(issues) > 5:
            summary += ", ..."
        super().__init__(f"graph contract is invalid: {summary}")


class _IssueCollector:
    """Keep a deterministic bounded reservoir of the smallest issue triples."""

    def __init__(self) -> None:
        self._issues: set[GraphValidationIssue] = set()
        self._overflow = False

    def add(self, path: str, code: str, message: str) -> None:
        issue = GraphValidationIssue(path=path, code=code, message=message)
        if issue in self._issues:
            return
        capacity = MAX_VALIDATION_ISSUES - 1
        if len(self._issues) < capacity:
            self._issues.add(issue)
            return
        self._overflow = True
        largest = max(self._issues)
        if issue < largest:
            self._issues.remove(largest)
            self._issues.add(issue)

    def result(self, semantic_digest: str | None = None) -> GraphValidationResult:
        issues = set(self._issues)
        if self._overflow:
            issues.add(
                GraphValidationIssue(
                    path="$",
                    code="too-many-issues",
                    message="Validation issue limit reached; additional issues were omitted.",
                )
            )
        ordered = tuple(sorted(issues))
        return GraphValidationResult(
            valid=not ordered,
            issues=ordered,
            semantic_digest=semantic_digest if not ordered else None,
        )


def _path(parent: str, key: object) -> str:
    if type(key) is int:
        return f"{parent}[{key}]"
    if type(key) is str and _SIMPLE_PATH_KEY.fullmatch(key):
        return f"{parent}.{key}"
    encoded = json.dumps(str(key), ensure_ascii=False)
    return f"{parent}[{encoded}]"


def _object(
    value: Any,
    path: str,
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    issues: _IssueCollector,
) -> dict[str, Any] | None:
    if type(value) is not dict:
        issues.add(path, "invalid-type", "Expected an object.")
        return None
    string_keys = {key for key in value if type(key) is str}
    for key in sorted(required - string_keys):
        issues.add(_path(path, key), "missing-field", "Required field is missing.")
    unknown = [key for key in value if type(key) is not str or key not in allowed]
    for key in sorted(unknown, key=lambda item: (type(item).__name__, str(item))):
        issues.add(_path(path, key), "unknown-field", "Field is not allowed.")
    return value


def _nonempty_string(
    value: Any,
    path: str,
    issues: _IssueCollector,
    *,
    maximum: int | None = None,
) -> bool:
    if type(value) is not str:
        issues.add(path, "invalid-type", "Expected a string.")
        return False
    if len(value) == 0:
        issues.add(path, "empty-string", "String must not be empty.")
        return False
    if maximum is not None and len(value) > maximum:
        issues.add(
            path,
            "string-too-long",
            f"String exceeds the {maximum}-character limit.",
        )
        return False
    return True


def _integer(value: Any, path: str, issues: _IssueCollector) -> bool:
    if type(value) is not int:
        issues.add(path, "invalid-type", "Expected an integer.")
        return False
    return True


def _constant(
    value: Any,
    expected: object,
    path: str,
    issues: _IssueCollector,
) -> bool:
    if type(value) is not type(expected):
        issues.add(path, "invalid-type", "Value has the wrong primitive type.")
        return False
    if value != expected:
        issues.add(path, "invalid-constant", "Value does not match the contract constant.")
        return False
    return True


def _enum(
    value: Any,
    allowed: frozenset[str],
    path: str,
    issues: _IssueCollector,
) -> bool:
    if type(value) is not str:
        issues.add(path, "invalid-type", "Expected a string.")
        return False
    if value not in allowed:
        issues.add(path, "invalid-enum", "Value is not a contract enum member.")
        return False
    return True


def _string_array(
    value: Any,
    path: str,
    issues: _IssueCollector,
    *,
    nonempty: bool = False,
) -> list[str] | None:
    if type(value) is not list:
        issues.add(path, "invalid-type", "Expected an array.")
        return None
    if nonempty and not value:
        issues.add(path, "empty-array", "Array must contain at least one item.")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_path = _path(path, index)
        if not _nonempty_string(item, item_path, issues):
            continue
        result.append(item)
        if item in seen:
            issues.add(item_path, "duplicate-item", "Array items must be unique.")
        else:
            seen.add(item)
    return result


def _validate_source_authority(
    value: Any,
    path: str,
    issues: _IssueCollector,
) -> None:
    authority = _object(
        value,
        path,
        required=_SOURCE_AUTHORITY_FIELDS,
        allowed=_SOURCE_AUTHORITY_FIELDS,
        issues=issues,
    )
    if authority is None:
        return
    for field in sorted(_SOURCE_AUTHORITY_FIELDS):
        if field in authority:
            _nonempty_string(authority[field], _path(path, field), issues)


def _validate_node(
    value: Any,
    path: str,
    issues: _IssueCollector,
) -> dict[str, Any] | None:
    node = _object(
        value,
        path,
        required=_NODE_FIELDS,
        allowed=_NODE_FIELDS,
        issues=issues,
    )
    if node is None:
        return None
    for field in ("id", "role", "verifier"):
        if field in node:
            _nonempty_string(node[field], _path(path, field), issues)
    if "depends_on" in node:
        _string_array(node["depends_on"], _path(path, "depends_on"), issues)
    if "permission" in node:
        _enum(node["permission"], PERMISSION_MODES, _path(path, "permission"), issues)
    if "output_contract" in node:
        _constant(
            node["output_contract"],
            NODE_RESULT_SCHEMA_ID,
            _path(path, "output_contract"),
            issues,
        )
    if "resources" in node:
        _string_array(node["resources"], _path(path, "resources"), issues)
    if "classification" in node:
        _enum(
            node["classification"],
            NODE_CLASSIFICATIONS,
            _path(path, "classification"),
            issues,
        )
    return node


def _validate_join(
    value: Any,
    path: str,
    issues: _IssueCollector,
) -> dict[str, Any] | None:
    join = _object(
        value,
        path,
        required=_JOIN_FIELDS,
        allowed=_JOIN_FIELDS,
        issues=issues,
    )
    if join is None:
        return None
    if "id" in join:
        _nonempty_string(join["id"], _path(path, "id"), issues)
    if "requires" in join:
        _string_array(join["requires"], _path(path, "requires"), issues, nonempty=True)
    if "policy" in join:
        _enum(join["policy"], JOIN_POLICIES, _path(path, "policy"), issues)
    return join


def _valid_identifier(value: Any) -> bool:
    return type(value) is str and len(value) > 0


def _valid_string_list(value: Any) -> bool:
    return (
        type(value) is list
        and all(_valid_identifier(item) for item in value)
        and len(value) == len(set(value))
    )


def _validate_dependency_references_and_cycles(
    nodes: dict[str, dict[str, Any]],
    node_paths: dict[str, str],
    issues: _IssueCollector,
) -> None:
    identifiers = frozenset(nodes)
    dependencies: dict[str, set[str]] = {}
    for node_id in sorted(nodes):
        raw_dependencies = nodes[node_id].get("depends_on")
        if not _valid_string_list(raw_dependencies):
            dependencies[node_id] = set()
            continue
        valid_dependencies: set[str] = set()
        for index, dependency in enumerate(raw_dependencies):
            dependency_path = _path(
                _path(node_paths[node_id], "depends_on"),
                index,
            )
            if dependency not in identifiers:
                issues.add(
                    dependency_path,
                    "missing-dependency",
                    "Dependency does not reference a declared node.",
                )
                continue
            valid_dependencies.add(dependency)
            if dependency == node_id:
                issues.add(
                    dependency_path,
                    "self-dependency",
                    "A node cannot depend on itself.",
                )
        dependencies[node_id] = valid_dependencies

    indegree = {node_id: len(dependencies[node_id]) for node_id in nodes}
    dependents: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    for node_id, declared in dependencies.items():
        for dependency in declared:
            dependents[dependency].add(node_id)
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    processed = 0
    while ready:
        current = heapq.heappop(ready)
        processed += 1
        for dependent in sorted(dependents[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, dependent)
    if processed != len(nodes):
        issues.add(
            "$.nodes",
            "dependency-cycle",
            "The dependency graph contains a cycle.",
        )


def _referenced_nodes(
    join: Mapping[str, Any],
    nodes: dict[str, dict[str, Any]],
    path: str,
    issues: _IssueCollector,
) -> list[dict[str, Any]]:
    requires = join.get("requires")
    if not _valid_string_list(requires) or not requires:
        return []
    referenced: list[dict[str, Any]] = []
    for index, node_id in enumerate(requires):
        target = nodes.get(node_id)
        if target is None:
            issues.add(
                _path(_path(path, "requires"), index),
                "missing-join-reference",
                "Join requirement does not reference a declared node.",
            )
        else:
            referenced.append(target)
    return referenced


def _validate_first_success(
    referenced: list[dict[str, Any]],
    path: str,
    issues: _IssueCollector,
) -> None:
    if not referenced:
        return
    if len(referenced) < 2:
        issues.add(
            path,
            "unsafe-first-success-nonredundant",
            "First-success requires at least two redundant nodes.",
        )
    if any(node.get("classification") != "optional" for node in referenced):
        issues.add(
            path,
            "unsafe-first-success-classification",
            "First-success requires only optional nodes.",
        )
    if any(node.get("permission") != "READ_ONLY_REVIEW" for node in referenced):
        issues.add(
            path,
            "unsafe-first-success-permission",
            "First-success requires read-only review permission.",
        )
    baseline = referenced[0]
    comparisons = (
        ("role", False),
        ("depends_on", True),
        ("verifier", False),
        ("output_contract", False),
        ("resources", True),
    )
    for field, compare_as_set in comparisons:
        expected = baseline.get(field)
        equivalent = True
        for candidate in referenced[1:]:
            actual = candidate.get(field)
            if compare_as_set:
                if not _valid_string_list(expected) or not _valid_string_list(actual):
                    equivalent = False
                elif set(expected) != set(actual):
                    equivalent = False
            elif actual != expected:
                equivalent = False
        if not equivalent:
            issues.add(
                path,
                f"unsafe-first-success-{field.replace('_', '-')}",
                "First-success nodes are not structurally equivalent.",
            )


def _validate_join_semantics(
    joins: list[tuple[str, dict[str, Any]]],
    nodes: dict[str, dict[str, Any]],
    human_gates: list[str] | None,
    issues: _IssueCollector,
) -> None:
    for path, join in joins:
        referenced = _referenced_nodes(join, nodes, path, issues)
        requires = join.get("requires")
        if (
            not _valid_string_list(requires)
            or not requires
            or len(referenced) != len(requires)
        ):
            continue
        policy = join.get("policy")
        if policy == "all-required":
            for index, target in enumerate(referenced):
                if target.get("classification") != "required":
                    issues.add(
                        _path(_path(path, "requires"), index),
                        "all-required-optional-node",
                        "All-required joins may reference only required nodes.",
                    )
        elif policy == "required-plus-optional":
            if not any(
                target.get("classification") == "required" for target in referenced
            ):
                issues.add(
                    path,
                    "required-plus-optional-missing-required",
                    "Required-plus-optional joins require at least one required node.",
                )
        elif policy == "first-success":
            _validate_first_success(referenced, path, issues)
        elif policy == "manual-gate":
            join_id = join.get("id")
            if (
                not human_gates
                or not _valid_identifier(join_id)
                or join_id not in human_gates
            ):
                issues.add(
                    path,
                    "manual-gate-mismatch",
                    "Manual-gate join identity must exactly match a declared human gate.",
                )
        elif policy == "corrective-join":
            for index, target in enumerate(referenced):
                if target.get("classification") != "required":
                    issues.add(
                        _path(_path(path, "requires"), index),
                        "corrective-join-optional-node",
                        "Corrective joins may reference only required nodes.",
                    )
            issues.add(
                path,
                "corrective-join-responsibility-unproven",
                "Graph Contract v1 cannot prove independent review and corrective responsibilities.",
            )


def _semantic_reference_identity(reference: str) -> str:
    """Remove a relocatable base while preserving an explicit record fragment."""

    _, separator, fragment = reference.rpartition("#")
    if separator and fragment:
        return f"#{fragment}"
    return reference


def _semantic_graph_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    authority = payload["source_authority"]
    projection: dict[str, Any] = {
        "schema_id": payload["schema_id"],
        "schema_version": payload["schema_version"],
        "graph_id": payload["graph_id"],
        "generation": payload["generation"],
        "source_authority": {
            "identity": authority["identity"],
            "reference": _semantic_reference_identity(authority["reference"]),
        },
        "governance_level": payload["governance_level"],
        "autonomy_level": payload["autonomy_level"],
        "human_gates": sorted(payload["human_gates"]),
        "nodes": [],
        "joins": [],
    }
    if "completion_verifier" in payload:
        projection["completion_verifier"] = payload["completion_verifier"]
    projection["nodes"] = sorted(
        (
            {
                "id": item["id"],
                "role": item["role"],
                "depends_on": sorted(item["depends_on"]),
                "permission": item["permission"],
                "verifier": item["verifier"],
                "output_contract": item["output_contract"],
                "resources": sorted(item["resources"]),
                "classification": item["classification"],
            }
            for item in payload["nodes"]
        ),
        key=lambda item: item["id"],
    )
    projection["joins"] = sorted(
        (
            {
                "id": item["id"],
                "requires": sorted(item["requires"]),
                "policy": item["policy"],
            }
            for item in payload["joins"]
        ),
        key=lambda item: item["id"],
    )
    return projection


def _semantic_graph_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _semantic_graph_projection(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_graph_contract(payload: Any) -> GraphValidationResult:
    """Validate a Graph Contract v1 payload without reading or changing state."""

    issues = _IssueCollector()
    graph = _object(
        payload,
        "$",
        required=_GRAPH_REQUIRED_FIELDS,
        allowed=_GRAPH_FIELDS,
        issues=issues,
    )
    if graph is None:
        return issues.result()

    if "schema_id" in graph:
        _constant(graph["schema_id"], GRAPH_SCHEMA_ID, "$.schema_id", issues)
    if "schema_version" in graph:
        if _integer(graph["schema_version"], "$.schema_version", issues):
            _constant(graph["schema_version"], SCHEMA_VERSION, "$.schema_version", issues)
    if "graph_id" in graph:
        _nonempty_string(graph["graph_id"], "$.graph_id", issues)
    if "generation" in graph:
        if _integer(graph["generation"], "$.generation", issues):
            if graph["generation"] < 1:
                issues.add(
                    "$.generation",
                    "value-too-small",
                    "Generation must be at least one.",
                )
    if "source_authority" in graph:
        _validate_source_authority(
            graph["source_authority"], "$.source_authority", issues
        )
    if "governance_level" in graph:
        _enum(
            graph["governance_level"],
            GOVERNANCE_LEVELS,
            "$.governance_level",
            issues,
        )
    if "autonomy_level" in graph:
        _enum(
            graph["autonomy_level"],
            AUTONOMY_LEVELS,
            "$.autonomy_level",
            issues,
        )
    if "completion_verifier" in graph:
        _nonempty_string(
            graph["completion_verifier"], "$.completion_verifier", issues
        )
    human_gates = (
        _string_array(graph["human_gates"], "$.human_gates", issues)
        if "human_gates" in graph
        else None
    )

    parsed_nodes: list[tuple[str, dict[str, Any]]] = []
    nodes_value = graph.get("nodes")
    if type(nodes_value) is not list:
        if "nodes" in graph:
            issues.add("$.nodes", "invalid-type", "Expected an array.")
    else:
        if not nodes_value:
            issues.add("$.nodes", "empty-array", "Array must contain at least one item.")
        for index, value in enumerate(nodes_value):
            path = _path("$.nodes", index)
            parsed = _validate_node(value, path, issues)
            if parsed is not None:
                parsed_nodes.append((path, parsed))

    parsed_joins: list[tuple[str, dict[str, Any]]] = []
    joins_value = graph.get("joins")
    if not isinstance(joins_value, list):
        if "joins" in graph:
            issues.add("$.joins", "invalid-type", "Expected an array.")
    else:
        for index, value in enumerate(joins_value):
            path = _path("$.joins", index)
            parsed = _validate_join(value, path, issues)
            if parsed is not None:
                parsed_joins.append((path, parsed))

    nodes: dict[str, dict[str, Any]] = {}
    node_paths: dict[str, str] = {}
    for path, parsed in parsed_nodes:
        node_id = parsed.get("id")
        if not _valid_identifier(node_id):
            continue
        if node_id in nodes:
            issues.add(
                _path(path, "id"),
                "duplicate-node-id",
                "Node identities must be unique.",
            )
        else:
            nodes[node_id] = parsed
            node_paths[node_id] = path

    join_ids: set[str] = set()
    for path, parsed in parsed_joins:
        join_id = parsed.get("id")
        if not _valid_identifier(join_id):
            continue
        if join_id in join_ids:
            issues.add(
                _path(path, "id"),
                "duplicate-join-id",
                "Join identities must be unique.",
            )
        else:
            join_ids.add(join_id)

    if nodes:
        _validate_dependency_references_and_cycles(nodes, node_paths, issues)
    _validate_join_semantics(parsed_joins, nodes, human_gates, issues)

    result = issues.result()
    if not result.valid:
        return result
    return issues.result(_semantic_graph_digest(graph))


def canonical_graph_digest(payload: Any) -> str:
    """Return the canonical semantic digest of a valid Graph Contract v1 payload."""

    result = validate_graph_contract(payload)
    if not result.valid or result.semantic_digest is None:
        raise GraphContractError(result.issues)
    return result.semantic_digest


def _validate_finding(
    value: Any,
    path: str,
    issues: _IssueCollector,
) -> dict[str, Any] | None:
    finding = _object(
        value,
        path,
        required=_FINDING_FIELDS,
        allowed=_FINDING_FIELDS,
        issues=issues,
    )
    if finding is None:
        return None
    if "finding_id" in finding:
        _nonempty_string(finding["finding_id"], _path(path, "finding_id"), issues)
    if "severity" in finding:
        _enum(
            finding["severity"],
            FINDING_SEVERITIES,
            _path(path, "severity"),
            issues,
        )
    if "summary" in finding:
        _nonempty_string(
            finding["summary"],
            _path(path, "summary"),
            issues,
            maximum=MAX_BOUNDED_TEXT_LENGTH,
        )
    if "evidence_refs" in finding:
        _string_array(
            finding["evidence_refs"], _path(path, "evidence_refs"), issues
        )
    return finding


def validate_node_result(
    payload: Any,
    graph: Any | None = None,
) -> GraphValidationResult:
    """Validate a Node Result v1 envelope without executing its proposals."""

    issues = _IssueCollector()
    result_payload = _object(
        payload,
        "$",
        required=_NODE_RESULT_REQUIRED_FIELDS,
        allowed=_NODE_RESULT_FIELDS,
        issues=issues,
    )
    if result_payload is None:
        return issues.result()

    if "schema_id" in result_payload:
        _constant(
            result_payload["schema_id"],
            NODE_RESULT_SCHEMA_ID,
            "$.schema_id",
            issues,
        )
    if "schema_version" in result_payload:
        if _integer(result_payload["schema_version"], "$.schema_version", issues):
            _constant(
                result_payload["schema_version"],
                SCHEMA_VERSION,
                "$.schema_version",
                issues,
            )
    if "node_id" in result_payload:
        _nonempty_string(result_payload["node_id"], "$.node_id", issues)
    if "status" in result_payload:
        _enum(result_payload["status"], NODE_STATUSES, "$.status", issues)
    for field in ("changed_paths", "evidence_refs", "proposed_next_nodes"):
        if field in result_payload:
            _string_array(result_payload[field], _path("$", field), issues)
    if "inspected_scope" in result_payload:
        _string_array(
            result_payload["inspected_scope"],
            "$.inspected_scope",
            issues,
            nonempty=True,
        )
    if "decision" in result_payload:
        _nonempty_string(
            result_payload["decision"],
            "$.decision",
            issues,
            maximum=MAX_BOUNDED_TEXT_LENGTH,
        )
    if "authority_change" in result_payload:
        if type(result_payload["authority_change"]) is not bool:
            issues.add("$.authority_change", "invalid-type", "Expected a boolean.")

    findings = result_payload.get("findings")
    finding_ids: set[str] = set()
    if type(findings) is not list:
        if "findings" in result_payload:
            issues.add("$.findings", "invalid-type", "Expected an array.")
    else:
        if len(findings) > MAX_FINDINGS:
            issues.add(
                "$.findings",
                "too-many-items",
                f"Findings exceed the {MAX_FINDINGS}-item limit.",
            )
        for index, value in enumerate(findings):
            path = _path("$.findings", index)
            finding = _validate_finding(value, path, issues)
            if finding is None:
                continue
            finding_id = finding.get("finding_id")
            if not _valid_identifier(finding_id):
                continue
            if finding_id in finding_ids:
                issues.add(
                    _path(path, "finding_id"),
                    "duplicate-finding-id",
                    "Finding identities must be unique.",
                )
            else:
                finding_ids.add(finding_id)

    status = result_payload.get("status")
    if status == "NO_ACTION_REQUIRED":
        inspected_scope = result_payload.get("inspected_scope")
        if type(inspected_scope) is not list or not inspected_scope:
            issues.add(
                "$.inspected_scope",
                "no-action-missing-inspected-scope",
                "No-action results require a non-empty inspected scope.",
            )
        decision = result_payload.get("decision")
        if not _valid_identifier(decision):
            issues.add(
                "$.decision",
                "no-action-missing-decision",
                "No-action results require a non-empty decision.",
            )
        evidence_refs = result_payload.get("evidence_refs")
        if type(evidence_refs) is not list or not evidence_refs:
            issues.add(
                "$.evidence_refs",
                "no-action-missing-evidence",
                "No-action results require evidence references.",
            )

    if result_payload.get("authority_change") is True and not _valid_identifier(
        result_payload.get("decision")
    ):
        issues.add(
            "$.decision",
            "authority-change-missing-decision",
            "Authority-change requests require a non-empty decision.",
        )

    if graph is not None:
        graph_result = validate_graph_contract(graph)
        if not graph_result.valid:
            issues.add(
                "$graph",
                "invalid-graph",
                "Graph binding must be a valid Graph Contract v1 payload.",
            )
        else:
            graph_nodes = {item["id"]: item for item in graph["nodes"]}
            graph_node_ids = set(graph_nodes)
            node_id = result_payload.get("node_id")
            if _valid_identifier(node_id) and node_id not in graph_node_ids:
                issues.add(
                    "$.node_id",
                    "unknown-node",
                    "Node Result does not reference a declared graph node.",
                )
            elif _valid_identifier(node_id):
                changed_paths = result_payload.get("changed_paths")
                if (
                    graph_nodes[node_id]["permission"] == "READ_ONLY_REVIEW"
                    and type(changed_paths) is list
                    and changed_paths
                ):
                    issues.add(
                        "$.changed_paths",
                        "read-only-node-changed-paths",
                        "Read-only review nodes cannot report changed paths.",
                    )
            proposed = result_payload.get("proposed_next_nodes")
            if _valid_string_list(proposed):
                for index, proposed_id in enumerate(proposed):
                    if proposed_id not in graph_node_ids:
                        issues.add(
                            _path("$.proposed_next_nodes", index),
                            "unknown-proposed-next-node",
                            "Proposed next node is not declared by the graph.",
                        )

    return issues.result()


def validate_node_transition(
    previous_status: str,
    next_status: str,
) -> NodeTransitionResult:
    """Return a deterministic transition decision without changing state."""

    if type(previous_status) is not str or previous_status not in NODE_STATUSES:
        return NodeTransitionResult(
            previous_status=previous_status,
            next_status=next_status,
            allowed=False,
            reason="unknown-previous-status",
        )
    if type(next_status) is not str or next_status not in NODE_STATUSES:
        return NodeTransitionResult(
            previous_status=previous_status,
            next_status=next_status,
            allowed=False,
            reason="unknown-next-status",
        )
    if previous_status in _TERMINAL_STATUSES:
        return NodeTransitionResult(
            previous_status=previous_status,
            next_status=next_status,
            allowed=False,
            reason="terminal-status",
        )
    if next_status in _ALLOWED_TRANSITIONS.get(previous_status, frozenset()):
        return NodeTransitionResult(
            previous_status=previous_status,
            next_status=next_status,
            allowed=True,
            reason="allowed-transition",
        )
    return NodeTransitionResult(
        previous_status=previous_status,
        next_status=next_status,
        allowed=False,
        reason="transition-not-allowed",
    )


__all__ = [
    "GraphContractError",
    "GraphValidationIssue",
    "GraphValidationResult",
    "NodeTransitionResult",
    "canonical_graph_digest",
    "validate_graph_contract",
    "validate_node_result",
    "validate_node_transition",
]
