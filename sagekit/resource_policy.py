"""Versioned resolution of the independent SAGE-Kit resource contract."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Sequence

from .resource_governor import RESOURCE_PROFILE_ID, ResourceClass


RESOURCE_POLICY_SCHEMA_VERSION = 1
_OVERRIDE_FIELDS = frozenset(
    {"runtime_exclusive", "active_agent_limit", "allowed_resource_classes"}
)
_NEUTRAL_RESOURCE_PROFILE = frozenset({"n/a", "na", "neutral"})


class ResourcePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceContract:
    profile_id: str
    active_agent_limits: Mapping[str, int]
    writer_limits: Mapping[str, int]
    writer_ownership: str
    allowed_resource_classes: tuple[str, ...]
    host_limits: Mapping[str, int]
    project_limits: Mapping[str, int]
    worktree_limits: Mapping[str, int]
    verification_controller: str
    descendant_default: str
    lease_requirements: Mapping[str, tuple[str, ...]]
    wait_policy: Mapping[str, float]
    process_policy: Mapping[str, Any]
    containment_policy: Mapping[str, Any]
    digest: str


@dataclass(frozen=True)
class ResolvedResourcePolicy:
    profile_id: str
    contract_digest: str
    active_agent_limit: int
    writer_limit: int
    writer_ownership: str
    allowed_resource_classes: tuple[str, ...]
    exclusive_resources: tuple[str, ...]
    host_limits: Mapping[str, int]
    project_limits: Mapping[str, int]
    worktree_limits: Mapping[str, int]
    verification_controller: str
    descendant_default: str
    lease_requirements: Mapping[str, tuple[str, ...]]
    wait_policy: Mapping[str, float]
    process_policy: Mapping[str, Any]
    containment_policy: Mapping[str, Any]
    compatibility_defaulted: bool
    digest: str

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "contract_digest": self.contract_digest,
            "active_agent_limit": self.active_agent_limit,
            "writer_limit": self.writer_limit,
            "writer_ownership": self.writer_ownership,
            "allowed_resource_classes": list(self.allowed_resource_classes),
            "exclusive_resources": list(self.exclusive_resources),
            "host_limits": dict(self.host_limits),
            "project_limits": dict(self.project_limits),
            "worktree_limits": dict(self.worktree_limits),
            "verification_controller": self.verification_controller,
            "descendant_default": self.descendant_default,
            "lease_requirements": {
                key: list(value) for key, value in sorted(self.lease_requirements.items())
            },
            "wait_policy": dict(self.wait_policy),
            "process_policy": dict(self.process_policy),
            "containment_policy": dict(self.containment_policy),
            "compatibility_defaulted": self.compatibility_defaulted,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_payload(), "resolved_policy_sha256": self.digest}


def load_resource_contract(
    profile_id: str = RESOURCE_PROFILE_ID,
    *,
    resource_root: Path | None = None,
) -> ResourceContract:
    base: Any = (
        resources.files("sagekit").joinpath("resources", "resource_governance")
        if resource_root is None
        else resource_root
    )
    path = base.joinpath(f"{profile_id}.json")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResourcePolicyError(f"could not load resource contract {profile_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResourcePolicyError("resource contract must be an object")
    expected = {
        "schema_version",
        "id",
        "active_agent_limits",
        "writer_limits",
        "writer_ownership",
        "allowed_resource_classes",
        "host_limits",
        "project_limits",
        "worktree_limits",
        "verification_controller",
        "descendant_default",
        "lease_requirements",
        "wait_policy",
        "process_policy",
        "containment_policy",
    }
    if set(payload) != expected or payload.get("schema_version") != RESOURCE_POLICY_SCHEMA_VERSION:
        raise ResourcePolicyError("resource contract fields or schema version are invalid")
    if payload.get("id") != profile_id:
        raise ResourcePolicyError("resource contract ID does not match requested profile")
    active_limits = _positive_int_mapping(
        payload.get("active_agent_limits"),
        "active_agent_limits",
        exact={"light", "standard", "heavy"},
    )
    writer_limits = _positive_int_mapping(
        payload.get("writer_limits"),
        "writer_limits",
        exact={"light", "standard", "heavy"},
    )
    host_limits = _positive_int_mapping(
        payload.get("host_limits"),
        "host_limits",
        exact={"cpu-heavy", "package-build"},
    )
    project_limits = _positive_int_mapping(
        payload.get("project_limits"),
        "project_limits",
        exact={"submit-exclusive", "git-index-mutation", "verification-controller"},
    )
    worktree_limits = _positive_int_mapping(
        payload.get("worktree_limits"),
        "worktree_limits",
        exact={"repo-write", "local-managed-command"},
    )
    allowed = _resource_classes(payload.get("allowed_resource_classes"))
    lease_raw = payload.get("lease_requirements")
    if not isinstance(lease_raw, dict) or set(lease_raw) != {item.value for item in ResourceClass}:
        raise ResourcePolicyError("lease_requirements must cover every resource class")
    leases: dict[str, tuple[str, ...]] = {}
    for key, value in lease_raw.items():
        leases[key] = _strings(value, f"lease_requirements.{key}")
    wait = payload.get("wait_policy")
    if not isinstance(wait, dict) or set(wait) != {"poll_interval_seconds", "max_wait_seconds"}:
        raise ResourcePolicyError("wait_policy fields are invalid")
    if any(type(value) not in {int, float} or float(value) <= 0 for value in wait.values()):
        raise ResourcePolicyError("wait_policy values must be positive numbers")
    process = payload.get("process_policy")
    if not isinstance(process, dict) or set(process) != {
        "max_direct_managed_children",
        "max_owned_processes",
        "max_output_bytes",
        "priority",
        "thread_limit",
    }:
        raise ResourcePolicyError("process_policy fields are invalid")
    if (
        type(process.get("max_direct_managed_children")) is not int
        or process["max_direct_managed_children"] < 1
    ):
        raise ResourcePolicyError("max_direct_managed_children must be a positive integer")
    if (
        type(process.get("max_owned_processes")) is not int
        or not 2 <= process["max_owned_processes"] <= 256
    ):
        raise ResourcePolicyError("max_owned_processes must be between 2 and 256")
    if type(process.get("max_output_bytes")) is not int or process["max_output_bytes"] <= 0:
        raise ResourcePolicyError("max_output_bytes must be positive")
    if type(process.get("thread_limit")) is not int or process["thread_limit"] <= 0:
        raise ResourcePolicyError("thread_limit must be a positive integer")
    if not isinstance(process.get("priority"), str) or not process.get("priority").strip():
        raise ResourcePolicyError("priority is not a non-empty string")
    containment = payload.get("containment_policy")
    if (
        not isinstance(containment, dict)
        or set(containment)
        != {"minimum_level", "hard_adapters_optional", "soft_bypass_disclosed"}
        or containment.get("minimum_level") != "MANAGED"
        or containment.get("soft_bypass_disclosed") is not True
    ):
        raise ResourcePolicyError("containment_policy is invalid or not conservative")
    _strings(containment.get("hard_adapters_optional"), "hard_adapters_optional")
    writer = _nonempty(payload.get("writer_ownership"), "writer_ownership")
    verification = _nonempty(payload.get("verification_controller"), "verification_controller")
    descendant = _nonempty(payload.get("descendant_default"), "descendant_default")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return ResourceContract(
        profile_id,
        active_limits,
        writer_limits,
        writer,
        allowed,
        host_limits,
        project_limits,
        worktree_limits,
        verification,
        descendant,
        leases,
        {key: float(value) for key, value in wait.items()},
        dict(process),
        dict(containment),
        hashlib.sha256(canonical).hexdigest(),
    )


def resolve_resource_policy(
    *,
    resource_contract_id: str | None,
    resource_profile: str | None,
    overrides: Mapping[str, Any] | None,
    permission_mode: str,
    execution_profile: str | None,
    milestone_packet: bool,
    resource_root: Path | None = None,
) -> ResolvedResourcePolicy:
    compatibility_defaulted = resource_contract_id is None and resource_profile is None
    contract_id = resource_contract_id or RESOURCE_PROFILE_ID
    profile_input = _normalize_resource_profile(resource_profile)
    profile_was_explicit = resource_profile is not None
    if profile_input is not None and profile_input != contract_id:
        raise ResourcePolicyError(
            f"unknown or unpinned resource profile: {profile_input}"
        )
    profile_id = (
        contract_id
        if compatibility_defaulted
        else ("N/A" if profile_input is None else profile_input)
    )
    if profile_was_explicit and profile_input is not None:
        profile_id = profile_input
    contract = load_resource_contract(contract_id, resource_root=resource_root)
    if profile_input is None:
        level = "light"
    else:
        level = _execution_level(execution_profile)
    if permission_mode == "READ_ONLY_REVIEW":
        level = "light"
    active_limit = contract.active_agent_limits[level]
    writer_limit = contract.writer_limits[level]
    allowed = _permission_ceiling(permission_mode, contract.allowed_resource_classes)
    exclusive: tuple[str, ...] = ()
    raw_overrides: Mapping[str, Any] = {} if overrides is None else overrides
    if not isinstance(raw_overrides, Mapping):
        raise ResourcePolicyError("resource_overrides must be an object")
    unknown = set(raw_overrides) - _OVERRIDE_FIELDS
    if unknown:
        raise ResourcePolicyError(
            "unknown resource override(s): " + ", ".join(sorted(unknown))
        )
    if "runtime_exclusive" in raw_overrides:
        exclusive = _exclusive_resources(raw_overrides["runtime_exclusive"])
    if "active_agent_limit" in raw_overrides:
        candidate = raw_overrides["active_agent_limit"]
        if type(candidate) is not int or candidate <= 0 or candidate > active_limit:
            raise ResourcePolicyError("active_agent_limit override may only reduce capacity")
        active_limit = candidate
    if "allowed_resource_classes" in raw_overrides:
        requested = _resource_classes(raw_overrides["allowed_resource_classes"])
        if not set(requested).issubset(allowed):
            raise ResourcePolicyError("allowed_resource_classes override expands authority")
        allowed = requested
    if milestone_packet:
        allowed = (ResourceClass.REASONING_ONLY.value,)
        active_limit = 1
        exclusive = ()
    unsigned = {
        "profile_id": profile_id,
        "contract_digest": contract.digest,
        "active_agent_limit": active_limit,
        "writer_limit": writer_limit,
        "writer_ownership": contract.writer_ownership,
        "allowed_resource_classes": list(allowed),
        "exclusive_resources": list(exclusive),
        "host_limits": dict(contract.host_limits),
        "project_limits": dict(contract.project_limits),
        "worktree_limits": dict(contract.worktree_limits),
        "verification_controller": contract.verification_controller,
        "descendant_default": contract.descendant_default,
        "lease_requirements": {
            key: list(value) for key, value in sorted(contract.lease_requirements.items())
        },
        "wait_policy": dict(contract.wait_policy),
        "process_policy": dict(contract.process_policy),
        "containment_policy": dict(contract.containment_policy),
        "compatibility_defaulted": compatibility_defaulted,
    }
    digest = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ResolvedResourcePolicy(
        profile_id,
        contract.digest,
        active_limit,
        writer_limit,
        contract.writer_ownership,
        tuple(allowed),
        exclusive,
        dict(contract.host_limits),
        dict(contract.project_limits),
        dict(contract.worktree_limits),
        contract.verification_controller,
        contract.descendant_default,
        dict(contract.lease_requirements),
        dict(contract.wait_policy),
        dict(contract.process_policy),
        dict(contract.containment_policy),
        compatibility_defaulted,
        digest,
    )


def _execution_level(execution_profile: str | None) -> str:
    if execution_profile is None:
        return "light"
    folded = execution_profile.casefold()
    if folded.startswith("heavy"):
        return "heavy"
    if folded.startswith("light"):
        return "light"
    return "standard"


def _normalize_resource_profile(profile: str | None) -> str | None:
    if profile is None:
        return None
    if not isinstance(profile, str) or not profile.strip():
        raise ResourcePolicyError("resource_profile must be a non-empty string")
    normalized = profile.strip().casefold()
    if normalized in _NEUTRAL_RESOURCE_PROFILE:
        return None
    return profile.strip()


def _permission_ceiling(permission_mode: str, configured: Sequence[str]) -> tuple[str, ...]:
    ceilings = {
        "READ_ONLY_REVIEW": {"reasoning-only"},
        "WRITE_AUTHORIZED": {
            "reasoning-only",
            "repo-read",
            "repo-write",
            "cpu-heavy",
            "io-heavy",
        },
        "CORRECTIVE_AUTHORIZED": {
            "reasoning-only",
            "repo-read",
            "repo-write",
            "cpu-heavy",
            "io-heavy",
        },
        "ENVIRONMENT_WRITE_AUTHORIZED": {
            "reasoning-only",
            "repo-read",
            "repo-write",
            "cpu-heavy",
            "io-heavy",
            "package-build",
            "runtime-exclusive",
        },
        "SUBMIT_AUTHORIZED": {item.value for item in ResourceClass},
    }
    if permission_mode not in ceilings:
        raise ResourcePolicyError(f"unknown permission mode: {permission_mode}")
    return tuple(item for item in configured if item in ceilings[permission_mode])


def _positive_int_mapping(value: Any, label: str, *, exact: set[str]) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != exact:
        raise ResourcePolicyError(f"{label} fields are invalid")
    if any(type(item) is not int or item <= 0 for item in value.values()):
        raise ResourcePolicyError(f"{label} values must be positive integers")
    return dict(value)


def _resource_classes(value: Any) -> tuple[str, ...]:
    values = _strings(value, "allowed_resource_classes")
    known = {item.value for item in ResourceClass}
    if set(values) - known or len(values) != len(set(values)):
        raise ResourcePolicyError("allowed_resource_classes contains unknown or duplicate values")
    return values


def _exclusive_resources(value: Any) -> tuple[str, ...]:
    values = _strings(value, "runtime_exclusive")
    normalized: list[str] = []
    for item in values:
        if (
            item != item.strip()
            or len(item) > 200
            or ".." in item
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", item)
        ):
            raise ResourcePolicyError(f"invalid runtime-exclusive resource: {item!r}")
        normalized.append(item.casefold())
    if len(normalized) != len(set(normalized)):
        raise ResourcePolicyError("runtime_exclusive contains duplicates")
    return tuple(sorted(normalized))


def _strings(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ResourcePolicyError(f"{label} must be an array of non-empty strings")
    return tuple(value)


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ResourcePolicyError(f"{label} must be a non-empty trimmed string")
    return value


__all__ = [
    "RESOURCE_POLICY_SCHEMA_VERSION",
    "ResolvedResourcePolicy",
    "ResourceContract",
    "ResourcePolicyError",
    "load_resource_contract",
    "resolve_resource_policy",
]
