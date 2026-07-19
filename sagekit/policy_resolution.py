from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .execution_documents import (
    ApprovalGate,
    ExecutionContract,
    ExecutionProject,
    MilestoneManifest,
    PhaseManifest,
    ProjectLock,
)


class PolicyResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedPolicy:
    profile_id: str
    profile_digest: str
    generic_rules: tuple[str, ...]
    values: Mapping[str, Any]
    sources: Mapping[str, str]
    digest: str


def resolve_policy(
    project: ExecutionProject,
    milestone: MilestoneManifest,
    phase: PhaseManifest | None,
) -> ResolvedPolicy:
    profile_id = phase.execution_profile if phase is not None else milestone.governance_profile
    if profile_id not in project.project_lock.profiles:
        raise PolicyResolutionError(f"unknown or unadopted profile: {profile_id}")
    profile = project.contract.profiles.get(profile_id)
    if profile is None:
        raise PolicyResolutionError(f"unknown profile: {profile_id}")

    values: dict[str, Any] = dict(project.contract.runtime_defaults)
    sources: dict[str, str] = {key: "runtime-default" for key in values}
    for key, value in profile.policy.items():
        values[key] = value
        sources[key] = f"pinned-profile:{profile_id}"

    validate_project_overrides(project.project_lock, project.contract)
    overrides = project.project_lock.overrides.get(profile_id, {})
    for key, value in overrides.items():
        values[key] = value
        sources[key] = f"project-override:{profile_id}"

    if phase is not None:
        values["permission_mode"] = phase.permission_mode
        sources["permission_mode"] = "phase-manifest"
        applicable = [gate for gate in milestone.approval_gates if phase.phase_id in gate.applies_to]
        _apply_gates(values, sources, phase, applicable)

    canonical_payload = {
        "profile_id": profile_id,
        "profile_digest": profile.digest,
        "values": values,
        "sources": sources,
    }
    canonical = json.dumps(
        canonical_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return ResolvedPolicy(
        profile_id,
        profile.digest,
        profile.generic_rules,
        values,
        sources,
        hashlib.sha256(canonical).hexdigest(),
    )


def validate_project_overrides(lock: ProjectLock, contract: ExecutionContract) -> None:
    adopted = set(lock.profiles)
    known = set(contract.profiles)
    overrideable = set(contract.overrideable_policy_keys)
    defaults = contract.runtime_defaults
    for profile_id, policy in lock.overrides.items():
        if profile_id not in adopted or profile_id not in known:
            raise PolicyResolutionError(f"unknown override profile: {profile_id}")
        for key, value in policy.items():
            if key not in overrideable or key not in defaults:
                raise PolicyResolutionError(f"unknown override policy key: {key}")
            if type(value) is not type(defaults[key]):
                raise PolicyResolutionError(f"override policy type mismatch for {key}")
            if isinstance(value, str) and not value.strip():
                raise PolicyResolutionError(f"override policy value is empty for {key}")


def _apply_gates(
    values: dict[str, Any],
    sources: dict[str, str],
    phase: PhaseManifest,
    gates: list[ApprovalGate],
) -> None:
    closed = [gate for gate in gates if gate.status in {"pending", "rejected"}]
    if phase.permission_mode != "READ_ONLY_REVIEW" and closed:
        rejected = [gate.id for gate in closed if gate.status == "rejected"]
        if rejected:
            raise PolicyResolutionError(
                "write permission would widen rejected gate(s): " + ", ".join(rejected)
            )
        raise PolicyResolutionError(
            "write permission requires approved gate(s): "
            + ", ".join(gate.id for gate in closed)
        )

    approved = [gate for gate in gates if gate.status == "approved"]
    modes = {gate.permission_mode for gate in approved}
    if len(modes) > 1:
        raise PolicyResolutionError("same-tier approved gates conflict on permission_mode")
    if approved:
        mode = approved[0].permission_mode
        values["permission_mode"] = mode
        sources["permission_mode"] = "approved-gate:" + ",".join(gate.id for gate in approved)

    requires_approval = values.get("approval_required_for_write") is True
    if phase.permission_mode != "READ_ONLY_REVIEW" and requires_approval and not approved:
        raise PolicyResolutionError("write permission requires an explicit approved gate")
    if values.get("permission_mode") != phase.permission_mode:
        raise PolicyResolutionError(
            "resolved permission_mode conflicts with phase manifest permission_mode"
        )


__all__ = [
    "PolicyResolutionError",
    "ResolvedPolicy",
    "resolve_policy",
    "validate_project_overrides",
]
