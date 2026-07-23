"""Pure internal adapters from accepted SAGE-Kit authority to Graph Contract v1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping

from .graph_contract import (
    AUTONOMY_LEVELS,
    GOVERNANCE_LEVELS,
    GRAPH_SCHEMA_ID,
    NODE_RESULT_SCHEMA_ID,
    PERMISSION_MODES,
    SCHEMA_VERSION,
    GraphValidationIssue,
    canonical_graph_digest,
    validate_graph_contract,
)
from .packet import (
    CompiledPacket,
    GENERATED_MARKER,
    PacketError,
    _is_recognized_generated_packet,
    _packet_payload_digest,
    _validate_packet_for_write,
)
from .spec_sources import (
    DocumentClass,
    NormalizedSpec,
    NormalizedSpecAttestationError,
    SourceProvenance,
    verify_normalized_spec_attestation,
)
from .workspace_binding import WorkspaceBinding


_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SEPARATING_SIGNALS = frozenset(
    {
        "separate-context",
        "independent-evaluator",
        "authority-separation",
        "state-boundary",
    }
)
_MULTI_NODE_SEPARATION_SIGNALS = frozenset(
    {
        "independent-evaluator",
        "authority-separation",
        "state-boundary",
    }
)
_PACKET_POLICY_FIELDS = frozenset(
    {"profile_id", "profile_digest", "values", "sources"}
)
_PACKET_GATE_FIELDS = frozenset(
    {"id", "applies_to", "status", "permission_mode", "authority_reference"}
)
_ATTESTED_TOP_LEVEL_FIELDS = frozenset(
    {
        "project_authority",
        "project",
        "contract_sha256",
        "milestone",
        "phases",
        "waves",
    }
)
_ATTESTED_PROJECT_AUTHORITY_FIELDS = frozenset(
    {
        "schema_version",
        "project_id",
        "adoption_profile",
        "execution_scope",
        "package",
        "profiles",
    }
)
_ATTESTED_PROJECT_FIELDS = frozenset(
    {
        "schema_version",
        "sagekit_contract",
        "execution_document_model",
        "effective_from",
        "legacy_documents",
        "profiles",
        "overrides",
        "resource_contract",
    }
)
_ATTESTED_MILESTONE_FIELDS = frozenset(
    {
        "milestone_id",
        "objective",
        "capability_outcome",
        "authority_references",
        "governance_profile",
        "dependency_dag",
        "approval_gates",
        "phase_ids",
        "acceptance_criteria",
        "invariants",
        "state",
        "evidence_references",
    }
)
_ATTESTED_PHASE_FIELDS = frozenset(
    {
        "phase_id",
        "objective",
        "depends_on",
        "execution_profile",
        "permission_mode",
        "owner",
        "writable_paths",
        "read_only_references",
        "forbidden_paths",
        "inherit_forbidden",
        "acceptance_criteria",
        "verification_commands",
        "evidence_requirements",
        "stop_conditions",
        "handoff_target",
        "state",
        "resource_profile",
        "resource_overrides",
    }
)
_ATTESTED_WAVE_FIELDS = frozenset({"id", "depends_on", "phase_ids"})
_PACKAGE_IDENTITY_FIELDS = frozenset({"name", "version", "digest"})
_PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class GraphNormalizationError(ValueError):
    """Bounded normalization error for callers that require exception semantics."""

    def __init__(self, reason_codes: tuple[str, ...]):
        self.reason_codes = reason_codes
        super().__init__("graph normalization failed: " + ", ".join(reason_codes))


class GraphAdmissionSignal(str, Enum):
    """The complete Stage 2C set of bounded, caller-supplied admission signals."""

    SEPARATE_CONTEXT = "separate-context"
    PARALLEL_JOIN = "parallel-join"
    INDEPENDENT_EVALUATOR = "independent-evaluator"
    AUTHORITY_SEPARATION = "authority-separation"
    STATE_BOUNDARY = "state-boundary"


@dataclass(frozen=True)
class GraphAdmissionRequest:
    """Admission inputs; requested gates are presence assertions, never mutations."""

    governance_level: str
    autonomy_level: str
    signals: tuple[GraphAdmissionSignal, ...]
    completion_verifier: str | None = None
    # Every named gate must already exist. Empty means assert none specifically,
    # while the Graph still retains every gate declared by active authority.
    requested_human_gates: tuple[str, ...] = ()


@dataclass(frozen=True)
class GraphAdmissionDecision:
    """A deterministic admission/collapsibility decision."""

    status: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class GraphNormalizationResult:
    """A Graph Contract v1 payload or an explicit refusal to return one."""

    decision: GraphAdmissionDecision
    graph: dict[str, Any] | None = None
    semantic_digest: str | None = None
    issues: tuple[GraphValidationIssue, ...] = ()


@dataclass(frozen=True)
class _AttestedPhaseGraphInput:
    phase_id: str
    owner: str
    depends_on: tuple[str, ...]
    permission: str
    verification_commands: tuple[str, ...]
    resources: tuple[str, ...]


@dataclass(frozen=True)
class _AttestedSpecGraphInput:
    milestone_id: str
    project_id: str | None
    human_gates: tuple[str, ...]
    phases: tuple[_AttestedPhaseGraphInput, ...]


def _decision(status: str, *reason_codes: str) -> GraphAdmissionDecision:
    return GraphAdmissionDecision(status, tuple(reason_codes))


def _invalid_result(*reason_codes: str) -> GraphNormalizationResult:
    return GraphNormalizationResult(_decision("INVALID_REQUEST", *reason_codes))


def _not_admitted_result(
    decision: GraphAdmissionDecision,
) -> GraphNormalizationResult:
    return GraphNormalizationResult(decision)


def _is_nonempty_string(value: object) -> bool:
    return type(value) is str and bool(value)


def _is_digest(value: object) -> bool:
    return type(value) is str and _HEX_DIGEST.fullmatch(value) is not None


def _canonical_digest(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _stable_verifier(namespace: str, verification: object) -> str:
    return (
        f"urn:sagekit:{namespace}:verification:sha256:"
        f"{_canonical_digest(verification)}"
    )


def _request_reason_codes(
    request: object,
) -> tuple[str, ...]:
    if type(request) is not GraphAdmissionRequest:
        return ("invalid-admission-request",)
    reasons: list[str] = []
    if (
        type(request.governance_level) is not str
        or request.governance_level not in GOVERNANCE_LEVELS
    ):
        reasons.append("invalid-governance-level")
    if (
        type(request.autonomy_level) is not str
        or request.autonomy_level not in AUTONOMY_LEVELS
    ):
        reasons.append("invalid-autonomy-level")
    if type(request.signals) is not tuple or any(
        type(signal) is not GraphAdmissionSignal for signal in request.signals
    ):
        reasons.append("invalid-admission-signal")
    elif len(request.signals) != len(set(request.signals)):
        reasons.append("duplicate-admission-signal")
    if request.completion_verifier is not None and not _is_nonempty_string(
        request.completion_verifier
    ):
        reasons.append("invalid-completion-verifier")
    gates = request.requested_human_gates
    if (
        type(gates) is not tuple
        or any(not _is_nonempty_string(gate) for gate in gates)
        or len(gates) != len(set(gates))
    ):
        reasons.append("invalid-requested-human-gate")
    return tuple(reasons)


def assess_graph_admission(
    request: GraphAdmissionRequest,
    *,
    candidate_node_count: int = 1,
    has_dependency: bool = False,
    has_safe_parallel_join: bool = False,
) -> GraphAdmissionDecision:
    """Assess bounded Graph admission without inspecting project or runtime state."""

    request_reasons = _request_reason_codes(request)
    if request_reasons:
        return _decision("INVALID_REQUEST", *request_reasons)
    if (
        type(candidate_node_count) is not int
        or candidate_node_count < 1
        or type(has_dependency) is not bool
        or type(has_safe_parallel_join) is not bool
    ):
        return _decision("INVALID_REQUEST", "invalid-candidate-shape")

    signal_values = frozenset(signal.value for signal in request.signals)
    if not signal_values:
        reasons = ["no-concrete-admission-signal"]
        if request.governance_level == "Light":
            reasons.append("light-graph-optional")
        return _decision("NOT_ADMITTED", *reasons)

    if candidate_node_count == 1:
        if not signal_values.intersection(_SEPARATING_SIGNALS):
            return _decision("NOT_ADMITTED", "single-node-collapsible")
        return _decision(
            "ADMITTED",
            "concrete-admission-signal",
            "non-collapsible-single-node",
        )

    safe_parallel = (
        GraphAdmissionSignal.PARALLEL_JOIN.value in signal_values
        and has_safe_parallel_join
    )
    separated = bool(
        signal_values.intersection(_MULTI_NODE_SEPARATION_SIGNALS)
    )
    if not (has_dependency or safe_parallel or separated):
        return _decision("NOT_ADMITTED", "multi-node-collapsible")
    reason = (
        "required-dependency"
        if has_dependency
        else (
            "safe-parallel-join"
            if safe_parallel
            else "non-collapsible-separation"
        )
    )
    return _decision("ADMITTED", "concrete-admission-signal", reason)


def _declared_gate_ids(raw_gates: object) -> tuple[str, ...] | None:
    if type(raw_gates) not in {tuple, list}:
        return None
    identities: list[str] = []
    for gate in raw_gates:
        if hasattr(gate, "id"):
            gate_id = getattr(gate, "id")
        elif type(gate) is dict and set(gate) == _PACKET_GATE_FIELDS:
            gate_id = gate.get("id")
        else:
            return None
        if not _is_nonempty_string(gate_id):
            return None
        identities.append(gate_id)
    if len(identities) != len(set(identities)):
        return None
    return tuple(sorted(identities))


def _controlled_human_gates(
    declared: tuple[str, ...],
    requested: tuple[str, ...],
) -> tuple[str, ...] | None:
    if not set(requested).issubset(declared):
        return None
    # Requests assert that named identities exist. They never select, add, remove,
    # open, close, waive, replace, or reclassify project authority.
    return declared


def _spec_metadata_reasons(spec: object) -> tuple[str, ...]:
    if type(spec) is not NormalizedSpec:
        return ("invalid-normalized-spec-type",)
    reasons: list[str] = []
    if spec.document_class is not DocumentClass.ACTIVE_SPEC:
        reasons.append("invalid-spec-document-class")
    if type(spec.provenance) is not SourceProvenance or not all(
        _is_nonempty_string(value)
        for value in (
            getattr(spec.provenance, "authority", None),
            getattr(spec.provenance, "canonical_path", None),
            getattr(spec.provenance, "adapter", None),
        )
    ):
        reasons.append("missing-spec-authority")
    return tuple(reasons)


def _attested_string_tuple(
    value: object,
    *,
    nonempty: bool = False,
) -> tuple[str, ...] | None:
    if type(value) is not list or (nonempty and not value):
        return None
    if (
        any(not _is_nonempty_string(item) for item in value)
        or len(value) != len(set(value))
    ):
        return None
    return tuple(value)


def _attested_project_id(value: object) -> str | None | bool:
    if value is None:
        return None
    if type(value) is not dict or set(value) != _ATTESTED_PROJECT_AUTHORITY_FIELDS:
        return False
    package = value.get("package")
    if (
        value.get("schema_version") != 1
        or type(value.get("project_id")) is not str
        or _PROJECT_ID_RE.fullmatch(value["project_id"]) is None
        or not _is_nonempty_string(value.get("adoption_profile"))
        or not _is_nonempty_string(value.get("execution_scope"))
        or type(package) is not dict
        or set(package) != _PACKAGE_IDENTITY_FIELDS
        or any(not _is_nonempty_string(item) for item in package.values())
        or not _is_digest(package.get("digest"))
        or _attested_string_tuple(value.get("profiles")) is None
    ):
        return False
    return value["project_id"]


def _attested_spec_graph_input(
    payload: object,
) -> _AttestedSpecGraphInput | None:
    if type(payload) is not dict or set(payload) != _ATTESTED_TOP_LEVEL_FIELDS:
        return None
    project = payload.get("project")
    milestone = payload.get("milestone")
    phases = payload.get("phases")
    waves = payload.get("waves")
    if (
        type(project) is not dict
        or set(project) != _ATTESTED_PROJECT_FIELDS
        or type(project.get("schema_version")) is not int
        or not _is_nonempty_string(project.get("sagekit_contract"))
        or not _is_nonempty_string(project.get("execution_document_model"))
        or _attested_string_tuple(project.get("profiles")) is None
        or type(project.get("overrides")) is not dict
        or not _is_digest(payload.get("contract_sha256"))
        or type(milestone) is not dict
        or set(milestone) != _ATTESTED_MILESTONE_FIELDS
        or type(phases) is not dict
        or type(waves) is not dict
    ):
        return None

    project_id = _attested_project_id(payload.get("project_authority"))
    if project_id is False:
        return None
    milestone_id = milestone.get("milestone_id")
    phase_ids = _attested_string_tuple(milestone.get("phase_ids"), nonempty=True)
    dependency_dag = milestone.get("dependency_dag")
    declared_gates = _declared_gate_ids(milestone.get("approval_gates"))
    if (
        not _is_nonempty_string(milestone_id)
        or phase_ids is None
        or set(phase_ids) != set(phases)
        or type(dependency_dag) is not dict
        or set(dependency_dag) != set(phases)
        or declared_gates is None
    ):
        return None

    for raw_gate in milestone["approval_gates"]:
        if (
            type(raw_gate) is not dict
            or set(raw_gate) != _PACKET_GATE_FIELDS
            or _attested_string_tuple(raw_gate.get("applies_to")) is None
            or not _is_nonempty_string(raw_gate.get("status"))
            or type(raw_gate.get("permission_mode")) is not str
            or raw_gate.get("permission_mode") not in PERMISSION_MODES
            or not _is_nonempty_string(raw_gate.get("authority_reference"))
        ):
            return None

    graph_phases: list[_AttestedPhaseGraphInput] = []
    for phase_id in sorted(phases):
        raw_phase = phases.get(phase_id)
        if (
            not _is_nonempty_string(phase_id)
            or type(raw_phase) is not dict
            or set(raw_phase) != _ATTESTED_PHASE_FIELDS
            or raw_phase.get("phase_id") != phase_id
            or not _is_nonempty_string(raw_phase.get("owner"))
            or type(raw_phase.get("permission_mode")) is not str
            or raw_phase.get("permission_mode") not in PERMISSION_MODES
        ):
            return None
        depends_on = _attested_string_tuple(raw_phase.get("depends_on"))
        dag_dependencies = _attested_string_tuple(dependency_dag.get(phase_id))
        verification = _attested_string_tuple(
            raw_phase.get("verification_commands"),
            nonempty=True,
        )
        overrides = raw_phase.get("resource_overrides")
        if (
            depends_on is None
            or dag_dependencies is None
            or depends_on != dag_dependencies
            or not set(depends_on).issubset(phases)
            or verification is None
            or type(overrides) is not dict
        ):
            return None
        resources = _attested_string_tuple(
            overrides.get("runtime_exclusive", [])
        )
        if resources is None:
            return None
        graph_phases.append(
            _AttestedPhaseGraphInput(
                phase_id=phase_id,
                owner=raw_phase["owner"],
                depends_on=tuple(sorted(depends_on)),
                permission=raw_phase["permission_mode"],
                verification_commands=verification,
                resources=tuple(sorted(resources)),
            )
        )

    for wave_id, raw_wave in waves.items():
        if (
            not _is_nonempty_string(wave_id)
            or type(raw_wave) is not dict
            or set(raw_wave) != _ATTESTED_WAVE_FIELDS
            or raw_wave.get("id") != wave_id
            or _attested_string_tuple(raw_wave.get("depends_on")) is None
            or _attested_string_tuple(raw_wave.get("phase_ids")) is None
        ):
            return None

    return _AttestedSpecGraphInput(
        milestone_id=milestone_id,
        project_id=project_id,
        human_gates=declared_gates,
        phases=tuple(graph_phases),
    )


def _finalize_graph(
    candidate: dict[str, Any],
    admitted: GraphAdmissionDecision,
) -> GraphNormalizationResult:
    validation = validate_graph_contract(candidate)
    if not validation.valid or validation.semantic_digest is None:
        return GraphNormalizationResult(
            _decision("INVALID_REQUEST", "graph-contract-invalid"),
            issues=validation.issues,
        )
    digest = canonical_graph_digest(candidate)
    if digest != validation.semantic_digest:
        return GraphNormalizationResult(
            _decision("INVALID_REQUEST", "graph-digest-inconsistent")
        )
    return GraphNormalizationResult(
        admitted,
        graph=candidate,
        semantic_digest=digest,
    )


def normalize_spec_to_graph(
    spec: NormalizedSpec,
    request: GraphAdmissionRequest,
) -> GraphNormalizationResult:
    """Normalize one complete ACTIVE_SPEC authority into Graph Contract v1."""

    spec_reasons = _spec_metadata_reasons(spec)
    if spec_reasons:
        return _invalid_result(*spec_reasons)
    request_reasons = _request_reason_codes(request)
    if request_reasons:
        return _invalid_result(*request_reasons)

    try:
        semantic_payload = verify_normalized_spec_attestation(spec)
    except NormalizedSpecAttestationError:
        return _invalid_result("invalid-semantic-attestation")
    attested = _attested_spec_graph_input(semantic_payload)
    if attested is None:
        return _invalid_result("invalid-semantic-attestation")

    human_gates = _controlled_human_gates(
        attested.human_gates,
        request.requested_human_gates,
    )
    if human_gates is None:
        return _invalid_result("unknown-requested-human-gate")

    phases = attested.phases
    has_dependency = any(phase.depends_on for phase in phases)
    signal_values = frozenset(signal.value for signal in request.signals)
    admission = assess_graph_admission(
        request,
        candidate_node_count=len(phases),
        has_dependency=has_dependency,
        has_safe_parallel_join=(
            len(phases) > 1
            and GraphAdmissionSignal.PARALLEL_JOIN.value in signal_values
        ),
    )
    if admission.status != "ADMITTED":
        return _not_admitted_result(admission)

    nodes: list[dict[str, Any]] = []
    for phase in phases:
        nodes.append(
            {
                "id": phase.phase_id,
                "role": phase.owner,
                "depends_on": sorted(phase.depends_on),
                "permission": phase.permission,
                "verifier": _stable_verifier(
                    "normalized-spec-v1",
                    list(phase.verification_commands),
                ),
                "output_contract": NODE_RESULT_SCHEMA_ID,
                "resources": list(phase.resources),
                "classification": "required",
            }
        )

    project_authority = attested.project_id or "legacy-unconfigured"
    candidate: dict[str, Any] = {
        "schema_id": GRAPH_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "graph_id": attested.milestone_id,
        "generation": 1,
        "source_authority": {
            "identity": (
                "urn:sagekit:normalized-spec:v1:project:"
                f"{project_authority}:sha256:"
                f"{spec.semantic_digest}"
            ),
            "reference": (
                f"{spec.provenance.canonical_path}"
                f"#ACTIVE_SPEC:{attested.milestone_id}"
            ),
        },
        "governance_level": request.governance_level,
        "autonomy_level": request.autonomy_level,
        "human_gates": list(human_gates),
        "nodes": nodes,
        "joins": [
            {
                "id": f"{attested.milestone_id}-implementation-complete",
                "requires": [phase.phase_id for phase in phases],
                "policy": "all-required",
            }
        ],
    }
    if request.completion_verifier is not None:
        candidate["completion_verifier"] = request.completion_verifier
    return _finalize_graph(candidate, admission)


def _packet_validation_reason(packet: object) -> str | None:
    if type(packet) is not CompiledPacket:
        return "invalid-packet-type"
    payload = packet.payload
    if not isinstance(payload, dict):
        return "invalid-packet-structure"
    if payload.get("schema_version") != 3:
        return "unsupported-packet-schema"
    if payload.get("_generated_by") != GENERATED_MARKER:
        return "invalid-packet-marker"
    if (
        not _is_digest(packet.digest)
        or payload.get("packet_sha256") != packet.digest
        or payload.get("mode") != packet.mode
        or _packet_payload_digest(payload) != packet.digest
    ):
        return "packet-digest-mismatch"
    if not _is_recognized_generated_packet(payload):
        return "invalid-packet-structure"
    try:
        _validate_packet_for_write(packet)
    except (PacketError, TypeError, ValueError):
        return "invalid-packet-binding"

    resolved_policy = payload.get("resolved_policy")
    bindings = payload.get("bindings")
    if (
        type(resolved_policy) is not dict
        or set(resolved_policy) != _PACKET_POLICY_FIELDS
        or type(bindings) is not dict
    ):
        return "invalid-policy-binding"
    if (
        not _is_nonempty_string(resolved_policy.get("profile_id"))
        or not _is_digest(resolved_policy.get("profile_digest"))
        or type(resolved_policy.get("values")) is not dict
        or type(resolved_policy.get("sources")) is not dict
        or _canonical_digest(resolved_policy)
        != bindings.get("resolved_policy_sha256")
    ):
        return "invalid-policy-binding"
    profiles = bindings.get("profiles")
    if (
        type(profiles) is not dict
        or profiles.get(resolved_policy["profile_id"])
        != resolved_policy["profile_digest"]
    ):
        return "invalid-policy-binding"
    return None


def _packet_gates(scope: Mapping[str, Any]) -> tuple[str, ...] | None:
    return _declared_gate_ids(scope.get("approval_gates"))


def _packet_resources(payload: Mapping[str, Any]) -> tuple[str, ...] | None:
    resource = payload.get("resolved_resource_policy")
    if type(resource) is not dict:
        return None
    raw = resource.get("exclusive_resources")
    if type(raw) is not list:
        return None
    if (
        any(not _is_nonempty_string(item) for item in raw)
        or len(raw) != len(set(raw))
    ):
        return None
    return tuple(sorted(raw))


def _packet_authority(
    payload: Mapping[str, Any],
) -> tuple[WorkspaceBinding, str] | None:
    try:
        binding = WorkspaceBinding.from_dict(payload.get("workspace_binding"))
    except (TypeError, ValueError):
        return None
    policy = payload.get("resolved_policy")
    if type(policy) is not dict or type(policy.get("values")) is not dict:
        return None
    permission = policy["values"].get("permission_mode")
    if (
        permission not in PERMISSION_MODES
        or permission != binding.permission_mode
    ):
        return None
    return binding, permission


def normalize_packet_to_graph(
    packet: CompiledPacket,
    request: GraphAdmissionRequest,
) -> GraphNormalizationResult:
    """Normalize one intact current-v3 packet execution unit into Graph v1."""

    packet_reason = _packet_validation_reason(packet)
    if packet_reason is not None:
        return _invalid_result(packet_reason)
    request_reasons = _request_reason_codes(request)
    if request_reasons:
        return _invalid_result(*request_reasons)

    payload = packet.payload
    target = payload["target"]
    bindings = payload["bindings"]
    source_contract = payload["source_contract"]
    scope = payload.get("scope")
    verification = payload.get("verification")
    if (
        type(target) is not dict
        or set(target) != {"milestone_id", "phase_id"}
        or not _is_nonempty_string(target.get("milestone_id"))
        or type(scope) is not dict
    ):
        return _invalid_result("invalid-packet-target")
    authority = _packet_authority(payload)
    resources = _packet_resources(payload)
    gates = _packet_gates(scope)
    if authority is None:
        return _invalid_result("insufficient-packet-authority")
    if resources is None:
        return _invalid_result("invalid-resource-policy-binding")
    if gates is None:
        return _invalid_result("insufficient-packet-authority")
    human_gates = _controlled_human_gates(
        gates, request.requested_human_gates
    )
    if human_gates is None:
        return _invalid_result("unknown-requested-human-gate")

    binding, permission = authority
    milestone_id = target["milestone_id"]
    phase_id = target["phase_id"]
    is_phase = phase_id is not None
    if is_phase:
        depends_on = scope.get("depends_on")
        owner = scope.get("owner")
        scope_permission = scope.get("permission_mode")
        if (
            not _is_nonempty_string(phase_id)
            or not _is_digest(bindings.get("phase_manifest_sha256"))
            or not _is_nonempty_string(owner)
            or owner != binding.controller
            or scope_permission != permission
            or type(depends_on) is not list
            or any(not _is_nonempty_string(item) for item in depends_on)
            or len(depends_on) != len(set(depends_on))
            or type(verification) is not list
            or not verification
            or any(not _is_nonempty_string(item) for item in verification)
        ):
            return _invalid_result("insufficient-packet-authority")
        # External dependencies cannot be named in Graph v1 without declaring
        # nodes whose role and permission the single-unit packet does not carry.
        if depends_on:
            return _invalid_result("insufficient-packet-authority")
        node_id = phase_id
        role = owner
        graph_id = f"{milestone_id}:{phase_id}"
    else:
        if (
            bindings.get("phase_manifest_sha256") is not None
            or permission != "READ_ONLY_REVIEW"
            or not _is_nonempty_string(binding.controller)
            or type(verification) is not list
            or not verification
        ):
            return _invalid_result("insufficient-packet-authority")
        node_id = milestone_id
        role = binding.controller
        graph_id = milestone_id

    admission = assess_graph_admission(
        request,
        candidate_node_count=1,
    )
    if admission.status != "ADMITTED":
        return _not_admitted_result(admission)

    node = {
        "id": node_id,
        "role": role,
        "depends_on": [],
        "permission": permission,
        "verifier": _stable_verifier(
            "compiled-packet-v3",
            verification,
        ),
        "output_contract": NODE_RESULT_SCHEMA_ID,
        "resources": list(resources),
        "classification": "required",
    }
    fragment = (
        f"phase:{phase_id}" if is_phase else f"milestone:{milestone_id}"
    )
    candidate: dict[str, Any] = {
        "schema_id": GRAPH_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "graph_id": graph_id,
        "generation": 1,
        "source_authority": {
            "identity": (
                "urn:sagekit:normalized-spec:v1:sha256:"
                f"{source_contract['semantic_sha256']}"
            ),
            "reference": f"urn:sagekit:compiled-packet:v3#{fragment}",
        },
        "governance_level": request.governance_level,
        "autonomy_level": request.autonomy_level,
        "human_gates": list(human_gates),
        "nodes": [node],
        "joins": [
            {
                "id": f"{node_id}-unit-complete",
                "requires": [node_id],
                "policy": "all-required",
            }
        ],
    }
    if request.completion_verifier is not None:
        candidate["completion_verifier"] = request.completion_verifier
    return _finalize_graph(candidate, admission)
