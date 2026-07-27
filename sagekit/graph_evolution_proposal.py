from __future__ import annotations

from collections.abc import Mapping
import re
from types import MappingProxyType
from typing import Any

from .evidence import EvidenceLineageOutcome
from .graph_contract import validate_graph_contract
from .graph_evolution_contract import (
    GraphEvolutionValidationIssue,
    canonical_graph_evolution_digest,
    validate_decision_chain,
    validate_graph_evolution_error,
    validate_graph_evolution_preauthorization,
    validate_graph_evolution_proposal,
    validate_graph_evolution_request,
)
from .graph_evolution_contract import _canonical_bytes as _strict_canonical_bytes
from .graph_evolution_contract import _parse_document as _strict_document


_PROPOSAL_SCHEMA_ID = "urn:sagekit:graph-evolution:v1:proposal"
_ERROR_SCHEMA_ID = "urn:sagekit:graph-evolution:v1:error"
_SCHEMA_VERSION = 1
_MAX_PARENT_CANONICAL_BYTES = 8 * 1024 * 1024
_MAX_LINEAGE_CANONICAL_BYTES = 8 * 1024 * 1024
_MAX_OUTCOME_CANONICAL_BYTES = 9 * 1024 * 1024
_MAX_ISSUES = 100
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_LINEAGE_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "graph_id",
        "graph_generation",
        "graph_digest",
        "decisions",
        "final_evidence_node_id",
    }
)
_ERROR_MESSAGES = {
    "INPUT_INVALID": "STRICT_DOCUMENT_REQUIRED",
    "INPUT_TOO_LARGE": "DOCUMENT_BYTE_BUDGET_EXCEEDED",
    "GRAPH_INVALID": "VALID_TARGET_GRAPH_REQUIRED",
    "GRAPH_BINDING_MISMATCH": "TARGET_GRAPH_BINDING_REQUIRED",
}
_NODE_TEMPLATES = {
    "ADD_CORRECTIVE": {
        "role": "Corrector",
        "permission": "CORRECTIVE_AUTHORIZED",
        "verifier": "verifier/corrective",
        "classification": "required",
    },
    "ADD_VERIFICATION": {
        "role": "Verifier",
        "permission": "READ_ONLY_REVIEW",
        "verifier": "verifier/verification",
        "classification": "required",
    },
    "ADD_INVESTIGATION": {
        "role": "Investigator",
        "permission": "READ_ONLY_REVIEW",
        "verifier": "verifier/investigation",
        "classification": "optional",
    },
}


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


class GraphEvolutionProposalOutcome:
    """Builder-created immutable snapshot of one proposal result or Error."""

    __slots__ = ("_result_snapshot", "_error_snapshot")

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise ValueError("GraphEvolutionProposalOutcome is builder-created")

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("GraphEvolutionProposalOutcome is immutable")

    def __delattr__(self, _name: str) -> None:
        raise AttributeError("GraphEvolutionProposalOutcome is immutable")

    @classmethod
    def _from_result(
        cls,
        result: Mapping[str, Any],
    ) -> GraphEvolutionProposalOutcome:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", _freeze_json(result))
        object.__setattr__(instance, "_error_snapshot", None)
        return instance

    @classmethod
    def _from_error(
        cls,
        error: Mapping[str, Any],
    ) -> GraphEvolutionProposalOutcome:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_result_snapshot", None)
        object.__setattr__(instance, "_error_snapshot", _freeze_json(error))
        return instance

    @property
    def result(self) -> dict[str, Any] | None:
        return _thaw_json(self._result_snapshot)

    @property
    def proposal(self) -> dict[str, Any] | None:
        result = self.result
        return None if result is None else result["proposal"]

    @property
    def error(self) -> dict[str, Any] | None:
        return _thaw_json(self._error_snapshot)

    @property
    def succeeded(self) -> bool:
        return self._result_snapshot is not None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GraphEvolutionProposalOutcome):
            return NotImplemented
        return (
            self._result_snapshot == other._result_snapshot
            and self._error_snapshot == other._error_snapshot
        )


def _issue(
    location: str,
    issue_code: str,
) -> GraphEvolutionValidationIssue:
    return GraphEvolutionValidationIssue(location, issue_code)


def _failure(
    error_code: str,
    document_kind: str,
    issues: list[GraphEvolutionValidationIssue]
    | tuple[GraphEvolutionValidationIssue, ...],
) -> GraphEvolutionProposalOutcome:
    ordered = tuple(sorted(set(issues)))[:_MAX_ISSUES]
    if not ordered:
        ordered = (_issue("$", "PROPOSAL_BUILD_FAILED"),)
    error = {
        "schema_id": _ERROR_SCHEMA_ID,
        "schema_version": _SCHEMA_VERSION,
        "error_code": error_code,
        "message_code": _ERROR_MESSAGES[error_code],
        "document_kind": document_kind,
        "issues": [item.as_dict() for item in ordered],
    }
    if not validate_graph_evolution_error(error).valid:
        error = {
            "schema_id": _ERROR_SCHEMA_ID,
            "schema_version": _SCHEMA_VERSION,
            "error_code": "INPUT_INVALID",
            "message_code": _ERROR_MESSAGES["INPUT_INVALID"],
            "document_kind": "proposal",
            "issues": [
                {
                    "issue_code": "PROPOSAL_BUILD_FAILED",
                    "location": "$",
                }
            ],
        }
    return GraphEvolutionProposalOutcome._from_error(error)


def _validator_failure(
    document_kind: str,
    issues: tuple[GraphEvolutionValidationIssue, ...],
) -> GraphEvolutionProposalOutcome:
    error_code = (
        "INPUT_TOO_LARGE"
        if any(
            item.issue_code == "DOCUMENT_BYTE_BUDGET_EXCEEDED"
            for item in issues
        )
        else "INPUT_INVALID"
    )
    return _failure(error_code, document_kind, issues)


def _snapshot_document(
    value: Any,
    *,
    document_kind: str,
    maximum_bytes: int,
) -> tuple[dict[str, Any] | None, GraphEvolutionProposalOutcome | None]:
    try:
        snapshot = _strict_document(value)
        canonical = _strict_canonical_bytes(snapshot)
    except (RecursionError, TypeError, ValueError):
        return None, _failure(
            "INPUT_INVALID",
            document_kind,
            [_issue("$", "STRICT_JSON_REQUIRED")],
        )
    if len(canonical) > maximum_bytes:
        return None, _failure(
            "INPUT_TOO_LARGE",
            document_kind,
            [_issue("$", "DOCUMENT_BYTE_BUDGET_EXCEEDED")],
        )
    return _thaw_json(_freeze_json(snapshot)), None


def _validate_lineage_binding(
    lineage: Any,
    parent_graph: dict[str, Any],
    parent_digest: str,
    request_lineage_digest: str,
) -> tuple[dict[str, Any] | None, GraphEvolutionProposalOutcome | None]:
    if (
        not isinstance(lineage, EvidenceLineageOutcome)
        or not lineage.succeeded
        or lineage.binding_digest is None
    ):
        return None, _failure(
            "INPUT_INVALID",
            "proposal",
            [_issue("$.stage5_lineage", "VALIDATED_LINEAGE_OUTCOME_REQUIRED")],
        )
    raw_result = lineage.result
    result, failure = _snapshot_document(
        raw_result,
        document_kind="proposal",
        maximum_bytes=_MAX_LINEAGE_CANONICAL_BYTES,
    )
    if failure is not None or result is None:
        return None, failure
    if (
        set(result) != _LINEAGE_FIELDS
        or result.get("schema_id")
        != "urn:sagekit:evidence-lineage:v1:result"
        or result.get("schema_version") != 1
        or type(result.get("decisions")) is not dict
        or not result["decisions"]
        or len(result["decisions"]) > 10_000
        or type(result.get("final_evidence_node_id")) is not str
        or result["final_evidence_node_id"] not in result["decisions"]
        or type(result.get("graph_digest")) is not str
        or _DIGEST.fullmatch(result["graph_digest"]) is None
    ):
        return None, _failure(
            "INPUT_INVALID",
            "proposal",
            [_issue("$.stage5_lineage", "VALIDATED_LINEAGE_OUTCOME_REQUIRED")],
        )
    if (
        result["graph_id"] != parent_graph["graph_id"]
        or result["graph_generation"] != parent_graph["generation"]
        or result["graph_digest"] != parent_digest
    ):
        return None, _failure(
            "GRAPH_BINDING_MISMATCH",
            "proposal",
            [
                _issue(
                    "$.stage5_lineage",
                    "LINEAGE_GRAPH_BINDING_MISMATCH",
                )
            ],
        )
    if request_lineage_digest != lineage.binding_digest:
        return None, _failure(
            "INPUT_INVALID",
            "proposal",
            [
                _issue(
                    "$.stage5_lineage_digest",
                    "LINEAGE_DIGEST_MISMATCH",
                )
            ],
        )
    return result, None


def _new_node(
    operation: str,
    node_id: str,
) -> dict[str, Any]:
    template = _NODE_TEMPLATES[operation]
    return {
        "id": node_id,
        "role": template["role"],
        "depends_on": [],
        "permission": template["permission"],
        "verifier": template["verifier"],
        "output_contract": "urn:sagekit:graph-contract:v1:node-result",
        "resources": [],
        "classification": template["classification"],
    }


def _split_node_id(
    subject_id: str,
    parent_graph: dict[str, Any],
    preauthorization: dict[str, Any],
) -> str | None:
    parent_ids = {node["id"] for node in parent_graph["nodes"]}
    available = sorted(
        node_id
        for node_id in preauthorization["allowed_node_ids"]
        if node_id not in parent_ids
    )
    related = [
        node_id
        for node_id in available
        if node_id.startswith(f"{subject_id}/")
        or node_id.startswith(f"{subject_id}-")
    ]
    if len(related) == 1:
        return related[0]
    if not related and len(available) == 1:
        return available[0]
    return None


def _build_target_graph(
    parent_graph: dict[str, Any],
    request: dict[str, Any],
    preauthorization: dict[str, Any],
) -> tuple[dict[str, Any] | None, GraphEvolutionProposalOutcome | None]:
    operation = request["operation"]
    target = _thaw_json(_freeze_json(parent_graph))
    target["generation"] = parent_graph["generation"] + 1
    subject_id = request["node_id"]

    if operation in _NODE_TEMPLATES:
        target["nodes"].append(_new_node(operation, subject_id))
        return target, None

    nodes_by_id = {node["id"]: node for node in parent_graph["nodes"]}
    subject = nodes_by_id.get(subject_id)
    if operation == "SPLIT_PENDING":
        if subject is None:
            return None, _failure(
                "INPUT_INVALID",
                "proposal",
                [_issue("$.request.node_id", "PENDING_SPLIT_REQUIRED")],
            )
        split_id = _split_node_id(subject_id, parent_graph, preauthorization)
        if split_id is None:
            return None, _failure(
                "INPUT_INVALID",
                "proposal",
                [_issue("$.request.node_id", "UNAMBIGUOUS_SPLIT_NODE_REQUIRED")],
            )
        split_node = _thaw_json(_freeze_json(subject))
        split_node["id"] = split_id
        target["nodes"].append(split_node)
        return target, None

    if operation == "DISABLE_OPTIONAL_PENDING":
        if subject is None or subject["classification"] != "optional":
            return None, _failure(
                "INPUT_INVALID",
                "proposal",
                [_issue("$.request.node_id", "OPTIONAL_SUBJECT_REQUIRED")],
            )
        for join in parent_graph["joins"]:
            if subject_id not in join["requires"]:
                continue
            if (
                join["policy"] != "first-success"
                or join["id"] in parent_graph["human_gates"]
            ):
                return None, _failure(
                    "INPUT_INVALID",
                    "proposal",
                    [
                        _issue(
                            "$.parent_graph.joins",
                            "REQUIRED_JOIN_OR_GATE_REFERENCES_SUBJECT",
                        )
                    ],
                )
        target["nodes"] = [
            node for node in target["nodes"] if node["id"] != subject_id
        ]
        updated_joins = []
        for join in target["joins"]:
            if subject_id not in join["requires"]:
                updated_joins.append(join)
                continue
            updated = dict(join)
            updated["requires"] = [
                node_id
                for node_id in join["requires"]
                if node_id != subject_id
            ]
            if updated["requires"]:
                updated_joins.append(updated)
        target["joins"] = updated_joins
        return target, None

    return None, _failure(
        "INPUT_INVALID",
        "proposal",
        [_issue("$.request.operation", "INVALID_OPERATION")],
    )


def _chain_precheck(
    request: dict[str, Any],
    preauthorization: dict[str, Any],
    proposal: dict[str, Any],
    parent_graph: dict[str, Any],
    request_digest: str,
    preauthorization_digest: str,
    proposal_digest: str,
) -> tuple[GraphEvolutionValidationIssue, ...]:
    evaluator = preauthorization["evaluator"]
    acceptance = {
        "schema_id": "urn:sagekit:graph-evolution:v1:acceptance",
        "schema_version": 1,
        "acceptance_id": f"acceptance/precheck/{proposal_digest}",
        "proposal_digest": proposal_digest,
        "preauthorization_digest": preauthorization_digest,
        "decision": "REJECTED",
        "authority": preauthorization["authority"],
        "evaluator": {
            "node_id": evaluator["node_id"],
            "role": evaluator["role"],
            "decision": "REJECT",
            "decision_ref": "decision/stage6b-precheck",
        },
        "reason_code": "EVALUATOR_REJECTED",
        "decision_refs": ["decision/stage6b-precheck"],
    }
    acceptance_digest = canonical_graph_evolution_digest(
        "acceptance",
        acceptance,
    )
    result = {
        "schema_id": "urn:sagekit:graph-evolution:v1:result",
        "schema_version": 1,
        "request_digest": request_digest,
        "preauthorization_digest": preauthorization_digest,
        "proposal_digest": proposal_digest,
        "acceptance_digest": acceptance_digest,
        "operation": request["operation"],
        "outcome": "REJECTED",
        "graph_id": request["graph_id"],
        "parent_generation": request["parent_generation"],
        "parent_graph_digest": request["parent_graph_digest"],
        "message_code": "EVOLUTION_REJECTED",
    }
    return validate_decision_chain(
        request,
        preauthorization,
        proposal,
        acceptance,
        result,
        parent_graph,
    ).issues


def build_graph_evolution_proposal(
    parent_graph: Any,
    request: Any,
    preauthorization: Any,
    stage5_lineage: Any,
) -> GraphEvolutionProposalOutcome:
    """Build one inert, digest-bound Graph evolution proposal without applying it."""

    request_validation = validate_graph_evolution_request(request)
    if not request_validation.valid or request_validation.digest is None:
        return _validator_failure("request", request_validation.issues)
    preauthorization_validation = validate_graph_evolution_preauthorization(
        preauthorization
    )
    if (
        not preauthorization_validation.valid
        or preauthorization_validation.digest is None
    ):
        return _validator_failure(
            "preauthorization",
            preauthorization_validation.issues,
        )

    request_snapshot, failure = _snapshot_document(
        request,
        document_kind="request",
        maximum_bytes=1024 * 1024,
    )
    if failure is not None or request_snapshot is None:
        return failure
    preauthorization_snapshot, failure = _snapshot_document(
        preauthorization,
        document_kind="preauthorization",
        maximum_bytes=1024 * 1024,
    )
    if failure is not None or preauthorization_snapshot is None:
        return failure
    parent_snapshot, failure = _snapshot_document(
        parent_graph,
        document_kind="proposal",
        maximum_bytes=_MAX_PARENT_CANONICAL_BYTES,
    )
    if failure is not None or parent_snapshot is None:
        return failure

    parent_validation = validate_graph_contract(parent_snapshot)
    if not parent_validation.valid or parent_validation.semantic_digest is None:
        return _failure(
            "GRAPH_INVALID",
            "proposal",
            [_issue("$.parent_graph", "PARENT_GRAPH_INVALID")],
        )
    parent_digest = parent_validation.semantic_digest
    _lineage_snapshot, failure = _validate_lineage_binding(
        stage5_lineage,
        parent_snapshot,
        parent_digest,
        request_snapshot["stage5_lineage_digest"],
    )
    if failure is not None:
        return failure

    operation = request_snapshot["operation"]
    proposal = dict(request_snapshot)
    proposal["schema_id"] = _PROPOSAL_SCHEMA_ID
    proposal["proposal_id"] = f"proposal/{request_validation.digest}"
    proposal["request_digest"] = request_validation.digest
    proposal["preauthorization_digest"] = preauthorization_validation.digest

    if operation != "NO_CHANGE":
        target_graph, failure = _build_target_graph(
            parent_snapshot,
            request_snapshot,
            preauthorization_snapshot,
        )
        if failure is not None or target_graph is None:
            return failure
        target_validation = validate_graph_contract(target_graph)
        if (
            not target_validation.valid
            or target_validation.semantic_digest is None
        ):
            return _failure(
                "GRAPH_INVALID",
                "proposal",
                [_issue("$.target_graph", "GRAPH_INVALID")],
            )
        proposal["target_generation"] = parent_snapshot["generation"] + 1
        proposal["target_graph"] = target_graph
        proposal["target_graph_digest"] = target_validation.semantic_digest

    proposal_validation = validate_graph_evolution_proposal(proposal)
    if not proposal_validation.valid or proposal_validation.digest is None:
        if any(
            item.issue_code == "DOCUMENT_BYTE_BUDGET_EXCEEDED"
            for item in proposal_validation.issues
        ):
            error_code = "INPUT_TOO_LARGE"
        elif any(
            item.issue_code in {"GRAPH_INVALID", "GRAPH_BINDING_MISMATCH"}
            for item in proposal_validation.issues
        ):
            error_code = "GRAPH_INVALID"
        else:
            error_code = "INPUT_INVALID"
        return _failure(
            error_code,
            "proposal",
            list(proposal_validation.issues),
        )

    chain_issues = _chain_precheck(
        request_snapshot,
        preauthorization_snapshot,
        proposal,
        parent_snapshot,
        request_validation.digest,
        preauthorization_validation.digest,
        proposal_validation.digest,
    )
    if chain_issues:
        return _failure("INPUT_INVALID", "proposal", list(chain_issues))

    result = {
        "proposal": proposal,
        "proposal_digest": proposal_validation.digest,
        "grants_execution_authority": False,
        "grants_graph_mutation_authority": False,
        "grants_gate_authority": False,
        "grants_write_authority": False,
        "grants_acceptance_authority": False,
    }
    try:
        if len(_strict_canonical_bytes(result)) > _MAX_OUTCOME_CANONICAL_BYTES:
            return _failure(
                "INPUT_TOO_LARGE",
                "proposal",
                [_issue("$", "DOCUMENT_BYTE_BUDGET_EXCEEDED")],
            )
    except (RecursionError, TypeError, ValueError):
        return _failure(
            "INPUT_INVALID",
            "proposal",
            [_issue("$", "STRICT_JSON_REQUIRED")],
        )
    return GraphEvolutionProposalOutcome._from_result(result)


__all__ = [
    "GraphEvolutionProposalOutcome",
    "build_graph_evolution_proposal",
]
