from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from . import __version__
from .execution_documents import (
    ExecutionDocumentError,
    _ensure_within,
    _repository_path,
)
from .policy_resolution import resolve_policy
from .spec_sources import (
    SourceConfigurationError,
    SourceProvenance,
    load_normalized_spec,
)
from .resource_policy import ResourcePolicyError, resolve_resource_policy
from .resource_governor import (
    ResourceBusy,
    ResourceClass,
    ResourceManager,
    ResourceRequest,
    default_host_identity,
    host_runtime_path,
    project_runtime_path,
)
from .workspace_binding import (
    WorkspaceBinding,
    build_workspace_binding,
    discover_workspace,
    verify_workspace,
)


GENERATED_MARKER = "sagekit-packet-compile@v3"
V2_GENERATED_MARKER = "sagekit-packet-compile@v2"
LEGACY_GENERATED_MARKER = "sagekit-packet-compile@v1"


class PacketError(ValueError):
    pass


class PacketConfigurationError(PacketError):
    pass


@dataclass(frozen=True)
class CompiledPacket:
    mode: str
    payload: Mapping[str, Any]
    digest: str
    provenance: SourceProvenance | None = None

    def to_json(self) -> str:
        return json.dumps(self.payload, indent=2, sort_keys=True) + "\n"

    def to_text(self) -> str:
        target = self.payload["target"]
        lines = [
            "# SAGE-Kit Ephemeral Execution Packet",
            "",
            f"Mode: {self.mode}",
            f"Milestone: {target['milestone_id']}",
        ]
        if target.get("phase_id"):
            lines.append(f"Phase: {target['phase_id']}")
        lines.extend(
            [
                f"Packet SHA-256: {self.digest}",
                "",
                "## Resolved Policy",
                "",
                json.dumps(self.payload["resolved_policy"], indent=2, sort_keys=True),
                "",
                "## Resolved Resource Policy",
                "",
                json.dumps(
                    self.payload["resolved_resource_policy"], indent=2, sort_keys=True
                ),
                "",
                "## Workspace Binding",
                "",
                json.dumps(self.payload["workspace_binding"], indent=2, sort_keys=True),
                "",
                "## Scope",
                "",
                json.dumps(self.payload["scope"], indent=2, sort_keys=True),
                "",
                "## Verification",
                "",
                json.dumps(self.payload["verification"], indent=2, sort_keys=True),
                "",
                "## Stop Conditions",
                "",
                json.dumps(self.payload["stop_conditions"], indent=2),
            ]
        )
        if "generic_rules" in self.payload:
            lines.extend(
                [
                    "",
                    "## Resolved Generic Rules",
                    "",
                    *[f"- {rule}" for rule in self.payload["generic_rules"]],
                ]
            )
        return "\n".join(lines) + "\n"


def compile_packet(
    root: Path,
    milestone_id: str,
    phase_id: str | None = None,
    *,
    source: Path | None = None,
    compact: bool = False,
    contract_root: Path | None = None,
) -> CompiledPacket:
    try:
        normalized = load_normalized_spec(
            root,
            milestone_id,
            source=source,
            contract_root=contract_root,
            phase_id=phase_id,
        )
        project = normalized.project
    except SourceConfigurationError as exc:
        raise PacketConfigurationError(str(exc)) from exc
    except (ExecutionDocumentError, ValueError) as exc:
        raise PacketError(str(exc)) from exc
    milestone = project.milestone
    if milestone.state not in {"planned", "active"}:
        raise PacketError(f"milestone state is not executable: {milestone.state}")
    phase = None
    if phase_id is not None:
        phase = project.phases.get(phase_id)
        if phase is None:
            raise PacketError(f"unknown phase ID: {phase_id}")
        if phase.state not in {"planned", "ready", "active"}:
            raise PacketError(f"phase state is not executable: {phase.state}")
        incomplete = [
            dependency
            for dependency in phase.depends_on
            if project.phases[dependency].state != "complete"
        ]
        if incomplete:
            raise PacketError(
                "phase dependencies are not complete: " + ", ".join(incomplete)
            )
    resolved = resolve_policy(project, milestone, phase)
    try:
        resource_policy = resolve_resource_policy(
            resource_contract_id=getattr(project.project_lock, "resource_contract", None),
            resource_profile=(getattr(phase, "resource_profile", None) if phase is not None else None),
            overrides=(getattr(phase, "resource_overrides", None) if phase is not None else None),
            permission_mode=(phase.permission_mode if phase is not None else "READ_ONLY_REVIEW"),
            execution_profile=(phase.execution_profile if phase is not None else None),
            milestone_packet=phase is None,
        )
    except ResourcePolicyError as exc:
        raise PacketError(str(exc)) from exc
    identity = discover_workspace(project.root)
    workspace_binding = build_workspace_binding(
        identity,
        base_head=identity.head,
        permission_mode=(phase.permission_mode if phase is not None else "READ_ONLY_REVIEW"),
        controller=(phase.owner if phase is not None else "milestone-orchestration-controller"),
        allowed_paths=(phase.writable_paths if phase is not None else ()),
        read_only_paths=(phase.read_only_references if phase is not None else milestone.authority_references),
        forbidden_paths=(phase.forbidden_paths if phase is not None else ()),
    )
    milestone_profile = project.contract.profiles[milestone.governance_profile]
    profile_bindings: dict[str, str] = {
        milestone_profile.id: milestone_profile.digest,
    }
    if phase is not None:
        phase_profile = project.contract.profiles[phase.execution_profile]
        profile_bindings[phase_profile.id] = phase_profile.digest

    scope: dict[str, Any]
    verification: list[Any]
    stop_conditions: list[str]
    if phase is None:
        scope = {
            "objective": milestone.objective,
            "capability_outcome": milestone.capability_outcome,
            "state": milestone.state,
            "phase_ids": list(milestone.phase_ids),
            "phase_states": {
                item.phase_id: item.state for item in project.phases.values()
            },
            "dependency_dag": {
                key: list(value) for key, value in milestone.dependency_dag.items()
            },
            "waves": {
                wave_id: {
                    "depends_on": list(wave.depends_on),
                    "phase_ids": list(wave.phase_ids),
                }
                for wave_id, wave in sorted(normalized.waves.items())
            },
            "approval_gates": [_gate_payload(gate) for gate in milestone.approval_gates],
            "acceptance_criteria": list(milestone.acceptance_criteria),
            "invariants": list(milestone.invariants),
            "authority_references": list(milestone.authority_references),
            "evidence_references": list(milestone.evidence_references),
        }
        verification = [
            {
                "phase_id": item.phase_id,
                "commands": list(item.verification_commands),
            }
            for item in project.phases.values()
        ]
        stop_conditions = [
            "Stop when milestone authority, dependency, approval, or evidence is missing."
        ]
    else:
        scope = {
            "objective": phase.objective,
            "milestone_state": milestone.state,
            "state": phase.state,
            "depends_on": list(phase.depends_on),
            "wave_id": next(
                (
                    wave_id
                    for wave_id, wave in normalized.waves.items()
                    if phase.phase_id in wave.phase_ids
                ),
                None,
            ),
            "permission_mode": phase.permission_mode,
            "owner": phase.owner,
            "writable_paths": list(phase.writable_paths),
            "read_only_references": list(phase.read_only_references),
            "forbidden_paths": list(phase.forbidden_paths),
            "inherit_forbidden": phase.inherit_forbidden,
            "acceptance_criteria": list(phase.acceptance_criteria),
            "evidence_requirements": list(phase.evidence_requirements),
            "handoff_target": phase.handoff_target,
            "approval_gates": [
                _gate_payload(gate)
                for gate in milestone.approval_gates
                if phase.phase_id in gate.applies_to
            ],
        }
        verification = list(phase.verification_commands)
        stop_conditions = list(phase.stop_conditions)

    bindings: dict[str, Any] = {
        "project_lock_sha256": project.project_lock.digest,
        "milestone_manifest_sha256": milestone.digest,
        "phase_manifest_sha256": phase.digest if phase is not None else None,
        "contract_sha256": project.contract.digest,
        "resolved_policy_sha256": resolved.digest,
        "resource_contract_sha256": resource_policy.contract_digest,
        "resolved_resource_policy_sha256": resource_policy.digest,
        "workspace_binding_sha256": workspace_binding.digest,
        "normalized_spec_sha256": normalized.semantic_digest,
        "profiles": dict(sorted(profile_bindings.items())),
    }
    body: dict[str, Any] = {
        "_generated_by": GENERATED_MARKER,
        "schema_version": 3,
        "kind": "sagekit-ephemeral-execution-packet",
        "document_model": project.project_lock.execution_document_model,
        "sagekit_contract": project.project_lock.sagekit_contract,
        "compiler_version": __version__,
        "mode": "compact" if compact else "standalone",
        "target": {
            "milestone_id": milestone.milestone_id,
            "phase_id": phase.phase_id if phase is not None else None,
        },
        "source_contract": {
            "model": "normalized-spec-v1",
            "semantic_sha256": normalized.semantic_digest,
            "active_class": "ACTIVE_SPEC",
        },
        "bindings": bindings,
        "resolved_policy": {
            "profile_id": resolved.profile_id,
            "profile_digest": resolved.profile_digest,
            "values": dict(resolved.values),
            "sources": dict(resolved.sources),
        },
        "resolved_resource_policy": resource_policy.to_dict(),
        "workspace_binding": workspace_binding.to_dict(),
        "scope": scope,
        "verification": verification,
        "stop_conditions": stop_conditions,
        "runtime_stop_handshake": {
            "required": True,
            "action": "stop-and-handoff",
            "triggers": [
                "missing-or-conflicting-authority",
                "scope-or-permission-expansion",
                "verification-or-safety-failure",
            ],
        },
    }
    if compact:
        body["profile_references"] = [
            {"id": profile_id, "digest": digest}
            for profile_id, digest in sorted(profile_bindings.items())
        ]
    else:
        rules: list[str] = []
        for profile_id in profile_bindings:
            for rule in project.contract.profiles[profile_id].generic_rules:
                if rule not in rules:
                    rules.append(rule)
        body["generic_rules"] = rules
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    body["packet_sha256"] = digest
    return CompiledPacket(
        body["mode"], body, digest, provenance=normalized.provenance
    )


def write_compiled_packet(
    root: Path,
    relative_output: str | Path,
    packet: CompiledPacket,
    *,
    overwrite_generated: bool = False,
) -> Path:
    _validate_packet_for_write(packet)
    project_root = root.resolve(strict=False)
    try:
        relative = _repository_path(project_root, str(relative_output), "packet output")
    except ExecutionDocumentError as exc:
        raise PacketError(str(exc)) from exc
    if _is_protected_authority(project_root, relative, packet):
        raise PacketError(f"refusing to write protected authority file: {relative}")
    destination = project_root / Path(*PurePosixPath(relative).parts)
    try:
        _ensure_within(project_root, destination, "packet output")
    except ExecutionDocumentError as exc:
        raise PacketError(str(exc)) from exc
    if destination.is_symlink() or destination.parent.is_symlink():
        raise PacketError("packet output symlink is not authorized")
    rendered = packet.to_json()
    with _packet_write_lease(project_root, relative, packet):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if not overwrite_generated:
                raise PacketError(f"packet output already exists: {relative}")
            try:
                existing = json.loads(destination.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise PacketError("existing output is not a recognized generated packet") from exc
            if not _is_recognized_generated_packet(existing):
                raise PacketError("existing output is not a recognized generated packet")
            handle, temporary_name = tempfile.mkstemp(
                prefix=".sagekit-packet-", suffix=".tmp", dir=destination.parent
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(rendered)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            return destination
        try:
            with destination.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(rendered)
        except FileExistsError as exc:
            raise PacketError(f"packet output already exists: {relative}") from exc
    return destination


@contextmanager
def _packet_write_lease(root: Path, relative: str, packet: CompiledPacket):
    if os.environ.get("SAGEKIT_DESCENDANT") == "1":
        raise PacketError("descendant cannot self-issue compiler repo-write authority")
    try:
        binding = WorkspaceBinding.from_dict(packet.payload.get("workspace_binding"))
    except ValueError as exc:
        raise PacketError(f"packet workspace binding is invalid: {exc}") from exc
    verification = verify_workspace(binding, current=discover_workspace(root))
    if not verification.ok:
        raise PacketError(
            "packet output workspace differs: " + "; ".join(verification.errors)
        )
    resource = packet.payload.get("resolved_resource_policy")
    if not isinstance(resource, dict):
        raise PacketError("packet resource policy is invalid")
    runtime_output = relative.casefold().startswith(".sagekit/packets/")
    allowed = resource.get("allowed_resource_classes")
    if not runtime_output and (
        not isinstance(allowed, list)
        or ResourceClass.REPO_WRITE.value not in allowed
    ):
        raise PacketError("packet does not authorize repo-write output")
    scope_output = any(
        relative == value or relative.startswith(f"{value.rstrip('/')}/")
        for value in binding.allowed_paths
    )
    if not runtime_output and not scope_output:
        raise PacketError("packet output is outside generated runtime or allowed paths")
    identity = discover_workspace(root)
    manager = ResourceManager(
        host_runtime=host_runtime_path(),
        project_runtime=project_runtime_path(
            Path(identity.project_root),
            Path(identity.git_common_dir) if identity.git_common_dir else None,
        ),
    )
    identity_digest = lambda value: hashlib.sha256(
        os.path.normcase(value).encode("utf-8")
    ).hexdigest()
    request = ResourceRequest(
        resource_class=ResourceClass.REPO_WRITE,
        run_id=f"packet-output-{packet.digest[:16]}",
        controller=binding.controller,
        stage="packet-output",
        authority_digest=packet.digest,
        host_identity=default_host_identity(),
        project_identity=identity_digest(
            identity.git_common_dir or identity.repository_root
        ),
        worktree_identity=identity_digest(identity.worktree_root),
        permission_mode=binding.permission_mode,
        allowed_classes=(ResourceClass.REPO_WRITE,),
    )
    try:
        lease = manager.acquire(request, wait_timeout=30.0)
    except ResourceBusy as exc:
        raise PacketError(f"{exc.state}: {exc}") from exc
    try:
        yield
    finally:
        manager.release(lease)


def _validate_packet_for_write(packet: CompiledPacket) -> None:
    payload = packet.payload
    if (
        not _is_recognized_generated_packet(payload)
        or payload.get("schema_version") not in {2, 3}
        or payload.get("packet_sha256") != packet.digest
        or payload.get("mode") != packet.mode
    ):
        raise PacketError("compiled packet digest or generated structure is invalid")
    try:
        binding = WorkspaceBinding.from_dict(payload.get("workspace_binding"))
    except ValueError as exc:
        raise PacketError(f"packet workspace binding is invalid: {exc}") from exc
    resource = payload.get("resolved_resource_policy")
    bindings = payload.get("bindings")
    if not isinstance(resource, dict) or not isinstance(bindings, dict):
        raise PacketError("packet resource bindings are invalid")
    stored = resource.get("resolved_policy_sha256")
    unsigned = dict(resource)
    unsigned.pop("resolved_policy_sha256", None)
    resolved_digest = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (
        stored != resolved_digest
        or bindings.get("resolved_resource_policy_sha256") != stored
        or bindings.get("workspace_binding_sha256") != binding.digest
    ):
        raise PacketError("packet resource or workspace digest differs")


def _is_protected_authority(
    root: Path, relative: str, packet: CompiledPacket | None = None
) -> bool:
    folded = relative.casefold()
    if folded in {
        "sage_project.json",
        "sagekit_config.json",
        "docs/active_context.md",
        "docs/doc_routing.md",
        "docs/sage_validation_scope.json",
    }:
        return True
    try:
        from .spec_sources import load_source_config

        config = load_source_config(root)
    except ValueError:
        config = None
    if config is not None and folded == config.active_context.casefold():
        return True
    if packet is not None and packet.provenance is not None:
        destination = (root / Path(*PurePosixPath(relative).parts)).resolve(strict=False)
        source = Path(packet.provenance.canonical_path)
        if _same_authority_location(root, source, destination):
            return True
    parts = tuple(part.casefold() for part in PurePosixPath(relative).parts)
    if parts and parts[-1] == "milestone_manifest.json":
        return True
    return len(parts) >= 4 and parts[0] == "docs" and parts[-2] == "phases" and parts[-1].endswith(".json")


def _same_authority_location(root: Path, source: Path, destination: Path) -> bool:
    """Compare physical file identity, including hardlinks and directory aliases."""

    def samefile(left: Path, right: Path) -> bool:
        try:
            if left.exists() and right.exists():
                return os.path.samefile(left, right)
        except OSError:
            pass
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
            str(right.resolve(strict=False))
        )

    if samefile(source, destination):
        return True
    if not source.is_dir():
        return False
    authority_files = [
        source / "MILESTONE_MANIFEST.json",
        source / "WAVES.json",
    ]
    phases = source / "phases"
    if phases.is_dir():
        authority_files.extend(phases.glob("*.json"))
    if any(samefile(path, destination) for path in authority_files if path.is_file()):
        return True
    probe = destination if destination.exists() else destination.parent
    while not probe.exists() and probe != root and probe.parent != probe:
        probe = probe.parent
    for ancestor in (probe, *probe.parents):
        if samefile(source, ancestor):
            return True
        if samefile(root, ancestor):
            break
    return False


def _gate_payload(gate: Any) -> dict[str, Any]:
    return {
        "id": gate.id,
        "applies_to": list(gate.applies_to),
        "status": gate.status,
        "permission_mode": gate.permission_mode,
        "authority_reference": gate.authority_reference,
    }


def _is_recognized_generated_packet(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    required = {
        "_generated_by",
        "schema_version",
        "kind",
        "document_model",
        "sagekit_contract",
        "compiler_version",
        "mode",
        "target",
        "bindings",
        "resolved_policy",
        "scope",
        "verification",
        "stop_conditions",
        "runtime_stop_handshake",
        "packet_sha256",
    }
    schema = payload.get("schema_version")
    marker = payload.get("_generated_by")
    if schema == 3 and marker == GENERATED_MARKER:
        required.update(
            {"resolved_resource_policy", "workspace_binding", "source_contract"}
        )
    elif schema == 2 and marker == V2_GENERATED_MARKER:
        required.update({"resolved_resource_policy", "workspace_binding"})
    elif schema == 1 and marker == LEGACY_GENERATED_MARKER:
        pass
    else:
        return False
    if not required.issubset(payload):
        return False
    if (
        payload.get("kind") != "sagekit-ephemeral-execution-packet"
        or payload.get("mode") not in {"standalone", "compact"}
    ):
        return False
    expected = set(required)
    if payload["mode"] == "standalone":
        expected.add("generic_rules")
    else:
        expected.add("profile_references")
    if set(payload) != expected:
        return False
    target = payload.get("target")
    bindings = payload.get("bindings")
    if (
        not isinstance(target, dict)
        or set(target) != {"milestone_id", "phase_id"}
        or not isinstance(bindings, dict)
    ):
        return False
    if schema == 3:
        source_contract = payload.get("source_contract")
        if (
            not isinstance(source_contract, dict)
            or set(source_contract) != {"model", "semantic_sha256", "active_class"}
            or source_contract.get("model") != "normalized-spec-v1"
            or source_contract.get("active_class") != "ACTIVE_SPEC"
            or not isinstance(source_contract.get("semantic_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", source_contract["semantic_sha256"]) is None
            or bindings.get("normalized_spec_sha256")
            != source_contract.get("semantic_sha256")
        ):
            return False
    stored = payload.get("packet_sha256")
    if not isinstance(stored, str) or re.fullmatch(r"[0-9a-f]{64}", stored) is None:
        return False
    unsigned = dict(payload)
    unsigned.pop("packet_sha256", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest() == stored


__all__ = [
    "CompiledPacket",
    "GENERATED_MARKER",
    "V2_GENERATED_MARKER",
    "PacketError",
    "PacketConfigurationError",
    "compile_packet",
    "write_compiled_packet",
]
