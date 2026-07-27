from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import Any
from unicodedata import normalize

from . import evidence as _evidence
from . import graph_evolution_contract as _contract
from . import graph_evolution_convergence as _convergence
from . import graph_evolution_proposal as _proposal
from . import review as _review
from .convergence import PreauthorizedConvergenceAuthority


_ACCEPTANCE_SCHEMA_ID = "urn:sagekit:graph-evolution:v1:acceptance"
_RESULT_SCHEMA_ID = "urn:sagekit:graph-evolution:v1:result"
_ERROR_SCHEMA_ID = "urn:sagekit:graph-evolution:v1:error"
_SCHEMA_VERSION = 1
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MUTATING_OPERATIONS = frozenset(
    {
        "ADD_CORRECTIVE",
        "ADD_VERIFICATION",
        "ADD_INVESTIGATION",
        "SPLIT_PENDING",
        "DISABLE_OPTIONAL_PENDING",
    }
)
_AUTO_CHANGE_CLASSES = frozenset({"C0", "C1"})
_AUTHORITY_ISSUES = frozenset(
    {
        "AUTHORITY_CHANGED",
        "BUDGET_EXHAUSTED",
        "CLASS_NOT_PREAUTHORIZED",
        "CONTRACT_CHANGED",
        "EVALUATOR_NOT_ALLOWED",
        "GENERATION_NOT_PREAUTHORIZED",
        "IMMUTABLE_GRAPH_CONTROL_CHANGED",
        "NODE_NOT_PREAUTHORIZED",
        "OPERATION_NOT_PREAUTHORIZED",
        "PARENT_AUTHORITY_MISMATCH",
        "PATH_NOT_PREAUTHORIZED",
        "PERMISSION_NOT_PREAUTHORIZED",
        "PROPOSER_PARENT_MISMATCH",
        "ROLE_NOT_PREAUTHORIZED",
        "STALE_PROPOSAL",
    }
)
_CANONICAL_GOVERNANCE_PATHS = frozenset(
    {
        "docs/SAGE_CORE.md",
        "docs/APPROVAL_GATES.md",
        "docs/QUALITY_GATES.md",
        "docs/agent/GOVERNANCE_LEVELS.md",
        "docs/agent/SESSION_ORCHESTRATION.md",
    }
)
_GRANT_FIELDS = (
    "grants_execution_authority",
    "grants_graph_mutation_authority",
    "grants_gate_authority",
    "grants_write_authority",
    "grants_acceptance_authority",
)


class GraphEvolutionAcceptanceCode(str, Enum):
    """Closed Stage 6C acceptance outcomes."""

    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    PM_DECISION_REQUIRED = "PM_DECISION_REQUIRED"
    PM_ACCEPTED = "PM_ACCEPTED"
    NO_CHANGE_ACCEPTED = "NO_CHANGE_ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED_NO_PROGRESS = "BLOCKED_NO_PROGRESS"


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


class GraphEvolutionAcceptanceOutcome:
    """Resolver-created immutable snapshots of one pure acceptance decision."""

    __slots__ = (
        "_result_snapshot",
        "_error_snapshot",
        "_convergence",
        "_receipt_status",
        "_issue_codes",
    )

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise ValueError("GraphEvolutionAcceptanceOutcome is resolver-created")

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("GraphEvolutionAcceptanceOutcome is immutable")

    def __delattr__(self, _name: str) -> None:
        raise AttributeError("GraphEvolutionAcceptanceOutcome is immutable")

    @classmethod
    def _from_resolution(
        cls,
        *,
        code: GraphEvolutionAcceptanceCode,
        proposal: Mapping[str, Any] | None,
        acceptance: Mapping[str, Any] | None,
        graph_evolution_result: Mapping[str, Any] | None,
        convergence: _convergence.GraphEvolutionConvergenceDecision | None,
        receipt_status: _review.ReceiptStatus,
        issue_codes: tuple[str, ...] = (),
        error: Mapping[str, Any] | None = None,
    ) -> GraphEvolutionAcceptanceOutcome:
        instance = object.__new__(cls)
        result = {
            "code": code.value,
            "proposal": (
                None if proposal is None else _thaw_json(_freeze_json(proposal))
            ),
            "acceptance": (
                None
                if acceptance is None
                else _thaw_json(_freeze_json(acceptance))
            ),
            "graph_evolution_result": (
                None
                if graph_evolution_result is None
                else _thaw_json(_freeze_json(graph_evolution_result))
            ),
            **{field: False for field in _GRANT_FIELDS},
        }
        object.__setattr__(instance, "_result_snapshot", _freeze_json(result))
        object.__setattr__(
            instance,
            "_error_snapshot",
            None if error is None else _freeze_json(error),
        )
        object.__setattr__(instance, "_convergence", convergence)
        object.__setattr__(instance, "_receipt_status", receipt_status)
        object.__setattr__(
            instance,
            "_issue_codes",
            tuple(dict.fromkeys(issue_codes)),
        )
        return instance

    @property
    def result(self) -> dict[str, Any]:
        return _thaw_json(self._result_snapshot)

    @property
    def error(self) -> dict[str, Any] | None:
        return _thaw_json(self._error_snapshot)

    @property
    def code(self) -> GraphEvolutionAcceptanceCode:
        return GraphEvolutionAcceptanceCode(self._result_snapshot["code"])

    @property
    def proposal(self) -> dict[str, Any] | None:
        return self.result["proposal"]

    @property
    def acceptance(self) -> dict[str, Any] | None:
        return self.result["acceptance"]

    @property
    def graph_evolution_result(self) -> dict[str, Any] | None:
        return self.result["graph_evolution_result"]

    @property
    def convergence(
        self,
    ) -> _convergence.GraphEvolutionConvergenceDecision | None:
        return self._convergence

    @property
    def receipt_status(self) -> _review.ReceiptStatus:
        return self._receipt_status

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return self._issue_codes

    @property
    def succeeded(self) -> bool:
        return self.code in {
            GraphEvolutionAcceptanceCode.AUTO_ACCEPTED,
            GraphEvolutionAcceptanceCode.PM_ACCEPTED,
            GraphEvolutionAcceptanceCode.NO_CHANGE_ACCEPTED,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GraphEvolutionAcceptanceOutcome):
            return NotImplemented
        return (
            self._result_snapshot == other._result_snapshot
            and self._error_snapshot == other._error_snapshot
            and self._convergence == other._convergence
            and self._receipt_status is other._receipt_status
            and self._issue_codes == other._issue_codes
        )


def _snapshot_document(
    value: Any,
    *,
    document_kind: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        snapshot = _contract._parse_document(value)
        canonical = _contract._canonical_bytes(snapshot)
    except (RecursionError, TypeError, ValueError):
        return None, _error(
            document_kind,
            "INPUT_INVALID",
            ("STRICT_JSON_REQUIRED",),
        )
    if len(canonical) > _MAX_SOURCE_BYTES:
        return None, _error(
            document_kind,
            "INPUT_TOO_LARGE",
            ("DOCUMENT_BYTE_BUDGET_EXCEEDED",),
        )
    return _thaw_json(_freeze_json(snapshot)), None


def _error(
    document_kind: str,
    error_code: str,
    issue_codes: tuple[str, ...],
) -> dict[str, Any]:
    messages = {
        "INPUT_INVALID": "STRICT_DOCUMENT_REQUIRED",
        "INPUT_TOO_LARGE": "DOCUMENT_BYTE_BUDGET_EXCEEDED",
    }
    return {
        "schema_id": _ERROR_SCHEMA_ID,
        "schema_version": _SCHEMA_VERSION,
        "error_code": error_code,
        "message_code": messages[error_code],
        "document_kind": document_kind,
        "issues": [
            {"issue_code": code, "location": "$"}
            for code in tuple(dict.fromkeys(issue_codes))[:100]
        ],
    }


def _resolved(
    code: GraphEvolutionAcceptanceCode,
    *,
    proposal: Mapping[str, Any] | None = None,
    acceptance: Mapping[str, Any] | None = None,
    graph_evolution_result: Mapping[str, Any] | None = None,
    convergence: _convergence.GraphEvolutionConvergenceDecision | None = None,
    receipt_status: _review.ReceiptStatus = _review.ReceiptStatus.INVALID_RECEIPT,
    issue_codes: tuple[str, ...] = (),
    error: Mapping[str, Any] | None = None,
) -> GraphEvolutionAcceptanceOutcome:
    return GraphEvolutionAcceptanceOutcome._from_resolution(
        code=code,
        proposal=proposal,
        acceptance=acceptance,
        graph_evolution_result=graph_evolution_result,
        convergence=convergence,
        receipt_status=receipt_status,
        issue_codes=issue_codes,
        error=error,
    )


def _validation_issue_codes(
    validation: _contract.GraphEvolutionValidationResult,
) -> tuple[str, ...]:
    return tuple(item.issue_code for item in validation.issues)


def _proposal_issue_codes(error: Mapping[str, Any] | None) -> tuple[str, ...]:
    if error is None or type(error.get("issues")) is not list:
        return ("PROPOSAL_BUILD_FAILED",)
    return tuple(
        item.get("issue_code", "PROPOSAL_BUILD_FAILED")
        for item in error["issues"]
        if type(item) is dict
    )


def _requires_pm(issue_codes: tuple[str, ...]) -> bool:
    return bool(_AUTHORITY_ISSUES.intersection(issue_codes))


def _is_canonical_governance_path(path: str) -> bool:
    return (
        path in _CANONICAL_GOVERNANCE_PATHS
        or path.startswith("docs/agent/")
        or path.startswith("sagekit/resources/docs/agent/")
        or path.startswith("docs/contracts/graph-evolution/")
        or path.startswith("sagekit/resources/contracts/graph-evolution/")
    )


def _identity_key(value: str) -> str:
    return normalize("NFKC", value).casefold()


def _independent_evaluator(
    request: Mapping[str, Any],
    preauthorization: Mapping[str, Any],
    assignment: object,
) -> bool:
    proposer_id = request["proposer"]["node_id"]
    acceptor_id = preauthorization["evaluator"]["node_id"]
    authority_ids = (
        request["authority"]["authority_id"],
        preauthorization["authority"]["authority_id"],
    )
    internal_principals = {
        _identity_key(proposer_id),
        _identity_key(acceptor_id),
        *(_identity_key(authority_id) for authority_id in authority_ids),
    }

    if type(assignment) is _review.FreshContextEvaluatorAssignment:
        return (
            _identity_key(assignment.author_identity)
            == _identity_key(proposer_id)
            and _identity_key(assignment.evaluator_identity)
            not in internal_principals
            and assignment.author_assignment_digest
            != assignment.evaluator_assignment_digest
        )
    if type(assignment) is _review.DeterministicEvaluatorAssignment:
        evaluator_key = _identity_key(acceptor_id)
        return evaluator_key not in {
            _identity_key(proposer_id),
            *(_identity_key(authority_id) for authority_id in authority_ids),
        }
    return False


def _lineage_issue_codes(
    lineage: _evidence.EvidenceLineageOutcome,
    *,
    operation: str,
) -> tuple[str, ...]:
    if not lineage.succeeded or lineage.result is None:
        return ("VALIDATED_LINEAGE_OUTCOME_REQUIRED",)
    if operation not in _MUTATING_OPERATIONS:
        return ()
    result = lineage.result
    final_id = result.get("final_evidence_node_id")
    decisions = result.get("decisions")
    if (
        type(final_id) is not str
        or type(decisions) is not dict
        or type(decisions.get(final_id)) is not dict
    ):
        return ("FINAL_EVIDENCE_DECISION_REQUIRED",)
    final_decision = decisions[final_id]
    if final_decision.get("disposition") != "INVALIDATE":
        return ("FINAL_EVIDENCE_REUSE_FORBIDDEN",)
    reasons = final_decision.get("reason_codes")
    if type(reasons) is not list or not {
        "CANDIDATE_CHANGED",
        "GRAPH_IDENTITY_CHANGED",
    }.intersection(reasons):
        return ("CANDIDATE_INVALIDATION_REQUIRED",)
    return ()


def _convergence_binding_issues(
    request: Mapping[str, Any],
    preauthorization: Mapping[str, Any],
    authority: PreauthorizedConvergenceAuthority,
) -> tuple[str, ...]:
    expected = preauthorization["authority"]
    issues: list[str] = []
    if (
        authority.authority_id != expected["authority_id"]
        or authority.authority_ref != expected["authority_ref"]
    ):
        issues.append("CONVERGENCE_AUTHORITY_MISMATCH")
    if authority.execution_scope != request["graph_id"]:
        issues.append("CONVERGENCE_SCOPE_MISMATCH")
    return tuple(issues)


def _acceptance_record(
    request: Mapping[str, Any],
    preauthorization: Mapping[str, Any],
    proposal_digest: str,
    preauthorization_digest: str,
    *,
    accepted: bool,
) -> dict[str, Any]:
    evaluator = preauthorization["evaluator"]
    decision_ref = evaluator["authority_ref"]
    decision_refs = list(
        dict.fromkeys([*request["decision_refs"], decision_ref])
    )
    return {
        "schema_id": _ACCEPTANCE_SCHEMA_ID,
        "schema_version": _SCHEMA_VERSION,
        "acceptance_id": (
            f"acceptance/{'auto' if accepted else 'rejected'}/{proposal_digest}"
        ),
        "proposal_digest": proposal_digest,
        "preauthorization_digest": preauthorization_digest,
        "decision": "ACCEPTED" if accepted else "REJECTED",
        "authority": _thaw_json(_freeze_json(preauthorization["authority"])),
        "evaluator": {
            "node_id": evaluator["node_id"],
            "role": evaluator["role"],
            "decision": "APPROVE" if accepted else "REJECT",
            "decision_ref": decision_ref,
        },
        "reason_code": (
            "WITHIN_PREAUTHORIZATION" if accepted else "EVALUATOR_REJECTED"
        ),
        "decision_refs": decision_refs,
    }


def _result_record(
    request: Mapping[str, Any],
    request_digest: str,
    preauthorization_digest: str,
    proposal: Mapping[str, Any],
    proposal_digest: str,
    acceptance: Mapping[str, Any],
    *,
    accepted: bool,
) -> dict[str, Any]:
    acceptance_digest = _contract.canonical_graph_evolution_digest(
        "acceptance",
        acceptance,
    )
    operation = request["operation"]
    if not accepted:
        outcome = "REJECTED"
        message = "EVOLUTION_REJECTED"
    elif operation == "NO_CHANGE":
        outcome = "NO_CHANGE"
        message = "NO_CHANGE_ACCEPTED"
    else:
        outcome = "ACCEPTED"
        message = "EVOLUTION_ACCEPTED"
    result = {
        "schema_id": _RESULT_SCHEMA_ID,
        "schema_version": _SCHEMA_VERSION,
        "request_digest": request_digest,
        "preauthorization_digest": preauthorization_digest,
        "proposal_digest": proposal_digest,
        "acceptance_digest": acceptance_digest,
        "operation": operation,
        "outcome": outcome,
        "graph_id": request["graph_id"],
        "parent_generation": request["parent_generation"],
        "parent_graph_digest": request["parent_graph_digest"],
        "message_code": message,
    }
    if accepted and operation in _MUTATING_OPERATIONS:
        result["target_generation"] = proposal["target_generation"]
        result["target_graph_digest"] = proposal["target_graph_digest"]
    return result


def _finalize_chain(
    *,
    code: GraphEvolutionAcceptanceCode,
    parent_graph: Mapping[str, Any],
    request: Mapping[str, Any],
    preauthorization: Mapping[str, Any],
    proposal: Mapping[str, Any],
    acceptance: Mapping[str, Any],
    convergence: _convergence.GraphEvolutionConvergenceDecision,
    receipt_status: _review.ReceiptStatus,
) -> GraphEvolutionAcceptanceOutcome:
    request_digest = _contract.canonical_graph_evolution_digest(
        "request",
        request,
    )
    preauthorization_digest = _contract.canonical_graph_evolution_digest(
        "preauthorization",
        preauthorization,
    )
    proposal_digest = _contract.canonical_graph_evolution_digest(
        "proposal",
        proposal,
    )
    accepted = acceptance["decision"] == "ACCEPTED"
    result = _result_record(
        request,
        request_digest,
        preauthorization_digest,
        proposal,
        proposal_digest,
        acceptance,
        accepted=accepted,
    )
    chain = _contract.validate_decision_chain(
        request,
        preauthorization,
        proposal,
        acceptance,
        result,
        parent_graph,
    )
    if not chain.valid:
        issue_codes = _validation_issue_codes(chain)
        routed_code = (
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED
            if _requires_pm(issue_codes)
            else GraphEvolutionAcceptanceCode.REJECTED
        )
        return _resolved(
            routed_code,
            proposal=proposal,
            convergence=convergence,
            receipt_status=receipt_status,
            issue_codes=issue_codes,
            error=_error("acceptance", "INPUT_INVALID", issue_codes),
        )
    return _resolved(
        code,
        proposal=proposal,
        acceptance=acceptance,
        graph_evolution_result=result,
        convergence=convergence,
        receipt_status=receipt_status,
    )


def resolve_graph_evolution_acceptance(
    parent_graph: Any,
    request: Any,
    preauthorization: Any,
    stage5_lineage_input: Any,
    convergence_authority: PreauthorizedConvergenceAuthority,
    convergence_evidence: _convergence.GraphEvolutionConvergenceEvidence,
    evaluator_selection: _review.EvaluatorSelection,
    evaluator_receipt: object,
    evaluator_assignment: object,
    *,
    previous_convergence: (
        _convergence.GraphEvolutionConvergenceState | None
    ) = None,
    pm_acceptance: Any | None = None,
    proposal_outcome: _proposal.GraphEvolutionProposalOutcome | None = None,
) -> GraphEvolutionAcceptanceOutcome:
    """Resolve an inert Stage 6 acceptance without applying or executing it."""

    sources = (
        ("acceptance", parent_graph),
        ("request", request),
        ("preauthorization", preauthorization),
        ("acceptance", stage5_lineage_input),
    )
    snapshots: list[dict[str, Any]] = []
    for document_kind, source in sources:
        snapshot, failure = _snapshot_document(
            source,
            document_kind=document_kind,
        )
        if failure is not None or snapshot is None:
            issue_codes = _proposal_issue_codes(failure)
            return _resolved(
                GraphEvolutionAcceptanceCode.REJECTED,
                issue_codes=issue_codes,
                error=failure,
            )
        snapshots.append(snapshot)
    (
        parent_snapshot,
        request_snapshot,
        preauthorization_snapshot,
        lineage_input_snapshot,
    ) = snapshots

    pm_snapshot: dict[str, Any] | None = None
    if pm_acceptance is not None:
        pm_snapshot, failure = _snapshot_document(
            pm_acceptance,
            document_kind="acceptance",
        )
        if failure is not None or pm_snapshot is None:
            issue_codes = _proposal_issue_codes(failure)
            return _resolved(
                GraphEvolutionAcceptanceCode.REJECTED,
                issue_codes=issue_codes,
                error=failure,
            )

    request_validation = _contract.validate_graph_evolution_request(
        request_snapshot
    )
    if not request_validation.valid:
        issue_codes = _validation_issue_codes(request_validation)
        return _resolved(
            GraphEvolutionAcceptanceCode.REJECTED,
            issue_codes=issue_codes,
            error=_error("request", "INPUT_INVALID", issue_codes),
        )
    preauthorization_validation = (
        _contract.validate_graph_evolution_preauthorization(
            preauthorization_snapshot
        )
    )
    if not preauthorization_validation.valid:
        issue_codes = _validation_issue_codes(preauthorization_validation)
        return _resolved(
            GraphEvolutionAcceptanceCode.REJECTED,
            issue_codes=issue_codes,
            error=_error("preauthorization", "INPUT_INVALID", issue_codes),
        )

    lineage = _evidence.resolve_evidence_lineage(
        parent_snapshot,
        lineage_input_snapshot,
    )
    if not isinstance(lineage, _evidence.EvidenceLineageOutcome):
        issue_codes = ("VALIDATED_LINEAGE_OUTCOME_REQUIRED",)
        return _resolved(
            GraphEvolutionAcceptanceCode.REJECTED,
            issue_codes=issue_codes,
            error=_error("acceptance", "INPUT_INVALID", issue_codes),
        )

    built = _proposal.build_graph_evolution_proposal(
        parent_snapshot,
        request_snapshot,
        preauthorization_snapshot,
        lineage,
    )
    if not built.succeeded or built.proposal is None:
        issue_codes = _proposal_issue_codes(built.error)
        return _resolved(
            (
                GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED
                if _requires_pm(issue_codes)
                else GraphEvolutionAcceptanceCode.REJECTED
            ),
            issue_codes=issue_codes,
            error=built.error,
        )
    proposal_snapshot = built.proposal

    if proposal_outcome is not None:
        if (
            not isinstance(
                proposal_outcome,
                _proposal.GraphEvolutionProposalOutcome,
            )
            or not proposal_outcome.succeeded
            or proposal_outcome.proposal != proposal_snapshot
            or proposal_outcome.result is None
            or any(
                proposal_outcome.result.get(field) is not False
                for field in _GRANT_FIELDS
            )
        ):
            issue_codes = ("STALE_PROPOSAL",)
            return _resolved(
                GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
                proposal=proposal_snapshot,
                issue_codes=issue_codes,
                error=_error("proposal", "INPUT_INVALID", issue_codes),
            )

    try:
        convergence = _convergence.evaluate_graph_evolution_convergence(
            convergence_authority,
            convergence_evidence,
            previous=previous_convergence,
        )
    except (TypeError, ValueError):
        issue_codes = ("CONVERGENCE_INPUT_INVALID",)
        return _resolved(
            GraphEvolutionAcceptanceCode.REJECTED,
            proposal=proposal_snapshot,
            issue_codes=issue_codes,
            error=_error("acceptance", "INPUT_INVALID", issue_codes),
        )

    receipt_status = _review.validate_evaluator_receipt(
        evaluator_selection,
        evaluator_receipt,
        evaluator_assignment,
    )
    if not _independent_evaluator(
        request_snapshot,
        preauthorization_snapshot,
        evaluator_assignment,
    ):
        receipt_status = _review.ReceiptStatus.INDEPENDENT_EVALUATOR_REQUIRED

    if (
        convergence.code
        is _convergence.GraphEvolutionConvergenceCode.BLOCKED_NO_PROGRESS
    ):
        return _resolved(
            GraphEvolutionAcceptanceCode.BLOCKED_NO_PROGRESS,
            proposal=proposal_snapshot,
            convergence=convergence,
            receipt_status=receipt_status,
            issue_codes=("NO_PROGRESS",),
        )

    convergence_binding_issues = _convergence_binding_issues(
        request_snapshot,
        preauthorization_snapshot,
        convergence_authority,
    )
    if convergence_binding_issues:
        return _resolved(
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
            proposal=proposal_snapshot,
            convergence=convergence,
            receipt_status=receipt_status,
            issue_codes=convergence_binding_issues,
        )

    lineage_issues = _lineage_issue_codes(
        lineage,
        operation=request_snapshot["operation"],
    )
    if lineage_issues:
        return _resolved(
            GraphEvolutionAcceptanceCode.REJECTED,
            proposal=proposal_snapshot,
            convergence=convergence,
            receipt_status=receipt_status,
            issue_codes=lineage_issues,
            error=_error("acceptance", "INPUT_INVALID", lineage_issues),
        )

    if receipt_status is not _review.ReceiptStatus.PASS:
        rejection = _acceptance_record(
            request_snapshot,
            preauthorization_snapshot,
            built.result["proposal_digest"],
            preauthorization_validation.digest,
            accepted=False,
        )
        return _finalize_chain(
            code=GraphEvolutionAcceptanceCode.REJECTED,
            parent_graph=parent_snapshot,
            request=request_snapshot,
            preauthorization=preauthorization_snapshot,
            proposal=proposal_snapshot,
            acceptance=rejection,
            convergence=convergence,
            receipt_status=receipt_status,
        )

    operation = request_snapshot["operation"]
    if operation == "NO_CHANGE":
        if (
            convergence.code
            is not _convergence.GraphEvolutionConvergenceCode.NO_CHANGE_ACCEPTED
        ):
            return _resolved(
                GraphEvolutionAcceptanceCode.REJECTED,
                proposal=proposal_snapshot,
                convergence=convergence,
                receipt_status=receipt_status,
                issue_codes=("NO_CHANGE_EVIDENCE_REQUIRED",),
            )
        acceptance = _acceptance_record(
            request_snapshot,
            preauthorization_snapshot,
            built.result["proposal_digest"],
            preauthorization_validation.digest,
            accepted=True,
        )
        return _finalize_chain(
            code=GraphEvolutionAcceptanceCode.NO_CHANGE_ACCEPTED,
            parent_graph=parent_snapshot,
            request=request_snapshot,
            preauthorization=preauthorization_snapshot,
            proposal=proposal_snapshot,
            acceptance=acceptance,
            convergence=convergence,
            receipt_status=receipt_status,
        )

    canonical_governance = any(
        _is_canonical_governance_path(path)
        for path in request_snapshot["affected_paths"]
    )
    pm_required = (
        request_snapshot["change_class"] not in _AUTO_CHANGE_CLASSES
        or canonical_governance
        or convergence.code
        is _convergence.GraphEvolutionConvergenceCode.PM_DECISION_REQUIRED
    )
    review_handoff = (
        convergence.code is _convergence.GraphEvolutionConvergenceCode.HANDOFF
    )
    if review_handoff:
        return _resolved(
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
            proposal=proposal_snapshot,
            convergence=convergence,
            receipt_status=receipt_status,
            issue_codes=("TARGETED_REVIEW_REQUIRED",),
        )

    if pm_snapshot is not None:
        pm_validation = _contract.validate_graph_evolution_acceptance(
            pm_snapshot
        )
        if not pm_validation.valid:
            issue_codes = _validation_issue_codes(pm_validation)
            return _resolved(
                GraphEvolutionAcceptanceCode.REJECTED,
                proposal=proposal_snapshot,
                convergence=convergence,
                receipt_status=receipt_status,
                issue_codes=issue_codes,
                error=_error("acceptance", "INPUT_INVALID", issue_codes),
            )
        pm_code = (
            GraphEvolutionAcceptanceCode.PM_ACCEPTED
            if pm_snapshot["decision"] == "ACCEPTED"
            else GraphEvolutionAcceptanceCode.REJECTED
        )
        return _finalize_chain(
            code=pm_code,
            parent_graph=parent_snapshot,
            request=request_snapshot,
            preauthorization=preauthorization_snapshot,
            proposal=proposal_snapshot,
            acceptance=pm_snapshot,
            convergence=convergence,
            receipt_status=receipt_status,
        )

    if pm_required:
        issue_codes = (
            ("CANONICAL_GOVERNANCE_DECISION_REQUIRED",)
            if canonical_governance
            else ("PM_AUTHORITY_REQUIRED",)
        )
        return _resolved(
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
            proposal=proposal_snapshot,
            convergence=convergence,
            receipt_status=receipt_status,
            issue_codes=issue_codes,
        )

    acceptance = _acceptance_record(
        request_snapshot,
        preauthorization_snapshot,
        built.result["proposal_digest"],
        preauthorization_validation.digest,
        accepted=True,
    )
    return _finalize_chain(
        code=GraphEvolutionAcceptanceCode.AUTO_ACCEPTED,
        parent_graph=parent_snapshot,
        request=request_snapshot,
        preauthorization=preauthorization_snapshot,
        proposal=proposal_snapshot,
        acceptance=acceptance,
        convergence=convergence,
        receipt_status=receipt_status,
    )


__all__ = [
    "GraphEvolutionAcceptanceCode",
    "GraphEvolutionAcceptanceOutcome",
    "resolve_graph_evolution_acceptance",
]
