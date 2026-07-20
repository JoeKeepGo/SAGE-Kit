"""CLI composition for workspace verification and managed resource execution."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .packet import _is_recognized_generated_packet
from .process_supervisor import ProcessClassification, ProcessResult, run_process
from .resource_governor import (
    DEFAULT_LEASE_TTL,
    ResourceBusy,
    ResourceClass,
    ResourceLease,
    ResourceManager,
    ResourceRequest,
    current_process_identity,
    default_host_identity,
    host_runtime_path,
    project_runtime_path,
)
from .resource_policy import resolve_resource_policy
from .workspace_binding import (
    WorkspaceBinding,
    authorize_command,
    build_workspace_binding,
    discover_workspace,
    verify_workspace,
)


class ResourceCliError(ValueError):
    pass


class ResourceOperationalError(ResourceCliError):
    pass


@dataclass(frozen=True)
class PacketAuthority:
    packet_digest: str
    binding: WorkspaceBinding
    allowed_classes: tuple[ResourceClass, ...]
    exclusive_resources: tuple[str, ...]
    process_policy: Mapping[str, Any]
    containment_policy: Mapping[str, Any]

    @property
    def permission_mode(self) -> str:
        return self.binding.permission_mode

    @property
    def controller(self) -> str:
        return self.binding.controller


@dataclass(frozen=True)
class LiveAuthority:
    digest: str
    binding: WorkspaceBinding
    allowed_classes: tuple[ResourceClass, ...]
    exclusive_resources: tuple[str, ...]
    process_policy: Mapping[str, Any]
    containment_policy: Mapping[str, Any]

    @property
    def permission_mode(self) -> str:
        return self.binding.permission_mode

    @property
    def controller(self) -> str:
        return self.binding.controller


def load_packet_authority(path: Path) -> PacketAuthority:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResourceCliError(f"could not load execution packet: {exc}") from exc
    if not _is_recognized_generated_packet(payload) or payload.get("schema_version") != 2:
        raise ResourceCliError("execution packet is not a recognized schema-v2 generated packet")
    binding = WorkspaceBinding.from_dict(payload.get("workspace_binding"))
    resource = payload.get("resolved_resource_policy")
    if not isinstance(resource, dict):
        raise ResourceCliError("execution packet resource policy is invalid")
    stored = resource.get("resolved_policy_sha256")
    unsigned = dict(resource)
    unsigned.pop("resolved_policy_sha256", None)
    if (
        not isinstance(stored, str)
        or _json_digest(unsigned) != stored
        or payload.get("bindings", {}).get("resolved_resource_policy_sha256") != stored
        or payload.get("bindings", {}).get("workspace_binding_sha256") != binding.digest
    ):
        raise ResourceCliError("execution packet resource/workspace digest differs")
    raw_allowed = resource.get("allowed_resource_classes")
    if not isinstance(raw_allowed, list):
        raise ResourceCliError("execution packet allowed resource classes are invalid")
    try:
        allowed = tuple(ResourceClass(value) for value in raw_allowed)
    except (TypeError, ValueError) as exc:
        raise ResourceCliError("execution packet contains an unknown resource class") from exc
    if len(allowed) != len(set(allowed)):
        raise ResourceCliError("execution packet resource classes contain duplicates")
    raw_exclusive = resource.get("exclusive_resources")
    process_policy = resource.get("process_policy")
    containment_policy = resource.get("containment_policy")
    if (
        not isinstance(raw_exclusive, list)
        or not all(isinstance(item, str) for item in raw_exclusive)
        or not isinstance(process_policy, dict)
        or not isinstance(containment_policy, dict)
    ):
        raise ResourceCliError("execution packet resource policy fields are invalid")
    return PacketAuthority(
        str(payload["packet_sha256"]),
        binding,
        allowed,
        tuple(raw_exclusive),
        dict(process_policy),
        dict(containment_policy),
    )


def live_authority(
    target: Path,
    *,
    permission_mode: str,
    controller: str,
) -> LiveAuthority:
    identity = discover_workspace(target)
    binding = build_workspace_binding(
        identity,
        base_head=identity.head,
        permission_mode=permission_mode,
        controller=controller,
        allowed_paths=(),
    )
    resolved = resolve_resource_policy(
        resource_contract_id=None,
        resource_profile=None,
        overrides=None,
        permission_mode=permission_mode,
        execution_profile="standard-phase@v1",
        milestone_packet=False,
    )
    return LiveAuthority(
        binding.digest,
        binding,
        tuple(ResourceClass(value) for value in resolved.allowed_resource_classes),
        resolved.exclusive_resources,
        resolved.process_policy,
        resolved.containment_policy,
    )


def authority_for(
    target: Path,
    *,
    packet_path: Path | None,
    permission_mode: str,
    controller: str,
) -> PacketAuthority | LiveAuthority:
    authority: PacketAuthority | LiveAuthority
    if packet_path is None:
        authority = live_authority(
            target, permission_mode=permission_mode, controller=controller
        )
    else:
        authority = load_packet_authority(packet_path)
    verification = verify_workspace(authority.binding, current=discover_workspace(target))
    if not verification.ok:
        raise ResourceCliError("workspace verification failed: " + "; ".join(verification.errors))
    inherited = _inherited_authority()
    if inherited is not None:
        parent_digest, parent_permission, parent_classes = inherited
        if _permission_rank(authority.permission_mode) > _permission_rank(parent_permission):
            raise ResourceCliError("descendant workspace authority increases permission mode")
        if not set(authority.allowed_classes).issubset(parent_classes):
            raise ResourceCliError("descendant workspace authority increases resource classes")
        if packet_path is None and authority.digest != parent_digest:
            raise ResourceCliError("descendant cannot mint a different live authority digest")
    return authority


def manager_for_target(
    target: Path,
    *,
    owner_parent: bool = False,
) -> tuple[ResourceManager, Any]:
    identity = discover_workspace(target)
    common = Path(identity.git_common_dir) if identity.git_common_dir else None
    process_identity = current_process_identity(os.getppid() if owner_parent else None)
    manager = ResourceManager(
        host_runtime=host_runtime_path(),
        project_runtime=project_runtime_path(Path(identity.project_root), common),
        process_identity=process_identity,
    )
    return manager, identity


def workspace_verify_payload(target: Path, packet_path: Path) -> tuple[int, dict[str, Any]]:
    authority = load_packet_authority(packet_path)
    result = verify_workspace(authority.binding, current=discover_workspace(target))
    return (
        0 if result.ok else 1,
        {
            "ok": result.ok,
            "state": "VERIFIED" if result.ok else "HANDOFF_READY",
            "binding_sha256": authority.binding.digest,
            "errors": list(result.errors),
        },
    )


def resource_status_payload(target: Path) -> dict[str, Any]:
    manager, _ = manager_for_target(target)
    return {
        "ok": True,
        "state": "AVAILABLE",
        "host_runtime": str(manager.host_runtime),
        "project_runtime": str(manager.project_runtime),
        "leases": [_public_lease(record.to_dict()) for record in manager.status()],
    }


def resource_acquire_payload(
    target: Path,
    *,
    resource_class: ResourceClass,
    run_id: str,
    stage: str,
    packet_path: Path | None,
    permission_mode: str,
    controller: str,
    wait_timeout: float,
    lease_ttl: float,
    exclusive: Sequence[str],
    on_wait=None,
) -> tuple[int, dict[str, Any]]:
    if os.environ.get("SAGEKIT_DESCENDANT") == "1":
        raise ResourceOperationalError(
            "descendant cannot acquire a resource lease without an explicit root delegation"
        )
    authority = authority_for(
        target,
        packet_path=packet_path,
        permission_mode=permission_mode,
        controller=controller,
    )
    if resource_class not in authority.allowed_classes:
        raise ResourceOperationalError(
            f"resource class {resource_class.value} exceeds packet or permission authority"
        )
    manager, identity = manager_for_target(target, owner_parent=True)
    request = _request(
        authority,
        identity,
        resource_class=resource_class,
        run_id=run_id,
        stage=stage,
        exclusive=exclusive,
    )
    try:
        lease = manager.acquire(
            request,
            wait_timeout=wait_timeout,
            lease_ttl=lease_ttl,
            on_wait=on_wait,
        )
    except ResourceBusy as exc:
        return 1, {
            "ok": False,
            "state": exc.state,
            "message": str(exc),
            "blocking_lease": (
                _public_lease(exc.blocking_lease.to_dict())
                if exc.blocking_lease is not None
                else None
            ),
        }
    return 0, {
        "ok": True,
        "state": "ACQUIRED",
        "lease": _public_lease(lease.record.to_dict()),
    }


def resource_heartbeat_payload(
    target: Path,
    *,
    lease_id: str,
    stage: str | None,
    lease_ttl: float,
) -> dict[str, Any]:
    manager, _ = manager_for_target(target, owner_parent=True)
    try:
        lease = manager.load_lease(lease_id)
        updated = manager.heartbeat(lease, stage=stage, lease_ttl=lease_ttl)
    except ValueError as exc:
        raise ResourceCliError(f"lease heartbeat configuration is invalid: {exc}") from exc
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise ResourceOperationalError(f"lease heartbeat failed: {exc}") from exc
    return {"ok": True, "state": "HEARTBEAT", "lease": _public_lease(updated.record.to_dict())}


def resource_release_payload(target: Path, *, lease_id: str) -> dict[str, Any]:
    manager, _ = manager_for_target(target, owner_parent=True)
    try:
        lease = manager.load_lease(lease_id)
        manager.release(lease)
    except ValueError as exc:
        raise ResourceCliError(f"lease release configuration is invalid: {exc}") from exc
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise ResourceOperationalError(f"lease release failed: {exc}") from exc
    return {"ok": True, "state": "RELEASED", "lease_id": lease_id}


def resource_run_payload(
    target: Path,
    *,
    resource_class: ResourceClass,
    run_id: str,
    stage: str,
    packet_path: Path | None,
    permission_mode: str,
    controller: str,
    wait_timeout: float,
    timeout: float,
    exclusive: Sequence[str],
    command: Sequence[str],
    required_containment: str | None = None,
    on_wait=None,
) -> tuple[int, dict[str, Any]]:
    if os.environ.get("SAGEKIT_DESCENDANT") == "1":
        raise ResourceOperationalError(
            "descendant cannot start a local command without an explicit root delegation"
        )
    authority = authority_for(
        target,
        packet_path=packet_path,
        permission_mode=permission_mode,
        controller=controller,
    )
    descendant = os.environ.get("SAGEKIT_DESCENDANT") == "1"
    decision = authorize_command(
        command,
        resource_class=resource_class,
        permission_mode=authority.permission_mode,
        allowed_classes=authority.allowed_classes,
        descendant=descendant,
    )
    if not decision.ok:
        raise ResourceOperationalError(decision.reason)
    manager, identity = manager_for_target(target)
    request = _request(
        authority,
        identity,
        resource_class=resource_class,
        run_id=run_id,
        stage=stage,
        exclusive=exclusive,
    )
    waiting: list[str] = []

    def wait_event(state: str) -> None:
        waiting.append(state)
        if on_wait is not None:
            on_wait(state)
    inherited_lease: ResourceLease | None = None
    if request.parent_lease_id is not None:
        try:
            candidate = manager.load_lease(request.parent_lease_id)
            if manager.lease_covers(candidate, request):
                inherited_lease = candidate
        except (OSError, ValueError, PermissionError) as exc:
            raise ResourceCliError(f"inherited lease is invalid: {exc}") from exc
    owned_lease: ResourceLease | None = None
    lease = inherited_lease
    if lease is None:
        try:
            owned_lease = manager.acquire(
                request,
                wait_timeout=wait_timeout,
                on_wait=wait_event,
            )
            lease = owned_lease
        except ResourceBusy as exc:
            return 1, {
                "ok": False,
                "state": exc.state,
                "waiting_does_not_consume_verification_budget": True,
                "message": str(exc),
            }
    assert lease is not None
    lease_box: list[ResourceLease] = [lease]
    result: ProcessResult | None = None
    release_error: str | None = None
    environment = {
        "SAGEKIT_ALLOWED_CLASSES": ResourceClass.REASONING_ONLY.value,
        "SAGEKIT_DESCENDANT": "1",
        "SAGEKIT_LEASE_ID": None,
        "SAGEKIT_DELEGATION_SECRET": None,
        "SAGEKIT_AUTHORITY_DIGEST": None,
        "SAGEKIT_PERMISSION_MODE": None,
        "SAGEKIT_CONTROLLER": None,
    }

    def heartbeat(event) -> None:
        if owned_lease is not None:
            lease_box[0] = manager.heartbeat(
                lease_box[0], stage=event.stage, lease_ttl=DEFAULT_LEASE_TTL
            )

    try:
        launch_verification = verify_workspace(
            authority.binding, current=discover_workspace(target)
        )
        if not launch_verification.ok:
            raise ResourceOperationalError(
                "workspace binding changed before launch: "
                + "; ".join(launch_verification.errors)
            )
        result = run_process(
            stage=stage,
            command=command,
            cwd=target,
            environment=environment,
            timeout=timeout,
            run_id=run_id,
            lease_id=lease.lease_id,
            max_output_bytes=int(authority.process_policy.get("max_output_bytes", 65_536)),
            max_owned_processes=int(
                authority.process_policy.get("max_owned_processes", 32)
            ),
            heartbeat_interval=min(10.0, max(0.1, DEFAULT_LEASE_TTL / 3)),
            on_heartbeat=heartbeat,
            required_containment=(
                required_containment
                or str(authority.containment_policy.get("minimum_level", "MANAGED"))
            ),
        )
    finally:
        if owned_lease is not None:
            try:
                manager.release(lease_box[0])
            except Exception as exc:  # reported as evidence, not silently discarded
                release_error = str(exc)
    if result is None:
        raise RuntimeError("managed process did not produce a result")
    exit_code = _resource_process_exit_code(
        result.classification,
        cleanup_complete=result.cleanup_complete,
        release_error=release_error,
    )
    payload = {
        "ok": exit_code == 0,
        "state": "COMPLETE" if exit_code == 0 else "HANDOFF_READY",
        "wait_events": waiting,
        "waiting_does_not_consume_verification_budget": True,
        "lease_id": lease.lease_id,
        "lease_reused": inherited_lease is not None,
        "release_error": release_error,
        "process": _process_payload(result),
        "soft_guarantee": (
            "SAGE-Kit enforces commands routed through resource run; it cannot hard-block "
            "an agent or arbitrary child that bypasses the cooperative runtime."
        ),
    }
    return exit_code, payload


def _request(
    authority: PacketAuthority | LiveAuthority,
    identity,
    *,
    resource_class: ResourceClass,
    run_id: str,
    stage: str,
    exclusive: Sequence[str],
) -> ResourceRequest:
    inherited = _inherited_authority()
    allowed = authority.allowed_classes
    return ResourceRequest(
        resource_class=resource_class,
        run_id=run_id,
        controller=authority.controller,
        stage=stage,
        authority_digest=(
            authority.packet_digest if isinstance(authority, PacketAuthority) else authority.digest
        ),
        host_identity=default_host_identity(),
        project_identity=_identity_digest(identity.git_common_dir or identity.repository_root),
        worktree_identity=_identity_digest(identity.worktree_root),
        permission_mode=authority.permission_mode,
        exclusive_resources=tuple(sorted(set(authority.exclusive_resources) | set(exclusive))),
        allowed_classes=allowed,
        parent_lease_id=os.environ.get("SAGEKIT_LEASE_ID"),
        descendant=inherited is not None,
    )


def _inherited_authority() -> tuple[str, str, set[ResourceClass]] | None:
    digest = os.environ.get("SAGEKIT_AUTHORITY_DIGEST")
    if digest is None:
        return None
    permission = os.environ.get("SAGEKIT_PERMISSION_MODE", "")
    raw = os.environ.get("SAGEKIT_ALLOWED_CLASSES", "")
    try:
        classes = {ResourceClass(value) for value in raw.split(",") if value}
    except ValueError as exc:
        raise ResourceCliError("inherited resource authority is invalid") from exc
    if not classes:
        raise ResourceCliError("inherited resource authority has no allowed classes")
    return digest, permission, classes


def _permission_rank(value: str) -> int:
    order = {
        "READ_ONLY_REVIEW": 0,
        "WRITE_AUTHORIZED": 1,
        "CORRECTIVE_AUTHORIZED": 1,
        "ENVIRONMENT_WRITE_AUTHORIZED": 2,
        "SUBMIT_AUTHORIZED": 3,
    }
    if value not in order:
        raise ResourceCliError(f"unknown permission mode: {value}")
    return order[value]


def _public_lease(payload: Mapping[str, Any]) -> dict[str, Any]:
    hidden = {"nonce", "process_creation", "delegation_sha256"}
    return {key: value for key, value in payload.items() if key not in hidden}


def _process_payload(result: ProcessResult) -> dict[str, Any]:
    return {
        "stage": result.stage,
        "run_id": result.run_id,
        "lease_id": result.lease_id,
        "argv": list(result.command),
        "cwd": result.cwd,
        "classification": result.classification.value,
        "exit_code": result.exit_code,
        "termination_reason": result.termination_reason,
        "elapsed_seconds": result.elapsed,
        "stdout_tail": result.stdout_tail,
        "stderr_tail": result.stderr_tail,
        "stdout_bytes": result.stdout_bytes,
        "stderr_bytes": result.stderr_bytes,
        "peak_owned_processes": result.peak_owned_processes,
        "child_cpu_seconds": result.child_cpu_seconds,
        "peak_rss_bytes": result.peak_rss_bytes,
        "heartbeat_count": result.heartbeat_count,
        "cleanup_complete": result.cleanup_complete,
        "containment_complete": result.containment_complete,
        "containment_level": result.containment_level,
        "orphan_check": result.orphan_check,
        "platform_adapter": result.platform_adapter,
        "limitations": list(result.limitations),
        "sampling_degraded": result.sampling_degraded,
        "cleanup_error": result.cleanup_error,
        "termination_escalated": result.termination_escalated,
        "orphan_count": result.orphan_count,
    }


def _resource_process_exit_code(
    classification: ProcessClassification,
    *,
    cleanup_complete: bool,
    release_error: str | None,
) -> int:
    if (
        classification is ProcessClassification.INTERNAL
        or not cleanup_complete
        or release_error is not None
    ):
        return 3
    if classification is ProcessClassification.SUCCESS:
        return 0
    return 1


def _identity_digest(value: str) -> str:
    return hashlib.sha256(os.path.normcase(value).encode("utf-8")).hexdigest()


def _json_digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "ResourceCliError",
    "authority_for",
    "load_packet_authority",
    "resource_acquire_payload",
    "resource_heartbeat_payload",
    "resource_release_payload",
    "resource_run_payload",
    "resource_status_payload",
    "workspace_verify_payload",
]
