from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from . import __version__
from .execution_documents import (
    ExecutionDocumentError,
    _ensure_within,
    _repository_path,
    load_execution_project,
)
from .policy_resolution import resolve_policy


GENERATED_MARKER = "sagekit-packet-compile@v1"


class PacketError(ValueError):
    pass


@dataclass(frozen=True)
class CompiledPacket:
    mode: str
    payload: Mapping[str, Any]
    digest: str

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
    compact: bool = False,
    contract_root: Path | None = None,
) -> CompiledPacket:
    try:
        project = load_execution_project(
            root, milestone_id, contract_root=contract_root
        )
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
        "profiles": dict(sorted(profile_bindings.items())),
    }
    body: dict[str, Any] = {
        "_generated_by": GENERATED_MARKER,
        "schema_version": 1,
        "kind": "sagekit-ephemeral-execution-packet",
        "document_model": project.project_lock.execution_document_model,
        "sagekit_contract": project.project_lock.sagekit_contract,
        "compiler_version": __version__,
        "mode": "compact" if compact else "standalone",
        "target": {
            "milestone_id": milestone.milestone_id,
            "phase_id": phase.phase_id if phase is not None else None,
        },
        "bindings": bindings,
        "resolved_policy": {
            "profile_id": resolved.profile_id,
            "profile_digest": resolved.profile_digest,
            "values": dict(resolved.values),
            "sources": dict(resolved.sources),
        },
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
    return CompiledPacket(body["mode"], body, digest)


def write_compiled_packet(
    root: Path,
    relative_output: str | Path,
    packet: CompiledPacket,
    *,
    overwrite_generated: bool = False,
) -> Path:
    project_root = root.resolve(strict=False)
    try:
        relative = _repository_path(project_root, str(relative_output), "packet output")
    except ExecutionDocumentError as exc:
        raise PacketError(str(exc)) from exc
    if _is_protected_authority(relative):
        raise PacketError(f"refusing to write protected authority file: {relative}")
    destination = project_root / Path(*PurePosixPath(relative).parts)
    try:
        _ensure_within(project_root, destination, "packet output")
    except ExecutionDocumentError as exc:
        raise PacketError(str(exc)) from exc
    if destination.is_symlink() or destination.parent.is_symlink():
        raise PacketError("packet output symlink is not authorized")
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = packet.to_json()
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


def _is_protected_authority(relative: str) -> bool:
    folded = relative.casefold()
    if folded in {
        "sage_project.json",
        "docs/active_context.md",
        "docs/doc_routing.md",
        "docs/sage_validation_scope.json",
    }:
        return True
    parts = tuple(part.casefold() for part in PurePosixPath(relative).parts)
    if parts and parts[-1] == "milestone_manifest.json":
        return True
    return len(parts) >= 4 and parts[0] == "docs" and parts[-2] == "phases" and parts[-1].endswith(".json")


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
    if not required.issubset(payload):
        return False
    if (
        payload.get("_generated_by") != GENERATED_MARKER
        or payload.get("schema_version") != 1
        or payload.get("kind") != "sagekit-ephemeral-execution-packet"
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
    "PacketError",
    "compile_packet",
    "write_compiled_packet",
]
