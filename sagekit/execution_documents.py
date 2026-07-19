from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping


PROJECT_LOCK_NAME = "SAGE_PROJECT.json"
MILESTONE_MANIFEST_NAME = "MILESTONE_MANIFEST.json"
DOCUMENT_MODEL = "thin-v1"
SCHEMA_VERSION = 1
PERMISSION_MODES = frozenset(
    {
        "READ_ONLY_REVIEW",
        "WRITE_AUTHORIZED",
        "CORRECTIVE_AUTHORIZED",
        "ENVIRONMENT_WRITE_AUTHORIZED",
        "SUBMIT_AUTHORIZED",
    }
)
MILESTONE_STATES = frozenset({"planned", "active", "blocked", "accepted", "closed"})
PHASE_STATES = frozenset({"planned", "ready", "active", "blocked", "complete"})
MILESTONE_ID_RE = re.compile(r"M[0-9]+(?:[._-][A-Za-z0-9]+)*")
PHASE_ID_RE = re.compile(r"P[0-9]+(?:[._-][A-Za-z0-9]+)*")

PROJECT_FIELDS = frozenset(
    {
        "schema_version",
        "sagekit_contract",
        "execution_document_model",
        "effective_from",
        "legacy_documents",
        "profiles",
        "overrides",
    }
)
MILESTONE_FIELDS = frozenset(
    {
        "schema_version",
        "sagekit_contract",
        "document_model",
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
PHASE_FIELDS = frozenset(
    {
        "schema_version",
        "sagekit_contract",
        "document_model",
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
    }
)
GATE_FIELDS = frozenset(
    {"id", "applies_to", "status", "permission_mode", "authority_reference"}
)
CONTRACT_FIELDS = frozenset(
    {
        "schema_version",
        "contract_id",
        "execution_document_model",
        "project_schema",
        "milestone_schema",
        "phase_schema",
        "runtime_defaults",
        "overrideable_policy_keys",
        "profiles",
    }
)
PROFILE_FIELDS = frozenset({"schema_version", "id", "generic_rules", "policy"})


class ExecutionDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectLock:
    path: Path
    schema_version: int
    sagekit_contract: str
    execution_document_model: str
    effective_from: str
    legacy_documents: str
    profiles: tuple[str, ...]
    overrides: Mapping[str, Mapping[str, Any]]
    digest: str


@dataclass(frozen=True)
class ApprovalGate:
    id: str
    applies_to: tuple[str, ...]
    status: str
    permission_mode: str
    authority_reference: str


@dataclass(frozen=True)
class MilestoneManifest:
    path: Path
    schema_version: int
    sagekit_contract: str
    document_model: str
    milestone_id: str
    objective: str
    capability_outcome: str
    authority_references: tuple[str, ...]
    governance_profile: str
    dependency_dag: Mapping[str, tuple[str, ...]]
    approval_gates: tuple[ApprovalGate, ...]
    phase_ids: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    invariants: tuple[str, ...]
    state: str
    evidence_references: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class PhaseManifest:
    path: Path
    schema_version: int
    sagekit_contract: str
    document_model: str
    phase_id: str
    objective: str
    depends_on: tuple[str, ...]
    execution_profile: str
    permission_mode: str
    owner: str
    writable_paths: tuple[str, ...]
    read_only_references: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    inherit_forbidden: bool
    acceptance_criteria: tuple[str, ...]
    verification_commands: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    handoff_target: str
    state: str
    digest: str


@dataclass(frozen=True)
class GovernanceProfile:
    id: str
    generic_rules: tuple[str, ...]
    policy: Mapping[str, Any]
    digest: str


@dataclass(frozen=True)
class ExecutionContract:
    contract_id: str
    execution_document_model: str
    runtime_defaults: Mapping[str, Any]
    overrideable_policy_keys: tuple[str, ...]
    profiles: Mapping[str, GovernanceProfile]
    resource_digests: Mapping[str, str]
    digest: str


@dataclass(frozen=True)
class ExecutionProject:
    root: Path
    project_lock: ProjectLock
    contract: ExecutionContract
    milestone: MilestoneManifest
    phases: Mapping[str, PhaseManifest]


def load_execution_project(
    root: Path,
    milestone_id: str | None = None,
    *,
    contract_root: Path | None = None,
) -> ExecutionProject:
    project_root = root.resolve(strict=False)
    if not project_root.is_dir():
        raise ExecutionDocumentError("project root must be an existing directory")
    lock = load_project_lock(project_root)
    contract = load_execution_contract(lock, contract_root=contract_root)
    selected = milestone_id or lock.effective_from
    if compare_milestone_ids(selected, lock.effective_from) < 0:
        raise ExecutionDocumentError(
            f"thin-v1 milestone {selected} precedes effective_from {lock.effective_from}"
        )
    milestone = load_milestone_manifest(project_root, selected, lock)
    phase_root = project_root / "docs" / selected / "phases"
    discovered = {
        path.stem
        for path in phase_root.glob("*.json")
        if path.is_file() or path.is_symlink()
    }
    declared = set(milestone.phase_ids)
    extra = discovered - declared
    if extra:
        raise ExecutionDocumentError(
            "undeclared phase manifest(s): " + ", ".join(sorted(extra))
        )
    phases = {
        phase_id: load_phase_manifest(project_root, selected, phase_id, lock)
        for phase_id in milestone.phase_ids
    }
    project = ExecutionProject(project_root, lock, contract, milestone, phases)
    validate_execution_project(project)
    # Policy validity and approval contradictions are part of loading fail-closed.
    from .policy_resolution import resolve_policy

    resolve_policy(project, milestone, None)
    for phase in phases.values():
        resolve_policy(project, milestone, phase)
    return project


def load_project_lock(root: Path) -> ProjectLock:
    path = root / PROJECT_LOCK_NAME
    payload, digest = _load_authority_json(root, path, "project lock")
    _exact_fields(payload, PROJECT_FIELDS, "project lock")
    _schema_version(payload, "project lock")
    contract = _nonempty(payload.get("sagekit_contract"), "project lock.sagekit_contract")
    if payload.get("execution_document_model") != DOCUMENT_MODEL:
        raise ExecutionDocumentError("project lock execution_document_model must be thin-v1")
    effective = _id(payload.get("effective_from"), MILESTONE_ID_RE, "effective_from")
    if payload.get("legacy_documents") != "immutable":
        raise ExecutionDocumentError("project lock legacy_documents must be immutable")
    profiles = _string_list(payload.get("profiles"), "project lock.profiles", nonempty=True)
    overrides = payload.get("overrides")
    if not isinstance(overrides, dict):
        raise ExecutionDocumentError("project lock.overrides must be an object")
    normalized_overrides: dict[str, Mapping[str, Any]] = {}
    for profile_id, values in overrides.items():
        if not isinstance(profile_id, str) or not isinstance(values, dict):
            raise ExecutionDocumentError("project lock overrides must map profile IDs to objects")
        normalized_overrides[profile_id] = dict(values)
    return ProjectLock(
        path,
        SCHEMA_VERSION,
        contract,
        DOCUMENT_MODEL,
        effective,
        "immutable",
        profiles,
        normalized_overrides,
        digest,
    )


def load_execution_contract(
    lock: ProjectLock, *, contract_root: Path | None = None
) -> ExecutionContract:
    base: Any
    if contract_root is None:
        base = resources.files("sagekit").joinpath("resources", "execution_documents")
    else:
        base = contract_root
    root = base.joinpath(lock.sagekit_contract)
    payload, digest = _load_json(root.joinpath("contract.json"), "execution contract")
    _exact_fields(payload, CONTRACT_FIELDS, "execution contract")
    _schema_version(payload, "execution contract")
    if payload.get("contract_id") != lock.sagekit_contract:
        raise ExecutionDocumentError("execution contract contract_id does not match project lock")
    if payload.get("execution_document_model") != lock.execution_document_model:
        raise ExecutionDocumentError("execution contract document model does not match project lock")
    resource_digests: dict[str, str] = {"contract.json": digest}
    for key in ("project_schema", "milestone_schema", "phase_schema"):
        filename = _safe_resource_name(payload.get(key), f"execution contract.{key}")
        schema, schema_digest = _load_json(root.joinpath(filename), filename)
        if not isinstance(schema, dict):
            raise ExecutionDocumentError(f"{filename} must contain an object")
        resource_digests[filename] = schema_digest
    defaults = payload.get("runtime_defaults")
    if not isinstance(defaults, dict):
        raise ExecutionDocumentError("execution contract.runtime_defaults must be an object")
    overrideable = _string_list(
        payload.get("overrideable_policy_keys"),
        "execution contract.overrideable_policy_keys",
    )
    if "approval_required_for_write" in overrideable:
        raise ExecutionDocumentError("approval_required_for_write must not be overrideable")
    if any(key not in defaults for key in overrideable):
        raise ExecutionDocumentError("overrideable policy key is missing from runtime defaults")
    profile_files = payload.get("profiles")
    if not isinstance(profile_files, dict) or not profile_files:
        raise ExecutionDocumentError("execution contract.profiles must be a non-empty object")
    profiles: dict[str, GovernanceProfile] = {}
    for profile_id, relative in profile_files.items():
        if not isinstance(profile_id, str):
            raise ExecutionDocumentError("execution contract profile ID must be a string")
        filename = _safe_resource_name(relative, f"profile {profile_id}", allow_subdir=True)
        profile_payload, profile_digest = _load_json(root.joinpath(filename), f"profile {profile_id}")
        _exact_fields(profile_payload, PROFILE_FIELDS, f"profile {profile_id}")
        _schema_version(profile_payload, f"profile {profile_id}")
        if profile_payload.get("id") != profile_id:
            raise ExecutionDocumentError(f"profile {profile_id} has mismatched id")
        rules = _string_list(
            profile_payload.get("generic_rules"), f"profile {profile_id}.generic_rules"
        )
        policy = profile_payload.get("policy")
        if not isinstance(policy, dict):
            raise ExecutionDocumentError(f"profile {profile_id}.policy must be an object")
        for key, value in policy.items():
            if key not in defaults or type(value) is not type(defaults[key]):
                raise ExecutionDocumentError(f"profile {profile_id} has unknown or mistyped policy {key}")
        profiles[profile_id] = GovernanceProfile(profile_id, rules, dict(policy), profile_digest)
        resource_digests[filename] = profile_digest
    unknown = set(lock.profiles) - set(profiles)
    if unknown:
        raise ExecutionDocumentError("unknown adopted profile(s): " + ", ".join(sorted(unknown)))
    composite = hashlib.sha256(
        json.dumps(resource_digests, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ExecutionContract(
        lock.sagekit_contract,
        lock.execution_document_model,
        dict(defaults),
        overrideable,
        profiles,
        dict(resource_digests),
        composite,
    )


def load_milestone_manifest(root: Path, milestone_id: str, lock: ProjectLock) -> MilestoneManifest:
    milestone_id = _id(milestone_id, MILESTONE_ID_RE, "milestone ID")
    path = root / "docs" / milestone_id / MILESTONE_MANIFEST_NAME
    payload, digest = _load_authority_json(root, path, "milestone manifest")
    _exact_fields(payload, MILESTONE_FIELDS, "milestone manifest")
    _schema_version(payload, "milestone manifest")
    _matching_contract(payload, lock, "milestone manifest")
    actual_id = _id(payload.get("milestone_id"), MILESTONE_ID_RE, "milestone_id")
    if actual_id != milestone_id:
        raise ExecutionDocumentError("milestone manifest ID does not match its path")
    phase_ids = _string_list(payload.get("phase_ids"), "phase_ids", nonempty=True)
    for phase_id in phase_ids:
        _id(phase_id, PHASE_ID_RE, "phase ID")
    dag_raw = payload.get("dependency_dag")
    if not isinstance(dag_raw, dict):
        raise ExecutionDocumentError("dependency_dag must be an object")
    dag: dict[str, tuple[str, ...]] = {}
    for phase_id, dependencies in dag_raw.items():
        _id(phase_id, PHASE_ID_RE, "dependency_dag phase ID")
        dag[phase_id] = _string_list(dependencies, f"dependency_dag.{phase_id}")
        for dependency in dag[phase_id]:
            _id(dependency, PHASE_ID_RE, "dependency ID")
    gates_raw = payload.get("approval_gates")
    if not isinstance(gates_raw, list):
        raise ExecutionDocumentError("approval_gates must be an array")
    gates: list[ApprovalGate] = []
    gate_ids: set[str] = set()
    for index, raw in enumerate(gates_raw):
        label = f"approval_gates[{index}]"
        if not isinstance(raw, dict):
            raise ExecutionDocumentError(f"{label} must be an object")
        _exact_fields(raw, GATE_FIELDS, label)
        gate_id = _nonempty(raw.get("id"), f"{label}.id")
        if gate_id.casefold() in gate_ids:
            raise ExecutionDocumentError(f"duplicate approval gate ID: {gate_id}")
        gate_ids.add(gate_id.casefold())
        applies_to = _string_list(raw.get("applies_to"), f"{label}.applies_to", nonempty=True)
        if any(item not in phase_ids for item in applies_to):
            raise ExecutionDocumentError(f"{label} applies to an unknown phase")
        status = raw.get("status")
        if status not in {"pending", "approved", "rejected"}:
            raise ExecutionDocumentError(f"{label}.status is invalid")
        permission = _permission(raw.get("permission_mode"), f"{label}.permission_mode")
        authority = _reference_path(root, raw.get("authority_reference"), f"{label}.authority_reference")
        _require_reference(root, authority, f"{label}.authority_reference")
        gates.append(ApprovalGate(gate_id, applies_to, status, permission, authority))
    authority_refs = _reference_list(root, payload.get("authority_references"), "authority_references")
    if not authority_refs:
        raise ExecutionDocumentError("authority_references must be a non-empty array")
    for reference in authority_refs:
        _require_reference(root, reference, "authority_references")
    evidence_refs = _reference_list(root, payload.get("evidence_references"), "evidence_references")
    for reference in evidence_refs:
        _require_reference(root, reference, "evidence_references")
    return MilestoneManifest(
        path,
        SCHEMA_VERSION,
        lock.sagekit_contract,
        DOCUMENT_MODEL,
        actual_id,
        _nonempty(payload.get("objective"), "milestone objective"),
        _nonempty(payload.get("capability_outcome"), "capability outcome"),
        authority_refs,
        _required_profile(
            payload.get("governance_profile"),
            "standard-milestone@v1",
            "governance_profile",
        ),
        dag,
        tuple(gates),
        phase_ids,
        _string_list(payload.get("acceptance_criteria"), "acceptance_criteria", nonempty=True),
        _string_list(payload.get("invariants"), "invariants", nonempty=True),
        _enum(payload.get("state"), MILESTONE_STATES, "milestone state"),
        evidence_refs,
        digest,
    )


def load_phase_manifest(
    root: Path, milestone_id: str, phase_id: str, lock: ProjectLock
) -> PhaseManifest:
    phase_id = _id(phase_id, PHASE_ID_RE, "phase ID")
    path = root / "docs" / milestone_id / "phases" / f"{phase_id}.json"
    payload, digest = _load_authority_json(root, path, f"phase manifest {phase_id}")
    _exact_fields(payload, PHASE_FIELDS, f"phase manifest {phase_id}")
    _schema_version(payload, f"phase manifest {phase_id}")
    _matching_contract(payload, lock, f"phase manifest {phase_id}")
    actual_id = _id(payload.get("phase_id"), PHASE_ID_RE, "phase_id")
    if actual_id != phase_id:
        raise ExecutionDocumentError("phase manifest ID does not match its path")
    permission = _permission(payload.get("permission_mode"), "phase permission_mode")
    writable = _path_list(root, payload.get("writable_paths"), "writable_paths")
    read_only = _reference_list(root, payload.get("read_only_references"), "read_only_references")
    forbidden = _path_list(root, payload.get("forbidden_paths"), "forbidden_paths")
    if permission == "READ_ONLY_REVIEW" and writable:
        raise ExecutionDocumentError("READ_ONLY_REVIEW phase must not declare writable paths")
    for reference in read_only:
        _require_reference(root, reference, "read_only_references")
    _reject_overlaps(writable, read_only, "writable/read-only")
    _reject_overlaps(writable, forbidden, "writable/forbidden")
    inherit_forbidden = payload.get("inherit_forbidden")
    if type(inherit_forbidden) is not bool:
        raise ExecutionDocumentError("inherit_forbidden must be boolean")
    return PhaseManifest(
        path,
        SCHEMA_VERSION,
        lock.sagekit_contract,
        DOCUMENT_MODEL,
        actual_id,
        _nonempty(payload.get("objective"), "phase objective"),
        _string_list(payload.get("depends_on"), "depends_on"),
        _required_profile(
            payload.get("execution_profile"),
            "standard-phase@v1",
            "execution_profile",
        ),
        permission,
        _nonempty(payload.get("owner"), "owner"),
        writable,
        read_only,
        forbidden,
        inherit_forbidden,
        _string_list(payload.get("acceptance_criteria"), "acceptance_criteria", nonempty=True),
        _string_list(payload.get("verification_commands"), "verification_commands", nonempty=True),
        _string_list(payload.get("evidence_requirements"), "evidence_requirements", nonempty=True),
        _string_list(payload.get("stop_conditions"), "stop_conditions", nonempty=True),
        _nonempty(payload.get("handoff_target"), "handoff_target"),
        _enum(payload.get("state"), PHASE_STATES, "phase state"),
        digest,
    )


def validate_execution_project(project: ExecutionProject) -> None:
    lock, contract, milestone = project.project_lock, project.contract, project.milestone
    if milestone.governance_profile not in lock.profiles:
        raise ExecutionDocumentError("unknown or unadopted milestone governance profile")
    phase_keys = set(milestone.phase_ids)
    if set(milestone.dependency_dag) != phase_keys:
        missing = phase_keys - set(milestone.dependency_dag)
        extra = set(milestone.dependency_dag) - phase_keys
        if missing:
            raise ExecutionDocumentError("dependency DAG missing phase: " + ", ".join(sorted(missing)))
        raise ExecutionDocumentError("dependency DAG contains unknown phase: " + ", ".join(sorted(extra)))
    for phase_id, dependencies in milestone.dependency_dag.items():
        missing = set(dependencies) - phase_keys
        if missing:
            raise ExecutionDocumentError(
                f"dependency DAG has missing dependency for {phase_id}: " + ", ".join(sorted(missing))
            )
    _reject_cycles(milestone.dependency_dag)
    for phase_id, phase in project.phases.items():
        if phase.execution_profile not in lock.profiles or phase.execution_profile not in contract.profiles:
            raise ExecutionDocumentError(f"unknown or unadopted profile: {phase.execution_profile}")
        if tuple(milestone.dependency_dag[phase_id]) != phase.depends_on:
            raise ExecutionDocumentError(f"dependency DAG for {phase_id} does not match phase manifest")


def _reject_cycles(dag: Mapping[str, tuple[str, ...]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ExecutionDocumentError(f"dependency DAG cycle includes {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in dag[node]:
            if dependency in dag:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in dag:
        visit(node)


def _load_authority_json(root: Path, path: Path, label: str) -> tuple[dict[str, Any], str]:
    _reject_reparse_components(root, path, label)
    _ensure_within(root, path, label)
    return _load_json(path, label)


def _load_json(path: Any, label: str) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ExecutionDocumentError(f"{label} is missing or unreadable: {exc}") from exc
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, _DuplicateKey) as exc:
        raise ExecutionDocumentError(f"{label} JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutionDocumentError(f"{label} must contain one JSON object")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return payload, hashlib.sha256(canonical).hexdigest()


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_fields(payload: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    unknown = sorted(set(payload) - expected)
    missing = sorted(expected - set(payload))
    if unknown:
        raise ExecutionDocumentError(f"{label} has unknown field(s): " + ", ".join(unknown))
    if missing:
        raise ExecutionDocumentError(f"{label} is missing field(s): " + ", ".join(missing))


def _schema_version(payload: Mapping[str, Any], label: str) -> None:
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise ExecutionDocumentError(f"{label} schema_version must be 1")


def _matching_contract(payload: Mapping[str, Any], lock: ProjectLock, label: str) -> None:
    if payload.get("sagekit_contract") != lock.sagekit_contract:
        raise ExecutionDocumentError(f"{label} sagekit_contract conflicts with project lock")
    if payload.get("document_model") != lock.execution_document_model:
        raise ExecutionDocumentError(f"{label} document_model conflicts with project lock")


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionDocumentError(f"{label} must be a non-empty string")
    return value.strip()


def _id(value: Any, pattern: re.Pattern[str], label: str) -> str:
    result = _nonempty(value, label)
    if pattern.fullmatch(result) is None:
        raise ExecutionDocumentError(f"{label} is invalid: {result}")
    return result


def _enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ExecutionDocumentError(f"{label} is invalid: {value}")
    return value


def _permission(value: Any, label: str) -> str:
    return _enum(value, PERMISSION_MODES, label)


def _required_profile(value: Any, expected: str, label: str) -> str:
    selected = _nonempty(value, label)
    if selected != expected:
        raise ExecutionDocumentError(f"{label} must be {expected}")
    return selected


def _string_list(value: Any, label: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ExecutionDocumentError(f"{label} must be {'a non-empty ' if nonempty else 'an '}array")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _nonempty(item, label)
        if text in seen:
            descriptor = "phase ID" if label == "phase_ids" else "value"
            raise ExecutionDocumentError(f"{label} contains duplicate {descriptor}: {text}")
        seen.add(text)
        result.append(text)
    return tuple(result)


def _repository_path(root: Path, value: Any, label: str) -> str:
    text = _nonempty(value, label)
    normalized_text = text[:-1] if text.endswith("/") else text
    posix = PurePosixPath(normalized_text)
    windows = PureWindowsPath(normalized_text)
    if (
        "\\" in text
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or normalized_text != posix.as_posix()
        or any(part in {".", ".."} for part in posix.parts)
        or any(part.endswith((".", " ")) for part in posix.parts)
        or any(character in text for character in "*?[]")
        or ":" in normalized_text
    ):
        raise ExecutionDocumentError(f"{label} must be a normalized project-relative path")
    candidate = root / Path(*posix.parts)
    _reject_reparse_components(root, candidate, label)
    _ensure_within(root, candidate, label)
    return posix.as_posix()


def _path_list(root: Path, value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ExecutionDocumentError(f"{label} must be an array")
    result = tuple(_repository_path(root, item, label) for item in value)
    folded = [item.casefold() for item in result]
    if len(folded) != len(set(folded)):
        raise ExecutionDocumentError(f"{label} contains duplicate path")
    return result


def _reference_path(root: Path, value: Any, label: str) -> str:
    text = _nonempty(value, label)
    if text.count("#") > 1:
        raise ExecutionDocumentError(f"{label} contains an invalid reference fragment")
    path_text, separator, fragment = text.partition("#")
    if separator and (not fragment or re.fullmatch(r"[A-Za-z0-9_.-]+", fragment) is None):
        raise ExecutionDocumentError(f"{label} contains an invalid reference fragment")
    relative = _repository_path(root, path_text, label)
    return relative + (f"#{fragment}" if separator else "")


def _reference_list(root: Path, value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ExecutionDocumentError(f"{label} must be an array")
    result = tuple(_reference_path(root, item, label) for item in value)
    folded = [item.casefold() for item in result]
    if len(folded) != len(set(folded)):
        raise ExecutionDocumentError(f"{label} contains duplicate reference")
    return result


def _ensure_within(root: Path, candidate: Path, label: str) -> None:
    resolved_root = root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    try:
        common = Path(os.path.commonpath([str(resolved_root), str(resolved_candidate)]))
    except ValueError as exc:
        raise ExecutionDocumentError(f"{label} resolves outside project root") from exc
    if os.path.normcase(str(common)) != os.path.normcase(str(resolved_root)):
        raise ExecutionDocumentError(f"{label} resolves outside project root")


def _reject_reparse_components(root: Path, candidate: Path, label: str) -> None:
    root_absolute = root.absolute()
    candidate_absolute = candidate.absolute()
    try:
        relative = candidate_absolute.relative_to(root_absolute)
    except ValueError:
        return
    current = root_absolute
    for part in relative.parts:
        current = current / part
        if not current.exists() and not current.is_symlink():
            continue
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ExecutionDocumentError(f"{label} path metadata is unreadable: {exc}") from exc
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if current.is_symlink() or (reparse_flag and attributes & reparse_flag):
            raise ExecutionDocumentError(f"{label} contains a symlink or reparse component")


def _require_reference(root: Path, relative: str, label: str) -> None:
    path_part = relative.partition("#")[0]
    path = root / Path(*PurePosixPath(path_part).parts)
    if path.is_symlink() or not path.is_file():
        raise ExecutionDocumentError(f"{label} does not identify an existing regular file: {relative}")


def _paths_overlap(left: str, right: str) -> bool:
    left_parts = tuple(part.casefold() for part in PurePosixPath(left.partition("#")[0]).parts)
    right_parts = tuple(part.casefold() for part in PurePosixPath(right.partition("#")[0]).parts)
    shortest = min(len(left_parts), len(right_parts))
    return left_parts[:shortest] == right_parts[:shortest]


def _reject_overlaps(left: tuple[str, ...], right: tuple[str, ...], label: str) -> None:
    for left_path in left:
        for right_path in right:
            if _paths_overlap(left_path, right_path):
                raise ExecutionDocumentError(
                    f"{label} path overlap: {left_path} and {right_path}"
                )


def _safe_resource_name(value: Any, label: str, *, allow_subdir: bool = False) -> str:
    text = _nonempty(value, label)
    path = PurePosixPath(text)
    if (
        "\\" in text
        or path.is_absolute()
        or text != path.as_posix()
        or any(part in {".", ".."} for part in path.parts)
        or (not allow_subdir and len(path.parts) != 1)
    ):
        raise ExecutionDocumentError(f"{label} contains an unsafe resource path")
    return path.as_posix()


def compare_milestone_ids(left: str, right: str) -> int:
    """Order unambiguous milestone majors and fail closed within ambiguous suffix families."""

    left_id = _id(left, MILESTONE_ID_RE, "milestone ID")
    right_id = _id(right, MILESTONE_ID_RE, "milestone ID")
    if left_id == right_id:
        return 0
    left_major = int(re.match(r"M([0-9]+)", left_id).group(1))
    right_major = int(re.match(r"M([0-9]+)", right_id).group(1))
    if left_major == right_major:
        raise ExecutionDocumentError(
            f"milestone ordering is ambiguous between {left_id} and {right_id}"
        )
    return -1 if left_major < right_major else 1


__all__ = [
    "ApprovalGate",
    "ExecutionContract",
    "ExecutionDocumentError",
    "ExecutionProject",
    "GovernanceProfile",
    "MilestoneManifest",
    "PhaseManifest",
    "ProjectLock",
    "load_execution_contract",
    "load_execution_project",
    "load_milestone_manifest",
    "load_phase_manifest",
    "load_project_lock",
    "validate_execution_project",
    "compare_milestone_ids",
]
